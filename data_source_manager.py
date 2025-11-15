"""
数据源管理器
实现akshare和tushare的自动切换机制
"""

import os
import pandas as pd
import requests
from typing import Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv
from network_optimizer import network_optimizer

# 加载环境变量
load_dotenv()


class DataSourceManager:
    """数据源管理器 - 实现akshare与tushare自动切换"""
    
    def __init__(self):
        self.tushare_token = os.getenv('TUSHARE_TOKEN', '')
        self.tushare_available = False
        self.tushare_api = None
        self.tdx_api_base = os.getenv('TDX_API_BASE', '').strip()
        self.tdx_available = bool(self.tdx_api_base)
        
        # 初始化tushare
        if self.tushare_token:
            try:
                import tushare as ts
                ts.set_token(self.tushare_token)
                self.tushare_api = ts.pro_api()
                self.tushare_available = True
                print("✅ Tushare数据源初始化成功")
            except Exception as e:
                print(f"⚠️ Tushare数据源初始化失败: {e}")
                self.tushare_available = False
        else:
            print("ℹ️ 未配置Tushare Token，将仅使用Akshare数据源")

        if self.tdx_available:
            print(f"✅ TDX API 数据源已启用 | Base URL = {self.tdx_api_base}")
        else:
            print("ℹ️ 未配置TDX API基础地址，将跳过TDX数据源")
    
    def get_stock_hist_data(self, symbol, start_date=None, end_date=None, adjust='qfq'):
        """
        获取股票历史数据（优先TDX，失败时使用tushare/akshare）
        
        Args:
            symbol: 股票代码（6位数字）
            start_date: 开始日期（格式：'20240101'或'2024-01-01'）
            end_date: 结束日期
            adjust: 复权类型（'qfq'前复权, 'hfq'后复权, ''不复权）
            
        Returns:
            DataFrame: 包含日期、开盘、收盘、最高、最低、成交量等列
        """
        # 标准化日期格式
        if start_date:
            start_date = start_date.replace('-', '')
        if end_date:
            end_date = end_date.replace('-', '')
        else:
            end_date = datetime.now().strftime('%Y%m%d')
        
        # 1. 优先使用本地 TDX API
        if self.tdx_available:
            try:
                df = self._fetch_tdx_kline(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    kline_type='day'
                )
                if df is not None and not df.empty:
                    print(f"[TDX] ✅ 成功获取 {symbol} 的历史数据 (共{len(df)}条)")
                    return df
                else:
                    print(f"[TDX] ⚠️ 未获取到 {symbol} 的历史数据，尝试其他数据源")
            except Exception as e:
                print(f"[TDX] ❌ 获取历史数据失败: {e}")
        
        # 2. 其次使用 Tushare
        if self.tushare_available:
            try:
                with network_optimizer.apply():
                    print(f"[Tushare] 正在获取 {symbol} 的历史数据...")
                    ts_code = self._convert_to_ts_code(symbol)
                    adj_dict = {'qfq': 'qfq', 'hfq': 'hfq', '': None}
                    adj = adj_dict.get(adjust, 'qfq')
                    df = self.tushare_api.daily(
                        ts_code=ts_code,
                        start_date=start_date,
                        end_date=end_date,
                        adj=adj
                    )
                if df is None:
                    print(f"[Tushare] ⚠️ 返回None")
                elif isinstance(df, dict):
                    print(f"[Tushare] ⚠️ 返回dict而非DataFrame: {list(df.keys())[:5]}")
                elif isinstance(df, pd.DataFrame):
                    if not df.empty:
                        df = df.rename(columns={'trade_date': 'date', 'vol': 'volume', 'amount': 'amount'})
                        df['date'] = pd.to_datetime(df['date'])
                        df = df.sort_values('date').reset_index(drop=True)
                        df['volume'] = df['volume'] * 100
                        df['amount'] = df['amount'] * 1000
                        print(f"[Tushare] ✅ 成功获取 {len(df)} 条数据")
                        return df
                    else:
                        print(f"[Tushare] ⚠️ DataFrame为空")
                else:
                    print(f"[Tushare] ⚠️ 返回类型错误: {type(df).__name__}")
            except Exception as e:
                print(f"[Tushare] ❌ 获取失败: {e}")
                import traceback
                traceback.print_exc()

        # 3. 最后使用 Akshare 兜底
        try:
            with network_optimizer.apply():
                import akshare as ak
                print(f"[Akshare] 正在获取 {symbol} 的历史数据(兜底)...")
                df = ak.stock_zh_a_hist(
                    symbol=symbol,
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                    adjust=adjust
                )
                if df is None:
                    print(f"[Akshare] ⚠️ 返回None")
                elif isinstance(df, dict):
                    print(f"[Akshare] ⚠️ 返回dict而非DataFrame: {list(df.keys())[:5]}")
                elif isinstance(df, pd.DataFrame):
                    if not df.empty:
                        df = df.rename(columns={'日期':'date','开盘':'open','收盘':'close','最高':'high','最低':'low','成交量':'volume','成交额':'amount','振幅':'amplitude','涨跌幅':'pct_change','涨跌额':'change','换手率':'turnover'})
                        df['date'] = pd.to_datetime(df['date'])
                        df = df.sort_values('date').reset_index(drop=True)
                        print(f"[Akshare] ✅ 成功获取 {len(df)} 条数据")
                        return df
                    else:
                        print(f"[Akshare] ⚠️ DataFrame为空")
                else:
                    print(f"[Akshare] ⚠️ 返回类型错误: {type(df).__name__}")
        except Exception as e:
            print(f"[Akshare] ❌ 获取失败: {e}")
            import traceback
            traceback.print_exc()
        
        print("❌ 所有数据源均获取失败")
        return None
    
    def _fetch_tdx_kline(self, symbol: str, start_date: Optional[str], end_date: Optional[str], kline_type: str = 'day'):
        """
        通过本地TDX API获取历史K线数据
        """
        if not self.tdx_available:
            return None
        
        params = {
            "code": symbol,
            "type": kline_type or "day"
        }
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        
        try:
            resp = requests.get(
                f"{self.tdx_api_base.rstrip('/')}/api/kline-history",
                params=params,
                timeout=8
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:
            print(f"[TDX] ❌ HTTP请求失败: {exc}")
            return None
        
        if not isinstance(payload, dict) or payload.get("code") != 0:
            print(f"[TDX] ⚠️ 接口返回异常: {payload}")
            return None
        
        raw_data = payload.get("data")
        if isinstance(raw_data, dict):
            records = raw_data.get("List") or raw_data.get("list") or raw_data.get("data")
        else:
            records = raw_data
        
        if not records:
            print(f"[TDX] ⚠️ 返回数据为空")
            return None
        
        rows = []
        for item in records:
            if not isinstance(item, dict):
                continue
            
            date_val = (
                item.get("Date") or
                item.get("date") or
                item.get("Time") or
                item.get("time")
            )
            if date_val is None:
                continue
            date_str = str(date_val)
            date_str = date_str.replace('-', '').replace('/', '')
            if len(date_str) >= 8:
                date_str = date_str[:8]
            
            def _price(key: str):
                val = item.get(key)
                if val is None:
                    return None
                try:
                    val = float(val)
                    return val / 1000  # 历史K线价格单位：厘 -> 元
                except (TypeError, ValueError):
                    return None
            
            def _volume(key: str):
                val = item.get(key)
                if val is None:
                    return None
                try:
                    val = float(val)
                    return val * 100  # 成交量单位：手 -> 股
                except (TypeError, ValueError):
                    return None
            
            def _amount(key: str):
                val = item.get(key)
                if val is None:
                    return None
                try:
                    val = float(val)
                    return val / 1000  # 成交额单位：厘 -> 元
                except (TypeError, ValueError):
                    return None
            
            rows.append({
                "date": date_str,
                "open": _price("Open"),
                "high": _price("High"),
                "low": _price("Low"),
                "close": _price("Close"),
                "volume": _volume("Volume"),
                "amount": _amount("Amount")
            })
        
        df = pd.DataFrame(rows)
        if df.empty:
            return None
        
        df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
        df = df.sort_values("date").reset_index(drop=True)
        return df
    
    def get_stock_basic_info(self, symbol):
        """
        获取股票基本信息（优先tushare，失败时使用akshare）
        
        Args:
            symbol: 股票代码
            
        Returns:
            dict: 股票基本信息
        """
        info = {
            "symbol": symbol,
            "name": "未知",
            "industry": "未知",
            "market": "未知"
        }
        
        # 优先使用 tushare
        if self.tushare_available:
            try:
                with network_optimizer.apply():
                    print(f"[Tushare] 正在获取 {symbol} 的基本信息...")
                    ts_code = self._convert_to_ts_code(symbol)
                    df = self.tushare_api.stock_basic(
                        ts_code=ts_code,
                        fields='ts_code,name,area,industry,market,list_date'
                    )
                if df is not None and not df.empty:
                    info['name'] = df.iloc[0]['name']
                    info['industry'] = df.iloc[0]['industry']
                    info['market'] = df.iloc[0]['market']
                    info['list_date'] = df.iloc[0]['list_date']
                    print(f"[Tushare] ✅ 成功获取基本信息")
                    return info
            except Exception as e:
                print(f"[Tushare] ❌ 获取失败: {e}")

        # 失败再使用 akshare 兜底
        try:
            with network_optimizer.apply():
                import akshare as ak
                print(f"[Akshare] 正在获取 {symbol} 的基本信息(兜底)...")
                stock_info = ak.stock_individual_info_em(symbol=symbol)
            if stock_info is not None and not stock_info.empty:
                for _, row in stock_info.iterrows():
                    key = row['item']
                    value = row['value']
                    if key == '股票简称':
                        info['name'] = value
                    elif key == '所处行业':
                        info['industry'] = value
                    elif key == '上市时间':
                        info['list_date'] = value
                    elif key == '总市值':
                        info['market_cap'] = value
                    elif key == '流通市值':
                        info['circulating_market_cap'] = value
                print(f"[Akshare] ✅ 成功获取基本信息")
                return info
        except Exception as e:
            print(f"[Akshare] ❌ 获取失败: {e}")
        
        return info
    
    def _get_tdx_quote(self, symbol: str):
        """
        使用本地 TDX API 获取实时行情
        """
        if not self.tdx_available:
            return None

        try:
            response = requests.get(
                f"{self.tdx_api_base.rstrip('/')}/api/quote",
                params={"code": symbol},
                timeout=5
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            print(f"[TDX] ❌ 获取实时行情失败: {exc}")
            return None

        if not isinstance(payload, dict) or payload.get('code') != 0:
            print(f"[TDX] ⚠️ 接口返回异常: {payload}")
            return None

        data_list = payload.get('data') or []
        if not data_list:
            print(f"[TDX] ⚠️ 未返回 {symbol} 的行情数据")
            return None

        quote = data_list[0]
        kline = quote.get('K') or {}

        def _scaled_value(source, key, scale=None):
            value = source.get(key)
            if value is None:
                return None
            try:
                value = float(value)
                if scale:
                    value = value / scale
                return value
            except (TypeError, ValueError):
                return None

        close_price = _scaled_value(kline, 'Close', 1000)
        last_price = _scaled_value(kline, 'Last', 1000)
        high_price = _scaled_value(kline, 'High', 1000)
        low_price = _scaled_value(kline, 'Low', 1000)
        open_price = _scaled_value(kline, 'Open', 1000)

        volume_raw = quote.get('TotalHand')
        try:
            volume = float(volume_raw) * 100 if volume_raw is not None else None
        except (TypeError, ValueError):
            volume = None

        amount_raw = quote.get('Amount')
        try:
            amount = float(amount_raw) / 1000 if amount_raw is not None else None
        except (TypeError, ValueError):
            amount = None

        change_percent = None
        if close_price is not None and last_price not in (None, 0):
            change_percent = (close_price - last_price) / last_price * 100

        change_amount = None
        if close_price is not None and last_price is not None:
            change_amount = close_price - last_price

        print(f"[TDX] ✅ 成功获取 {symbol} 实时行情")
        return {
            'symbol': symbol,
            'name': quote.get('Name') or quote.get('Code') or quote.get('code'),
            'price': close_price,
            'change_percent': change_percent,
            'change': change_amount,
            'volume': volume,
            'amount': amount,
            'high': high_price,
            'low': low_price,
            'open': open_price,
            'pre_close': last_price,
            'timestamp': quote.get('ServerTime'),
            'source': 'tdx'
        }

    def get_realtime_quotes(self, symbol):
        """
        获取实时行情数据（优先TDX；TDX缺失则：股票走tushare daily，ETF走tushare fund_daily；再兜底akshare）。
        Args:
            symbol: 6位代码或带后缀ts_code
        Returns:
            dict: 实时行情数据
        """
        # 统一基码/后缀
        base_code = self._convert_from_ts_code(symbol) if '.' in str(symbol) else str(symbol).strip()
        # 优先使用TDX API
        tdx_result = self._get_tdx_quote(base_code)
        if tdx_result:
            return tdx_result

        quotes = {}
        is_etf = self._looks_like_etf_code(base_code)

        # 优先使用 tushare（按证券类型选择接口）
        if self.tushare_available:
            try:
                ts_code = self._convert_to_ts_code(base_code)
                with network_optimizer.apply():
                    print(f"[Tushare] 正在获取 {base_code} 的实时行情...")
                    today = datetime.now().strftime('%Y%m%d')
                    if is_etf:
                        # ETF用 fund_daily 接口
                        df = self.tushare_api.fund_daily(ts_code=ts_code, start_date=today, end_date=today)
                    else:
                        df = self.tushare_api.daily(ts_code=ts_code, start_date=today, end_date=today)
                if df is not None and not df.empty:
                    row = df.iloc[0]
                    # 字段对齐（fund_daily 与 daily 命名基本一致）
                    pre_close = row.get('pre_close')
                    price = row.get('close')
                    pct_chg = row.get('pct_chg')
                    if pct_chg is None and pre_close not in (None, 0):
                        try:
                            pct_chg = (float(price) - float(pre_close)) / float(pre_close) * 100
                        except Exception:
                            pct_chg = None
                    quotes = {
                        'symbol': base_code,
                        'price': price,
                        'change_percent': pct_chg,
                        'volume': (row.get('vol') * 100 if row.get('vol') is not None else None),
                        'amount': (row.get('amount') * 1000 if row.get('amount') is not None else None),
                        'high': row.get('high'),
                        'low': row.get('low'),
                        'open': row.get('open'),
                        'pre_close': pre_close,
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'source': 'tushare'
                    }
                    print(f"[Tushare] ✅ 成功获取实时行情")
                    return quotes
            except Exception as e:
                print(f"[Tushare] ❌ 获取失败: {e}")

        # 失败再使用 akshare 兜底（仅A股现货表，部分ETF也可能包含）
        try:
            with network_optimizer.apply():
                import akshare as ak
                print(f"[Akshare] 正在获取 {base_code} 的实时行情(兜底)...")
                df = ak.stock_zh_a_spot_em()
            stock_df = df[df['代码'] == base_code]
            if not stock_df.empty:
                row = stock_df.iloc[0]
                quotes = {
                    'symbol': base_code,
                    'name': row.get('名称'),
                    'price': row.get('最新价'),
                    'change_percent': row.get('涨跌幅'),
                    'change': row.get('涨跌额'),
                    'volume': row.get('成交量'),
                    'amount': row.get('成交额'),
                    'high': row.get('最高'),
                    'low': row.get('最低'),
                    'open': row.get('今开'),
                    'pre_close': row.get('昨收'),
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'source': 'akshare'
                }
                print(f"[Akshare] ✅ 成功获取实时行情")
                return quotes
        except Exception as e:
            print(f"[Akshare] ❌ 获取失败: {e}")
        
        return quotes
    
    def get_financial_data(self, symbol, report_type='income'):
        """
        获取财务数据（优先tushare，失败时使用akshare）
        
        Args:
            symbol: 股票代码
            report_type: 报表类型（'income'利润表, 'balance'资产负债表, 'cashflow'现金流量表）
            
        Returns:
            DataFrame: 财务数据
        """
        # 优先使用 tushare
        if self.tushare_available:
            try:
                with network_optimizer.apply():
                    print(f"[Tushare] 正在获取 {symbol} 的财务数据...")
                    ts_code = self._convert_to_ts_code(symbol)
                    if report_type == 'income':
                        df = self.tushare_api.income(ts_code=ts_code)
                    elif report_type == 'balance':
                        df = self.tushare_api.balancesheet(ts_code=ts_code)
                    elif report_type == 'cashflow':
                        df = self.tushare_api.cashflow(ts_code=ts_code)
                    else:
                        df = None
                if df is not None and not df.empty:
                    print(f"[Tushare] ✅ 成功获取财务数据")
                    return df
            except Exception as e:
                print(f"[Tushare] ❌ 获取失败: {e}")

        # 失败再使用 akshare 兜底
        try:
            with network_optimizer.apply():
                import akshare as ak
                print(f"[Akshare] 正在获取 {symbol} 的财务数据(兜底)...")
                if report_type == 'income':
                    df = ak.stock_financial_report_sina(stock=symbol, symbol="利润表")
                elif report_type == 'balance':
                    df = ak.stock_financial_report_sina(stock=symbol, symbol="资产负债表")
                elif report_type == 'cashflow':
                    df = ak.stock_financial_report_sina(stock=symbol, symbol="现金流量表")
                else:
                    df = None
            if df is not None and not df.empty:
                print(f"[Akshare] ✅ 成功获取财务数据")
                return df
        except Exception as e:
            print(f"[Akshare] ❌ 获取失败: {e}")
        
        return None
    
    def _convert_to_ts_code(self, symbol):
        """
        将6位股票代码转换为tushare格式（带市场后缀）
        
        Args:
            symbol: 6位股票代码
            
        Returns:
            str: tushare格式代码（如：000001.SZ）
        """
        if not symbol or len(symbol) != 6:
            return symbol
        
        # 根据代码判断市场
        # ETF常见前缀：上交所ETF多为5开头（如510xxx），深交所ETF多为1开头（如159xxx）
        if symbol.startswith('6'):
            return f"{symbol}.SH"
        if symbol.startswith('5'):
            return f"{symbol}.SH"
        if symbol.startswith('1') or symbol.startswith('0') or symbol.startswith('3'):
            return f"{symbol}.SZ"
        if symbol.startswith('8') or symbol.startswith('4'):
            return f"{symbol}.BJ"
        # 默认深圳
        return f"{symbol}.SZ"
    
    def _convert_from_ts_code(self, ts_code):
        """
        将tushare格式代码转换为6位代码
        
        Args:
            ts_code: tushare格式代码（如：000001.SZ）
            
        Returns:
            str: 6位股票代码
        """
        if '.' in ts_code:
            return ts_code.split('.')[0]
        return ts_code

    def _looks_like_etf_code(self, code: str) -> bool:
        try:
            s = str(code).strip()
            return len(s) == 6 and (s.startswith('5') or s.startswith('1'))
        except Exception:
            return False

    def get_security_name_and_type(self, symbol: str) -> Optional[dict]:
        """
        通过6位代码或带后缀代码，识别股票/ETF并返回名称与标准ts_code。
        返回: { 'name': str, 'type': 'stock'|'etf', 'ts_code': '000001.SZ' }
        失败返回 None。
        """
        code_raw = (symbol or '').strip().upper()
        if not code_raw:
            return None
        base_code = code_raw.split('.')[0] if '.' in code_raw else code_raw
        # 仅接受6位数字
        if len(base_code) != 6 or not base_code.isdigit():
            return None

        # 1) 尝试TDX实时接口快速拿名称（覆盖股票/ETF）
        try:
            q = self._get_tdx_quote(base_code)
            if q and isinstance(q, dict):
                nm = q.get('name')
                if nm:
                    typ = 'etf' if self._looks_like_etf_code(base_code) else 'stock'
                    return {
                        'name': str(nm),
                        'type': typ,
                        'ts_code': self._convert_to_ts_code(base_code)
                    }
        except Exception:
            pass

        # 2) Tushare: 先按股票查询
        if self.tushare_available:
            ts_code = self._convert_to_ts_code(base_code)
            try:
                with network_optimizer.apply():
                    df = self.tushare_api.stock_basic(ts_code=ts_code, fields='ts_code,name')
                if df is not None and not df.empty:
                    return {
                        'name': str(df.iloc[0]['name']),
                        'type': 'stock',
                        'ts_code': ts_code,
                    }
            except Exception:
                pass

            # 3) Tushare: ETF/基金基本信息
            try:
                with network_optimizer.apply():
                    # 直接用ts_code精确查询；若数据源不支持，再按market粗查。
                    fdf = None
                    try:
                        fdf = self.tushare_api.fund_basic(ts_code=ts_code)
                    except Exception:
                        fdf = None
                    if (fdf is None) or fdf.empty:
                        # 退而求其次，按ETF市场拉取再过滤
                        fdf = self.tushare_api.fund_basic(market='E')
                        if fdf is not None and not fdf.empty:
                            fdf = fdf[fdf['ts_code'] == ts_code]
                if fdf is not None and not fdf.empty:
                    # 字段可能为 name 或 fund_name
                    row = fdf.iloc[0]
                    nm = row.get('name') if 'name' in row else row.get('fund_name')
                    if nm:
                        return {
                            'name': str(nm),
                            'type': 'etf',
                            'ts_code': ts_code,
                        }
            except Exception:
                pass

        # 4) Akshare兜底（仅股票）
        try:
            with network_optimizer.apply():
                import akshare as ak
                stock_info = ak.stock_individual_info_em(symbol=base_code)
            if stock_info is not None and not stock_info.empty:
                for _, row in stock_info.iterrows():
                    if row.get('item') == '股票简称' and row.get('value'):
                        return {
                            'name': str(row['value']),
                            'type': 'stock',
                            'ts_code': self._convert_to_ts_code(base_code)
                        }
        except Exception:
            pass

        return None


# 全局数据源管理器实例
data_source_manager = DataSourceManager()

