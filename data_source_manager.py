"""
数据源管理器
实现akshare和tushare的自动切换机制
"""

import os
import pandas as pd
import requests
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
        获取股票历史数据（优先tushare，失败时使用akshare）
        
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
        
        # 优先使用 Tushare
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
                # 检查返回类型
                if df is None:
                    print(f"[Tushare] ⚠️ 返回None")
                elif isinstance(df, dict):
                    print(f"[Tushare] ⚠️ 返回dict而非DataFrame: {list(df.keys())[:5]}")
                    df = None  # 将dict视为无效数据
                elif isinstance(df, pd.DataFrame):
                    if not df.empty:
                        df = df.rename(columns={'trade_date': 'date', 'vol': 'volume', 'amount': 'amount'})
                        df['date'] = pd.to_datetime(df['date'])
                        df = df.sort_values('date')
                        df['volume'] = df['volume'] * 100
                        df['amount'] = df['amount'] * 1000
                        print(f"[Tushare] ✅ 成功获取 {len(df)} 条数据")
                        return df
                    else:
                        print(f"[Tushare] ⚠️ DataFrame为空")
                else:
                    print(f"[Tushare] ⚠️ 返回类型错误: {type(df).__name__}")
                    df = None
            except Exception as e:
                print(f"[Tushare] ❌ 获取失败: {e}")
                import traceback
                traceback.print_exc()

        # 失败再使用 Akshare 兜底
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
                # 检查返回类型
                if df is None:
                    print(f"[Akshare] ⚠️ 返回None")
                elif isinstance(df, dict):
                    print(f"[Akshare] ⚠️ 返回dict而非DataFrame: {list(df.keys())[:5]}")
                    df = None  # 将dict视为无效数据
                elif isinstance(df, pd.DataFrame):
                    if not df.empty:
                        df = df.rename(columns={'日期':'date','开盘':'open','收盘':'close','最高':'high','最低':'low','成交量':'volume','成交额':'amount','振幅':'amplitude','涨跌幅':'pct_change','涨跌额':'change','换手率':'turnover'})
                        df['date'] = pd.to_datetime(df['date'])
                        print(f"[Akshare] ✅ 成功获取 {len(df)} 条数据")
                        return df
                    else:
                        print(f"[Akshare] ⚠️ DataFrame为空")
                else:
                    print(f"[Akshare] ⚠️ 返回类型错误: {type(df).__name__}")
                    df = None
        except Exception as e:
            print(f"[Akshare] ❌ 获取失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 两个数据源都失败
        print("❌ 所有数据源均获取失败")
        return None
    
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
        获取实时行情数据（优先tushare，失败时使用akshare）
        
        Args:
            symbol: 股票代码
            
        Returns:
            dict: 实时行情数据
        """
        # 优先使用TDX API
        tdx_result = self._get_tdx_quote(symbol)
        if tdx_result:
            return tdx_result

        quotes = {}

        # 优先使用 tushare
        if self.tushare_available:
            try:
                with network_optimizer.apply():
                    print(f"[Tushare] 正在获取 {symbol} 的实时行情...")
                    ts_code = self._convert_to_ts_code(symbol)
                    df = self.tushare_api.daily(
                        ts_code=ts_code,
                        start_date=datetime.now().strftime('%Y%m%d'),
                        end_date=datetime.now().strftime('%Y%m%d')
                    )
                if df is not None and not df.empty:
                    row = df.iloc[0]
                    quotes = {
                        'symbol': symbol,
                        'price': row['close'],
                        'change_percent': row['pct_chg'],
                        'volume': row['vol'] * 100,
                        'amount': row['amount'] * 1000,
                        'high': row['high'],
                        'low': row['low'],
                        'open': row['open'],
                        'pre_close': row['pre_close']
                    }
                    print(f"[Tushare] ✅ 成功获取实时行情")
                    return quotes
            except Exception as e:
                print(f"[Tushare] ❌ 获取失败: {e}")

        # 失败再使用 akshare 兜底
        try:
            with network_optimizer.apply():
                import akshare as ak
                print(f"[Akshare] 正在获取 {symbol} 的实时行情(兜底)...")
                df = ak.stock_zh_a_spot_em()
            stock_df = df[df['代码'] == symbol]
            if not stock_df.empty:
                row = stock_df.iloc[0]
                quotes = {
                    'symbol': symbol,
                    'name': row['名称'],
                    'price': row['最新价'],
                    'change_percent': row['涨跌幅'],
                    'change': row['涨跌额'],
                    'volume': row['成交量'],
                    'amount': row['成交额'],
                    'high': row['最高'],
                    'low': row['最低'],
                    'open': row['今开'],
                    'pre_close': row['昨收']
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
        if symbol.startswith('6'):
            # 上海主板
            return f"{symbol}.SH"
        elif symbol.startswith('0') or symbol.startswith('3'):
            # 深圳主板和创业板
            return f"{symbol}.SZ"
        elif symbol.startswith('8') or symbol.startswith('4'):
            # 北交所
            return f"{symbol}.BJ"
        else:
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


# 全局数据源管理器实例
data_source_manager = DataSourceManager()

