"""
数据源管理器
实现akshare和tushare的自动切换机制
"""

import os
from typing import Dict, Any, List, Optional
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class DataSourceManager:
    """数据源管理器 - 实现akshare与tushare自动切换"""
    
    def __init__(self):
        self.tushare_token = os.getenv('TUSHARE_TOKEN', '')
        self.tushare_available = False
        self.tushare_api = None
        
        # 初始化tushare
        if self.tushare_token:
            try:
                import tushare as ts
                ts.set_token(self.tushare_token)
                self.tushare_api = ts.pro_api()
                self.tushare_available = True
                print(" Tushare数据源初始化成功")
            except Exception as e:
                print(f" Tushare数据源初始化失败: {e}")
                self.tushare_available = False
        else:
            print(" 未配置Tushare Token，将仅使用Akshare数据源")
    
    def get_stock_hist_data(self, symbol, start_date=None, end_date=None, adjust='qfq'):
        """
        获取股票历史数据（优先tushare直连，失败时使用akshare）
        
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
        
        # 优先使用tushare（直连，不使用代理）
        if self.tushare_available:
            try:
                print(f"[Tushare] 正在获取 {symbol} 的历史数据（优先数据源，直连）...")
                
                # 临时清除代理环境变量，确保tushare直连
                import os
                old_http_proxy = os.environ.get('HTTP_PROXY')
                old_https_proxy = os.environ.get('HTTPS_PROXY')
                
                # 清除代理设置
                if 'HTTP_PROXY' in os.environ:
                    del os.environ['HTTP_PROXY']
                if 'HTTPS_PROXY' in os.environ:
                    del os.environ['HTTPS_PROXY']
                
                try:
                    # 转换股票代码格式（添加市场后缀）
                    ts_code = self._convert_to_ts_code(symbol)
                    
                    # 转换复权类型
                    adj_dict = {'qfq': 'qfq', 'hfq': 'hfq', '': None}
                    adj = adj_dict.get(adjust, 'qfq')
                    
                    # 获取数据（直连）
                    df = self.tushare_api.daily(
                        ts_code=ts_code,
                        start_date=start_date,
                        end_date=end_date,
                        adj=adj
                    )
                    
                    if df is not None and not df.empty:
                        # 标准化列名和数据格式
                        df = df.rename(columns={
                            'trade_date': 'date',
                            'vol': 'volume',
                            'amount': 'amount'
                        })
                        df['date'] = pd.to_datetime(df['date'])
                        df = df.sort_values('date')
                        
                        # 转换成交量单位（tushare单位是手，转换为股）
                        df['volume'] = df['volume'] * 100
                        # 转换成交额单位（tushare单位是千元，转换为元）
                        df['amount'] = df['amount'] * 1000
                        
                        print(f"[Tushare]  成功获取 {len(df)} 条数据（直连）")
                        return df
                finally:
                    # 恢复代理设置
                    if old_http_proxy:
                        os.environ['HTTP_PROXY'] = old_http_proxy
                    if old_https_proxy:
                        os.environ['HTTPS_PROXY'] = old_https_proxy
                        
            except Exception as e:
                print(f"[Tushare]  获取失败: {e}")
        
        # tushare失败，尝试akshare（通过统一网络API）
        try:
            from standard_network_api import get_akshare_data
            print(f"[Akshare] 正在获取 {symbol} 的历史数据（备用数据源）...")
            
            df = get_akshare_data(
                'stock_zh_a_hist',
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust=adjust
            )
            
            if df is not None and not df.empty:
                # 标准化列名
                df = df.rename(columns={
                    '日期': 'date',
                    '开盘': 'open',
                    '收盘': 'close',
                    '最高': 'high',
                    '最低': 'low',
                    '成交量': 'volume',
                    '成交额': 'amount',
                    '振幅': 'amplitude',
                    '涨跌幅': 'pct_change',
                    '涨跌额': 'change',
                    '换手率': 'turnover'
                })
                df['date'] = pd.to_datetime(df['date'])
                print(f"[Akshare]  成功获取 {len(df)} 条数据")
                return df
        except Exception as e:
            print(f"[Akshare]  获取失败: {e}")
        
        # 两个数据源都失败
        print(" 所有数据源均获取失败")
        return None
    
    def get_stock_basic_info(self, symbol):
        """
        获取股票基本信息（优先tushare直连，失败时使用akshare）
        
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
        
        # 优先使用tushare（直连，不使用代理）
        if self.tushare_available:
            try:
                print(f"[Tushare] 正在获取 {symbol} 的基本信息（优先数据源，直连）...")
                
                # 临时清除代理环境变量，确保tushare直连
                import os
                old_http_proxy = os.environ.get('HTTP_PROXY')
                old_https_proxy = os.environ.get('HTTPS_PROXY')
                
                # 清除代理设置
                if 'HTTP_PROXY' in os.environ:
                    del os.environ['HTTP_PROXY']
                if 'HTTPS_PROXY' in os.environ:
                    del os.environ['HTTPS_PROXY']
                
                try:
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
                        
                        print(f"[Tushare]  成功获取基本信息（直连）")
                        return info
                finally:
                    # 恢复代理设置
                    if old_http_proxy:
                        os.environ['HTTP_PROXY'] = old_http_proxy
                    if old_https_proxy:
                        os.environ['HTTPS_PROXY'] = old_https_proxy
                        
            except Exception as e:
                print(f"[Tushare]  获取失败: {e}")
        
        # tushare失败，尝试akshare
        try:
            import akshare as ak
            print(f"[Akshare] 正在获取 {symbol} 的基本信息（备用数据源）...")
            
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
                
                print(f"[Akshare]  成功获取基本信息")
                return info
        except Exception as e:
            print(f"[Akshare]  获取失败: {e}")
        
        return info
    
    def get_realtime_quotes(self, symbol):
        """
        获取实时行情数据（优先使用Tushare realtime_quote）
        
        Args:
            symbol: 股票代码
            
        Returns:
            dict: 实时行情数据（包含实时价格与涨跌幅）
        """
        quotes = {}
        from datetime import datetime
        
        ts_code = self._convert_to_ts_code(symbol)
        
        # 优先使用Tushare realtime_quote 接口（官方实时行情）
        if self.tushare_available:
            try:
                print(f"[Tushare] 正在获取 {symbol} 的实时行情（realtime_quote接口）...")
                df = self._make_tushare_request(
                    self.tushare_api.realtime_quote,
                    ts_code=ts_code
                )
                if df is not None and not df.empty:
                    row = df.iloc[0]
                    quotes = {
                        'symbol': symbol,
                        'name': row.get('name', ''),
                        'close': row.get('last'),
                        'price': row.get('last'),
                        'pct_chg': row.get('pct_chg', 0),
                        'change_percent': row.get('pct_chg', 0),
                        'change': row.get('chg', row.get('change', 0)),
                        'volume': row.get('vol', 0),
                        'amount': row.get('amount', 0),
                        'high': row.get('high', 0),
                        'low': row.get('low', 0),
                        'open': row.get('open', 0),
                        'pre_close': row.get('pre_close', 0),
                        'trade_time': row.get('trade_time'),
                        'bid1': row.get('bid1'),
                        'ask1': row.get('ask1'),
                        'data_source': 'Tushare_realtime_quote',
                        'is_realtime': True
                    }
                    print(f"[Tushare] 成功获取实时行情（价格: {quotes['price']}, 涨跌幅: {quotes['pct_chg']}%）")
                    return quotes
                else:
                    print("[Tushare] realtime_quote 返回空数据")
            except Exception as e:
                print(f"[Tushare] realtime_quote接口获取失败: {e}")
        
        # 判断是否在交易时间内（A股交易时间：9:30-11:30, 13:00-15:00）
        current_time = datetime.now()
        current_hour = current_time.hour
        current_minute = current_time.minute
        is_trading_hours = (
            (9 <= current_hour < 11) or 
            (current_hour == 11 and current_minute < 30) or
            (13 <= current_hour < 15)
        )
        
        # 备选：使用Akshare实时行情
        if not quotes:
            try:
                import akshare as ak
                if is_trading_hours:
                    print(f"[Akshare] 正在获取 {symbol} 的实时行情（交易时间内，备用数据源）...")
                else:
                    print(f"[Akshare] 正在获取 {symbol} 的实时行情（非交易时间，备用数据源）...")
                
                try:
                    from network_optimizer import network_optimizer
                    def _akshare_call(**kwargs):
                        return ak.stock_zh_a_spot_em()
                    df = network_optimizer._make_request_with_retry(_akshare_call, use_proxy=True)
                except ImportError:
                    df = ak.stock_zh_a_spot_em()
                
                if df is not None and not df.empty:
                    stock_df = df[df['代码'] == symbol]
                    if not stock_df.empty:
                        row = stock_df.iloc[0]
                        quotes = {
                            'symbol': symbol,
                            'name': row['名称'],
                            'close': row['最新价'],
                            'price': row['最新价'],
                            'pct_chg': row['涨跌幅'],
                            'change_percent': row['涨跌幅'],
                            'change': row['涨跌额'],
                            'volume': row['成交量'],
                            'amount': row['成交额'],
                            'high': row['最高'],
                            'low': row['最低'],
                            'open': row['今开'],
                            'pre_close': row['昨收'],
                            'data_source': 'Akshare_实时行情',
                            'is_realtime': True
                        }
                        print(f"[Akshare] 成功获取备用实时行情（价格: {row['最新价']}, 涨跌幅: {row['涨跌幅']}%）")
                        return quotes
                    else:
                        print(f"[Akshare] 数据中未找到股票代码 {symbol}")
                else:
                    print("[Akshare] 返回空数据")
            except Exception as e:
                print(f"[Akshare] 获取失败: {e}")
        
        # 兜底：使用Tushare日线收盘价（非实时）
        if not quotes and self.tushare_available:
            try:
                if is_trading_hours:
                    print(f"[Tushare] 正在获取 {symbol} 的最近交易日收盘价（备选，注意：这是收盘价，非实时价格）...")
                else:
                    print(f"[Tushare] 正在获取 {symbol} 的最近交易日收盘价（非交易时间，直连）...")
                
                # 临时清除代理环境变量，确保tushare直连
                import os
                old_http_proxy = os.environ.get('HTTP_PROXY')
                old_https_proxy = os.environ.get('HTTPS_PROXY')
                
                # 清除代理设置
                if 'HTTP_PROXY' in os.environ:
                    del os.environ['HTTP_PROXY']
                if 'HTTPS_PROXY' in os.environ:
                    del os.environ['HTTPS_PROXY']
                
                try:
                    ts_code = self._convert_to_ts_code(symbol)
                    # 尝试最近6个交易日，如果当天无数据则回退到最近的交易日
                    from datetime import timedelta
                    base_date = datetime.now()
                    
                    for i in range(0, 6):
                        try_date = (base_date - timedelta(days=i)).strftime('%Y%m%d')
                        df = self.tushare_api.daily(
                            ts_code=ts_code,
                            start_date=try_date,
                            end_date=try_date
                        )
                        
                        if df is not None and not df.empty:
                            row = df.iloc[0]
                            quotes = {
                                'symbol': symbol,
                                'close': row['close'],  # 收盘价（非实时）
                                'price': row['close'],
                                'pct_chg': row['pct_chg'],  # 涨跌幅（收盘价计算）
                                'change_percent': row['pct_chg'],
                                'volume': row['vol'] * 100,
                                'amount': row['amount'] * 1000,
                                'high': row['high'],
                                'low': row['low'],
                                'open': row['open'],
                                'pre_close': row['pre_close'],
                                'trade_date': try_date,
                                'data_source': 'Tushare_收盘价',
                                'is_realtime': False,  # 标记为非实时数据（收盘价）
                                'note': '收盘价数据，非实时价格'
                            }
                            if is_trading_hours:
                                print(f"[Tushare]  获取到收盘价（交易日: {try_date}，注意：这不是当前实时价格）")
                            else:
                                print(f"[Tushare]  获取到收盘价（交易日: {try_date}）")
                            return quotes
                    
                    print(f"[Tushare]  最近6个交易日均无数据")
                finally:
                    # 恢复代理设置
                    if old_http_proxy:
                        os.environ['HTTP_PROXY'] = old_http_proxy
                    if old_https_proxy:
                        os.environ['HTTPS_PROXY'] = old_https_proxy
                        
            except Exception as e:
                print(f"[Tushare]  获取失败: {e}")
        
        # 如果所有数据源都失败，尝试使用Tushare的历史数据作为最后回退
        if not quotes and self.tushare_available:
            try:
                print(f"[Tushare] 尝试使用历史数据作为最后回退...")
                ts_code = self._convert_to_ts_code(symbol)
                # 获取最近30天的数据
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
                df = self.tushare_api.daily(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date
                )
                if df is not None and not df.empty:
                    # 取最新的一条
                    df = df.sort_values('trade_date', ascending=False)
                    row = df.iloc[0]
                    quotes = {
                        'symbol': symbol,
                        'close': row['close'],
                        'price': row['close'],
                        'pct_chg': row['pct_chg'],
                        'change_percent': row['pct_chg'],
                        'trade_date': row['trade_date'],
                        'data_source': 'Tushare_历史回退'
                    }
                    print(f"[Tushare]  使用历史数据回退成功（交易日: {row['trade_date']}）")
                    return quotes
            except Exception as e:
                print(f"[Tushare]  历史数据回退失败: {e}")
        
        if not quotes:
            print(f"[警告] 所有数据源均无法获取 {symbol} 的实时行情数据")
        
        return quotes
    
    def get_financial_data(self, symbol, report_type='income'):
        """
        获取财务数据（优先tushare直连，失败时使用akshare）
        
        Args:
            symbol: 股票代码
            report_type: 报表类型（'income'利润表, 'balance'资产负债表, 'cashflow'现金流量表）
            
        Returns:
            DataFrame: 财务数据
        """
        # 优先使用tushare（直连，不使用代理）
        if self.tushare_available:
            try:
                print(f"[Tushare] 正在获取 {symbol} 的财务数据（优先数据源，直连）...")
                
                # 临时清除代理环境变量，确保tushare直连
                import os
                old_http_proxy = os.environ.get('HTTP_PROXY')
                old_https_proxy = os.environ.get('HTTPS_PROXY')
                
                # 清除代理设置
                if 'HTTP_PROXY' in os.environ:
                    del os.environ['HTTP_PROXY']
                if 'HTTPS_PROXY' in os.environ:
                    del os.environ['HTTPS_PROXY']
                
                try:
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
                        print(f"[Tushare]  成功获取财务数据（直连）")
                        return df
                finally:
                    # 恢复代理设置
                    if old_http_proxy:
                        os.environ['HTTP_PROXY'] = old_http_proxy
                    if old_https_proxy:
                        os.environ['HTTPS_PROXY'] = old_https_proxy
                        
            except Exception as e:
                print(f"[Tushare]  获取失败: {e}")
        
        # tushare失败，尝试akshare
        try:
            import akshare as ak
            print(f"[Akshare] 正在获取 {symbol} 的财务数据（备用数据源）...")
            
            if report_type == 'income':
                df = ak.stock_financial_report_sina(stock=symbol, symbol="利润表")
            elif report_type == 'balance':
                df = ak.stock_financial_report_sina(stock=symbol, symbol="资产负债表")
            elif report_type == 'cashflow':
                df = ak.stock_financial_report_sina(stock=symbol, symbol="现金流量表")
            else:
                df = None
            
            if df is not None and not df.empty:
                print(f"[Akshare]  成功获取财务数据")
                return df
        except Exception as e:
            print(f"[Akshare]  获取失败: {e}")
        
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


    def is_margin_trading_stock(self, symbol):
        """
        判断股票是否为融资融券标的（通过尝试获取数据来判断）
        
        Args:
            symbol: 股票代码
            
        Returns:
            bool: 是否为融资融券标的
        """
        try:
            # 转换股票代码为tushare格式
            ts_code = self._convert_to_ts_code(symbol)
            
            # 使用Tushare尝试获取融资融券数据来判断
            if self.tushare_available:
                try:
                    # 临时清除代理环境变量，确保tushare直连
                    import os
                    old_http_proxy = os.environ.get('HTTP_PROXY')
                    old_https_proxy = os.environ.get('HTTPS_PROXY')
                    
                    # 清除代理设置
                    if 'HTTP_PROXY' in os.environ:
                        del os.environ['HTTP_PROXY']
                    if 'HTTPS_PROXY' in os.environ:
                        del os.environ['HTTPS_PROXY']
                    
                    try:
                        # 尝试获取个股融资融券明细数据来判断
                        trade_date = datetime.now().strftime('%Y%m%d')
                        df = self.tushare_api.margin_detail(ts_code=ts_code, trade_date=trade_date)
                        if df is not None and not df.empty:
                            print(f"[Tushare]  {symbol} 是融资融券标的（有数据）")
                            return True
                        else:
                            print(f"[Tushare]  {symbol} 不是融资融券标的（无数据）")
                            return False
                    except Exception as detail_error:
                        error_msg = str(detail_error)
                        if "权限" in error_msg or "积分" in error_msg or "permission" in error_msg.lower():
                            print(f"[Tushare]  {symbol} 可能是融资融券标的（权限不足，假设是）")
                            return True  # 权限不足时假设是融资融券标的
                        else:
                            print(f"[Tushare]  {symbol} 不是融资融券标的（获取失败: {detail_error}）")
                            return False
                    finally:
                        # 恢复代理设置
                        if old_http_proxy:
                            os.environ['HTTP_PROXY'] = old_http_proxy
                        if old_https_proxy:
                            os.environ['HTTPS_PROXY'] = old_https_proxy
                            
                except Exception as e:
                    print(f"[Tushare]  判断融资融券标的失败: {e}")
                    return False
            else:
                print(f"[Tushare]  Tushare不可用，假设是融资融券标的")
                return True  # Tushare不可用时假设是融资融券标的
                
        except Exception as e:
            print(f"[ERROR] 判断融资融券标的失败: {e}")
            return True  # 出错时假设是融资融券标的

    def get_margin_trading_data(self, symbol, trade_date=None):
        """
        获取融资融券数据（优先tushare直连，失败时使用akshare）
        智能选择交易日期：开盘前自动选择前一交易日
        
        Args:
            symbol: 股票代码
            trade_date: 交易日期（格式：'20240101'，默认为最新）
            
        Returns:
            dict: 融资融券数据
        """
        from datetime import datetime, timedelta
        
        # 智能选择交易日期
        trade_date = self._get_appropriate_trade_date(symbol, trade_date)
        print(f"[INFO] 融资融券数据查询日期: {trade_date} (智能选择)")
        
        # 直接尝试获取融资融券数据，如果获取失败则说明不是融资融券标的
        
        margin_data = {}
        
        # 优先使用tushare（直连，不使用代理）
        if self.tushare_available:
            try:
                print(f"[Tushare] 正在获取 {symbol} 的融资融券数据（优先数据源，直连）...")
                
                # 临时清除代理环境变量，确保tushare直连
                import os
                old_http_proxy = os.environ.get('HTTP_PROXY')
                old_https_proxy = os.environ.get('HTTPS_PROXY')
                
                # 清除代理设置
                if 'HTTP_PROXY' in os.environ:
                    del os.environ['HTTP_PROXY']
                if 'HTTPS_PROXY' in os.environ:
                    del os.environ['HTTPS_PROXY']
                
                try:
                    # 转换股票代码为tushare格式
                    ts_code = self._convert_to_ts_code(symbol)
                    
                    # 尝试获取个股融资融券明细数据（查找最新可用数据）
                    try:
                        print(f"[Tushare]  正在查找{ts_code}的最新融资融券数据...")
                        
                        # 生成最近10个交易日的日期列表
                        test_dates = []
                        current_date = datetime.strptime(trade_date, '%Y%m%d')
                        for i in range(10):  # 尝试最近10个交易日
                            test_date = current_date - timedelta(days=i)
                            test_dates.append(test_date.strftime('%Y%m%d'))
                        
                        # 按时间顺序尝试获取数据
                        for test_date in test_dates:
                            try:
                                print(f"[Tushare]    尝试日期: {test_date}")
                                df = self.tushare_api.margin_detail(ts_code=ts_code, trade_date=test_date)
                                if df is not None and not df.empty:
                                    row = df.iloc[0]
                                    margin_data = {
                                        'trade_date': row.get('trade_date', ''),
                                        'margin_balance': row.get('rzye', 0),  # 融资余额
                                        'short_balance': row.get('rqye', 0),   # 融券余额
                                        'margin_buy': row.get('rzmre', 0),    # 融资买入额
                                        'short_sell': row.get('rqmcl', 0),    # 融券卖出量
                                        'margin_repay': row.get('rzche', 0),  # 融资偿还额
                                        'short_repay': row.get('rqyl', 0),    # 融券余量
                                        'margin_short_balance': row.get('rzrqye', 0)  # 融资融券余额
                                    }
                                    print(f"[Tushare]    成功获取{test_date}的融资融券数据（最新可用数据）")
                                    break
                                else:
                                    print(f"[Tushare]    {test_date}无数据")
                            except Exception as test_error:
                                print(f"[Tushare]    {test_date}获取失败: {test_error}")
                                continue
                        
                        if not margin_data:
                            print(f"[Tushare]  未找到{ts_code}的融资融券数据（最近10个交易日）")
                            
                    except Exception as detail_error:
                        print(f"[Tushare]  个股融资融券明细获取失败: {detail_error}")
                    
                    # 如果个股数据获取失败，尝试获取市场汇总数据（查找最新可用数据）
                    if not margin_data:
                        try:
                            print(f"[Tushare]  尝试获取市场汇总融资融券数据（查找最新可用数据）...")
                            
                            # 生成最近10个交易日的日期列表
                            test_dates = []
                            current_date = datetime.strptime(trade_date, '%Y%m%d')
                            for i in range(10):  # 尝试最近10个交易日
                                test_date = current_date - timedelta(days=i)
                                test_dates.append(test_date.strftime('%Y%m%d'))
                            
                            # 按时间顺序尝试获取市场汇总数据
                            for test_date in test_dates:
                                try:
                                    print(f"[Tushare]    尝试市场汇总数据日期: {test_date}")
                                    df_summary = self.tushare_api.margin(trade_date=test_date)
                                    if df_summary is not None and not df_summary.empty:
                                        # 使用市场汇总数据
                                        row = df_summary.iloc[0]
                                        margin_data = {
                                            'trade_date': row.get('trade_date', ''),
                                            'margin_balance': row.get('rzye', 0),  # 融资余额
                                            'short_balance': row.get('rqye', 0),   # 融券余额
                                            'margin_buy': row.get('rzmre', 0),    # 融资买入额
                                            'short_sell': row.get('rqmcl', 0),    # 融券卖出量
                                            'margin_repay': row.get('rzche', 0),  # 融资偿还额
                                            'short_repay': row.get('rqyl', 0),    # 融券余量
                                            'margin_short_balance': row.get('rzrqye', 0)  # 融资融券余额
                                        }
                                        print(f"[Tushare]    成功获取{test_date}的市场汇总融资融券数据（最新可用数据）")
                                        break
                                    else:
                                        print(f"[Tushare]    {test_date}市场汇总数据为空")
                                except Exception as test_error:
                                    print(f"[Tushare]    {test_date}市场汇总数据获取失败: {test_error}")
                                    continue
                            
                            if not margin_data:
                                print(f"[Tushare]  未找到市场汇总融资融券数据（最近10个交易日）")
                                
                        except Exception as summary_error:
                            print(f"[Tushare]  市场汇总融资融券数据获取失败: {summary_error}")
                        
                except Exception as te:
                    print(f"[Tushare]  获取失败: {te}")
                finally:
                    # 恢复代理设置
                    if old_http_proxy:
                        os.environ['HTTP_PROXY'] = old_http_proxy
                    if old_https_proxy:
                        os.environ['HTTPS_PROXY'] = old_https_proxy
                        
            except Exception as e:
                print(f"[Tushare] 融资融券数据获取失败: {e}")
        
        # 如果tushare失败，使用akshare作为备用
        if not margin_data:
            try:
                print(f"[Akshare] 正在获取 {symbol} 的融资融券数据（备用数据源）...")
                from standard_network_api import get_akshare_data
                
                df = get_akshare_data('stock_margin_underlying_info_szse', date=trade_date)
                if df is not None and not df.empty:
                    stock_data = df[df['证券代码'] == symbol]
                    if not stock_data.empty:
                        row = stock_data.iloc[0]
                        margin_data = {
                            'trade_date': trade_date,
                            'margin_balance': row.get('融资余额', 0),
                            'short_balance': row.get('融券余额', 0),
                            'margin_buy': row.get('融资买入额', 0),
                            'short_sell': row.get('融券卖出量', 0),
                            'margin_repay': row.get('融资偿还额', 0),
                            'short_repay': row.get('融券余量', 0),
                            'margin_short_balance': row.get('融资融券余额', 0)
                        }
                        print(f"[Akshare]  成功获取融资融券数据")
                    else:
                        print(f"[Akshare]  未找到 {symbol} 的融资融券数据")
                else:
                    print(f"[Akshare]  融资融券数据为空")
                    
            except Exception as e:
                print(f"[Akshare] 融资融券数据获取失败: {e}")
        
        return margin_data
    
    def get_hsgt_fund_flow_data(self, symbol, trade_date=None):
        """
        获取沪深港通资金流向数据（优先Tushare，失败后回退Akshare）
        智能选择交易日期：开盘前自动选择前一交易日

        Args:
            symbol: 股票代码
            trade_date: 交易日期（格式：'20240101'，默认为最新）

        Returns:
            dict: 沪深港通资金流向数据
        """
        from datetime import datetime, timedelta

        # 智能选择交易日期
        trade_date = self._get_appropriate_trade_date(symbol, trade_date)
        print(f"[INFO] 沪深港通资金流向数据查询日期: {trade_date} (智能选择)")

        hsgt_data = {}

        # 判断股票类型
        is_a_stock = self._is_chinese_stock(symbol)
        is_hk_stock = self._is_hk_stock(symbol)

        if not is_a_stock and not is_hk_stock:
            print(f"[INFO] {symbol} 不是A股或港股，跳过沪深港通数据获取")
            return None

        # 优先尝试 Tushare 接口
        if self.tushare_available:
            try:
                print("[Tushare] 正在获取沪深港通Top10数据...")
                hsgt_data = {
                    'trade_date': trade_date,
                    'data_source': 'Tushare_hsgt_top10'
                }

                def _fetch_market(market_type: str):
                    return self._make_tushare_request(
                        self.tushare_api.hsgt_top10,
                        trade_date=trade_date,
                        market_type=market_type
                    )

                def _sum_column(df, column):
                    if df is None or df.empty or column not in df.columns:
                        return 0
                    series = df[column].dropna()
                    return float(series.sum()) if not series.empty else 0

                if is_a_stock:
                    df_hgt = _fetch_market('1')  # 沪股通
                    df_sgt = _fetch_market('3')  # 深股通
                    if df_hgt is not None and not df_hgt.empty:
                        hsgt_data['hgt_top10'] = df_hgt.to_dict('records')
                    if df_sgt is not None and not df_sgt.empty:
                        hsgt_data['sgt_top10'] = df_sgt.to_dict('records')

                    total_amount = _sum_column(df_hgt, 'amount') + _sum_column(df_sgt, 'amount')
                    total_net = _sum_column(df_hgt, 'net_amount') + _sum_column(df_sgt, 'net_amount')

                    if total_amount or total_net or hsgt_data.get('hgt_top10') or hsgt_data.get('sgt_top10'):
                        hsgt_data['stock_type'] = 'A股'
                        hsgt_data['north_turnover'] = total_amount
                        hsgt_data['north_net_amount'] = total_net
                        if total_net > 0:
                            hsgt_data['interpretation'] = f"北向资金Top10合计净流入 {total_net:,.0f} 元"
                        elif total_net < 0:
                            hsgt_data['interpretation'] = f"北向资金Top10合计净流出 {abs(total_net):,.0f} 元"
                        else:
                            hsgt_data['interpretation'] = "北向Top10净额为0或数据缺失"
                        print("[Tushare] 成功获取北向资金Top10数据")
                        return hsgt_data

                if is_hk_stock:
                    df_ggt_sh = _fetch_market('2')  # 港股通（沪）
                    df_ggt_sz = _fetch_market('4')  # 港股通（深）
                    if df_ggt_sh is not None and not df_ggt_sh.empty:
                        hsgt_data['ggt_sh_top10'] = df_ggt_sh.to_dict('records')
                    if df_ggt_sz is not None and not df_ggt_sz.empty:
                        hsgt_data['ggt_sz_top10'] = df_ggt_sz.to_dict('records')

                    total_amount = _sum_column(df_ggt_sh, 'amount') + _sum_column(df_ggt_sz, 'amount')
                    total_net = _sum_column(df_ggt_sh, 'net_amount') + _sum_column(df_ggt_sz, 'net_amount')

                    if total_amount or total_net or hsgt_data.get('ggt_sh_top10') or hsgt_data.get('ggt_sz_top10'):
                        hsgt_data['stock_type'] = '港股'
                        hsgt_data['south_turnover'] = total_amount
                        hsgt_data['south_net_amount'] = total_net
                        if total_net > 0:
                            hsgt_data['interpretation'] = f"南向资金Top10合计净流入 {total_net:,.0f} 元"
                        elif total_net < 0:
                            hsgt_data['interpretation'] = f"南向资金Top10合计净流出 {abs(total_net):,.0f} 元"
                        else:
                            hsgt_data['interpretation'] = "南向Top10净额为0或数据缺失"
                        print("[Tushare] 成功获取南向资金Top10数据")
                        return hsgt_data

                print("[Tushare] 未获取到Top10数据，尝试备用数据源")
            except Exception as e:
                print(f"[Tushare] 沪深港通数据获取失败: {e}")

        # 回退 Akshare 汇总数据
        print(f"[INFO] 使用 Akshare 作为备用数据源")
        print(f"[Akshare] 正在获取沪深港通资金流向汇总数据...")
        try:
            from standard_network_api import get_akshare_data

            df_summary = get_akshare_data('stock_hsgt_fund_flow_summary_em')
            if df_summary is not None and not df_summary.empty:
                latest_row = df_summary.iloc[0]

                if is_a_stock:
                    hgt = latest_row.get('沪股通', 0) * 1_000_000
                    sgt = latest_row.get('深股通', 0) * 1_000_000
                    north_money = hgt + sgt

                    hsgt_data = {
                        'trade_date': latest_row.get('交易日期', ''),
                        'stock_type': 'A股',
                        'hgt': hgt,
                        'sgt': sgt,
                        'north_money': north_money,
                        'south_money': latest_row.get('南向资金', 0) * 1_000_000,
                        'analysis_focus': '北向资金流入情况',
                        'data_source': 'Akshare_沪深港通汇总'
                    }

                    if north_money > 0:
                        hsgt_data['interpretation'] = f"北向资金净流入{north_money:,.0f}元，外资看好A股"
                    elif north_money < 0:
                        hsgt_data['interpretation'] = f"北向资金净流出{abs(north_money):,.0f}元，外资谨慎"
                    else:
                        hsgt_data['interpretation'] = "北向资金基本平衡"

                elif is_hk_stock:
                    ggt_ss = latest_row.get('港股通(沪)', 0) * 1_000_000
                    ggt_sz = latest_row.get('港股通(深)', 0) * 1_000_000
                    south_money = ggt_ss + ggt_sz

                    hsgt_data = {
                        'trade_date': latest_row.get('交易日期', ''),
                        'stock_type': '港股',
                        'ggt_ss': ggt_ss,
                        'ggt_sz': ggt_sz,
                        'north_money': latest_row.get('北向资金', 0) * 1_000_000,
                        'south_money': south_money,
                        'analysis_focus': '南向资金流入情况',
                        'data_source': 'Akshare_沪深港通汇总'
                    }

                    if south_money > 0:
                        hsgt_data['interpretation'] = f"南向资金净流入{south_money:,.0f}元，内地资金看好港股"
                    elif south_money < 0:
                        hsgt_data['interpretation'] = f"南向资金净流出{abs(south_money):,.0f}元，内地资金谨慎"
                    else:
                        hsgt_data['interpretation'] = "南向资金基本平衡"

                print(f"[Akshare] 成功获取沪深港通资金流向汇总数据（数据来源: {hsgt_data.get('data_source')}）")
                return hsgt_data
            else:
                print("[Akshare] 沪深港通资金流向汇总数据为空")

        except Exception as e:
            print(f"[Akshare] 沪深港通资金流向数据获取失败: {e}")

        return hsgt_data
    
    def get_research_reports_data(self, symbol: str, days: int = 90) -> Dict:
        """
        获取研报数据（Tushare优先，直连）
        
        Args:
            symbol: 股票代码
            days: 获取最近多少天的研报数据
            
        Returns:
            研报数据字典
        """
        if not self.tushare_available:
            print(f"[INFO] Tushare不可用，跳过研报数据获取")
            return None
        
        try:
            # 转换股票代码格式
            ts_code = self._convert_to_ts_code(symbol)
            if not ts_code:
                print(f"[INFO] {symbol} 不是有效的股票代码，跳过研报数据获取")
                return None
            
            print(f"[Tushare] 正在获取 {symbol} 的研报数据（优先数据源，直连）...")
            
            # 临时清除代理环境变量，确保tushare直连
            import os
            old_http_proxy = os.environ.get('HTTP_PROXY')
            old_https_proxy = os.environ.get('HTTPS_PROXY')
            
            if 'HTTP_PROXY' in os.environ:
                del os.environ['HTTP_PROXY']
            if 'HTTPS_PROXY' in os.environ:
                del os.environ['HTTPS_PROXY']
            
            try:
                # 计算日期范围
                from datetime import datetime, timedelta
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
                
                # 获取研报数据
                df_reports = self.tushare_api.report_rc(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date
                )
                
                if df_reports is not None and not df_reports.empty:
                    print(f"[Tushare] 成功获取 {len(df_reports)} 条研报数据")
                    
                    # 分析研报数据
                    reports_analysis = self._analyze_research_reports(df_reports)
                    reports_analysis['data_source'] = 'Tushare'
                    reports_analysis['data_success'] = True
                    
                    return reports_analysis
                else:
                    print(f"[Tushare] 未找到 {symbol} 的研报数据")
                    return None
                    
            finally:
                # 恢复代理环境变量
                if old_http_proxy:
                    os.environ['HTTP_PROXY'] = old_http_proxy
                if old_https_proxy:
                    os.environ['HTTPS_PROXY'] = old_https_proxy
                    
        except Exception as e:
            print(f"[Tushare] 研报数据获取失败: {e}")
            return None
    
    def _analyze_research_reports(self, df_reports) -> Dict:
        """
        分析研报数据
        
        Args:
            df_reports: 研报数据DataFrame
            
        Returns:
            研报分析结果
        """
        analysis = {
            'total_reports': len(df_reports),
            'reports_data': [],
            'summary': {}
        }
        
        # 处理每条研报数据
        for idx, row in df_reports.iterrows():
            report_data = {
                'report_date': row.get('report_date', ''),
                'report_title': row.get('report_title', ''),
                'org_name': row.get('org_name', ''),
                'author_name': row.get('author_name', ''),
                'rating': row.get('rating', ''),
                'report_type': row.get('report_type', ''),
                'classify': row.get('classify', ''),
                'quarter': row.get('quarter', ''),
                'target_price_max': row.get('max_price'),
                'target_price_min': row.get('min_price'),
                'op_rt': row.get('op_rt'),  # 营业收入
                'op_pr': row.get('op_pr'),  # 营业利润
                'np': row.get('np'),        # 净利润
                'eps': row.get('eps'),      # 每股收益
                'pe': row.get('pe'),        # 市盈率
                'roe': row.get('roe'),      # 净资产收益率
                'ev_ebitda': row.get('ev_ebitda'),  # 企业价值倍数
            }
            analysis['reports_data'].append(report_data)
        
        # 统计分析
        if len(df_reports) > 0:
            # 机构统计
            org_counts = df_reports['org_name'].value_counts()
            analysis['summary']['top_institutions'] = org_counts.head(5).to_dict()
            
            # 评级统计
            rating_counts = df_reports['rating'].value_counts()
            analysis['summary']['rating_distribution'] = rating_counts.to_dict()
            
            # 目标价格统计
            max_prices = df_reports['max_price'].dropna()
            min_prices = df_reports['min_price'].dropna()
            if not max_prices.empty:
                analysis['summary']['target_price_stats'] = {
                    'max': float(max_prices.max()),
                    'min': float(max_prices.min()),
                    'avg': float(max_prices.mean()),
                    'count': len(max_prices)
                }
            elif not min_prices.empty:
                analysis['summary']['target_price_stats'] = {
                    'max': float(min_prices.max()),
                    'min': float(min_prices.min()),
                    'avg': float(min_prices.mean()),
                    'count': len(min_prices)
                }
            
            # 财务指标统计
            eps_values = df_reports['eps'].dropna()
            pe_values = df_reports['pe'].dropna()
            roe_values = df_reports['roe'].dropna()
            
            if not eps_values.empty:
                analysis['summary']['eps_stats'] = {
                    'max': float(eps_values.max()),
                    'min': float(eps_values.min()),
                    'avg': float(eps_values.mean())
                }
            
            if not pe_values.empty:
                analysis['summary']['pe_stats'] = {
                    'max': float(pe_values.max()),
                    'min': float(pe_values.min()),
                    'avg': float(pe_values.mean())
                }
            
            if not roe_values.empty:
                analysis['summary']['roe_stats'] = {
                    'max': float(roe_values.max()),
                    'min': float(roe_values.min()),
                    'avg': float(roe_values.mean())
                }
            
            # 最新研报信息
            latest_report = df_reports.iloc[0]
            analysis['summary']['latest_report'] = {
                'date': latest_report.get('report_date', ''),
                'title': latest_report.get('report_title', ''),
                'org': latest_report.get('org_name', ''),
                'rating': latest_report.get('rating', ''),
                'target_price': latest_report.get('max_price') or latest_report.get('min_price')
            }
        
        return analysis
    
    def _is_chinese_stock(self, symbol):
        """判断是否为中国A股"""
        return symbol.isdigit() and len(symbol) == 6
    
    def _is_hk_stock(self, symbol):
        """判断是否为港股"""
        # 港股代码通常是4-5位数字，或者以HK开头
        if symbol.startswith('HK'):
            return True
        if symbol.isdigit() and len(symbol) in [4, 5]:
            # 进一步判断是否为港股（这里简化处理）
            return False  # 暂时不识别港股，需要根据实际情况调整
        return False
    
    def _is_before_market_open(self):
        """判断当前时间是否在开盘前"""
        from datetime import datetime, time
        now = datetime.now()
        current_time = now.time()
        
        # 工作日判断（简化处理，不考虑节假日）
        if now.weekday() >= 5:  # 周六日
            return True
        
        # 开盘时间：9:30-11:30, 13:00-15:00
        morning_start = time(9, 30)
        morning_end = time(11, 30)
        afternoon_start = time(13, 0)
        afternoon_end = time(15, 0)
        
        # 如果在开盘时间内，返回False
        if (morning_start <= current_time <= morning_end) or (afternoon_start <= current_time <= afternoon_end):
            return False
        
        # 如果在开盘时间前，返回True
        return True
    
    def _get_appropriate_trade_date(self, symbol, trade_date=None):
        """获取合适的交易日期（开盘前选择前一交易日）"""
        from datetime import datetime, timedelta
        
        if not trade_date:
            trade_date = datetime.now().strftime('%Y%m%d')
        
        # 如果当前时间在开盘前，选择前一交易日
        if self._is_before_market_open():
            current_date = datetime.strptime(trade_date, '%Y%m%d')
            # 往前推1-3天，找到最近的交易日（简化处理，不考虑节假日）
            for i in range(1, 4):
                prev_date = current_date - timedelta(days=i)
                # 跳过周末
                if prev_date.weekday() < 5:
                    return prev_date.strftime('%Y%m%d')
        
        return trade_date
    
    def get_turnover_rate_data(self, symbol, trade_date=None):
        """
        获取换手率数据（优先tushare直连，失败时使用akshare）
        
        Args:
            symbol: 股票代码
            trade_date: 交易日期（格式：'20240101'，默认为最新）
            
        Returns:
            dict: 换手率数据
        """
        # 在函数开始时就导入 datetime，避免变量名冲突
        from datetime import datetime, timedelta
        
        if not trade_date:
            trade_date = datetime.now().strftime('%Y%m%d')
        # 根据时间选择更合适的交易日（开盘前用前一交易日）
        trade_date = self._get_appropriate_trade_date(symbol, trade_date)
        
        turnover_data = {}
        
        # 优先使用tushare（直连，不使用代理）
        if self.tushare_available:
            try:
                print(f"[Tushare] 正在获取 {symbol} 的换手率数据（优先数据源，直连）...")
                
                # 临时清除代理环境变量，确保tushare直连
                import os
                old_http_proxy = os.environ.get('HTTP_PROXY')
                old_https_proxy = os.environ.get('HTTPS_PROXY')
                
                # 清除代理设置
                if 'HTTP_PROXY' in os.environ:
                    del os.environ['HTTP_PROXY']
                if 'HTTPS_PROXY' in os.environ:
                    del os.environ['HTTPS_PROXY']
                
                try:
                    ts_code = self._convert_to_ts_code(symbol)
                    # 连续回退最多5个自然日，找到最近的可用数据
                    base_date = datetime.strptime(trade_date, '%Y%m%d')
                    for i in range(0, 5):
                        try_date = (base_date - timedelta(days=i)).strftime('%Y%m%d')
                        df = self.tushare_api.daily_basic(ts_code=ts_code, trade_date=try_date)
                        if df is not None and not df.empty:
                            row = df.iloc[0]
                            turnover_data = {
                                'trade_date': row.get('trade_date', try_date),
                                'turnover_rate': row.get('turnover_rate', 0),
                                'turnover_rate_f': row.get('turnover_rate_f', 0),
                                'volume_ratio': row.get('volume_ratio', 0),
                                'pe': row.get('pe', 0),
                                'pe_ttm': row.get('pe_ttm', 0),
                                'pb': row.get('pb', 0),
                                'total_mv': row.get('total_mv', 0),
                                'circ_mv': row.get('circ_mv', 0)
                            }
                            print(f"[Tushare]  成功获取换手率数据（交易日: {try_date}）")
                            break
                    if not turnover_data:
                        print(f"[Tushare]  换手率数据为空（已回退5日仍无数据）")
                        
                except Exception as te:
                    print(f"[Tushare]  获取失败: {te}")
                finally:
                    # 恢复代理设置
                    if old_http_proxy:
                        os.environ['HTTP_PROXY'] = old_http_proxy
                    if old_https_proxy:
                        os.environ['HTTPS_PROXY'] = old_https_proxy
                        
            except Exception as e:
                print(f"[Tushare] 换手率数据获取失败: {e}")
        
        # 如果tushare失败，使用akshare作为备用
        if not turnover_data:
            try:
                print(f"[Akshare] 正在获取 {symbol} 的换手率数据（备用数据源）...")
                from standard_network_api import get_akshare_data
                
                df = get_akshare_data('stock_zh_a_spot_em')
                if df is not None and not df.empty:
                    stock_data = df[df['代码'] == symbol]
                    if not stock_data.empty:
                        row = stock_data.iloc[0]
                        turnover_data = {
                            'trade_date': trade_date,
                            'turnover_rate': row.get('换手率', 0),
                            'volume_ratio': row.get('量比', 0),
                            'pe': row.get('市盈率-动态', 0),
                            'pb': row.get('市净率', 0),
                            'total_mv': row.get('总市值', 0),
                            'circ_mv': row.get('流通市值', 0)
                        }
                        print(f"[Akshare]  成功获取换手率数据")
                    else:
                        print(f"[Akshare]  未找到 {symbol} 的换手率数据")
                else:
                    print(f"[Akshare]  换手率数据为空")
                    
            except Exception as e:
                print(f"[Akshare] 换手率数据获取失败: {e}")
        
        return turnover_data
    
    def get_market_index_data(self, index_code='000001.SH', trade_date=None):
        """
        获取市场指数数据（优先tushare直连，失败时使用akshare）
        
        Args:
            index_code: 指数代码（默认：000001.SH 上证指数）
            trade_date: 交易日期（格式：'20240101'，默认为最新）
            
        Returns:
            dict: 指数数据
        """
        if not trade_date:
            trade_date = datetime.now().strftime('%Y%m%d')
        
        index_data = {}
        
        # 优先使用tushare（直连，不使用代理）
        if self.tushare_available:
            try:
                print(f"[Tushare] 正在获取 {index_code} 的指数数据（优先数据源，直连）...")
                
                # 临时清除代理环境变量，确保tushare直连
                import os
                old_http_proxy = os.environ.get('HTTP_PROXY')
                old_https_proxy = os.environ.get('HTTPS_PROXY')
                
                # 清除代理设置
                if 'HTTP_PROXY' in os.environ:
                    del os.environ['HTTP_PROXY']
                if 'HTTPS_PROXY' in os.environ:
                    del os.environ['HTTPS_PROXY']
                
                try:
                    # 获取指数数据
                    df = self.tushare_api.index_daily(ts_code=index_code, trade_date=trade_date)
                    
                    if df is not None and not df.empty:
                        row = df.iloc[0]
                        index_data = {
                            'trade_date': row.get('trade_date', ''),
                            'close': row.get('close', 0),
                            'open': row.get('open', 0),
                            'high': row.get('high', 0),
                            'low': row.get('low', 0),
                            'pre_close': row.get('pre_close', 0),
                            'change': row.get('change', 0),
                            'pct_chg': row.get('pct_chg', 0),
                            'vol': row.get('vol', 0),
                            'amount': row.get('amount', 0)
                        }
                        print(f"[Tushare]  成功获取指数数据")
                    else:
                        print(f"[Tushare]  指数数据为空")
                        
                except Exception as te:
                    print(f"[Tushare]  获取失败: {te}")
                finally:
                    # 恢复代理设置
                    if old_http_proxy:
                        os.environ['HTTP_PROXY'] = old_http_proxy
                    if old_https_proxy:
                        os.environ['HTTPS_PROXY'] = old_https_proxy
                        
            except Exception as e:
                print(f"[Tushare] 指数数据获取失败: {e}")
        
        # 如果tushare失败，使用akshare作为备用
        if not index_data:
            try:
                print(f"[Akshare] 正在获取 {index_code} 的指数数据（备用数据源）...")
                from standard_network_api import get_akshare_data
                
                df = get_akshare_data('stock_zh_index_spot_em')
                if df is not None and not df.empty:
                    # 根据指数代码查找对应数据
                    if index_code == '000001.SH':
                        index_name = '上证指数'
                    elif index_code == '399001.SZ':
                        index_name = '深证成指'
                    elif index_code == '399006.SZ':
                        index_name = '创业板指'
                    else:
                        index_name = index_code
                    
                    stock_data = df[df['名称'] == index_name]
                    if not stock_data.empty:
                        row = stock_data.iloc[0]
                        index_data = {
                            'trade_date': trade_date,
                            'close': row.get('最新价', 0),
                            'change': row.get('涨跌额', 0),
                            'pct_chg': row.get('涨跌幅', 0),
                            'vol': row.get('成交量', 0),
                            'amount': row.get('成交额', 0)
                        }
                        print(f"[Akshare]  成功获取指数数据")
                    else:
                        print(f"[Akshare]  未找到 {index_name} 的指数数据")
                else:
                    print(f"[Akshare]  指数数据为空")
                    
            except Exception as e:
                print(f"[Akshare] 指数数据获取失败: {e}")
        
        return index_data
    
    def get_concept_data(self):
        """
        获取概念板块数据（优先tushare直连，失败时使用akshare）
        
        Returns:
            DataFrame: 概念板块数据
        """
        # 优先使用tushare（直连，不使用代理）
        if self.tushare_available:
            try:
                print(f"[Tushare] 正在获取概念板块数据（优先数据源，直连）...")
                
                # 临时清除代理环境变量，确保tushare直连
                import os
                old_http_proxy = os.environ.get('HTTP_PROXY')
                old_https_proxy = os.environ.get('HTTPS_PROXY')
                
                # 清除代理设置
                if 'HTTP_PROXY' in os.environ:
                    del os.environ['HTTP_PROXY']
                if 'HTTPS_PROXY' in os.environ:
                    del os.environ['HTTPS_PROXY']
                
                try:
                    # 获取概念板块数据
                    df = self.tushare_api.concept()
                    
                    if df is not None and not df.empty:
                        print(f"[Tushare]  成功获取概念板块数据: {len(df)} 条")
                        return df
                    else:
                        print(f"[Tushare]  概念板块数据为空")
                        
                except Exception as te:
                    print(f"[Tushare]  获取失败: {te}")
                finally:
                    # 恢复代理设置
                    if old_http_proxy:
                        os.environ['HTTP_PROXY'] = old_http_proxy
                    if old_https_proxy:
                        os.environ['HTTPS_PROXY'] = old_https_proxy
                        
            except Exception as e:
                print(f"[Tushare] 概念板块数据获取失败: {e}")
        
        # 如果tushare失败，使用akshare作为备用
        try:
            print(f"[Akshare] 正在获取概念板块数据（备用数据源）...")
            from standard_network_api import get_akshare_data
            
            df = get_akshare_data('stock_board_concept_name_em')
            if df is not None and not df.empty:
                print(f"[Akshare]  成功获取概念板块数据: {len(df)} 条")
                return df
            else:
                print(f"[Akshare]  概念板块数据为空")
                
        except Exception as e:
            print(f"[Akshare] 概念板块数据获取失败: {e}")
        
        return None
    
    def get_industry_data(self):
        """
        获取行业板块数据（优先tushare直连，失败时使用akshare）
        
        Returns:
            DataFrame: 行业板块数据
        """
        # 优先使用tushare（直连，不使用代理）
        if self.tushare_available:
            try:
                print(f"[Tushare] 正在获取行业板块数据（优先数据源，直连）...")
                
                # 临时清除代理环境变量，确保tushare直连
                import os
                old_http_proxy = os.environ.get('HTTP_PROXY')
                old_https_proxy = os.environ.get('HTTPS_PROXY')
                
                # 清除代理设置
                if 'HTTP_PROXY' in os.environ:
                    del os.environ['HTTP_PROXY']
                if 'HTTPS_PROXY' in os.environ:
                    del os.environ['HTTPS_PROXY']
                
                try:
                    # 获取行业板块数据（使用股票基本信息中的行业分类）
                    df = self.tushare_api.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name,industry')
                    
                    if df is not None and not df.empty:
                        # 按行业分组统计
                        industry_stats = df.groupby('industry').agg({
                            'ts_code': 'count',
                            'name': 'first'
                        }).rename(columns={'ts_code': 'count'}).reset_index()
                        
                        print(f"[Tushare]  成功获取行业板块数据: {len(industry_stats)} 个行业")
                        return industry_stats
                    else:
                        print(f"[Tushare]  行业板块数据为空")
                        
                except Exception as te:
                    print(f"[Tushare]  获取失败: {te}")
                finally:
                    # 恢复代理设置
                    if old_http_proxy:
                        os.environ['HTTP_PROXY'] = old_http_proxy
                    if old_https_proxy:
                        os.environ['HTTPS_PROXY'] = old_https_proxy
                        
            except Exception as e:
                print(f"[Tushare] 行业板块数据获取失败: {e}")
        
        # 如果tushare失败，使用akshare作为备用
        try:
            print(f"[Akshare] 正在获取行业板块数据（备用数据源）...")
            from standard_network_api import get_akshare_data
            
            df = get_akshare_data('stock_board_industry_name_em')
            if df is not None and not df.empty:
                print(f"[Akshare]  成功获取行业板块数据: {len(df)} 条")
                return df
            else:
                print(f"[Akshare]  行业板块数据为空")
                
        except Exception as e:
            print(f"[Akshare] 行业板块数据获取失败: {e}")
        
        return None
    
    def get_longhubang_daily_stats(self, trade_date=None):
        """
        获取龙虎榜每日统计数据（优先tushare直连，失败时使用akshare）
        
        Args:
            trade_date: 交易日期（格式：'20240101'，默认为最新）
            
        Returns:
            DataFrame: 龙虎榜每日统计数据
        """
        if not trade_date:
            trade_date = datetime.now().strftime('%Y%m%d')
        
        # 优先使用tushare（直连，不使用代理）
        if self.tushare_available:
            try:
                print(f"[Tushare] 正在获取 {trade_date} 的龙虎榜每日统计（优先数据源，直连）...")
                
                # 临时清除代理环境变量，确保tushare直连
                import os
                old_http_proxy = os.environ.get('HTTP_PROXY')
                old_https_proxy = os.environ.get('HTTPS_PROXY')
                
                # 清除代理设置
                if 'HTTP_PROXY' in os.environ:
                    del os.environ['HTTP_PROXY']
                if 'HTTPS_PROXY' in os.environ:
                    del os.environ['HTTPS_PROXY']
                
                try:
                    # 获取龙虎榜每日统计数据
                    df = self.tushare_api.top_list(trade_date=trade_date)
                    
                    if df is not None and not df.empty:
                        print(f"[Tushare]  成功获取龙虎榜每日统计: {len(df)} 条记录")
                        return df
                    else:
                        print(f"[Tushare]  龙虎榜每日统计数据为空")
                        
                except Exception as te:
                    print(f"[Tushare]  获取失败: {te}")
                finally:
                    # 恢复代理设置
                    if old_http_proxy:
                        os.environ['HTTP_PROXY'] = old_http_proxy
                    if old_https_proxy:
                        os.environ['HTTPS_PROXY'] = old_https_proxy
                        
            except Exception as e:
                print(f"[Tushare] 龙虎榜每日统计获取失败: {e}")
        
        # 取消Akshare备用路径，避免参数不兼容与代理重试噪音
        print(f"[LHB] 跳过Akshare备用数据源（统一以Tushare为准）")
        
        return None
    
    def get_tushare_data(self, interface_name, **kwargs):
        """
        通用Tushare数据获取方法（直连，不使用代理）
        
        Args:
            interface_name: Tushare接口名称（如'fund_basic', 'stock_basic'等）
            **kwargs: 接口参数
            
        Returns:
            DataFrame: 查询结果，失败时返回None
        """
        if not self.tushare_available:
            print(f"[Tushare] Tushare数据源不可用")
            return None
        
        try:
            print(f"[Tushare] 正在获取 {interface_name} 数据（直连）...")
            
            # 临时清除代理环境变量，确保tushare直连
            import os
            old_http_proxy = os.environ.get('HTTP_PROXY')
            old_https_proxy = os.environ.get('HTTPS_PROXY')
            
            # 清除代理设置
            if 'HTTP_PROXY' in os.environ:
                del os.environ['HTTP_PROXY']
            if 'HTTPS_PROXY' in os.environ:
                del os.environ['HTTPS_PROXY']
            
            try:
                # 获取接口方法
                if hasattr(self.tushare_api, interface_name):
                    method = getattr(self.tushare_api, interface_name)
                    df = method(**kwargs)
                    
                    if df is not None and not df.empty:
                        print(f"[Tushare]  成功获取数据: {len(df)} 条记录")
                        return df
                    else:
                        print(f"[Tushare]  数据为空")
                        return None
                else:
                    print(f"[Tushare]  接口 {interface_name} 不存在")
                    return None
                    
            except Exception as te:
                print(f"[Tushare]  获取失败: {te}")
                return None
            finally:
                # 恢复代理设置
                if old_http_proxy:
                    os.environ['HTTP_PROXY'] = old_http_proxy
                if old_https_proxy:
                    os.environ['HTTPS_PROXY'] = old_https_proxy
                    
        except Exception as e:
            print(f"[Tushare] 数据获取异常: {e}")
            return None
    
    def get_longhubang_institution_details(self, trade_date=None, ts_code=None):
        """
        获取龙虎榜机构明细数据（优先tushare直连，失败时使用akshare）
        
        Args:
            trade_date: 交易日期（格式：'20240101'，默认为最新）
            ts_code: TS代码（可选）
            
        Returns:
            DataFrame: 龙虎榜机构明细数据
        """
        if not trade_date:
            trade_date = datetime.now().strftime('%Y%m%d')
        
        # 优先使用tushare（直连，不使用代理）
        if self.tushare_available:
            try:
                print(f"[Tushare] 正在获取 {trade_date} 的龙虎榜机构明细（优先数据源，直连）...")
                
                # 临时清除代理环境变量，确保tushare直连
                import os
                old_http_proxy = os.environ.get('HTTP_PROXY')
                old_https_proxy = os.environ.get('HTTPS_PROXY')
                
                # 清除代理设置
                if 'HTTP_PROXY' in os.environ:
                    del os.environ['HTTP_PROXY']
                if 'HTTPS_PROXY' in os.environ:
                    del os.environ['HTTPS_PROXY']
                
                try:
                    # 获取龙虎榜机构明细数据
                    params = {'trade_date': trade_date}
                    if ts_code:
                        params['ts_code'] = ts_code
                    
                    df = self.tushare_api.top_inst(**params)
                    
                    if df is not None and not df.empty:
                        print(f"[Tushare]  成功获取龙虎榜机构明细: {len(df)} 条记录")
                        return df
                    else:
                        print(f"[Tushare]  龙虎榜机构明细数据为空")
                        
                except Exception as te:
                    print(f"[Tushare]  获取失败: {te}")
                finally:
                    # 恢复代理设置
                    if old_http_proxy:
                        os.environ['HTTP_PROXY'] = old_http_proxy
                    if old_https_proxy:
                        os.environ['HTTPS_PROXY'] = old_https_proxy
                        
            except Exception as e:
                print(f"[Tushare] 龙虎榜机构明细获取失败: {e}")
        
        # 取消Akshare备用路径，避免参数不兼容与代理重试噪音
        print(f"[LHB] 跳过Akshare备用数据源（统一以Tushare为准）")
        
        return None
    
    def get_longhubang_comprehensive_data(self, trade_date=None):
        """
        获取龙虎榜综合数据（包含每日统计和机构明细）
        
        Args:
            trade_date: 交易日期（格式：'20240101'，默认为最新）
            
        Returns:
            dict: 包含每日统计和机构明细的综合数据
        """
        if not trade_date:
            trade_date = datetime.now().strftime('%Y%m%d')
        
        print(f"[Tushare] 正在获取 {trade_date} 的龙虎榜综合数据...")
        
        # 获取每日统计数据
        daily_stats = self.get_longhubang_daily_stats(trade_date)
        
        # 获取机构明细数据
        institution_details = self.get_longhubang_institution_details(trade_date)
        
        # 组合数据
        comprehensive_data = {
            'trade_date': trade_date,
            'daily_stats': daily_stats,
            'institution_details': institution_details,
            'data_success': daily_stats is not None or institution_details is not None
        }
        
        if comprehensive_data['data_success']:
            print(f"[Tushare] 龙虎榜综合数据获取成功")
        else:
            print(f"[Tushare] 龙虎榜综合数据获取失败")
        
        return comprehensive_data


# 全局数据源管理器实例
data_source_manager = DataSourceManager()

