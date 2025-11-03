#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Tushare对北交所股票数据的支持
使用统一数据访问接口，不修改程序
"""

import sys
import io
from datetime import datetime, timedelta
from typing import Dict, Any

# 设置UTF-8编码输出（Windows兼容）
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from unified_data_access import UnifiedDataAccess
from debug_logger import debug_logger

# 北交所测试股票列表（8开头或4开头）
BSE_TEST_STOCKS = [
    "830001",  # 大地股份（示例）
    "832149",  # 同辉信息（示例）
    "830946",  # 森萱医药（示例）
    "830779",  # 沃捷传媒（示例）
    "430047",  # 诺思兰德（示例，4开头）
]


def test_stock_basic_info(symbol: str, fetcher: UnifiedDataAccess) -> Dict[str, Any]:
    """测试获取股票基本信息"""
    print(f"\n{'='*60}")
    print(f"📊 测试1: 获取基本信息 - {symbol}")
    print(f"{'='*60}")
    
    try:
        start_time = datetime.now()
        info = fetcher.get_stock_basic_info(symbol)
        elapsed = (datetime.now() - start_time).total_seconds()
        
        if info:
            print(f"✅ 成功获取基本信息 (耗时: {elapsed:.2f}秒)")
            print(f"   代码: {info.get('symbol', 'N/A')}")
            print(f"   名称: {info.get('name', 'N/A')}")
            print(f"   行业: {info.get('industry', 'N/A')}")
            print(f"   市场: {info.get('market', 'N/A')}")
            return {"success": True, "data": info, "elapsed": elapsed}
        else:
            print(f"❌ 获取基本信息失败: 返回None或空")
            return {"success": False, "error": "返回None或空", "elapsed": elapsed}
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"❌ 获取基本信息异常: {error_type} - {error_msg}")
        debug_logger.error("测试基本信息失败", symbol=symbol, error_type=error_type, error_message=error_msg)
        return {"success": False, "error": f"{error_type}: {error_msg}", "elapsed": 0}


def test_stock_info(symbol: str, fetcher: UnifiedDataAccess) -> Dict[str, Any]:
    """测试获取股票完整信息（包含实时行情、估值等）"""
    print(f"\n{'='*60}")
    print(f"📊 测试2: 获取完整信息 - {symbol}")
    print(f"{'='*60}")
    
    try:
        start_time = datetime.now()
        info = fetcher.get_stock_info(symbol)
        elapsed = (datetime.now() - start_time).total_seconds()
        
        if info:
            print(f"✅ 成功获取完整信息 (耗时: {elapsed:.2f}秒)")
            print(f"   代码: {info.get('symbol', 'N/A')}")
            print(f"   名称: {info.get('name', 'N/A')}")
            print(f"   当前价格: {info.get('current_price', 'N/A')}")
            print(f"   涨跌幅: {info.get('change_percent', 'N/A')}")
            print(f"   市盈率: {info.get('pe_ratio', 'N/A')}")
            print(f"   市净率: {info.get('pb_ratio', 'N/A')}")
            print(f"   市值: {info.get('market_cap', 'N/A')}")
            print(f"   Beta系数: {info.get('beta', 'N/A')}")
            print(f"   52周最高: {info.get('52_week_high', 'N/A')}")
            print(f"   52周最低: {info.get('52_week_low', 'N/A')}")
            return {"success": True, "data": info, "elapsed": elapsed}
        else:
            print(f"❌ 获取完整信息失败: 返回None或空")
            return {"success": False, "error": "返回None或空", "elapsed": elapsed}
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"❌ 获取完整信息异常: {error_type} - {error_msg}")
        debug_logger.error("测试完整信息失败", symbol=symbol, error_type=error_type, error_message=error_msg)
        return {"success": False, "error": f"{error_type}: {error_msg}", "elapsed": 0}


def test_stock_hist_data(symbol: str, fetcher: UnifiedDataAccess) -> Dict[str, Any]:
    """测试获取历史K线数据"""
    print(f"\n{'='*60}")
    print(f"📊 测试3: 获取历史K线数据 - {symbol}")
    print(f"{'='*60}")
    
    try:
        # 获取最近30天的数据
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
        
        start_time = datetime.now()
        df = fetcher.get_stock_hist_data(symbol, start_date=start_date, end_date=end_date)
        elapsed = (datetime.now() - start_time).total_seconds()
        
        if df is not None and not df.empty:
            print(f"✅ 成功获取历史K线数据 (耗时: {elapsed:.2f}秒)")
            print(f"   数据条数: {len(df)}")
            print(f"   日期范围: {df.index[0] if hasattr(df.index[0], 'strftime') else str(df.index[0])} 至 {df.index[-1] if hasattr(df.index[-1], 'strftime') else str(df.index[-1])}")
            if 'close' in df.columns or '收盘' in df.columns:
                close_col = 'close' if 'close' in df.columns else '收盘'
                latest_close = df[close_col].iloc[-1]
                print(f"   最新收盘价: {latest_close}")
            return {"success": True, "data_count": len(df), "elapsed": elapsed}
        else:
            print(f"❌ 获取历史K线数据失败: 返回None或空DataFrame")
            return {"success": False, "error": "返回None或空DataFrame", "elapsed": elapsed}
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"❌ 获取历史K线数据异常: {error_type} - {error_msg}")
        debug_logger.error("测试历史K线数据失败", symbol=symbol, error_type=error_type, error_message=error_msg)
        return {"success": False, "error": f"{error_type}: {error_msg}", "elapsed": 0}


def test_financial_data(symbol: str, fetcher: UnifiedDataAccess) -> Dict[str, Any]:
    """测试获取财务数据"""
    print(f"\n{'='*60}")
    print(f"📊 测试4: 获取财务数据 - {symbol}")
    print(f"{'='*60}")
    
    try:
        start_time = datetime.now()
        financial_data = fetcher.get_financial_data(symbol)
        elapsed = (datetime.now() - start_time).total_seconds()
        
        if financial_data and isinstance(financial_data, dict):
            print(f"✅ 成功获取财务数据 (耗时: {elapsed:.2f}秒)")
            # 显示部分财务数据
            if 'income_statement' in financial_data and financial_data['income_statement']:
                income_info = financial_data['income_statement']
                if isinstance(income_info, dict) and 'periods' in income_info:
                    print(f"   利润表数据: {income_info.get('periods', 0)} 条")
            if 'balance_sheet' in financial_data and financial_data['balance_sheet']:
                balance_info = financial_data['balance_sheet']
                if isinstance(balance_info, dict) and 'periods' in balance_info:
                    print(f"   资产负债表数据: {balance_info.get('periods', 0)} 条")
            if 'cash_flow' in financial_data and financial_data['cash_flow']:
                cashflow_info = financial_data['cash_flow']
                if isinstance(cashflow_info, dict) and 'periods' in cashflow_info:
                    print(f"   现金流量表数据: {cashflow_info.get('periods', 0)} 条")
            return {"success": True, "elapsed": elapsed}
        else:
            print(f"❌ 获取财务数据失败: 返回None或非字典类型")
            return {"success": False, "error": "返回None或非字典类型", "elapsed": elapsed}
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"❌ 获取财务数据异常: {error_type} - {error_msg}")
        debug_logger.error("测试财务数据失败", symbol=symbol, error_type=error_type, error_message=error_msg)
        return {"success": False, "error": f"{error_type}: {error_msg}", "elapsed": 0}


def test_research_reports(symbol: str, fetcher: UnifiedDataAccess) -> Dict[str, Any]:
    """测试获取研报数据"""
    print(f"\n{'='*60}")
    print(f"📊 测试5: 获取研报数据 - {symbol}")
    print(f"{'='*60}")
    
    try:
        start_time = datetime.now()
        research_data = fetcher.get_research_reports_data(symbol, days=180)
        elapsed = (datetime.now() - start_time).total_seconds()
        
        if research_data and isinstance(research_data, dict):
            count = research_data.get('count', 0)
            if count > 0:
                print(f"✅ 成功获取研报数据 (耗时: {elapsed:.2f}秒)")
                print(f"   研报数量: {count}")
                reports = research_data.get('reports', [])
                if reports:
                    print(f"   最新研报: {reports[0].get('title', 'N/A')[:50]}...")
                return {"success": True, "count": count, "elapsed": elapsed}
            else:
                print(f"⚠️ 研报数据为空 (耗时: {elapsed:.2f}秒)")
                return {"success": True, "count": 0, "elapsed": elapsed, "note": "数据为空"}
        else:
            print(f"❌ 获取研报数据失败: 返回None或非字典类型")
            return {"success": False, "error": "返回None或非字典类型", "elapsed": elapsed}
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"❌ 获取研报数据异常: {error_type} - {error_msg}")
        debug_logger.error("测试研报数据失败", symbol=symbol, error_type=error_type, error_message=error_msg)
        return {"success": False, "error": f"{error_type}: {error_msg}", "elapsed": 0}


def test_announcement_data(symbol: str, fetcher: UnifiedDataAccess) -> Dict[str, Any]:
    """测试获取公告数据"""
    print(f"\n{'='*60}")
    print(f"📊 测试6: 获取公告数据 - {symbol}")
    print(f"{'='*60}")
    
    try:
        start_time = datetime.now()
        announcement_data = fetcher.get_announcement_data(symbol, days=30)
        elapsed = (datetime.now() - start_time).total_seconds()
        
        if announcement_data and isinstance(announcement_data, dict):
            count = len(announcement_data.get('announcements', []))
            if count > 0:
                print(f"✅ 成功获取公告数据 (耗时: {elapsed:.2f}秒)")
                print(f"   公告数量: {count}")
                announcements = announcement_data.get('announcements', [])
                if announcements:
                    print(f"   最新公告: {announcements[0].get('title', 'N/A')[:50]}...")
                return {"success": True, "count": count, "elapsed": elapsed}
            else:
                print(f"⚠️ 公告数据为空 (耗时: {elapsed:.2f}秒)")
                return {"success": True, "count": 0, "elapsed": elapsed, "note": "数据为空"}
        else:
            print(f"❌ 获取公告数据失败: 返回None或非字典类型")
            return {"success": False, "error": "返回None或非字典类型", "elapsed": elapsed}
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"❌ 获取公告数据异常: {error_type} - {error_msg}")
        debug_logger.error("测试公告数据失败", symbol=symbol, error_type=error_type, error_message=error_msg)
        return {"success": False, "error": f"{error_type}: {error_msg}", "elapsed": 0}


def test_chip_distribution(symbol: str, fetcher: UnifiedDataAccess) -> Dict[str, Any]:
    """测试获取筹码分布数据"""
    print(f"\n{'='*60}")
    print(f"📊 测试7: 获取筹码分布数据 - {symbol}")
    print(f"{'='*60}")
    
    try:
        # 先获取当前价格
        stock_info = fetcher.get_stock_info(symbol)
        current_price = stock_info.get('current_price') if stock_info else None
        if isinstance(current_price, str) and current_price == 'N/A':
            current_price = None
        
        start_time = datetime.now()
        chip_data = fetcher.get_chip_distribution_data(symbol, current_price=current_price)
        elapsed = (datetime.now() - start_time).total_seconds()
        
        if chip_data and isinstance(chip_data, dict):
            print(f"✅ 成功获取筹码分布数据 (耗时: {elapsed:.2f}秒)")
            summary = chip_data.get('summary', {})
            if summary:
                print(f"   筹码集中度: {summary.get('concentration', 'N/A')}")
                print(f"   平均成本: {summary.get('avg_cost', 'N/A')}")
                print(f"   成本区间: {summary.get('cost_range', 'N/A')}")
            return {"success": True, "elapsed": elapsed}
        else:
            print(f"❌ 获取筹码分布数据失败: 返回None或非字典类型")
            return {"success": False, "error": "返回None或非字典类型", "elapsed": elapsed}
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"❌ 获取筹码分布数据异常: {error_type} - {error_msg}")
        debug_logger.error("测试筹码分布数据失败", symbol=symbol, error_type=error_type, error_message=error_msg)
        return {"success": False, "error": f"{error_type}: {error_msg}", "elapsed": 0}


def run_single_stock_test(symbol: str, fetcher: UnifiedDataAccess) -> Dict[str, Any]:
    """对单只股票运行所有测试"""
    print(f"\n{'#'*80}")
    print(f"# 测试股票: {symbol}")
    print(f"{'#'*80}")
    
    results = {
        "symbol": symbol,
        "tests": {}
    }
    
    # 测试1: 基本信息
    results["tests"]["basic_info"] = test_stock_basic_info(symbol, fetcher)
    
    # 测试2: 完整信息
    results["tests"]["stock_info"] = test_stock_info(symbol, fetcher)
    
    # 测试3: 历史K线数据
    results["tests"]["hist_data"] = test_stock_hist_data(symbol, fetcher)
    
    # 测试4: 财务数据
    results["tests"]["financial_data"] = test_financial_data(symbol, fetcher)
    
    # 测试5: 研报数据
    results["tests"]["research_reports"] = test_research_reports(symbol, fetcher)
    
    # 测试6: 公告数据
    results["tests"]["announcement_data"] = test_announcement_data(symbol, fetcher)
    
    # 测试7: 筹码分布数据
    results["tests"]["chip_distribution"] = test_chip_distribution(symbol, fetcher)
    
    return results


def print_summary(all_results: list):
    """打印测试结果汇总"""
    print(f"\n\n{'='*80}")
    print(f"📊 测试结果汇总")
    print(f"{'='*80}")
    
    # 统计总体成功率
    total_tests = 0
    successful_tests = 0
    
    test_names = {
        "basic_info": "基本信息",
        "stock_info": "完整信息",
        "hist_data": "历史K线",
        "financial_data": "财务数据",
        "research_reports": "研报数据",
        "announcement_data": "公告数据",
        "chip_distribution": "筹码分布"
    }
    
    for result in all_results:
        symbol = result["symbol"]
        print(f"\n股票代码: {symbol}")
        print("-" * 80)
        
        for test_key, test_result in result["tests"].items():
            total_tests += 1
            test_name = test_names.get(test_key, test_key)
            if test_result.get("success"):
                successful_tests += 1
                elapsed = test_result.get("elapsed", 0)
                status = "✅ 成功"
                if test_result.get("note"):
                    status += f" ({test_result.get('note')})"
                print(f"  {test_name:15s}: {status:20s} (耗时: {elapsed:.2f}秒)")
            else:
                error = test_result.get("error", "未知错误")
                print(f"  {test_name:15s}: ❌ 失败 - {error[:50]}")
    
    print(f"\n{'='*80}")
    print(f"总体统计:")
    print(f"  测试股票数: {len(all_results)}")
    print(f"  测试项总数: {total_tests}")
    print(f"  成功项数: {successful_tests}")
    print(f"  失败项数: {total_tests - successful_tests}")
    if total_tests > 0:
        success_rate = (successful_tests / total_tests) * 100
        print(f"  成功率: {success_rate:.1f}%")
    print(f"{'='*80}")


def main():
    """主函数"""
    print(f"\n{'='*80}")
    print(f"🧪 Tushare北交所股票数据支持测试")
    print(f"{'='*80}")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试股票: {', '.join(BSE_TEST_STOCKS)}")
    print(f"\n说明:")
    print(f"  本测试使用统一数据访问接口(UnifiedDataAccess)验证Tushare对北交所股票数据的支持")
    print(f"  北交所股票代码通常以8或4开头，转换为ts_code时会加上.BJ后缀")
    print(f"{'='*80}")
    
    # 初始化统一数据访问接口
    fetcher = UnifiedDataAccess()
    
    # 运行所有测试
    all_results = []
    for symbol in BSE_TEST_STOCKS:
        try:
            result = run_single_stock_test(symbol, fetcher)
            all_results.append(result)
        except Exception as e:
            print(f"\n❌ 测试股票 {symbol} 时发生异常: {type(e).__name__} - {str(e)}")
            debug_logger.error("股票测试异常", symbol=symbol, error_type=type(e).__name__, error_message=str(e))
        finally:
            print("\n")  # 添加分隔
    
    # 打印汇总
    print_summary(all_results)
    
    print(f"\n测试完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"详细日志请查看: debug.log")


if __name__ == "__main__":
    main()

