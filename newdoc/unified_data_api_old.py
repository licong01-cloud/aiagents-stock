#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一数据获取API
实现Tushare优先、Akshare备选、直连优先、代理备选的统一策略
"""

import os
import pandas as pd
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Union, List
import warnings
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

warnings.filterwarnings('ignore')

class UnifiedDataAPI:
    """统一数据获取API - Tushare优先，Akshare备选"""
    
    def __init__(self):
        self.tushare_available = False
        self.tushare_api = None
        self.akshare_available = False
        
        # 初始化Tushare
        self._init_tushare()
        
        # 初始化Akshare
        self._init_akshare()
        
        # 初始化网络优化器
        self._init_network_optimizer()
    
    def _init_tushare(self):
        """初始化Tushare"""
        try:
            import tushare as ts
            token = os.getenv('TUSHARE_TOKEN', '')
            if token:
                ts.set_token(token)
                self.tushare_api = ts.pro_api()
                self.tushare_available = True
                print("[OK] Tushare数据源初始化成功")
            else:
                print("[WARN] 未配置Tushare Token")
        except Exception as e:
            print(f"[WARN] Tushare初始化失败: {e}")
    
    def _init_akshare(self):
        """初始化Akshare"""
        try:
            import akshare as ak
            self.akshare_available = True
            print("[OK] Akshare数据源初始化成功")
        except Exception as e:
            print(f"[WARN] Akshare初始化失败: {e}")
    
    def _init_network_optimizer(self):
        """初始化网络优化器"""
        try:
            from network_optimizer import network_optimizer
            self.network_optimizer = network_optimizer
        except ImportError:
            self.network_optimizer = None
    
    def _convert_to_ts_code(self, symbol: str) -> str:
        """将股票代码转换为Tushare格式"""
        if len(symbol) == 6 and symbol.isdigit():
            # A股代码
            if symbol.startswith(('00', '30')):
                return f"{symbol}.SZ"  # 深市
            elif symbol.startswith(('60', '68')):
                return f"{symbol}.SH"  # 沪市
            # ETF 常见代码段
            elif symbol.startswith(('51', '56', '58')):
                return f"{symbol}.SH"  # 沪市ETF
            elif symbol.startswith(('15', '16')):
                return f"{symbol}.SZ"  # 深市ETF（如159xxx、16xxxx）
        return symbol
    
    def _make_tushare_request(self, func, **kwargs):
        """执行Tushare请求（直连）"""
        if not self.tushare_available:
            raise Exception("Tushare不可用")
        
        # 临时清除代理设置，确保直连
        old_http_proxy = os.environ.get('HTTP_PROXY')
        old_https_proxy = os.environ.get('HTTPS_PROXY')
        
        try:
            # 清除代理设置
            if 'HTTP_PROXY' in os.environ:
                del os.environ['HTTP_PROXY']
            if 'HTTPS_PROXY' in os.environ:
                del os.environ['HTTPS_PROXY']
            
            # 执行Tushare请求
            result = func(**kwargs)
            return result
        finally:
            # 恢复代理设置
            if old_http_proxy:
                os.environ['HTTP_PROXY'] = old_http_proxy
            if old_https_proxy:
                os.environ['HTTPS_PROXY'] = old_https_proxy
    
    def _make_akshare_request(self, func_name: str, **kwargs):
        """执行Akshare请求（支持直连和代理）"""
        if not self.akshare_available:
            raise Exception("Akshare不可用")
        
        import akshare as ak
        
        # 获取Akshare函数
        func = getattr(ak, func_name, None)
        if not func:
            raise Exception(f"Akshare函数 {func_name} 不存在")
        
        # 如果有网络优化器，使用统一网络API
        if self.network_optimizer:
            def _akshare_call(**retry_kwargs):
                return func(**kwargs)
            
            return self.network_optimizer._make_request_with_retry(_akshare_call)
        else:
            # 直接调用
            return func(**kwargs)
    
    def get_stock_basic_info(self, symbol: str) -> Dict[str, Any]:
        """获取股票基本信息"""
        print(f"[统一API] 获取股票基本信息: {symbol}")
        
        # 1. 优先使用Tushare
        if self.tushare_available:
            try:
                print(f"[Tushare] 正在获取股票基本信息（直连）...")
                ts_code = self._convert_to_ts_code(symbol)
                
                # 获取股票基本信息
                df = self._make_tushare_request(
                    self.tushare_api.stock_basic,
                    ts_code=ts_code,
                    fields='ts_code,symbol,name,area,industry,market,list_date'
                )
                
                if df is not None and not df.empty:
                    row = df.iloc[0]
                    result = {
                        'symbol': symbol,
                        'name': row.get('name', ''),
                        'area': row.get('area', ''),
                        'industry': row.get('industry', ''),
                        'market': row.get('market', ''),
                        'list_date': row.get('list_date', ''),
                        'data_source': 'Tushare'
                    }
                    print(f"[Tushare] 成功获取股票基本信息")
                    return result
            except Exception as e:
                print(f"[Tushare] 获取失败: {e}")
        
        # 2. 备选使用Akshare
        if self.akshare_available:
            try:
                print(f"[Akshare] 正在获取股票基本信息（备选）...")
                df = self._make_akshare_request('stock_individual_info_em', symbol=symbol)
                
                if df is not None and not df.empty:
                    row = df.iloc[0]
                    result = {
                        'symbol': symbol,
                        'name': row.get('股票简称', ''),
                        'area': row.get('所属地域', ''),
                        'industry': row.get('所属行业', ''),
                        'market': 'A股',
                        'list_date': '',
                        'data_source': 'Akshare'
                    }
                    print(f"[Akshare] 成功获取股票基本信息")
                    return result
            except Exception as e:
                print(f"[Akshare] 获取失败: {e}")
        
        raise Exception("所有数据源都获取失败")
    
    def get_stock_daily_data(self, symbol: str, start_date: str = None, end_date: str = None, 
                           limit: int = 100) -> pd.DataFrame:
        """获取股票日线数据"""
        print(f"[统一API] 获取股票日线数据: {symbol}")
        
        if not start_date:
            start_date = (datetime.now() - timedelta(days=limit)).strftime('%Y%m%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')
        
        # 1. 优先使用Tushare
        if self.tushare_available:
            try:
                print(f"[Tushare] 正在获取股票日线数据（直连）...")
                ts_code = self._convert_to_ts_code(symbol)
                
                df = self._make_tushare_request(
                    self.tushare_api.daily,
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date
                )
                
                if df is not None and not df.empty:
                    # 标准化列名
                    df = df.rename(columns={
                        'ts_code': 'symbol',
                        'trade_date': 'date',
                        'close': 'close',
                        'open': 'open',
                        'high': 'high',
                        'low': 'low',
                        'vol': 'volume',
                        'amount': 'amount',
                        'pct_chg': 'pct_chg'
                    })
                    df['data_source'] = 'Tushare'
                    print(f"[Tushare] 成功获取 {len(df)} 条日线数据")
                    return df
            except Exception as e:
                print(f"[Tushare] 获取失败: {e}")
        
        # 2. 备选使用Akshare
        if self.akshare_available:
            try:
                print(f"[Akshare] 正在获取股票日线数据（备选）...")
                df = self._make_akshare_request(
                    'stock_zh_a_hist',
                    symbol=symbol,
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq"
                )
                
                if df is not None and not df.empty:
                    df['data_source'] = 'Akshare'
                    print(f"[Akshare] 成功获取 {len(df)} 条日线数据")
                    return df
            except Exception as e:
                print(f"[Akshare] 获取失败: {e}")
        
        raise Exception("所有数据源都获取失败")
    
    def get_stock_realtime_quotes(self, symbol: str) -> Dict[str, Any]:
        """获取股票实时行情"""
        print(f"[统一API] 获取股票实时行情: {symbol}")
        
        # 1. 优先使用Tushare（当日无数据时回退最近可用交易日）
        if self.tushare_available:
            try:
                print(f"[Tushare] 正在获取实时行情（直连）...")
                ts_code = self._convert_to_ts_code(symbol)
                from datetime import timedelta
                base_date = datetime.now()
                fields = 'ts_code,trade_date,close,turnover_rate,pe,pb,total_mv,circ_mv'
                for i in range(0, 6):
                    try_date = (base_date - timedelta(days=i)).strftime('%Y%m%d')
                    df = self._make_tushare_request(
                        self.tushare_api.daily_basic,
                        ts_code=ts_code,
                        trade_date=try_date,
                        fields=fields
                    )
                    if df is not None and not df.empty:
                        row = df.iloc[0]
                        result = {
                            'symbol': symbol,
                            'price': row.get('close', 0),
                            'turnover_rate': row.get('turnover_rate', 0),
                            'pe_ratio': row.get('pe', 0),
                            'pb_ratio': row.get('pb', 0),
                            'total_mv': row.get('total_mv', 0),
                            'circ_mv': row.get('circ_mv', 0),
                            'trade_date': row.get('trade_date', try_date),
                            'data_source': 'Tushare'
                        }
                        print(f"[Tushare] 成功获取实时行情（交易日: {try_date}）")
                        return result
            except Exception as e:
                print(f"[Tushare] 获取失败: {e}")
        
        # 2. 备选使用Akshare
        if self.akshare_available:
            try:
                print(f"[Akshare] 正在获取实时行情（备选）...")
                df = self._make_akshare_request('stock_zh_a_spot_em')
                
                if df is not None and not df.empty:
                    stock_df = df[df['代码'] == symbol]
                    if not stock_df.empty:
                        row = stock_df.iloc[0]
                        result = {
                            'symbol': symbol,
                            'price': row.get('最新价', 0),
                            'change_percent': row.get('涨跌幅', 0),
                            'volume': row.get('成交量', 0),
                            'amount': row.get('成交额', 0),
                            'high': row.get('最高', 0),
                            'low': row.get('最低', 0),
                            'open': row.get('今开', 0),
                            'pre_close': row.get('昨收', 0),
                            'data_source': 'Akshare'
                        }
                        print(f"[Akshare] 成功获取实时行情")
                        return result
            except Exception as e:
                print(f"[Akshare] 获取失败: {e}")
        
        raise Exception("所有数据源都获取失败")
    
    def get_fund_flow_data(self, symbol: str, days: int = 20) -> Dict[str, Any]:
        """获取资金流向数据（moneyflow_ths -> moneyflow_dc -> moneyflow -> Akshare）"""
        print(f"[统一API] 获取资金流向数据: {symbol}")
        
        def _build_result(df: Optional[pd.DataFrame], source_label: str) -> Optional[Dict[str, Any]]:
            """标准化资金流向数据结构"""
            if df is None or df.empty:
                return None
            # 按日期排序，确保顺序正确
            if 'trade_date' in df.columns:
                df = df.sort_values('trade_date')
            # 取最近N个交易日
            df = df.tail(days)
            if 'trade_date' in df.columns:
                df = df.sort_values('trade_date')
            records = df.to_dict('records')
            if not records:
                return None
            return {
                'symbol': symbol,
                'data': records,
                'data_success': True,
                'data_period': f"最近{len(records)}个交易日",
                'data_source': source_label
            }
        
        # 统一的日期区间（适当扩大以避免节假日）
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days * 3)).strftime('%Y%m%d')
        ts_code = self._convert_to_ts_code(symbol)
        
        # 1. 优先 moneyflow_ths（同花顺深度资金数据）
        if self.tushare_available:
            try:
                print(f"[Tushare] moneyflow_ths 获取资金流向数据（THS数据）...")
                df = self._make_tushare_request(
                    self.tushare_api.moneyflow_ths,
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date
                )
                result = _build_result(df, 'Tushare_moneyflow_ths')
                if result:
                    print(f"[Tushare] 成功获取 {len(result['data'])} 条资金流向数据（moneyflow_ths）")
                    return result
                else:
                    print("[Tushare] moneyflow_ths 返回空数据")
            except Exception as e:
                print(f"[Tushare] moneyflow_ths接口获取失败: {e}")
        
        # 2. 次优 moneyflow_dc（东财版资金流向，单次6000条）
        if self.tushare_available:
            try:
                print(f"[Tushare] moneyflow_dc 获取资金流向数据（东财数据）...")
                df = self._make_tushare_request(
                    self.tushare_api.moneyflow_dc,
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date
                )
                result = _build_result(df, 'Tushare_moneyflow_dc')
                if result:
                    print(f"[Tushare] 成功获取 {len(result['data'])} 条资金流向数据（moneyflow_dc）")
                    return result
                else:
                    print("[Tushare] moneyflow_dc 返回空数据")
            except Exception as e:
                print(f"[Tushare] moneyflow_dc接口获取失败: {e}")
        
        # 3. 兜底 moneyflow（标准资金流向数据）
        if self.tushare_available:
            try:
                print(f"[Tushare] moneyflow 获取资金流向数据（标准数据）...")
                df = self._make_tushare_request(
                    self.tushare_api.moneyflow,
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date
                )
                result = _build_result(df, 'Tushare_moneyflow')
                if result:
                    print(f"[Tushare] 成功获取 {len(result['data'])} 条资金流向数据（moneyflow）")
                    return result
                else:
                    print("[Tushare] moneyflow 返回空数据")
            except Exception as e:
                print(f"[Tushare] moneyflow接口获取失败: {e}")
        
        # 4. 最后备选使用Akshare（仅在Tushare无数据时）
        if self.akshare_available:
            try:
                print(f"[Akshare] 正在获取资金流向数据（最后备选）...")
                
                # 判断市场
                market = "sz" if symbol.startswith(('00', '30')) else "sh"
                
                df = self._make_akshare_request(
                    'stock_individual_fund_flow',
                    stock=symbol,
                    market=market
                )
                
                if df is not None and not df.empty:
                    # 取最近N天数据
                    df = df.tail(days)
                    
                    result = {
                        'symbol': symbol,
                        'data': df.to_dict('records'),
                        'data_success': True,
                        'data_period': f"最近{days}个交易日",
                        'data_source': 'Akshare'
                    }
                    print(f"[Akshare] 成功获取 {len(df)} 条资金流向数据")
                    return result
            except Exception as e:
                print(f"[Akshare] 获取失败: {e}")
        
        raise Exception("所有数据源都获取失败")
    
    def get_market_sentiment_data(self, symbol: str) -> Dict[str, Any]:
        """获取市场情绪数据"""
        print(f"[统一API] 获取市场情绪数据: {symbol}")
        
        result = {
            'symbol': symbol,
            'data_success': False,
            'data_source': 'None'
        }
        
        # 1. 优先使用Tushare获取大盘指数（支持日期回退，避免当日空数据）
        if self.tushare_available:
            try:
                print(f"[Tushare] 正在获取市场情绪数据（直连）...")
                
                # 使用日期区间，取最近可用一日，避免当日未更新导致空数据
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=7)).strftime('%Y%m%d')
                index_df = self._make_tushare_request(
                    self.tushare_api.index_daily,
                    ts_code='000001.SH',  # 上证指数
                    start_date=start_date,
                    end_date=end_date
                )
                
                if index_df is not None and not index_df.empty:
                    # 取最后一行作为最近交易日
                    row = index_df.sort_values('trade_date').iloc[-1]
                    result['market_index'] = {
                        'index_name': '上证指数',
                        'close': row.get('close', 0),
                        'pct_chg': row.get('pct_chg', 0),
                        'data_source': 'Tushare'
                    }
                    result['data_success'] = True
                    result['data_source'] = 'Tushare'
                    print(f"[Tushare] 成功获取市场情绪数据")
                    return result
            except Exception as e:
                print(f"[Tushare] 获取失败: {e}")
        
        # 2. 备选使用Akshare
        if self.akshare_available:
            try:
                print(f"[Akshare] 正在获取市场情绪数据（备选）...")
                
                df = self._make_akshare_request('stock_zh_a_spot_em')
                
                if df is not None and not df.empty:
                    # 获取上证指数
                    sh_index = df[df['代码'] == '000001']
                    if not sh_index.empty:
                        row = sh_index.iloc[0]
                        result['market_index'] = {
                            'index_name': '上证指数',
                            'close': row.get('最新价', 0),
                            'pct_chg': row.get('涨跌幅', 0),
                            'data_source': 'Akshare'
                        }
                        result['data_success'] = True
                        result['data_source'] = 'Akshare'
                        print(f"[Akshare] 成功获取市场情绪数据")
                        return result
            except Exception as e:
                print(f"[Akshare] 获取失败: {e}")
        
        return result
    
    def get_etf_data(self, symbol: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """获取ETF数据"""
        print(f"[统一API] 获取ETF数据: {symbol}")
        
        if not start_date:
            start_date = (datetime.now() - timedelta(days=100)).strftime('%Y%m%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')
        
        # 1. 优先使用Tushare
        if self.tushare_available:
            try:
                print(f"[Tushare] 正在获取ETF数据（直连）...")
                ts_code = self._convert_to_ts_code(symbol)
                
                df = self._make_tushare_request(
                    self.tushare_api.fund_daily,
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date
                )
                
                if df is not None and not df.empty:
                    df['data_source'] = 'Tushare'
                    print(f"[Tushare] 成功获取 {len(df)} 条ETF数据")
                    return df
            except Exception as e:
                print(f"[Tushare] 获取失败: {e}")
        
        # 2. 备选使用Akshare
        if self.akshare_available:
            try:
                print(f"[Akshare] 正在获取ETF数据（备选）...")
                # akshare 需要带市场前缀，如 sh510300 / sz159915
                symbol_prefixed = (
                    f"sh{symbol}" if symbol.startswith(('51', '56', '58')) else
                    (f"sz{symbol}" if symbol.startswith(('15', '16')) else symbol)
                )
                df = self._make_akshare_request('fund_etf_hist_sina', symbol=symbol_prefixed)
                
                if df is not None and not df.empty:
                    df['data_source'] = 'Akshare'
                    print(f"[Akshare] 成功获取 {len(df)} 条ETF数据")
                    return df
            except Exception as e:
                print(f"[Akshare] 获取失败: {e}")
        
        raise Exception("所有数据源都获取失败")
    
    def get_beta_coefficient(self, symbol: str, index_code: str = '000300.SH', days: int = 250) -> float:
        """
        计算股票Beta系数
        
        Args:
            symbol: 股票代码
            index_code: 参考指数代码（默认沪深300）
            days: 回溯天数（默认250个交易日，约1年）
            
        Returns:
            float: Beta系数（如果计算失败返回None）
        """
        print(f"[统一API] 计算Beta系数: {symbol} vs {index_code}")
        
        if not self.tushare_available:
            print("[WARNING] Tushare不可用，无法计算Beta系数")
            return None
        
        try:
            import numpy as np
            
            # 计算日期范围
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days * 2)).strftime('%Y%m%d')  # 多获取一些以确保足够的数据
            
            ts_code = self._convert_to_ts_code(symbol)
            
            # 获取股票日线数据
            print(f"[Tushare] 获取股票日线数据...")
            df_stock = self._make_tushare_request(
                self.tushare_api.daily,
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                fields='ts_code,trade_date,close,pct_chg'
            )
            
            # 获取指数日线数据
            print(f"[Tushare] 获取指数日线数据...")
            df_index = self._make_tushare_request(
                self.tushare_api.index_daily,
                ts_code=index_code,
                start_date=start_date,
                end_date=end_date,
                fields='ts_code,trade_date,close,pct_chg'
            )
            
            if df_stock is None or df_stock.empty or df_index is None or df_index.empty:
                print("[ERROR] 数据获取失败")
                return None
            
            # 排序并取最近N天
            df_stock = df_stock.sort_values('trade_date').tail(days)
            df_index = df_index.sort_values('trade_date').tail(days)
            
            print(f"[OK] 股票数据: {len(df_stock)} 条, 指数数据: {len(df_index)} 条")
            
            # 计算Beta
            stock_returns = df_stock['pct_chg'].values
            index_returns = df_index['pct_chg'].values
            
            # 确保长度一致
            min_len = min(len(stock_returns), len(index_returns))
            if min_len < 50:  # 至少需要50个交易日的数据
                print(f"[WARNING] 数据不足({min_len}条)，建议至少50个交易日")
                return None
            
            stock_returns = stock_returns[-min_len:]
            index_returns = index_returns[-min_len:]
            
            # 计算协方差和方差
            covariance = np.cov(stock_returns, index_returns)[0][1]
            variance = np.var(index_returns)
            
            if variance == 0:
                print("[ERROR] 指数方差为0，无法计算Beta")
                return None
            
            beta = covariance / variance
            
            print(f"[OK] Beta系数 = {beta:.4f}")
            return beta
            
        except Exception as e:
            print(f"[ERROR] Beta系数计算失败: {e}")
            return None
    
    def get_52week_high_low(self, symbol: str) -> Dict[str, Any]:
        """
        获取52周高低位数据
        
        Args:
            symbol: 股票代码
            
        Returns:
            dict: 包含52周高低位信息
        """
        print(f"[统一API] 获取52周高低位: {symbol}")
        
        result = {
            'success': False,
            'high_52w': None,
            'low_52w': None,
            'high_date': None,
            'low_date': None,
            'current_price': None,
            'position_percent': None,  # 当前价格在52周区间的位置（0-100%）
        }
        
        if not self.tushare_available:
            print("[WARNING] Tushare不可用，无法获取52周高低位")
            return result
        
        try:
            # 获取过去52周（约365天）的数据
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
            
            ts_code = self._convert_to_ts_code(symbol)
            
            print(f"[Tushare] 获取日线数据...")
            df = self._make_tushare_request(
                self.tushare_api.daily,
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                fields='ts_code,trade_date,close,high,low'
            )
            
            if df is None or df.empty:
                print("[ERROR] 数据获取失败")
                return result
            
            print(f"[OK] 获取 {len(df)} 个交易日数据")
            
            # 计算52周高低位
            high_52w = df['high'].max()
            low_52w = df['low'].min()
            current_price = df.iloc[0]['close']  # 最新收盘价（已按日期排序，第一条是最新的）
            
            # 找到高低位的日期
            high_date = df[df['high'] == high_52w].iloc[0]['trade_date']
            low_date = df[df['low'] == low_52w].iloc[0]['trade_date']
            
            # 计算当前价格相对位置
            price_range = high_52w - low_52w
            if price_range > 0:
                position = (current_price - low_52w) / price_range * 100
            else:
                position = 50.0  # 如果区间为0，默认50%
            
            result['success'] = True
            result['high_52w'] = high_52w
            result['low_52w'] = low_52w
            result['high_date'] = high_date
            result['low_date'] = low_date
            result['current_price'] = current_price
            result['position_percent'] = position
            
            print(f"[OK] 52周高: {high_52w:.2f}, 52周低: {low_52w:.2f}, 当前: {current_price:.2f}, 位置: {position:.1f}%")
            
            return result
            
        except Exception as e:
            print(f"[ERROR] 52周高低位获取失败: {e}")
            return result
    
    def get_hsgt_capital_flow(self, symbol: str = None, trade_date: str = None) -> Dict[str, Any]:
        """
        获取沪深港通资金流向数据（北向/南向资金）
        
        Args:
            symbol: 股票代码（可选，如果指定则返回该股票的北向持仓）
            trade_date: 交易日期（可选，默认最近交易日）
            
        Returns:
            dict: 北向资金数据
        """
        print(f"[统一API] 获取沪深港通资金流向")
        
        result = {
            'success': False,
            'trade_date': None,
            'data': None,
            'data_type': None,  # 'summary' 或 'top10'
        }
        
        if not self.tushare_available:
            print("[WARNING] Tushare不可用，无法获取北向资金数据")
            return result
        
        try:
            # 如果没有指定日期，尝试最近10个交易日
            if not trade_date:
                for i in range(10):
                    test_date = (datetime.now() - timedelta(days=i)).strftime('%Y%m%d')
                    
                    # 尝试获取hsgt_top10数据（19点后可用当天数据）
                    try:
                        df = self._make_tushare_request(
                            self.tushare_api.hsgt_top10,
                            trade_date=test_date,
                            market_type='1'  # 1=沪股通, 3=深股通
                        )
                        
                        if df is not None and not df.empty:
                            print(f"[OK] 获取到{test_date}的北向资金Top10数据")
                            result['success'] = True
                            result['trade_date'] = test_date
                            result['data'] = df
                            result['data_type'] = 'top10'
                            return result
                    except Exception:
                        continue
                
                print("[INFO] 未找到最近的北向资金数据")
                return result
            else:
                # 指定日期查询
                df = self._make_tushare_request(
                    self.tushare_api.hsgt_top10,
                    trade_date=trade_date,
                    market_type='1'
                )
                
                if df is not None and not df.empty:
                    print(f"[OK] 获取到{trade_date}的北向资金数据")
                    result['success'] = True
                    result['trade_date'] = trade_date
                    result['data'] = df
                    result['data_type'] = 'top10'
                    return result
                else:
                    print(f"[INFO] {trade_date}无北向资金数据")
                    return result
            
        except Exception as e:
            print(f"[ERROR] 北向资金获取失败: {e}")
            return result
    
    def get_margin_detail(self, symbol: str, days: int = 30) -> Dict[str, Any]:
        """
        获取融资融券明细数据
        
        Args:
            symbol: 股票代码
            days: 回溯天数（默认30天）
            
        Returns:
            dict: 融资融券数据
        """
        print(f"[统一API] 获取融资融券数据: {symbol}")
        
        result = {
            'success': False,
            'symbol': symbol,
            'data': None,
            'latest': None,
        }
        
        if not self.tushare_available:
            print("[WARNING] Tushare不可用，无法获取融资融券数据")
            return result
        
        try:
            ts_code = self._convert_to_ts_code(symbol)
            exchange_id = 'SSE' if ts_code.endswith('.SH') else 'SZSE'
            
            print(f"[Tushare] 获取融资融券数据（margin_detail）...")
            frames: List[pd.DataFrame] = []
            collected_dates = set()
            max_query_days = max(days * 3, 30)
            
            for offset in range(max_query_days):
                trade_date = (datetime.now() - timedelta(days=offset)).strftime('%Y%m%d')
                try:
                    df = self._make_tushare_request(
                        self.tushare_api.margin_detail,
                        ts_code=ts_code,
                        trade_date=trade_date,
                        exchange_id=exchange_id
                    )
                except Exception as e:
                    print(f"[Tushare] margin_detail({trade_date}) 调用失败: {e}")
                    continue
                
                if df is not None and not df.empty:
                    frames.append(df)
                    collected_dates.update(df['trade_date'].astype(str).tolist())
                    print(f"[Tushare] 获取到 {trade_date} 的融资融券数据 {len(df)} 条")
                    if len(collected_dates) >= days:
                        break
            
            if not frames:
                print("[INFO] 未获取到融资融券数据（可能不是融资融券标的或数据未更新）")
                return result
            
            df = pd.concat(frames, ignore_index=True)
            df['trade_date'] = df['trade_date'].astype(str)
            df = df.drop_duplicates(subset=['trade_date']).sort_values('trade_date', ascending=False)
            df = df.head(days)
            
            latest = df.iloc[0]
            
            result['success'] = True
            result['data'] = df
            result['latest'] = {
                'trade_date': latest.get('trade_date'),
                'rzye': latest.get('rzye', 0),
                'rqye': latest.get('rqye', 0),
                'rzmre': latest.get('rzmre', 0),
                'rzche': latest.get('rzche', 0),
                'rqmcl': latest.get('rqmcl', 0),
                'rqchl': latest.get('rqchl', 0),
                'rzrqye': latest.get('rzrqye', 0),
                'net_buy': (latest.get('rzmre', 0) or 0) - (latest.get('rzche', 0) or 0),
            }
            
            print(f"[OK] 共获取 {len(df)} 个交易日的融资融券数据，最新日期: {result['latest']['trade_date']}")
            print(f"[OK] 最新融资余额: {result['latest']['rzye']/1e8:.2f}亿元")
            print(f"[OK] 融资净买入: {result['latest']['net_buy']/1e8:.2f}亿元")
            
            return result
            
        except Exception as e:
            print(f"[ERROR] 融资融券数据获取失败: {e}")
            return result
    
    def get_sector_fund_flow(self, symbol: str) -> Dict[str, Any]:
        """
        获取股票所属板块/行业的资金流向数据
        
        Args:
            symbol: 股票代码
            
        Returns:
            dict: 板块/行业资金流向数据
        """
        print(f"[统一API] 获取板块/行业资金流向: {symbol}")
        
        result = {
            'success': False,
            'symbol': symbol,
            'sector_name': None,
            'sector_data': None,  # 板块数据
            'industry_data': None,  # 行业数据
        }
        
        if not self.tushare_available:
            print("[WARNING] Tushare不可用，无法获取板块资金流向")
            return result
        
        try:
            # 步骤1: 获取股票所属行业
            print(f"[Tushare] 获取股票基本信息...")
            ts_code = self._convert_to_ts_code(symbol)
            
            df_basic = self._make_tushare_request(
                self.tushare_api.stock_basic,
                ts_code=ts_code,
                fields='ts_code,name,industry'
            )
            
            if df_basic is None or df_basic.empty:
                print("[INFO] 无法获取股票行业信息")
                return result
            
            industry = df_basic.iloc[0]['industry']
            result['sector_name'] = industry
            print(f"[OK] 所属行业: {industry}")
            
            # 步骤2: 获取行业资金流向（Tushare moneyflow_ind_ths）
            print(f"[Tushare] 获取行业资金流向（moneyflow_ind_ths接口）...")
            
            try:
                # 尝试获取今天的数据
                trade_date = datetime.now().strftime('%Y%m%d')
                df_ind = self._make_tushare_request(
                    self.tushare_api.moneyflow_ind_ths,
                    trade_date=trade_date
                )
                
                # 如果今天数据未更新，尝试前一天
                if df_ind is None or df_ind.empty:
                    print(f"[INFO] 今日数据未更新，尝试前一交易日...")
                    trade_date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
                    df_ind = self._make_tushare_request(
                        self.tushare_api.moneyflow_ind_ths,
                        trade_date=trade_date
                    )
                
                if df_ind is not None and not df_ind.empty:
                    print(f"[OK] 获取 {len(df_ind)} 个行业数据")
                    
                    # 查找匹配的行业
                    matched = df_ind[df_ind['industry'].str.contains(industry, na=False)]
                    
                    if not matched.empty:
                        result['success'] = True
                        result['industry_data'] = matched.iloc[0].to_dict()
                        print(f"[OK] 找到{industry}行业资金流向数据")
                        print(f"    净额: {result['industry_data']['net_amount']}亿元")
                        return result
                    else:
                        print(f"[INFO] 未找到{industry}行业的精确匹配")
                        # 返回所有行业数据供参考
                        result['success'] = True
                        result['industry_data'] = df_ind.to_dict('records')
                        print(f"[OK] 返回所有行业资金流向数据")
                        return result
                else:
                    print(f"[INFO] Tushare行业资金流向数据未更新")
                    
            except Exception as e:
                print(f"[ERROR] Tushare行业资金流向获取失败: {e}")
            
            # 步骤3: 尝试获取板块资金流向（Tushare moneyflow_cnt_ths）
            print(f"[Tushare] 获取板块资金流向（moneyflow_cnt_ths接口）...")
            
            try:
                trade_date = datetime.now().strftime('%Y%m%d')
                df_cnt = self._make_tushare_request(
                    self.tushare_api.moneyflow_cnt_ths,
                    trade_date=trade_date
                )
                
                if df_cnt is None or df_cnt.empty:
                    trade_date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
                    df_cnt = self._make_tushare_request(
                        self.tushare_api.moneyflow_cnt_ths,
                        trade_date=trade_date
                    )
                
                if df_cnt is not None and not df_cnt.empty:
                    print(f"[OK] 获取 {len(df_cnt)} 个板块数据")
                    result['success'] = True
                    result['sector_data'] = df_cnt.to_dict('records')
                    return result
                    
            except Exception as e:
                print(f"[ERROR] Tushare板块资金流向获取失败: {e}")
            
            return result
            
        except Exception as e:
            print(f"[ERROR] 板块资金流向获取失败: {e}")
            return result

# 创建全局实例
unified_data_api = UnifiedDataAPI()

# 导出主要函数
def get_stock_basic_info(symbol: str) -> Dict[str, Any]:
    """获取股票基本信息"""
    return unified_data_api.get_stock_basic_info(symbol)

def get_stock_daily_data(symbol: str, start_date: str = None, end_date: str = None, limit: int = 100) -> pd.DataFrame:
    """获取股票日线数据"""
    return unified_data_api.get_stock_daily_data(symbol, start_date, end_date, limit)

def get_stock_realtime_quotes(symbol: str) -> Dict[str, Any]:
    """获取股票实时行情"""
    return unified_data_api.get_stock_realtime_quotes(symbol)

def get_fund_flow_data(symbol: str, days: int = 20) -> Dict[str, Any]:
    """获取资金流向数据"""
    return unified_data_api.get_fund_flow_data(symbol, days)

def get_market_sentiment_data(symbol: str) -> Dict[str, Any]:
    """获取市场情绪数据"""
    return unified_data_api.get_market_sentiment_data(symbol)

def get_etf_data(symbol: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """获取ETF数据"""
    return unified_data_api.get_etf_data(symbol, start_date, end_date)

def get_beta_coefficient(symbol: str, index_code: str = '000300.SH', days: int = 250) -> float:
    """计算股票Beta系数"""
    return unified_data_api.get_beta_coefficient(symbol, index_code, days)

def get_52week_high_low(symbol: str) -> Dict[str, Any]:
    """获取52周高低位数据"""
    return unified_data_api.get_52week_high_low(symbol)

def get_hsgt_capital_flow(symbol: str = None, trade_date: str = None) -> Dict[str, Any]:
    """获取沪深港通资金流向数据"""
    return unified_data_api.get_hsgt_capital_flow(symbol, trade_date)

def get_margin_detail(symbol: str, days: int = 30) -> Dict[str, Any]:
    """获取融资融券明细数据"""
    return unified_data_api.get_margin_detail(symbol, days)

def get_sector_fund_flow(symbol: str) -> Dict[str, Any]:
    """获取股票所属板块的资金流向数据"""
    return unified_data_api.get_sector_fund_flow(symbol)


# ========== 辅助函数 ==========

def get_fund_flow_days_count(fund_flow_result: Dict[str, Any]) -> int:
    """
    从资金流向结果中获取实际数据天数
    
    用途：统一处理资金流向数据结构，避免各模块重复实现相同逻辑
    支持两种数据结构：
    1. 直接返回：{'data': [...], 'data_success': True}
    2. 嵌套返回：{'fund_flow_data': {'data': [...]}, 'data_success': True}
    
    Args:
        fund_flow_result: get_fund_flow_data() 的返回结果
        
    Returns:
        int: 实际获取的交易日数量
        
    示例：
        >>> result = get_fund_flow_data('000001')
        >>> days = get_fund_flow_days_count(result)
        >>> print(f"成功获取 {days} 个交易日的数据")
    """
    if not fund_flow_result or not fund_flow_result.get('data_success'):
        return 0
    
    # 方式1: 检查顶层是否直接有data（统一API直接返回）
    if 'data' in fund_flow_result:
        data_list = fund_flow_result.get('data', [])
        return len(data_list) if data_list else 0
    
    # 方式2: 从嵌套的fund_flow_data中获取data列表（Fetcher类返回）
    inner_data = fund_flow_result.get('fund_flow_data', {})
    if inner_data and isinstance(inner_data, dict):
        data_list = inner_data.get('data', [])
        return len(data_list) if data_list else 0
    
    return 0


def get_fund_flow_data_source(fund_flow_result: Dict[str, Any]) -> str:
    """
    从资金流向结果中获取真实数据源
    
    支持两种数据结构：
    1. 直接返回：{'data_source': 'Tushare_moneyflow', ...}
    2. 嵌套返回：{'fund_flow_data': {'data_source': 'Tushare_moneyflow'}, ...}
    
    Args:
        fund_flow_result: get_fund_flow_data() 的返回结果
        
    Returns:
        str: 数据源名称（如 'Tushare_moneyflow', 'Akshare'）
    """
    if not fund_flow_result or not fund_flow_result.get('data_success'):
        return 'Unknown'
    
    # 方式1: 检查顶层是否直接有data_source（统一API直接返回）
    if 'data_source' in fund_flow_result:
        return fund_flow_result['data_source']
    
    # 方式2: 从嵌套的fund_flow_data中获取data_source（Fetcher类返回）
    inner_data = fund_flow_result.get('fund_flow_data', {})
    if inner_data and isinstance(inner_data, dict) and 'data_source' in inner_data:
        return inner_data['data_source']
    
    # 兜底：从外层的source字段获取
    return fund_flow_result.get('source', 'Unknown')
