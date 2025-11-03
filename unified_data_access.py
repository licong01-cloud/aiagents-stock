from typing import Optional, Dict, Any
import time as time_module
import pandas as pd
from datetime import datetime, timedelta, time

from data_source_manager import data_source_manager
from network_optimizer import network_optimizer
from debug_logger import debug_logger


class UnifiedDataAccess:
    """
    统一数据访问模块（首页用）
    - 直接代理 data_source_manager 能力
    - 对现有专用模块做兜底封装（A股为主）
    - 预留研报/公告/筹码等接口（先返回占位结构，后续由数据源补齐）
    """

    def __init__(self):
        """初始化统一数据访问模块"""
        # 导入StockDataFetcher以兼容旧代码（用于计算技术指标）
        from stock_data import StockDataFetcher
        self.stock_data_fetcher = StockDataFetcher()

    # 基础代理：直接走数据源管理器
    def get_stock_hist_data(self, symbol: str, start_date: Optional[str] = None,
                            end_date: Optional[str] = None, adjust: str = 'qfq'):
        return data_source_manager.get_stock_hist_data(symbol, start_date, end_date, adjust)

    def get_stock_basic_info(self, symbol: str) -> Dict[str, Any]:
        return data_source_manager.get_stock_basic_info(symbol)
    
    def get_stock_info(self, symbol: str) -> Dict[str, Any]:
        """获取股票完整信息（包含基本信息、实时行情、估值指标等）"""
        debug_logger.info("get_stock_info开始", symbol=symbol, method="get_stock_info")
        
        # 获取基本信息
        info = self.get_stock_basic_info(symbol)
        if not info:
            info = {
                "symbol": symbol,
                "name": "未知",
                "industry": "未知",
                "market": "未知"
            }
        
        # 初始化估值和行情字段
        info.setdefault('current_price', 'N/A')
        info.setdefault('change_percent', 'N/A')
        info.setdefault('pe_ratio', 'N/A')
        info.setdefault('pb_ratio', 'N/A')
        info.setdefault('market_cap', 'N/A')
        info.setdefault('dividend_yield', 'N/A')
        info.setdefault('ps_ratio', 'N/A')
        info.setdefault('beta', 'N/A')
        info.setdefault('52_week_high', 'N/A')
        info.setdefault('52_week_low', 'N/A')
        
        # 优先使用Tushare获取实时行情和估值数据
        if data_source_manager.tushare_available:
            try:
                debug_logger.debug("尝试从Tushare获取实时行情和估值", symbol=symbol)
                ts_code = data_source_manager._convert_to_ts_code(symbol)
                
                # 根据日期和时间判断，获取合适的交易日
                trade_date = self._get_appropriate_trade_date()
                debug_logger.debug("选择的交易日", trade_date=trade_date, symbol=symbol)
                
                try:
                    # 获取daily_basic（包含市盈率、市净率、市值等）
                    with network_optimizer.apply():
                        daily_basic = data_source_manager.tushare_api.daily_basic(
                            ts_code=ts_code,
                            trade_date=trade_date
                        )
                    
                    if daily_basic is not None and not daily_basic.empty:
                        row = daily_basic.iloc[0]
                        
                        # 市盈率、市净率、市值
                        if row.get('pe') and pd.notna(row.get('pe')) and row.get('pe') > 0:
                            info['pe_ratio'] = round(float(row['pe']), 2)
                        if row.get('pb') and pd.notna(row.get('pb')) and row.get('pb') > 0:
                            info['pb_ratio'] = round(float(row['pb']), 2)
                        if row.get('total_mv') and pd.notna(row.get('total_mv')):
                            info['market_cap'] = float(row['total_mv']) * 10000  # Tushare单位：万元，转换为元
                        
                        debug_logger.debug("Tushare获取daily_basic成功", 
                                         symbol=symbol,
                                         trade_date=trade_date,
                                         pe=info.get('pe_ratio'),
                                         pb=info.get('pb_ratio'))
                        
                        # 获取daily数据（当前价格、涨跌幅）
                        with network_optimizer.apply():
                            daily = data_source_manager.tushare_api.daily(
                                ts_code=ts_code,
                                start_date=trade_date,
                                end_date=trade_date
                            )
                        
                        if daily is not None and not daily.empty:
                            daily_row = daily.iloc[0]
                            info['current_price'] = round(float(daily_row['close']), 2)
                            info['change_percent'] = round(float(daily_row['pct_chg']), 2)
                            
                            debug_logger.debug("Tushare获取daily成功",
                                             symbol=symbol,
                                             trade_date=trade_date,
                                             price=info.get('current_price'),
                                             change_pct=info.get('change_percent'))
                        else:
                            # 如果当日数据不可用，尝试回退到最近几个交易日
                            debug_logger.debug("当日数据不可用，尝试回退查找", trade_date=trade_date)
                            for days_back in range(1, 5):
                                fallback_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y%m%d')
                                try:
                                    with network_optimizer.apply():
                                        daily = data_source_manager.tushare_api.daily(
                                            ts_code=ts_code,
                                            start_date=fallback_date,
                                            end_date=fallback_date
                                        )
                                    if daily is not None and not daily.empty:
                                        daily_row = daily.iloc[0]
                                        info['current_price'] = round(float(daily_row['close']), 2)
                                        info['change_percent'] = round(float(daily_row['pct_chg']), 2)
                                        debug_logger.debug("回退获取数据成功",
                                                         symbol=symbol,
                                                         fallback_date=fallback_date,
                                                         price=info.get('current_price'))
                                        break
                                except Exception as e:
                                    debug_logger.debug(f"回退获取{fallback_date}数据失败", error=str(e))
                                    continue
                                
                except Exception as e:
                    debug_logger.warning(f"Tushare获取{trade_date}数据失败，尝试回退", error=str(e), symbol=symbol)
                    # 如果选择的交易日数据获取失败，回退到最近几个交易日
                    for days_back in range(1, 5):
                        fallback_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y%m%d')
                        try:
                            with network_optimizer.apply():
                                daily_basic = data_source_manager.tushare_api.daily_basic(
                                    ts_code=ts_code,
                                    trade_date=fallback_date
                                )
                            if daily_basic is not None and not daily_basic.empty:
                                row = daily_basic.iloc[0]
                                if row.get('pe') and pd.notna(row.get('pe')) and row.get('pe') > 0:
                                    info['pe_ratio'] = round(float(row['pe']), 2)
                                if row.get('pb') and pd.notna(row.get('pb')) and row.get('pb') > 0:
                                    info['pb_ratio'] = round(float(row['pb']), 2)
                                if row.get('total_mv') and pd.notna(row.get('total_mv')):
                                    info['market_cap'] = float(row['total_mv']) * 10000
                                
                                daily = data_source_manager.tushare_api.daily(
                                    ts_code=ts_code,
                                    start_date=fallback_date,
                                    end_date=fallback_date
                                )
                                if daily is not None and not daily.empty:
                                    daily_row = daily.iloc[0]
                                    info['current_price'] = round(float(daily_row['close']), 2)
                                    info['change_percent'] = round(float(daily_row['pct_chg']), 2)
                                debug_logger.debug("回退获取成功", fallback_date=fallback_date, symbol=symbol)
                                break
                        except Exception as e2:
                            debug_logger.debug(f"回退获取{fallback_date}失败", error=str(e2))
                            continue
                        
            except Exception as e:
                debug_logger.warning("Tushare获取实时数据失败", error=e, symbol=symbol)
        
        # Tushare失败或数据不完整，使用Akshare备用
        if info['current_price'] == 'N/A' or info['pe_ratio'] == 'N/A':
            try:
                debug_logger.debug("尝试从Akshare获取详细信息", symbol=symbol)
                with network_optimizer.apply():
                    import akshare as ak
                    stock_info_df = ak.stock_individual_info_em(symbol=symbol)
                    
                    if stock_info_df is not None and not stock_info_df.empty:
                        for _, row in stock_info_df.iterrows():
                            key = row['item']
                            value = row['value']
                            
                            if key == '股票简称' and info['name'] == '未知':
                                info['name'] = value
                            elif key == '总市值':
                                try:
                                    if value and value != '-':
                                        info['market_cap'] = float(value)
                                except:
                                    pass
                            elif key == '市盈率-动态' and info['pe_ratio'] == 'N/A':
                                try:
                                    if value and value != '-':
                                        pe_val = float(value)
                                        if 0 < pe_val <= 1000:
                                            info['pe_ratio'] = pe_val
                                except:
                                    pass
                            elif key == '市净率' and info['pb_ratio'] == 'N/A':
                                try:
                                    if value and value != '-':
                                        pb_val = float(value)
                                        if 0 < pb_val <= 100:
                                            info['pb_ratio'] = pb_val
                                except:
                                    pass
                        
                        debug_logger.debug("Akshare获取详细信息成功", symbol=symbol)
            except Exception as e:
                debug_logger.warning("Akshare获取详细信息失败", error=e, symbol=symbol)
        
        # 如果还是没有当前价格，尝试从实时行情获取
        if info['current_price'] == 'N/A':
            try:
                debug_logger.debug("尝试从实时行情获取价格", symbol=symbol)
                quotes = self.get_realtime_quotes(symbol)
                if quotes and isinstance(quotes, dict):
                    if quotes.get('price'):
                        info['current_price'] = quotes['price']
                    if quotes.get('change_percent'):
                        info['change_percent'] = quotes['change_percent']
                    debug_logger.debug("实时行情获取成功", symbol=symbol)
            except Exception as e:
                debug_logger.debug("实时行情获取失败", error=e, symbol=symbol)
        
        # 如果还是没有，尝试从历史数据获取最新收盘价
        if info['current_price'] == 'N/A':
            try:
                debug_logger.debug("尝试从历史数据获取最新价格", symbol=symbol)
                hist_data = self.get_stock_hist_data(
                    symbol=symbol,
                    start_date=(datetime.now() - timedelta(days=30)).strftime('%Y%m%d'),
                    end_date=datetime.now().strftime('%Y%m%d')
                )
                
                if hist_data is not None and not hist_data.empty and isinstance(hist_data, pd.DataFrame):
                    if 'close' in hist_data.columns:
                        info['current_price'] = round(float(hist_data.iloc[-1]['close']), 2)
                        # 计算涨跌幅
                        if len(hist_data) > 1:
                            prev_close = hist_data.iloc[-2]['close']
                            change_pct = ((hist_data.iloc[-1]['close'] - prev_close) / prev_close) * 100
                            info['change_percent'] = round(change_pct, 2)
                        debug_logger.debug("历史数据获取成功", symbol=symbol)
            except Exception as e:
                debug_logger.debug("历史数据获取失败", error=e, symbol=symbol)
        
        # 获取Beta系数（仅A股，在获取完基本信息后）
        if info.get('beta') == 'N/A' and self._is_chinese_stock(symbol):
            try:
                debug_logger.debug("尝试获取Beta系数", symbol=symbol)
                beta = self.get_beta_coefficient(symbol)
                if beta is not None:
                    info['beta'] = round(float(beta), 4)
                    debug_logger.debug("Beta系数获取成功", symbol=symbol, beta=info['beta'])
            except Exception as e:
                debug_logger.debug("Beta系数获取失败", error=e, symbol=symbol)
        
        # 获取52周高低位（仅A股，在获取完基本信息后）
        if (info.get('52_week_high') == 'N/A' or info.get('52_week_low') == 'N/A') and self._is_chinese_stock(symbol):
            try:
                debug_logger.debug("尝试获取52周高低位", symbol=symbol)
                week52_data = self.get_52week_high_low(symbol)
                if week52_data and week52_data.get('success'):
                    info['52_week_high'] = week52_data.get('high_52w', 'N/A')
                    info['52_week_low'] = week52_data.get('low_52w', 'N/A')
                    debug_logger.debug("52周高低位获取成功", 
                                     symbol=symbol,
                                     high=info.get('52_week_high'),
                                     low=info.get('52_week_low'))
            except Exception as e:
                debug_logger.debug("52周高低位获取失败", error=e, symbol=symbol)
        
        debug_logger.info("get_stock_info完成",
                         symbol=symbol,
                         has_price=(info.get('current_price') != 'N/A'),
                         has_pe=(info.get('pe_ratio') != 'N/A'),
                         has_pb=(info.get('pb_ratio') != 'N/A'),
                         has_beta=(info.get('beta') != 'N/A'),
                         has_52week=(info.get('52_week_high') != 'N/A'))
        
        return info
    
    def get_stock_data(self, symbol: str, period: str = '1y'):
        """获取股票历史数据（别名方法，兼容app.py旧接口）"""
        
        debug_logger.info("UnifiedDataAccess.get_stock_data调用",
                         symbol=symbol,
                         period=period,
                         method="get_stock_data")
        
        # 根据period计算日期范围
        end_date = datetime.now().strftime('%Y%m%d')
        
        period_map = {
            '1mo': 30,
            '3mo': 90,
            '6mo': 180,
            '1y': 365,
            '2y': 730,
            '5y': 1825,
            'max': 3650
        }
        days = period_map.get(period, 365)
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
        
        debug_logger.debug("计算日期范围",
                          start_date=start_date,
                          end_date=end_date,
                          days=days)
        
        result = self.get_stock_hist_data(symbol, start_date, end_date)
        
        debug_logger.data_info("get_stock_hist_data返回", result)
        
        # 处理返回结果
        if result is None:
            debug_logger.warning("get_stock_hist_data返回None", symbol=symbol, period=period)
            return None
        
        # 如果是字典，尝试转换为DataFrame或返回错误
        if isinstance(result, dict):
            # 检查是否是错误响应
            if "error" in result:
                debug_logger.error("数据源返回错误",
                                 error=result.get("error"),
                                 symbol=symbol,
                                 period=period)
                return None
            
            # 尝试将字典转换为DataFrame
            try:
                debug_logger.warning("尝试将dict转换为DataFrame", symbol=symbol, dict_keys=list(result.keys()))
                # 如果是单行数据字典，转换为DataFrame
                if all(not isinstance(v, (list, pd.Series)) for v in result.values()):
                    # 单行数据，转换为单行DataFrame
                    df = pd.DataFrame([result])
                    debug_logger.info("成功将单行dict转换为DataFrame", symbol=symbol, rows=1)
                    return df
                else:
                    # 多行数据字典，尝试直接转换
                    df = pd.DataFrame(result)
                    debug_logger.info("成功将多行dict转换为DataFrame", symbol=symbol, rows=len(df))
                    return df
            except Exception as e:
                debug_logger.error("无法将dict转换为DataFrame",
                                 error=e,
                                 symbol=symbol,
                                 dict_keys=list(result.keys())[:5])
                return None
        
        # 验证返回类型 - 必须是DataFrame
        if not isinstance(result, pd.DataFrame):
            debug_logger.error("get_stock_hist_data返回类型错误",
                             expected_type="DataFrame or None",
                             actual_type=type(result).__name__,
                             symbol=symbol,
                             period=period,
                             result_preview=str(result)[:200])
            return None
        
        # 数据标准化：确保列名正确
        try:
            # 标准化列名（统一为大写）
            column_mapping = {
                'date': 'Date',
                'open': 'Open',
                'high': 'High',
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume',
                'amount': 'Amount'
            }
            
            # 重命名列
            result = result.rename(columns=column_mapping)
            
            # 确保Date列为datetime类型并设置为索引
            if 'Date' in result.columns:
                result['Date'] = pd.to_datetime(result['Date'])
                result = result.set_index('Date')
            elif result.index.name == 'date' or (hasattr(result.index, 'dtype') and 'datetime' in str(result.index.dtype)):
                # 索引已经是日期类型
                result.index.name = 'Date'
            
            # 确保数值列为float类型
            numeric_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            for col in numeric_columns:
                if col in result.columns:
                    result[col] = pd.to_numeric(result[col], errors='coerce')
            
            # 按日期排序
            result = result.sort_index()
            
            debug_logger.debug("数据标准化完成",
                             symbol=symbol,
                             rows=len(result),
                             columns=list(result.columns),
                             date_range=f"{result.index.min()} ~ {result.index.max()}")
            
        except Exception as e:
            debug_logger.error("数据标准化失败",
                             error=e,
                             symbol=symbol,
                             columns=list(result.columns) if hasattr(result, 'columns') else 'N/A')
            # 即使标准化失败，也返回原始数据
        
        return result

    def get_realtime_quotes(self, symbol: str) -> Dict[str, Any]:
        return data_source_manager.get_realtime_quotes(symbol)

    def get_financial_data(self, symbol: str, report_type: str = 'income') -> Dict[str, Any]:
        """获取财务数据（包装为字典格式）
        
        Args:
            symbol: 股票代码
            report_type: 报表类型（'income'利润表, 'balance'资产负债表, 'cashflow'现金流量表）
            
        Returns:
            字典格式的财务数据，包含：
            - data_success: 是否成功
            - income_statement: 利润表（DataFrame转换为字典）
            - balance_sheet: 资产负债表
            - cash_flow: 现金流量表
            - error: 错误信息（如果有）
        """
        debug_logger.info(f"开始获取财务数据", symbol=symbol, report_type=report_type, method="get_financial_data")
        
        result = {
            "symbol": symbol,
            "data_success": False,
            "income_statement": None,
            "balance_sheet": None,
            "cash_flow": None,
            "source": None
        }
        
        try:
            # 如果只请求一种报表类型，直接获取
            df = data_source_manager.get_financial_data(symbol, report_type)
            
            if df is not None and isinstance(df, pd.DataFrame) and not df.empty:
                # 将DataFrame转换为字典格式
                # 转换为记录列表（每行一个字典）
                records = df.to_dict('records')
                
                # 根据报表类型存储
                if report_type == 'income':
                    result["income_statement"] = {
                        "data": records,
                        "periods": len(records),
                        "columns": df.columns.tolist()
                    }
                    result["source"] = "tushare" if data_source_manager.tushare_available else "akshare"
                elif report_type == 'balance':
                    result["balance_sheet"] = {
                        "data": records,
                        "periods": len(records),
                        "columns": df.columns.tolist()
                    }
                    result["source"] = "tushare" if data_source_manager.tushare_available else "akshare"
                elif report_type == 'cashflow':
                    result["cash_flow"] = {
                        "data": records,
                        "periods": len(records),
                        "columns": df.columns.tolist()
                    }
                    result["source"] = "tushare" if data_source_manager.tushare_available else "akshare"
                
                result["data_success"] = True
                debug_logger.info(f"财务数据获取成功", 
                                symbol=symbol,
                                report_type=report_type,
                                periods=len(records),
                                source=result["source"])
            else:
                result["error"] = f"未能获取{report_type}财务数据"
                debug_logger.warning(f"财务数据为空", symbol=symbol, report_type=report_type)
                
        except Exception as e:
            result["error"] = str(e)
            debug_logger.error(f"获取财务数据失败", error=e, symbol=symbol, report_type=report_type)
        
        return result

    # 兜底封装：现有专用模块（A股为主）
    def get_quarterly_reports(self, symbol: str) -> Optional[Dict[str, Any]]:
        try:
            from quarterly_report_data import QuarterlyReportDataFetcher
            with network_optimizer.apply():
                return QuarterlyReportDataFetcher().get_quarterly_reports(symbol)
        except Exception as e:
            return {"symbol": symbol, "data_success": False, "error": str(e)}

    def get_fund_flow_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        try:
            from fund_flow_akshare import FundFlowAkshareDataFetcher
            with network_optimizer.apply():
                return FundFlowAkshareDataFetcher().get_fund_flow_data(symbol)
        except Exception as e:
            return {"symbol": symbol, "data_success": False, "error": str(e)}

    def get_market_sentiment_data(self, symbol: str, stock_data) -> Optional[Dict[str, Any]]:
        try:
            from market_sentiment_data import MarketSentimentDataFetcher
            with network_optimizer.apply():
                return MarketSentimentDataFetcher().get_market_sentiment_data(symbol, stock_data)
        except Exception as e:
            return {"symbol": symbol, "data_success": False, "error": str(e)}

    def get_news_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        try:
            from qstock_news_data import QStockNewsDataFetcher
            with network_optimizer.apply():
                return QStockNewsDataFetcher().get_stock_news(symbol)
        except Exception as e:
            return {"symbol": symbol, "data_success": False, "error": str(e)}
    
    def get_stock_news(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取股票新闻（别名方法，兼容app.py旧接口）"""
        return self.get_news_data(symbol)
    
    def get_risk_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取风险数据（限售解禁、大股东减持等）"""
        try:
            from risk_data_fetcher import RiskDataFetcher
            with network_optimizer.apply():
                return RiskDataFetcher().get_risk_data(symbol)
        except Exception as e:
            return {"symbol": symbol, "data_success": False, "error": str(e)}

    # 预留接口（先返回占位，后续补齐具体数据源实现）
    def get_research_reports_data(self, symbol: str, days: int = 180) -> Dict[str, Any]:
        """获取机构研报数据 (Tushare优先，包含研报内容，基于内容分析)
        
        Args:
            symbol: 股票代码
            days: 查询天数，默认180天（6个月）
            
        Returns:
            研报数据字典，包含研报内容和统计分析
        """
        start_time = time_module.time()
        debug_logger.info("开始获取研报数据", symbol=symbol, days=days)
        print(f"📑 [UnifiedDataAccess] 正在获取 {symbol} 机构研报数据（最近{days}天，包含内容）...")
        
        data = {
            "symbol": symbol,
            "research_reports": [],
            "data_success": False,
            "source": None,
            "report_count": 0,
            "analysis_summary": {},
            "content_analysis": {}  # 研报内容分析结果
        }
        
        # 只支持A股
        if not self._is_chinese_stock(symbol):
            data["error"] = "机构研报数据仅支持中国A股股票"
            print(f"   ⚠️ 机构研报数据仅支持A股")
            debug_logger.warning("研报数据仅支持A股", symbol=symbol)
            return data
        
        # 1. 优先使用Tushare report_rc接口（研报数据，包含内容）
        if data_source_manager.tushare_available:
            try:
                print(f"   [方法1-Tushare] 正在获取研报数据（report_rc接口，包含内容）...")
                ts_code = self._convert_to_ts_code(symbol)
                
                # 计算日期范围（6个月，约180天）
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
                
                with network_optimizer.apply():
                    df_reports = data_source_manager.tushare_api.report_rc(
                        ts_code=ts_code,
                        start_date=start_date,
                        end_date=end_date
                    )
                
                if df_reports is not None and not df_reports.empty:
                    print(f"   ✓ 获取到 {len(df_reports)} 条Tushare研报数据（含内容）")
                    
                    # 去重：基于日期+机构+标题去重（在DataFrame层面）
                    if len(df_reports) > 0:
                        # 使用日期+机构+标题作为唯一标识
                        df_reports['_unique_key'] = (
                            df_reports['report_date'].astype(str) + '_' +
                            df_reports['org_name'].astype(str) + '_' +
                            df_reports['report_title'].astype(str)
                        )
                        # 去重，保留第一条
                        df_reports = df_reports.drop_duplicates(subset=['_unique_key'], keep='first')
                        df_reports = df_reports.drop(columns=['_unique_key'])
                        print(f"   ✓ 去重后剩余 {len(df_reports)} 条研报数据")
                    
                    # 使用增强的统计分析（包含内容分析）
                    analysis = self._analyze_research_reports(df_reports)
                    
                    # 转换为统一的返回格式（包含研报内容）
                    # 再次去重（在字典层面，基于日期+机构+标题）
                    seen_keys = set()
                    reports = []
                    for report_data in analysis.get('reports_data', []):
                        # 生成唯一键
                        unique_key = (
                            str(report_data.get('report_date', '')) + '_' +
                            str(report_data.get('org_name', '')) + '_' +
                            str(report_data.get('report_title', ''))
                        )
                        
                        # 如果已存在，跳过
                        if unique_key in seen_keys:
                            continue
                        seen_keys.add(unique_key)
                        
                        reports.append({
                            '日期': report_data.get('report_date', ''),
                            '研报标题': report_data.get('report_title', ''),
                            '机构名称': report_data.get('org_name', ''),
                            '研究员': report_data.get('author_name', ''),
                            '评级': report_data.get('rating', ''),
                            '目标价': str(report_data.get('target_price_max') or report_data.get('target_price_min') or 'N/A'),
                            '研报类型': report_data.get('report_type', ''),
                            '研报内容': report_data.get('content', ''),  # 添加研报内容
                            '内容摘要': report_data.get('content_summary', ''),  # 内容摘要
                        })
                    
                    data["research_reports"] = reports
                    data["report_count"] = analysis.get('total_reports', 0)
                    data["analysis_summary"] = analysis.get('summary', {})
                    data["content_analysis"] = analysis.get('content_analysis', {})  # 内容分析结果
                    data["data_success"] = True
                    data["source"] = "tushare"
                    
                    print(f"   ✅ 成功获取 {len(reports)} 条机构研报（含内容和内容分析）")
                    debug_logger.info("研报数据获取成功（Tushare，含内容）", 
                                    symbol=symbol, 
                                    count=len(reports),
                                    source="tushare")
                    
                    elapsed_time = time_module.time() - start_time
                    debug_logger.info("研报数据获取完成", 
                                     symbol=symbol, 
                                     success=True,
                                     count=len(reports),
                                     elapsed=f"{elapsed_time:.2f}s")
                    return data
                else:
                    print(f"   ℹ️ Tushare未找到研报数据")
            except Exception as e:
                debug_logger.warning("Tushare获取研报失败", error=e, symbol=symbol)
                print(f"   ⚠️ Tushare获取失败: {e}")
        
        # 2. 备选使用Akshare
        try:
            print(f"   [方法2-Akshare] 正在获取研报数据（备用数据源）...")
            with network_optimizer.apply():
                import akshare as ak
                # 获取机构研报数据 - 东方财富
                df = ak.stock_research_report_em(symbol=symbol)
                
                if df is not None and not df.empty:
                    # 转换为字典列表，取最新数据（去重）
                    seen_keys = set()
                    reports = []
                    for idx, row in df.iterrows():
                        # 生成唯一键（基于日期+机构+标题）
                        date = str(row.get('日期', ''))
                        org = str(row.get('机构名称', ''))
                        title = str(row.get('研报标题', ''))
                        unique_key = f"{date}_{org}_{title}"
                        
                        # 如果已存在，跳过
                        if unique_key in seen_keys:
                            continue
                        seen_keys.add(unique_key)
                        
                        report = {
                            '日期': date,
                            '研报标题': title,
                            '机构名称': org,
                            '研究员': str(row.get('研究员', '')),
                            '评级': str(row.get('评级', '')),
                            '目标价': str(row.get('目标价', 'N/A')),
                            '相关股票': str(row.get('相关股票', '')),
                            '研报内容': '',  # Akshare数据源不包含内容
                            '内容摘要': '',  # Akshare数据源不包含内容
                        }
                        reports.append(report)
                    
                    # 简单的统计分析（Akshare数据字段有限）
                    rating_list = [r['评级'] for r in reports if r['评级']]
                    total = len(reports)
                    buy_count = sum(1 for r in rating_list 
                                  if any(keyword in str(r) for keyword in ['买入', '增持', '推荐', '强推']))
                    neutral_count = sum(1 for r in rating_list 
                                      if any(keyword in str(r) for keyword in ['持有', '中性', '观望']))
                    sell_count = sum(1 for r in rating_list 
                                   if any(keyword in str(r) for keyword in ['卖出', '减持', '回避']))
                    
                    data["research_reports"] = reports
                    data["report_count"] = len(reports)
                    data["analysis_summary"] = {
                        'rating_ratio': {
                            'buy_ratio': round(buy_count / total * 100, 2) if total > 0 else 0,
                            'neutral_ratio': round(neutral_count / total * 100, 2) if total > 0 else 0,
                            'sell_ratio': round(sell_count / total * 100, 2) if total > 0 else 0,
                        }
                    }
                    data["data_success"] = True
                    data["source"] = "akshare"
                    
                    print(f"   ✅ 成功获取 {len(reports)} 条机构研报（Akshare）")
                    debug_logger.info("研报数据获取成功（Akshare）", 
                                    symbol=symbol, 
                                    count=len(reports),
                                    source="akshare")
                else:
                    print(f"   ℹ️ 未找到机构研报数据")
                    data["error"] = "未找到机构研报数据"
        
        except Exception as e:
            debug_logger.error("获取机构研报失败", error=e, symbol=symbol)
            print(f"   ❌ 获取机构研报失败: {e}")
            data["error"] = str(e)
            import traceback
            traceback.print_exc()
        
        elapsed_time = time_module.time() - start_time
        debug_logger.info("研报数据获取完成", 
                         symbol=symbol, 
                         success=data.get('data_success', False),
                         count=data.get('report_count', 0),
                         elapsed=f"{elapsed_time:.2f}s")
        
        return data

    def get_announcement_data(self, symbol: str, days: int = 30) -> Dict[str, Any]:
        """获取公告数据 - 过去N天的上市公司公告 (Tushare优先)
        
        Args:
            symbol: 股票代码
            days: 获取最近N天的公告，默认30天
            
        Returns:
            包含公告列表的字典
        """
        start_time = time_module.time()
        debug_logger.info(f"开始获取公告数据", symbol=symbol, days=days, method="get_announcement_data")
        print(f"📢 [UnifiedDataAccess] 正在获取 {symbol} 最近{days}天的公告数据...")
        
        data = {
            "symbol": symbol,
            "announcements": [],
            "data_success": False,
            "source": None,
            "days": days
        }
        
        # 只支持A股
        if not self._is_chinese_stock(symbol):
            data["error"] = "公告数据仅支持中国A股股票"
            debug_logger.warning(f"公告数据仅支持A股", symbol=symbol, is_chinese=False)
            print(f"   ⚠️ 公告数据仅支持A股")
            return data
        
        try:
            debug_logger.debug(f"进入公告数据获取try块", symbol=symbol)
            from datetime import datetime, timedelta
            import pandas as pd
            
            # 计算时间范围
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            start_date_str = start_date.strftime('%Y%m%d')
            end_date_str = end_date.strftime('%Y%m%d')
            
            announcements = []
            
            # 方法1: 优先使用Tushare获取公告
            if data_source_manager.tushare_available:
                try:
                    print(f"   [方法1-Tushare] 正在获取公告数据...")
                    ts_code = data_source_manager._convert_to_ts_code(symbol)
                    
                    # 使用Tushare的announcement接口
                    df = data_source_manager.tushare_api.announcement(
                        ts_code=ts_code,
                        start_date=start_date_str,
                        end_date=end_date_str
                    )
                    
                    if df is not None and isinstance(df, pd.DataFrame) and not df.empty:
                        print(f"   ✓ 获取到 {len(df)} 条Tushare公告数据")
                        
                        for idx, row in df.iterrows():
                            try:
                                ann_date = row.get('ann_date', '')
                                ts_code = row.get('ts_code', '')
                                
                                # 构建公告链接（根据交易所）
                                link = 'N/A'
                                if pd.notna(ann_date) and pd.notna(ts_code):
                                    if ts_code.endswith('.SH'):
                                        # 上交所
                                        link = f"http://www.sse.com.cn/disclosure/bond/announcement/{ann_date}/{ts_code.replace('.SH', '')}.pdf"
                                    elif ts_code.endswith('.SZ'):
                                        # 深交所
                                        link = f"http://www.cninfo.com.cn/new/disclosure/detail?plate=&orgId=&stockCode={ts_code.replace('.SZ', '')}&announcementId=&announcementTime={ann_date}"
                                    elif ts_code.endswith('.BJ'):
                                        # 北交所
                                        link = f"http://www.bse.cn/disclosure/{ann_date}/{ts_code.replace('.BJ', '')}.pdf"
                                
                                announcement = {
                                    '日期': ann_date if pd.notna(ann_date) else 'N/A',
                                    '公告标题': str(row.get('title', 'N/A')),
                                    '公告类型': str(row.get('type', 'N/A')),
                                    '公告摘要': str(row.get('content', ''))[:200] if pd.notna(row.get('content')) else '',
                                    '公告链接': link
                                }
                                announcements.append(announcement)
                            except Exception as e:
                                debug_logger.debug(f"解析Tushare公告行失败", error=e, row_idx=idx)
                                continue
                        
                        if announcements:
                            data["source"] = "tushare"
                            print(f"   [方法1] ✅ 成功获取 {len(announcements)} 条公告")
                except Exception as e:
                    debug_logger.warning(f"Tushare获取公告失败", error=e, symbol=symbol)
                    print(f"   [方法1] ❌ 失败: {e}")
            
            # 方法2: 如果Tushare失败，尝试使用问财获取公告
            if not announcements:
                try:
                    print(f"   [方法2-问财] 正在获取公告数据...")
                    with network_optimizer.apply():
                        import pywencai
                        
                        # 构造查询语句：获取公告
                        query = f"{symbol}公告"
                        res = pywencai.get(query=query, loop=True)
                    
                    if res is not None:
                        # 处理嵌套结构（tableV1）
                        df_result = None
                        if isinstance(res, pd.DataFrame):
                            df_result = res
                        elif isinstance(res, dict):
                            try:
                                df_result = pd.DataFrame([res])
                            except:
                                df_result = None
                        
                        # 检查是否是嵌套结构
                        if df_result is not None and 'tableV1' in df_result.columns and len(df_result.columns) == 1:
                            table_v1_data = df_result.iloc[0]['tableV1']
                            if isinstance(table_v1_data, pd.DataFrame):
                                df_result = table_v1_data
                            elif isinstance(table_v1_data, list) and len(table_v1_data) > 0:
                                df_result = pd.DataFrame(table_v1_data)
                        
                        if df_result is not None and not df_result.empty:
                            print(f"   ✓ 获取到 {len(df_result)} 条原始公告数据")
                            
                            for idx, row in df_result.iterrows():
                                try:
                                    # 查找日期列和标题列
                                    date_col = None
                                    title_col = None
                                    type_col = None
                                    
                                    for col in df_result.columns:
                                        col_str = str(col).lower()
                                        if '日期' in col_str or 'date' in col_str or '时间' in col_str:
                                            date_col = col
                                        elif '标题' in col_str or '公告' in col_str or 'title' in col_str or '名称' in col_str:
                                            title_col = col
                                        elif '类型' in col_str or 'type' in col_str or '类别' in col_str:
                                            type_col = col
                                    
                                    # 提取公告信息
                                    item = {}
                                    for col in df_result.columns:
                                        value = row.get(col)
                                        if value is not None and not (isinstance(value, float) and pd.isna(value)):
                                            if not isinstance(value, pd.DataFrame):
                                                try:
                                                    item[col] = str(value)
                                                except:
                                                    pass
                                    
                                    if item:
                                        # 尝试解析日期
                                        date_str = None
                                        if date_col and date_col in item:
                                            date_str = item[date_col]
                                        else:
                                            # 从所有字段中查找日期
                                            for key, val in item.items():
                                                if '日期' in str(key) or '时间' in str(key):
                                                    date_str = val
                                                    break
                                        
                                        # 验证日期是否在范围内
                                        in_range = True
                                        if date_str:
                                            try:
                                                pub_date = pd.to_datetime(str(date_str))
                                                if pub_date < start_date or pub_date > end_date:
                                                    in_range = False
                                                date_str = pub_date.strftime('%Y-%m-%d')
                                            except:
                                                in_range = False  # 日期解析失败，可能不是最近的数据
                                        
                                        if in_range:
                                            # 提取标题
                                            title = None
                                            if title_col and title_col in item:
                                                title = item[title_col]
                                            else:
                                                # 从所有字段中查找标题
                                                for key, val in item.items():
                                                    if '标题' in str(key) or '公告' in str(key) or '名称' in str(key):
                                                        title = val
                                                        break
                                            
                                            if not title:
                                                # 如果没有标题，尝试使用第一个非日期字段
                                                for key, val in item.items():
                                                    key_str = str(key).lower()
                                                    if '日期' not in key_str and '时间' not in key_str:
                                                        val_str = str(val)
                                                        # 跳过HTML标签和过短的无意义内容
                                                        if not val_str.startswith('<') and len(val_str) > 10:
                                                            title = val_str[:200]  # 限制长度
                                                            break
                                            
                                            if title:
                                                # 清理HTML标签
                                                import re
                                                # 移除HTML标签
                                                title_clean = re.sub(r'<[^>]+>', '', str(title))
                                                # 移除多余的空白
                                                title_clean = re.sub(r'\s+', ' ', title_clean).strip()
                                                
                                                # 如果清理后太短，跳过
                                                if len(title_clean) < 5:
                                                    continue
                                                
                                                announcement = {
                                                    '日期': date_str or 'N/A',
                                                    '公告标题': title_clean[:200],
                                                    '公告类型': item.get(type_col, 'N/A') if type_col and type_col in item else 'N/A',
                                                    '公告摘要': ''
                                                }
                                                announcements.append(announcement)
                                except Exception as e:
                                    debug_logger.debug(f"解析公告行失败", error=e, row_idx=idx)
                                    continue
                            
                            if announcements:
                                data["source"] = "pywencai"
                                print(f"   [方法2] ✅ 成功获取 {len(announcements)} 条公告")
                        else:
                            print(f"   [方法2] ⚠️ 未获取到公告数据")
                
                except Exception as e:
                    debug_logger.warning(f"问财获取公告失败", error=e, symbol=symbol)
                    print(f"   [方法2] ❌ 失败: {e}")
            
            # 方法3: 如果Tushare和问财都失败，尝试使用Akshare的新闻接口筛选
            if not announcements:
                try:
                    print(f"   [方法3-Akshare] 正在获取个股信息页的公告...")
                    with network_optimizer.apply():
                        import akshare as ak
                        # 使用个股新闻数据作为公告的替代（虽然不完全准确，但能提供一定信息）
                        df = ak.stock_news_em(symbol=symbol)
                        
                        if df is not None and not df.empty:
                            print(f"   ✓ 获取到 {len(df)} 条新闻数据")
                            
                            for idx, row in df.iterrows():
                                try:
                                    date_str = str(row.get('发布时间', row.get('时间', '')))
                                    if date_str and date_str != 'nan':
                                        pub_date = pd.to_datetime(date_str)
                                        # 只保留时间范围内的数据
                                        if pub_date >= start_date and pub_date <= end_date:
                                            # 检查标题中是否包含"公告"等关键词
                                            title = str(row.get('新闻标题', row.get('标题', 'N/A')))
                                            if any(keyword in title for keyword in ['公告', '披露', '报告', '预告', '公告']):
                                                announcement = {
                                                    '日期': pub_date.strftime('%Y-%m-%d'),
                                                    '公告标题': title,
                                                    '公告类型': '新闻公告',
                                                    '公告摘要': str(row.get('新闻内容', ''))[:200] if row.get('新闻内容') else ''
                                                }
                                                announcements.append(announcement)
                                except:
                                    continue
                            
                            if announcements:
                                data["source"] = "akshare"
                                print(f"   [方法3] ✅ 筛选出 {len(announcements)} 条相关公告信息")
                            else:
                                print(f"   [方法3] ⚠️ 未找到包含公告关键词的新闻")
                        else:
                            print(f"   [方法3] ⚠️ 未获取到数据")
                    
                except Exception as e:
                    debug_logger.warning(f"Akshare获取公告失败", error=e, symbol=symbol)
                    print(f"   [方法3] ❌ 失败: {e}")
            
            # 整理结果
            if announcements:
                # 按日期排序（最新的在前）
                announcements.sort(key=lambda x: x['日期'], reverse=True)
                
                data["announcements"] = announcements
                data["data_success"] = True
                data["count"] = len(announcements)
                data["date_range"] = {
                    "start": start_date.strftime('%Y-%m-%d'),
                    "end": end_date.strftime('%Y-%m-%d')
                }
                print(f"   ✅ 最终成功获取 {len(announcements)} 条公告 (时间范围: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')})")
            else:
                print(f"   ℹ️ 所有数据源均未找到公告数据")
                data["error"] = f"未找到最近{days}天的公告数据"
        
        except Exception as e:
            debug_logger.error(f"获取公告失败", error=e, symbol=symbol, days=days)
            print(f"   ❌ 获取公告失败: {e}")
            import traceback
            traceback.print_exc()
            data["error"] = str(e)
        
        elapsed_time = time_module.time() - start_time
        debug_logger.info(f"公告数据获取完成", 
                         symbol=symbol, 
                         success=data.get('data_success', False),
                         count=data.get('count', 0),
                         elapsed=f"{elapsed_time:.2f}s")
        
        return data
    
    def _is_chinese_stock(self, symbol):
        """判断是否为中国A股"""
        return symbol.isdigit() and len(symbol) == 6

    def get_chip_distribution_data(self, symbol: str, trade_date: str = None, current_price: float = None) -> Dict[str, Any]:
        """获取筹码分布数据 - 使用Tushare的cyq_perf和cyq_chips接口（仅A股）
        
        Args:
            symbol: 股票代码（6位数字）
            trade_date: 交易日期（格式：YYYYMMDD），默认最新交易日
            
        Returns:
            包含筹码分布信息的字典，包括：
            - cyq_perf: 每日筹码及胜率数据
            - cyq_chips: 每日筹码分布数据
            - latest_date: 最新数据日期
        """
        start_time = time_module.time()
        debug_logger.info(f"开始获取筹码分布数据", symbol=symbol, trade_date=trade_date, method="get_chip_distribution_data")
        print(f"🎯 [UnifiedDataAccess] 正在获取 {symbol} 的筹码分布数据...")
        
        data = {
            "symbol": symbol,
            "data_success": False,
            "cyq_perf": None,      # 筹码分布及胜率数据
            "cyq_chips": None,     # 每日筹码分布数据
            "latest_date": None,
            "source": None
        }
        
        # 只支持A股
        if not self._is_chinese_stock(symbol):
            data["error"] = "筹码分布数据仅支持中国A股股票"
            debug_logger.warning(f"筹码数据仅支持A股", symbol=symbol, is_chinese=False)
            print(f"   ⚠️ 筹码分布数据仅支持A股")
            return data
        
        try:
            # 使用Tushare获取筹码分布数据
            if not data_source_manager.tushare_available:
                data["error"] = "Tushare数据源不可用，筹码分布数据需要Tushare支持"
                print(f"   ⚠️ Tushare不可用，无法获取筹码分布数据")
                return data
            
            print(f"   [Tushare] 正在获取筹码分布数据...")
            ts_code = data_source_manager._convert_to_ts_code(symbol)
            
            # 如果没有指定日期，使用最新交易日
            if not trade_date:
                trade_date = datetime.now().strftime('%Y%m%d')
            
            # 方法1: 获取每日筹码及胜率数据 (cyq_perf)
            try:
                print(f"   [方法1] 正在获取cyq_perf数据（筹码分布及胜率）...")
                # cyq_perf接口参数：ts_code, trade_date
                # 获取最近30天的数据用于分析
                end_date = trade_date
                start_date = (datetime.strptime(end_date, '%Y%m%d') - timedelta(days=30)).strftime('%Y%m%d')
                
                df_perf = data_source_manager.tushare_api.cyq_perf(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date
                )
                
                if df_perf is not None and isinstance(df_perf, pd.DataFrame) and not df_perf.empty:
                    # 转换为字典列表
                    perf_records = df_perf.to_dict('records')
                    # 获取最新一条记录
                    latest_perf = perf_records[-1] if perf_records else None
                    
                    data["cyq_perf"] = {
                        "data": perf_records,
                        "latest": latest_perf,
                        "count": len(perf_records)
                    }
                    
                    if latest_perf:
                        data["latest_date"] = latest_perf.get('trade_date', trade_date)
                    
                    print(f"   [方法1] ✅ 成功获取 {len(perf_records)} 条cyq_perf数据")
                    debug_logger.info(f"Tushare cyq_perf获取成功", 
                                    symbol=symbol,
                                    count=len(perf_records),
                                    latest_date=data.get('latest_date'))
                else:
                    print(f"   [方法1] ⚠️ 未获取到cyq_perf数据")
            except Exception as e:
                debug_logger.warning(f"Tushare cyq_perf获取失败", error=e, symbol=symbol)
                print(f"   [方法1] ❌ 失败: {e}")
            
            # 方法2: 获取每日筹码分布数据 (cyq_chips)
            try:
                print(f"   [方法2] 正在获取cyq_chips数据（每日筹码分布）...")
                # cyq_chips接口参数：ts_code, trade_date
                # 获取指定日期的筹码分布数据
                df_chips = data_source_manager.tushare_api.cyq_chips(
                    ts_code=ts_code,
                    trade_date=trade_date
                )
                
                if df_chips is not None and isinstance(df_chips, pd.DataFrame) and not df_chips.empty:
                    # 转换为字典列表
                    chips_records = df_chips.to_dict('records')
                    
                    data["cyq_chips"] = {
                        "data": chips_records,
                        "count": len(chips_records),
                        "trade_date": trade_date
                    }
                    
                    # 如果还没有latest_date，使用trade_date
                    if not data["latest_date"]:
                        data["latest_date"] = trade_date
                    
                    print(f"   [方法2] ✅ 成功获取 {len(chips_records)} 条cyq_chips数据")
                    debug_logger.info(f"Tushare cyq_chips获取成功", 
                                    symbol=symbol,
                                    count=len(chips_records),
                                    trade_date=trade_date)
                else:
                    # 如果指定日期没有数据，尝试获取最近几个交易日的数据
                    print(f"   [方法2] ⚠️ {trade_date}未获取到数据，尝试获取最近交易日数据...")
                    for i in range(1, 6):  # 回溯5个交易日
                        try_date = (datetime.strptime(trade_date, '%Y%m%d') - timedelta(days=i)).strftime('%Y%m%d')
                        df_chips = data_source_manager.tushare_api.cyq_chips(
                            ts_code=ts_code,
                            trade_date=try_date
                        )
                        if df_chips is not None and isinstance(df_chips, pd.DataFrame) and not df_chips.empty:
                            chips_records = df_chips.to_dict('records')
                            data["cyq_chips"] = {
                                "data": chips_records,
                                "count": len(chips_records),
                                "trade_date": try_date
                            }
                            data["latest_date"] = try_date
                            print(f"   [方法2] ✅ 成功获取 {try_date} 的 {len(chips_records)} 条cyq_chips数据")
                            break
                    else:
                        print(f"   [方法2] ⚠️ 最近5个交易日均未获取到cyq_chips数据")
            except Exception as e:
                debug_logger.warning(f"Tushare cyq_chips获取失败", error=e, symbol=symbol)
                print(f"   [方法2] ❌ 失败: {e}")
            
            # 判断是否成功获取数据
            if data["cyq_perf"] or data["cyq_chips"]:
                data["data_success"] = True
                data["source"] = "tushare"
                
                # 生成汇总信息（当前状态）
                summary = {}
                if data["cyq_perf"] and data["cyq_perf"].get("latest"):
                    latest = data["cyq_perf"]["latest"]
                    # 根据实际返回字段提取信息
                    summary["交易日期"] = latest.get('trade_date', 'N/A')
                    summary["5%成本"] = latest.get('cost_5pct', 'N/A')
                    summary["15%成本"] = latest.get('cost_15pct', 'N/A')
                    summary["50%成本（中位）"] = latest.get('cost_50pct', 'N/A')
                    summary["85%成本"] = latest.get('cost_85pct', 'N/A')
                    summary["95%成本"] = latest.get('cost_95pct', 'N/A')
                    summary["加权平均成本"] = latest.get('weight_avg', 'N/A')
                    summary["历史最低"] = latest.get('his_low', 'N/A')
                    summary["历史最高"] = latest.get('his_high', 'N/A')
                    # 计算成本区间范围（集中度指标）
                    if pd.notna(latest.get('cost_50pct')) and pd.notna(latest.get('cost_85pct')) and pd.notna(latest.get('cost_15pct')):
                        try:
                            cost_range = float(latest.get('cost_85pct', 0)) - float(latest.get('cost_15pct', 0))
                            cost_center = float(latest.get('cost_50pct', 0))
                            if cost_center > 0:
                                concentration_pct = (cost_range / cost_center) * 100
                                if concentration_pct < 10:
                                    summary["筹码集中度"] = "高"
                                elif concentration_pct > 30:
                                    summary["筹码集中度"] = "低"
                                else:
                                    summary["筹码集中度"] = "中等"
                                summary["成本区间"] = f"{cost_range:.2f} ({concentration_pct:.1f}%)"
                        except:
                            summary["筹码集中度"] = "N/A"
                    else:
                        summary["筹码集中度"] = "N/A"
                    
                    summary["数据期数"] = data["cyq_perf"].get("count", 0)
                
                # 生成30天筹码分布变化分析
                if data["cyq_perf"] and data["cyq_perf"].get("data") and len(data["cyq_perf"]["data"]) >= 2:
                    # 如果没有传入当前价格，尝试使用加权平均成本作为参考
                    analysis_price = current_price
                    if not analysis_price and latest and pd.notna(latest.get('weight_avg')):
                        analysis_price = float(latest.get('weight_avg', 0))
                    
                    change_analysis = self._analyze_chip_changes(data["cyq_perf"]["data"], analysis_price)
                    if change_analysis:
                        summary["30天变化分析"] = change_analysis
                        data["change_analysis"] = change_analysis
                
                if data["cyq_chips"]:
                    summary["筹码分布数据点"] = data["cyq_chips"]["count"]
                    summary["筹码分布日期"] = data["cyq_chips"].get("trade_date", 'N/A')
                
                data["summary"] = summary
                
                print(f"   ✅ 筹码分布数据获取完成（数据日期: {data.get('latest_date', 'N/A')}）")
                debug_logger.info(f"筹码分布数据获取成功",
                                symbol=symbol,
                                has_perf=(data["cyq_perf"] is not None),
                                has_chips=(data["cyq_chips"] is not None),
                                latest_date=data.get('latest_date'))
            else:
                data["error"] = "未能获取筹码分布数据，cyq_perf和cyq_chips均失败"
                print(f"   ⚠️ 所有数据源均未获取到筹码数据")
        
        except Exception as e:
            debug_logger.error(f"获取筹码数据失败", error=e, symbol=symbol)
            print(f"   ❌ 获取筹码数据失败: {e}")
            import traceback
            traceback.print_exc()
            data["error"] = str(e)
        
        elapsed_time = time_module.time() - start_time
        debug_logger.info(f"筹码数据获取完成",
                         symbol=symbol,
                         success=data.get('data_success', False),
                         source=data.get('source'),
                         has_perf=(data.get('cyq_perf') is not None),
                         has_chips=(data.get('cyq_chips') is not None),
                         elapsed=f"{elapsed_time:.2f}s")
        
        return data

    def _convert_to_ts_code(self, symbol: str) -> str:
        """将股票代码转换为Tushare格式"""
        return data_source_manager._convert_to_ts_code(symbol)
    
    def _is_trading_day(self, date: datetime = None) -> bool:
        """判断是否为交易日（简化版：周一到周五）
        
        Args:
            date: 日期对象，默认为当前日期
            
        Returns:
            bool: 是否为交易日（周一到周五）
        """
        if date is None:
            date = datetime.now()
        
        # 周一到周五（0-4）为交易日
        weekday = date.weekday()
        return weekday < 5  # 0-4为周一到周五
    
    def _is_trading_time(self) -> bool:
        """判断当前是否在交易时间内（A股：9:30-11:30, 13:00-15:00）
        
        Returns:
            bool: 是否在交易时间内
        """
        now = datetime.now()
        current_time = now.time()
        
        # 排除周末
        if not self._is_trading_day(now):
            return False
        
        # A股交易时间：9:30-11:30, 13:00-15:00
        morning_start = time(9, 30)
        morning_end = time(11, 30)
        afternoon_start = time(13, 0)
        afternoon_end = time(15, 0)
        
        is_trading = (
            (morning_start <= current_time <= morning_end) or
            (afternoon_start <= current_time <= afternoon_end)
        )
        
        return is_trading
    
    def _get_appropriate_trade_date(self) -> str:
        """获取合适的交易日（根据日期和时间判断）
        
        规则：
        - 非交易日 → 返回上一交易日
        - 交易日开盘前（<9:30）→ 返回上一交易日
        - 交易日开盘后（>=9:30）→ 返回当日
        
        Returns:
            str: 交易日期（格式：YYYYMMDD）
        """
        now = datetime.now()
        current_time = now.time()
        current_date = now.date()
        
        # 判断是否为交易日
        is_trading_day = self._is_trading_day(now)
        
        # 判断是否在交易时间内（开盘后）
        is_trading_time = self._is_trading_time()
        
        # 判断是否在开盘前（9:30之前）
        is_before_open = current_time < time(9, 30)
        
        # 1. 非交易日 → 返回上一交易日
        if not is_trading_day:
            debug_logger.debug("非交易日，查找上一交易日", current_date=current_date, weekday=now.weekday())
            # 往前找，跳过周末
            for days_back in range(1, 8):  # 最多找7天
                prev_date = now - timedelta(days=days_back)
                if self._is_trading_day(prev_date):
                    trade_date = prev_date.strftime('%Y%m%d')
                    debug_logger.debug("找到上一交易日", trade_date=trade_date, days_back=days_back)
                    return trade_date
        
        # 2. 交易日但开盘前（<9:30）→ 返回上一交易日
        if is_trading_day and is_before_open:
            debug_logger.debug("交易日开盘前，查找上一交易日", current_date=current_date, current_time=current_time)
            # 往前找一天（可能是周五→周四，或周一→周五）
            for days_back in range(1, 4):  # 最多找3天（周五到周一的情况）
                prev_date = now - timedelta(days=days_back)
                if self._is_trading_day(prev_date):
                    trade_date = prev_date.strftime('%Y%m%d')
                    debug_logger.debug("开盘前找到上一交易日", trade_date=trade_date, days_back=days_back)
                    return trade_date
        
        # 3. 交易日开盘后（>=9:30）→ 返回当日
        if is_trading_day and is_trading_time:
            trade_date = now.strftime('%Y%m%d')
            debug_logger.debug("交易日开盘后，使用当日数据", trade_date=trade_date, current_time=current_time)
            return trade_date
        
        # 4. 交易日但收盘后（>15:00）→ 返回当日（收盘数据）
        if is_trading_day and current_time > time(15, 0):
            trade_date = now.strftime('%Y%m%d')
            debug_logger.debug("交易日收盘后，使用当日收盘数据", trade_date=trade_date, current_time=current_time)
            return trade_date
        
        # 5. 其他情况（如午休时间）→ 使用当日
        trade_date = now.strftime('%Y%m%d')
        debug_logger.debug("其他情况，使用当日数据", trade_date=trade_date, 
                          is_trading_day=is_trading_day,
                          current_time=current_time)
        return trade_date

    # ========== 方案1：恢复高级功能 ==========
    
    def get_etf_data(self, symbol: str, start_date: Optional[str] = None, 
                     end_date: Optional[str] = None) -> Optional[pd.DataFrame]:
        """获取ETF数据
        
        Args:
            symbol: ETF代码（6位数字）
            start_date: 开始日期（格式：'20240101'或'2024-01-01'）
            end_date: 结束日期
            
        Returns:
            DataFrame: ETF历史数据，失败时返回None
        """
        debug_logger.info("开始获取ETF数据", symbol=symbol, start_date=start_date, end_date=end_date)
        print(f"📊 [UnifiedDataAccess] 正在获取 {symbol} 的ETF数据...")
        
        # 标准化日期格式
        if not start_date:
            start_date = (datetime.now() - timedelta(days=100)).strftime('%Y%m%d')
        else:
            start_date = start_date.replace('-', '')
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')
        else:
            end_date = end_date.replace('-', '')
        
        # 1. 优先使用Tushare
        if data_source_manager.tushare_available:
            try:
                print(f"   [Tushare] 正在获取ETF数据（优先数据源）...")
                with network_optimizer.apply():
                    ts_code = self._convert_to_ts_code(symbol)
                    df = data_source_manager.tushare_api.fund_daily(
                        ts_code=ts_code,
                        start_date=start_date,
                        end_date=end_date
                    )
                    
                    if df is not None and not df.empty:
                        df['data_source'] = 'Tushare'
                        print(f"   ✅ 成功获取 {len(df)} 条ETF数据（Tushare）")
                        debug_logger.info("ETF数据获取成功", symbol=symbol, source="Tushare", count=len(df))
                        return df
            except Exception as e:
                debug_logger.warning(f"Tushare获取ETF数据失败", error=e, symbol=symbol)
                print(f"   ⚠️ Tushare获取失败: {e}")
        
        # 2. 备选使用Akshare
        try:
            print(f"   [Akshare] 正在获取ETF数据（备用数据源）...")
            with network_optimizer.apply():
                import akshare as ak
                # akshare 需要带市场前缀，如 sh510300 / sz159915
                symbol_prefixed = (
                    f"sh{symbol}" if symbol.startswith(('51', '56', '58')) else
                    (f"sz{symbol}" if symbol.startswith(('15', '16')) else symbol)
                )
                df = ak.fund_etf_hist_sina(symbol=symbol_prefixed)
                
                if df is not None and not df.empty:
                    df['data_source'] = 'Akshare'
                    print(f"   ✅ 成功获取 {len(df)} 条ETF数据（Akshare）")
                    debug_logger.info("ETF数据获取成功", symbol=symbol, source="Akshare", count=len(df))
                    return df
        except Exception as e:
            debug_logger.warning(f"Akshare获取ETF数据失败", error=e, symbol=symbol)
            print(f"   ⚠️ Akshare获取失败: {e}")
        
        print(f"   ❌ 所有数据源均获取失败")
        return None
    
    def get_beta_coefficient(self, symbol: str, index_code: str = '000300.SH', days: int = 250) -> Optional[float]:
        """计算股票Beta系数
        
        Args:
            symbol: 股票代码
            index_code: 参考指数代码（默认沪深300）
            days: 回溯天数（默认250个交易日，约1年）
            
        Returns:
            float: Beta系数，如果计算失败返回None
        """
        debug_logger.info("开始计算Beta系数", symbol=symbol, index_code=index_code, days=days)
        print(f"📈 [UnifiedDataAccess] 正在计算 {symbol} 的Beta系数（vs {index_code}）...")
        
        if not data_source_manager.tushare_available:
            print(f"   ⚠️ Tushare不可用，无法计算Beta系数")
            debug_logger.warning("Tushare不可用，无法计算Beta", symbol=symbol)
            return None
        
        try:
            import numpy as np
            
            # 计算日期范围
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days * 2)).strftime('%Y%m%d')  # 多获取一些以确保足够的数据
            
            ts_code = self._convert_to_ts_code(symbol)
            
            # 获取股票日线数据
            print(f"   [Tushare] 获取股票日线数据...")
            with network_optimizer.apply():
                df_stock = data_source_manager.tushare_api.daily(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date,
                    fields='ts_code,trade_date,close,pct_chg'
                )
                
                # 获取指数日线数据
                print(f"   [Tushare] 获取指数日线数据...")
                df_index = data_source_manager.tushare_api.index_daily(
                    ts_code=index_code,
                    start_date=start_date,
                    end_date=end_date,
                    fields='ts_code,trade_date,close,pct_chg'
                )
            
            if df_stock is None or df_stock.empty or df_index is None or df_index.empty:
                print(f"   ❌ 数据获取失败")
                debug_logger.warning("Beta计算数据获取失败", symbol=symbol)
                return None
            
            # 排序并取最近N天
            df_stock = df_stock.sort_values('trade_date').tail(days)
            df_index = df_index.sort_values('trade_date').tail(days)
            
            print(f"   ℹ️ 股票数据: {len(df_stock)} 条, 指数数据: {len(df_index)} 条")
            
            # 计算Beta
            stock_returns = df_stock['pct_chg'].values
            index_returns = df_index['pct_chg'].values
            
            # 确保长度一致
            min_len = min(len(stock_returns), len(index_returns))
            if min_len < 50:  # 至少需要50个交易日的数据
                print(f"   ⚠️ 数据不足({min_len}条)，建议至少50个交易日")
                debug_logger.warning("Beta计算数据不足", symbol=symbol, min_len=min_len)
                return None
            
            stock_returns = stock_returns[-min_len:]
            index_returns = index_returns[-min_len:]
            
            # 计算协方差和方差
            covariance = np.cov(stock_returns, index_returns)[0][1]
            variance = np.var(index_returns)
            
            if variance == 0:
                print(f"   ❌ 指数方差为0，无法计算Beta")
                debug_logger.warning("Beta计算：指数方差为0", symbol=symbol)
                return None
            
            beta = covariance / variance
            
            print(f"   ✅ Beta系数 = {beta:.4f}")
            debug_logger.info("Beta系数计算成功", symbol=symbol, beta=beta, index_code=index_code)
            return beta
            
        except Exception as e:
            print(f"   ❌ Beta系数计算失败: {e}")
            debug_logger.error("Beta系数计算失败", error=e, symbol=symbol)
            import traceback
            traceback.print_exc()
            return None
    
    def get_52week_high_low(self, symbol: str) -> Dict[str, Any]:
        """获取52周高低位数据
        
        Args:
            symbol: 股票代码
            
        Returns:
            dict: 包含52周高低位信息
        """
        debug_logger.info("开始获取52周高低位", symbol=symbol)
        print(f"📊 [UnifiedDataAccess] 正在获取 {symbol} 的52周高低位数据...")
        
        result = {
            'success': False,
            'high_52w': None,
            'low_52w': None,
            'high_date': None,
            'low_date': None,
            'current_price': None,
            'position_percent': None,  # 当前价格在52周区间的位置（0-100%）
        }
        
        if not data_source_manager.tushare_available:
            print(f"   ⚠️ Tushare不可用，无法获取52周高低位")
            debug_logger.warning("Tushare不可用，无法获取52周高低位", symbol=symbol)
            return result
        
        try:
            # 获取过去52周（约365天）的数据
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
            
            ts_code = self._convert_to_ts_code(symbol)
            
            print(f"   [Tushare] 获取日线数据...")
            with network_optimizer.apply():
                df = data_source_manager.tushare_api.daily(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date,
                    fields='ts_code,trade_date,close,high,low'
                )
            
            if df is None or df.empty:
                print(f"   ❌ 数据获取失败")
                debug_logger.warning("52周高低位数据获取失败", symbol=symbol)
                return result
            
            print(f"   ℹ️ 获取 {len(df)} 个交易日数据")
            
            # 确保按日期排序
            df = df.sort_values('trade_date')
            
            # 计算52周高低位
            high_52w = df['high'].max()
            low_52w = df['low'].min()
            current_price = df.iloc[-1]['close']  # 最新收盘价（最后一行）
            
            # 找到高低位的日期
            high_row = df[df['high'] == high_52w].iloc[0]
            low_row = df[df['low'] == low_52w].iloc[0]
            high_date = high_row['trade_date']
            low_date = low_row['trade_date']
            
            # 计算当前价格相对位置
            price_range = high_52w - low_52w
            if price_range > 0:
                position = (current_price - low_52w) / price_range * 100
            else:
                position = 50.0  # 如果区间为0，默认50%
            
            result['success'] = True
            result['high_52w'] = float(high_52w)
            result['low_52w'] = float(low_52w)
            result['high_date'] = str(high_date)
            result['low_date'] = str(low_date)
            result['current_price'] = float(current_price)
            result['position_percent'] = float(position)
            
            print(f"   ✅ 52周高: {high_52w:.2f}, 52周低: {low_52w:.2f}, 当前: {current_price:.2f}, 位置: {position:.1f}%")
            debug_logger.info("52周高低位获取成功", 
                            symbol=symbol,
                            high_52w=high_52w,
                            low_52w=low_52w,
                            current_price=current_price,
                            position_percent=position)
            
            return result
            
        except Exception as e:
            print(f"   ❌ 52周高低位获取失败: {e}")
            debug_logger.error("52周高低位获取失败", error=e, symbol=symbol)
            import traceback
            traceback.print_exc()
            return result
    
    def get_sector_fund_flow(self, symbol: str) -> Dict[str, Any]:
        """获取股票所属板块/行业的资金流向数据
        
        Args:
            symbol: 股票代码
            
        Returns:
            dict: 板块/行业资金流向数据
        """
        debug_logger.info("开始获取板块资金流向", symbol=symbol)
        print(f"📊 [UnifiedDataAccess] 正在获取 {symbol} 的板块/行业资金流向数据...")
        
        result = {
            'success': False,
            'symbol': symbol,
            'sector_name': None,
            'sector_data': None,  # 板块数据
            'industry_data': None,  # 行业数据
        }
        
        if not data_source_manager.tushare_available:
            print(f"   ⚠️ Tushare不可用，无法获取板块资金流向")
            debug_logger.warning("Tushare不可用，无法获取板块资金流向", symbol=symbol)
            return result
        
        try:
            # 步骤1: 获取股票所属行业
            print(f"   [Tushare] 获取股票基本信息...")
            ts_code = self._convert_to_ts_code(symbol)
            
            with network_optimizer.apply():
                df_basic = data_source_manager.tushare_api.stock_basic(
                    ts_code=ts_code,
                    fields='ts_code,name,industry'
                )
            
            if df_basic is None or df_basic.empty:
                print(f"   ⚠️ 无法获取股票行业信息")
                debug_logger.warning("无法获取股票行业信息", symbol=symbol)
                return result
            
            industry = df_basic.iloc[0]['industry']
            result['sector_name'] = industry
            print(f"   ℹ️ 所属行业: {industry}")
            
            # 步骤2: 获取行业资金流向（Tushare moneyflow_ind_ths）
            print(f"   [Tushare] 获取行业资金流向（moneyflow_ind_ths接口）...")
            
            try:
                # 尝试获取今天的数据
                trade_date = datetime.now().strftime('%Y%m%d')
                with network_optimizer.apply():
                    df_ind = data_source_manager.tushare_api.moneyflow_ind_ths(
                        trade_date=trade_date
                    )
                
                # 如果今天数据未更新，尝试前一天
                if df_ind is None or df_ind.empty:
                    print(f"   ℹ️ 今日数据未更新，尝试前一交易日...")
                    trade_date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
                    with network_optimizer.apply():
                        df_ind = data_source_manager.tushare_api.moneyflow_ind_ths(
                            trade_date=trade_date
                        )
                
                if df_ind is not None and not df_ind.empty:
                    print(f"   ℹ️ 获取 {len(df_ind)} 个行业数据")
                    
                    # 查找匹配的行业
                    if 'industry' in df_ind.columns:
                        matched = df_ind[df_ind['industry'].str.contains(industry, na=False)]
                        
                        if not matched.empty:
                            result['success'] = True
                            result['industry_data'] = matched.iloc[0].to_dict()
                            print(f"   ✅ 找到{industry}行业资金流向数据")
                            if 'net_amount' in result['industry_data']:
                                print(f"     净额: {result['industry_data']['net_amount']}亿元")
                            debug_logger.info("行业资金流向获取成功", 
                                            symbol=symbol, 
                                            industry=industry,
                                            net_amount=result['industry_data'].get('net_amount'))
                            return result
                        else:
                            print(f"   ℹ️ 未找到{industry}行业的精确匹配")
                            # 返回所有行业数据供参考
                            result['success'] = True
                            result['industry_data'] = df_ind.to_dict('records')
                            print(f"   ✅ 返回所有行业资金流向数据")
                            return result
                    else:
                        # 如果没有industry列，返回所有数据
                        result['success'] = True
                        result['industry_data'] = df_ind.to_dict('records')
                        print(f"   ✅ 返回行业资金流向数据")
                        return result
                else:
                    print(f"   ℹ️ Tushare行业资金流向数据未更新")
                    
            except Exception as e:
                debug_logger.warning("Tushare行业资金流向获取失败", error=e, symbol=symbol)
                print(f"   ⚠️ 行业资金流向获取失败: {e}")
            
            # 步骤3: 尝试获取板块资金流向（Tushare moneyflow_cnt_ths）
            print(f"   [Tushare] 获取板块资金流向（moneyflow_cnt_ths接口）...")
            
            try:
                trade_date = datetime.now().strftime('%Y%m%d')
                with network_optimizer.apply():
                    df_cnt = data_source_manager.tushare_api.moneyflow_cnt_ths(
                        trade_date=trade_date
                    )
                
                if df_cnt is None or df_cnt.empty:
                    trade_date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
                    with network_optimizer.apply():
                        df_cnt = data_source_manager.tushare_api.moneyflow_cnt_ths(
                            trade_date=trade_date
                        )
                
                if df_cnt is not None and not df_cnt.empty:
                    print(f"   ✅ 获取 {len(df_cnt)} 个板块数据")
                    result['success'] = True
                    result['sector_data'] = df_cnt.to_dict('records')
                    debug_logger.info("板块资金流向获取成功", symbol=symbol, count=len(df_cnt))
                    return result
                    
            except Exception as e:
                debug_logger.warning("Tushare板块资金流向获取失败", error=e, symbol=symbol)
                print(f"   ⚠️ 板块资金流向获取失败: {e}")
            
            return result
            
        except Exception as e:
            print(f"   ❌ 板块资金流向获取失败: {e}")
            debug_logger.error("板块资金流向获取失败", error=e, symbol=symbol)
            import traceback
            traceback.print_exc()
            return result

    # ========== 方案2：增强研报功能 ==========
    
    def _analyze_research_reports_from_surv(self, df_reports: pd.DataFrame) -> Dict[str, Any]:
        """分析机构调研数据（stk_surv接口）
        
        Args:
            df_reports: 机构调研数据DataFrame
            
        Returns:
            调研分析结果，包含统计分析
        """
        if df_reports is None or df_reports.empty:
            return {
                'total_reports': 0,
                'reports_data': [],
                'summary': {}
            }
        
        analysis = {
            'total_reports': len(df_reports),
            'reports_data': [],
            'summary': {}
        }
        
        # 获取可能的字段名（处理不同版本的字段名）
        date_col = None
        org_col = None
        visitor_col = None
        type_col = None
        title_col = None
        
        for col in df_reports.columns:
            col_lower = col.lower()
            if 'date' in col_lower and date_col is None:
                date_col = col
            elif 'org' in col_lower and org_col is None:
                org_col = col
            elif 'visitor' in col_lower or 'vis' in col_lower:
                visitor_col = col
            elif 'type' in col_lower and type_col is None:
                type_col = col
            elif 'title' in col_lower or 'name' in col_lower:
                title_col = col
        
        # 处理每条调研数据
        for idx, row in df_reports.iterrows():
            report_data = {
                'trade_date': str(row.get(date_col or 'trade_date', '')),
                'title': str(row.get(title_col or 'title', '机构调研')),
                'org_name': str(row.get(org_col or 'org_name', row.get('vis_org', ''))),
                'visitors': str(row.get(visitor_col or 'visitor', row.get('visitors', ''))),
                'rating': 'N/A',  # 机构调研数据通常没有评级
                'target_price': 'N/A',  # 机构调研数据通常没有目标价
                'organ_type': str(row.get(type_col or 'organ_type', '')),
                'vis_time': str(row.get('vis_time', '')),
                'vis_type': str(row.get('vis_type', '')),
            }
            analysis['reports_data'].append(report_data)
        
        # 统计分析
        if len(df_reports) > 0:
            # 机构统计
            org_col_actual = org_col or 'org_name'
            if org_col_actual in df_reports.columns:
                org_counts = df_reports[org_col_actual].value_counts()
                analysis['summary']['top_institutions'] = org_counts.head(10).to_dict()
            elif 'vis_org' in df_reports.columns:
                org_counts = df_reports['vis_org'].value_counts()
                analysis['summary']['top_institutions'] = org_counts.head(10).to_dict()
            
            # 机构类型统计
            type_col_actual = type_col or 'organ_type'
            if type_col_actual in df_reports.columns:
                type_counts = df_reports[type_col_actual].value_counts()
                analysis['summary']['organ_type_distribution'] = type_counts.to_dict()
            
            # 调研类型统计
            if 'vis_type' in df_reports.columns:
                vis_type_counts = df_reports['vis_type'].value_counts()
                analysis['summary']['vis_type_distribution'] = vis_type_counts.to_dict()
            
            # 时间分布统计（按月份）
            date_col_actual = date_col or 'trade_date'
            if date_col_actual in df_reports.columns:
                try:
                    # 提取年月信息
                    df_reports['year_month'] = df_reports[date_col_actual].astype(str).str[:6]
                    month_counts = df_reports['year_month'].value_counts().sort_index()
                    analysis['summary']['monthly_distribution'] = month_counts.to_dict()
                except:
                    pass
            
            # 最新调研信息
            if len(df_reports) > 0:
                latest_report = df_reports.iloc[0]
                analysis['summary']['latest_survey'] = {
                    'date': str(latest_report.get(date_col_actual, '')),
                    'org': str(latest_report.get(org_col_actual, latest_report.get('vis_org', ''))),
                    'visitors': str(latest_report.get(visitor_col or 'visitor', '')),
                    'type': str(latest_report.get(type_col_actual, ''))
                }
            
            # 统计信息
            analysis['summary']['total_count'] = len(df_reports)
            if org_col_actual in df_reports.columns:
                analysis['summary']['unique_orgs'] = len(df_reports[org_col_actual].dropna().unique())
            elif 'vis_org' in df_reports.columns:
                analysis['summary']['unique_orgs'] = len(df_reports['vis_org'].dropna().unique())
            else:
                analysis['summary']['unique_orgs'] = 0
        
        return analysis
    
    def _analyze_research_reports(self, df_reports: pd.DataFrame) -> Dict[str, Any]:
        """分析研报数据（增强版）
        
        Args:
            df_reports: 研报数据DataFrame
            
        Returns:
            研报分析结果，包含统计分析
        """
        if df_reports is None or df_reports.empty:
            return {
                'total_reports': 0,
                'reports_data': [],
                'summary': {}
            }
        
        analysis = {
            'total_reports': len(df_reports),
            'reports_data': [],
            'summary': {}
        }
        
        # 处理每条研报数据（包含内容）
        all_contents = []  # 收集所有研报内容用于整体分析
        
        # 打印列名以便调试
        if len(df_reports) > 0:
            debug_logger.debug(f"report_rc接口返回的列名: {df_reports.columns.tolist()}")
        
        for idx, row in df_reports.iterrows():
            # 获取研报内容
            # 注意：Tushare report_rc接口不提供研报完整内容，只提供标题、评级、目标价等元数据
            # 如果需要完整研报内容，需要使用其他数据源或接口
            content = ''  # report_rc接口没有content字段
            
            # 生成内容摘要（如果内容太长，进行截取）
            content_summary = ''
            if content:
                # 如果内容超过500字符，取前500字符作为摘要
                if len(content) > 500:
                    content_summary = content[:500] + '...'
                else:
                    content_summary = content
                all_contents.append(content)
            
            report_data = {
                'report_date': str(row.get('report_date', '')),
                'report_title': str(row.get('report_title', '')),
                'org_name': str(row.get('org_name', '')),
                'author_name': str(row.get('author_name', '')),
                'rating': str(row.get('rating', '')),
                'report_type': str(row.get('report_type', '')),
                'classify': str(row.get('classify', '')),
                'quarter': str(row.get('quarter', '')),
                'target_price_max': row.get('max_price'),
                'target_price_min': row.get('min_price'),
                'op_rt': row.get('op_rt'),  # 营业收入
                'op_pr': row.get('op_pr'),  # 营业利润
                'np': row.get('np'),        # 净利润
                'eps': row.get('eps'),      # 每股收益
                'pe': row.get('pe'),        # 市盈率
                'roe': row.get('roe'),      # 净资产收益率
                'ev_ebitda': row.get('ev_ebitda'),  # 企业价值倍数
                'content': content,  # 完整研报内容
                'content_summary': content_summary,  # 内容摘要
            }
            analysis['reports_data'].append(report_data)
        
        # 对研报内容进行整体分析
        if all_contents:
            analysis['content_analysis'] = self._analyze_research_content(all_contents)
        
        # 统计分析
        if len(df_reports) > 0:
            # 机构统计
            if 'org_name' in df_reports.columns:
                org_counts = df_reports['org_name'].value_counts()
                analysis['summary']['top_institutions'] = org_counts.head(5).to_dict()
            
            # 评级统计（增强：计算买入/中性/卖出比例）
            if 'rating' in df_reports.columns:
                rating_counts = df_reports['rating'].value_counts()
                analysis['summary']['rating_distribution'] = rating_counts.to_dict()
                
                # 计算买入/中性/卖出比例
                total = len(df_reports)
                buy_count = sum(1 for r in rating_counts.index 
                              if any(keyword in str(r) for keyword in ['买入', '增持', '推荐', '强推']))
                neutral_count = sum(1 for r in rating_counts.index 
                                  if any(keyword in str(r) for keyword in ['持有', '中性', '观望']))
                sell_count = sum(1 for r in rating_counts.index 
                               if any(keyword in str(r) for keyword in ['卖出', '减持', '回避']))
                
                analysis['summary']['rating_ratio'] = {
                    'buy_ratio': round(buy_count / total * 100, 2) if total > 0 else 0,
                    'neutral_ratio': round(neutral_count / total * 100, 2) if total > 0 else 0,
                    'sell_ratio': round(sell_count / total * 100, 2) if total > 0 else 0,
                }
            
            # 目标价格统计
            if 'max_price' in df_reports.columns:
                max_prices = df_reports['max_price'].dropna()
                if not max_prices.empty:
                    analysis['summary']['target_price_stats'] = {
                        'max': float(max_prices.max()),
                        'min': float(max_prices.min()),
                        'avg': float(max_prices.mean()),
                        'count': len(max_prices)
                    }
            elif 'min_price' in df_reports.columns:
                min_prices = df_reports['min_price'].dropna()
                if not min_prices.empty:
                    analysis['summary']['target_price_stats'] = {
                        'max': float(min_prices.max()),
                        'min': float(min_prices.min()),
                        'avg': float(min_prices.mean()),
                        'count': len(min_prices)
                    }
            
            # 财务指标统计
            for col in ['eps', 'pe', 'roe']:
                if col in df_reports.columns:
                    values = df_reports[col].dropna()
                    if not values.empty:
                        analysis['summary'][f'{col}_stats'] = {
                            'max': float(values.max()),
                            'min': float(values.min()),
                            'avg': float(values.mean())
                        }
            
            # 最新研报信息
            if len(df_reports) > 0:
                latest_report = df_reports.iloc[0]
                analysis['summary']['latest_report'] = {
                    'date': str(latest_report.get('report_date', '')),
                    'title': str(latest_report.get('report_title', '')),
                    'org': str(latest_report.get('org_name', '')),
                    'rating': str(latest_report.get('rating', '')),
                    'target_price': latest_report.get('max_price') or latest_report.get('min_price')
                }
        
        # 如果没有内容分析，初始化为空字典
        if 'content_analysis' not in analysis:
            analysis['content_analysis'] = {}
        
        return analysis
    
    def _analyze_research_content(self, contents: list) -> Dict[str, Any]:
        """分析研报内容
        
        Args:
            contents: 研报内容列表
            
        Returns:
            内容分析结果
        """
        if not contents:
            return {
                'has_content': False,
                'total_length': 0,
                'avg_length': 0,
                'key_topics': [],
                'sentiment_analysis': {}
            }
        
        # 合并所有内容
        combined_content = ' '.join([c for c in contents if c])
        total_length = len(combined_content)
        avg_length = total_length / len(contents) if contents else 0
        
        # 提取关键词（简单方法：根据常见关键词）
        key_topics = []
        common_keywords = [
            '增长', '业绩', '盈利', '收入', '净利润', 'EPS', 'ROE', '估值',
            '买入', '持有', '推荐', '目标价', '风险', '机会', '前景',
            '行业', '市场', '竞争', '优势', '创新', '转型', '扩张'
        ]
        
        content_lower = combined_content.lower()
        for keyword in common_keywords:
            if keyword in content_lower:
                key_topics.append(keyword)
        
        # 情感倾向分析（简单统计）
        positive_words = ['增长', '提升', '改善', '利好', '看好', '买入', '推荐', '机会', '优势']
        negative_words = ['下降', '下滑', '风险', '担忧', '卖出', '减持', '挑战', '困难']
        
        positive_count = sum(1 for word in positive_words if word in content_lower)
        negative_count = sum(1 for word in negative_words if word in content_lower)
        
        sentiment = 'neutral'
        if positive_count > negative_count * 1.5:
            sentiment = 'positive'
        elif negative_count > positive_count * 1.5:
            sentiment = 'negative'
        
        return {
            'has_content': True,
            'total_reports_with_content': len([c for c in contents if c]),
            'total_length': total_length,
            'avg_length': round(avg_length, 0),
            'key_topics': key_topics[:10],  # 前10个关键词
            'sentiment_analysis': {
                'sentiment': sentiment,
                'positive_signals': positive_count,
                'negative_signals': negative_count,
                'sentiment_score': round((positive_count - negative_count) / max(positive_count + negative_count, 1) * 100, 2)
            }
        }
    
    def _analyze_chip_changes(self, perf_data: list, current_price: float = None) -> Dict[str, Any]:
        """分析过去30天筹码分布变化，判断主力资金行为
        
        Args:
            perf_data: cyq_perf数据列表（按日期排序）
            current_price: 当前股价（可选，用于判断相对位置）
            
        Returns:
            筹码变化分析结果
        """
        if not perf_data or len(perf_data) < 2:
            return None
        
        try:
            # 确保数据按日期排序（最早的在前）
            sorted_data = sorted(perf_data, key=lambda x: str(x.get('trade_date', '')), reverse=False)
            earliest = sorted_data[0]  # 30天前
            latest = sorted_data[-1]  # 最新
            
            analysis = {
                'period': f"{earliest.get('trade_date', 'N/A')} 至 {latest.get('trade_date', 'N/A')}",
                'days_count': len(sorted_data),
                'cost_changes': {},
                'concentration_changes': {},
                'main_force_behavior': {},
                'chip_peak_analysis': {}
            }
            
            # 1. 成本价格变化
            cost_fields = ['cost_5pct', 'cost_15pct', 'cost_50pct', 'cost_85pct', 'cost_95pct', 'weight_avg']
            for field in cost_fields:
                earliest_val = earliest.get(field)
                latest_val = latest.get(field)
                if pd.notna(earliest_val) and pd.notna(latest_val):
                    try:
                        change = float(latest_val) - float(earliest_val)
                        change_pct = (change / float(earliest_val)) * 100 if float(earliest_val) > 0 else 0
                        analysis['cost_changes'][field] = {
                            'earliest': round(float(earliest_val), 2),
                            'latest': round(float(latest_val), 2),
                            'change': round(change, 2),
                            'change_pct': round(change_pct, 2)
                        }
                    except:
                        pass
            
            # 2. 筹码集中度变化
            def calc_concentration(record):
                """计算单日筹码集中度"""
                try:
                    cost_15 = float(record.get('cost_15pct', 0))
                    cost_85 = float(record.get('cost_85pct', 0))
                    cost_50 = float(record.get('cost_50pct', 0))
                    if cost_50 > 0:
                        range_pct = ((cost_85 - cost_15) / cost_50) * 100
                        if range_pct < 10:
                            return '高', range_pct
                        elif range_pct > 30:
                            return '低', range_pct
                        else:
                            return '中', range_pct
                except:
                    pass
                return None, None
            
            earliest_conc_level, earliest_conc_pct = calc_concentration(earliest)
            latest_conc_level, latest_conc_pct = calc_concentration(latest)
            
            if earliest_conc_level and latest_conc_level:
                analysis['concentration_changes'] = {
                    'earliest_level': earliest_conc_level,
                    'latest_level': latest_conc_level,
                    'earliest_pct': round(earliest_conc_pct, 2) if earliest_conc_pct else None,
                    'latest_pct': round(latest_conc_pct, 2) if latest_conc_pct else None,
                    'trend': '提升' if latest_conc_pct < earliest_conc_pct else '下降' if latest_conc_pct > earliest_conc_pct else '稳定'
                }
            
            # 3. 筹码峰移动分析（基于加权平均成本和50%成本）
            if 'cost_changes' in analysis and 'weight_avg' in analysis['cost_changes']:
                weight_avg_change = analysis['cost_changes']['weight_avg']['change']
                cost_50_change = analysis['cost_changes'].get('cost_50pct', {}).get('change', 0)
                
                # 判断筹码峰移动方向
                if weight_avg_change > 0 and cost_50_change > 0:
                    analysis['chip_peak_analysis']['peak_direction'] = '上移'
                    analysis['chip_peak_analysis']['peak_speed'] = '快速' if abs(weight_avg_change) > abs(cost_50_change) * 1.5 else '缓慢'
                elif weight_avg_change < 0 and cost_50_change < 0:
                    analysis['chip_peak_analysis']['peak_direction'] = '下移'
                    analysis['chip_peak_analysis']['peak_speed'] = '快速' if abs(weight_avg_change) > abs(cost_50_change) * 1.5 else '缓慢'
                else:
                    analysis['chip_peak_analysis']['peak_direction'] = '震荡'
                    analysis['chip_peak_analysis']['peak_speed'] = '不稳定'
            
            # 4. 主力资金行为判断（业界最佳实践）
            main_force_signals = []
            behavior_score = 0  # 正数表示吸筹，负数表示出货
            
            # 信号1: 成本集中度提升 + 低位成本增加 → 收集筹码
            if analysis['concentration_changes'].get('trend') == '提升':
                if latest_conc_level in ['高', '中']:
                    main_force_signals.append('集中度提升，可能主力收集筹码')
                    behavior_score += 2
            
            # 信号2: 加权平均成本下降 + 股价相对稳定 → 低位吸筹
            if 'weight_avg' in analysis['cost_changes']:
                weight_change = analysis['cost_changes']['weight_avg']['change']
                if weight_change < 0 and current_price:
                    try:
                        price_vs_cost = (float(current_price) - float(latest.get('weight_avg', 0))) / float(latest.get('weight_avg', 0)) * 100
                        if price_vs_cost < 10:  # 股价接近或低于平均成本
                            main_force_signals.append('平均成本下降且股价接近成本，可能低位吸筹')
                            behavior_score += 2
                    except:
                        pass
            
            # 信号3: 筹码峰上移 + 高位成本增加 → 获利出逃
            if analysis['chip_peak_analysis'].get('peak_direction') == '上移':
                if 'cost_85pct' in analysis['cost_changes'] and 'cost_15pct' in analysis['cost_changes']:
                    high_cost_increase = analysis['cost_changes']['cost_85pct']['change']
                    low_cost_change = analysis['cost_changes']['cost_15pct']['change']
                    if high_cost_increase > 0 and abs(high_cost_increase) > abs(low_cost_change) * 1.5:
                        main_force_signals.append('高位成本快速上升，筹码峰上移，可能获利出逃')
                        behavior_score -= 3
            
            # 信号4: 筹码集中度下降 + 成本区间扩大 → 散户接盘
            if analysis['concentration_changes'].get('trend') == '下降':
                if latest_conc_level == '低':
                    main_force_signals.append('集中度下降且区间扩大，可能散户接盘')
                    behavior_score -= 2
            
            # 信号5: 低位成本稳定 + 中位成本上移 → 洗盘后拉升
            if 'cost_5pct' in analysis['cost_changes'] and 'cost_50pct' in analysis['cost_changes']:
                low_stable = abs(analysis['cost_changes']['cost_5pct']['change']) < abs(analysis['cost_changes']['cost_5pct']['earliest']) * 0.1
                mid_up = analysis['cost_changes']['cost_50pct']['change'] > 0
                if low_stable and mid_up:
                    main_force_signals.append('低位成本稳定，中位成本上移，可能洗盘后拉升')
                    behavior_score += 1
            
            # 综合判断主力行为
            if behavior_score >= 3:
                main_force_judgment = '收集低价筹码'
                main_force_confidence = '高'
            elif behavior_score >= 1:
                main_force_judgment = '可能收集筹码'
                main_force_confidence = '中'
            elif behavior_score <= -3:
                main_force_judgment = '获利出逃'
                main_force_confidence = '高'
            elif behavior_score <= -1:
                main_force_judgment = '可能获利了结'
                main_force_confidence = '中'
            else:
                main_force_judgment = '震荡整理'
                main_force_confidence = '低'
            
            analysis['main_force_behavior'] = {
                'judgment': main_force_judgment,
                'confidence': main_force_confidence,
                'score': behavior_score,
                'signals': main_force_signals,
                'description': self._generate_main_force_description(main_force_judgment, main_force_signals, analysis)
            }
            
            return analysis
            
        except Exception as e:
            debug_logger.warning(f"筹码变化分析失败", error=e)
            import traceback
            traceback.print_exc()
            return None
    
    def _generate_main_force_description(self, judgment: str, signals: list, analysis: dict) -> str:
        """生成主力行为描述文本"""
        desc = f"主力行为判断: {judgment}\n"
        desc += f"置信度: {analysis['main_force_behavior'].get('confidence', 'N/A')}\n\n"
        
        if signals:
            desc += "关键信号:\n"
            for i, signal in enumerate(signals, 1):
                desc += f"{i}. {signal}\n"
        
        desc += f"\n筹码峰变化: {analysis['chip_peak_analysis'].get('peak_direction', 'N/A')} "
        desc += f"({analysis['chip_peak_analysis'].get('peak_speed', 'N/A')})\n"
        
        if 'cost_changes' in analysis and 'weight_avg' in analysis['cost_changes']:
            change_info = analysis['cost_changes']['weight_avg']
            desc += f"平均成本变化: {change_info['change']:+.2f} ({change_info['change_pct']:+.2f}%)\n"
        
        if 'concentration_changes' in analysis:
            conc = analysis['concentration_changes']
            desc += f"集中度变化: {conc.get('earliest_level', 'N/A')} → {conc.get('latest_level', 'N/A')} ({conc.get('trend', 'N/A')})"
        
        return desc


unified_data_access = UnifiedDataAccess()


