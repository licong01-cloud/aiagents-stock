#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全面测试Tushare和AKShare对北交所股票数据的支持情况
参考文档：
- Tushare: https://tushare.pro/document/
- AKShare: https://akshare.akfamily.xyz/data/index.html
"""

import sys
import io
from datetime import datetime, timedelta
import pandas as pd
import traceback

# 设置UTF-8编码输出（Windows兼容）
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 导入数据源
import akshare as ak
from data_source_manager import data_source_manager
from unified_data_access import UnifiedDataAccess
from debug_logger import debug_logger

# 北交所测试股票列表
BSE_TEST_STOCKS = [
    "830001",  # 大地股份
    "832149",  # 利尔达
    "830946",  # 森萱医药
    "830779",  # 武汉蓝电
    "430047",  # 诺思兰德（4开头）
]

def print_header(title: str):
    """打印标题"""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}")


def test_tushare_basic_info(symbol: str):
    """测试Tushare获取北交所股票基本信息"""
    print(f"\n[测试] Tushare - 基本信息 ({symbol})")
    try:
        ts_code = f"{symbol}.BJ"
        print(f"  转换后的ts_code: {ts_code}")
        
        if not data_source_manager.tushare_available:
            print(f"  ❌ Tushare未初始化")
            return {"success": False, "reason": "Tushare未初始化"}
        
        # 测试stock_basic接口
        try:
            df = data_source_manager.tushare_api.stock_basic(
                ts_code=ts_code,
                exchange='',
                list_status='L',
                fields='ts_code,symbol,name,area,industry,list_date'
            )
            if df is not None and not df.empty:
                print(f"  ✅ 成功获取基本信息")
                print(f"     {df.to_dict('records')[0]}")
                return {"success": True, "data": df}
            else:
                print(f"  ⚠️ 返回空数据")
                return {"success": False, "reason": "返回空数据"}
        except Exception as e:
            error_msg = str(e)
            print(f"  ❌ 获取失败: {error_msg}")
            return {"success": False, "reason": error_msg}
    except Exception as e:
        print(f"  ❌ 异常: {type(e).__name__} - {str(e)}")
        return {"success": False, "reason": str(e)}


def test_tushare_daily_data(symbol: str):
    """测试Tushare获取北交所股票日线数据"""
    print(f"\n[测试] Tushare - 日线数据 ({symbol})")
    try:
        ts_code = f"{symbol}.BJ"
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
        
        if not data_source_manager.tushare_available:
            print(f"  ❌ Tushare未初始化")
            return {"success": False, "reason": "Tushare未初始化"}
        
        try:
            df = data_source_manager.tushare_api.daily(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )
            if df is not None and not df.empty:
                print(f"  ✅ 成功获取日线数据: {len(df)} 条")
                print(f"     最新收盘价: {df.iloc[0]['close'] if len(df) > 0 else 'N/A'}")
                return {"success": True, "count": len(df), "data": df}
            else:
                print(f"  ⚠️ 返回空数据")
                return {"success": False, "reason": "返回空数据"}
        except Exception as e:
            error_msg = str(e)
            print(f"  ❌ 获取失败: {error_msg}")
            return {"success": False, "reason": error_msg}
    except Exception as e:
        print(f"  ❌ 异常: {type(e).__name__} - {str(e)}")
        return {"success": False, "reason": str(e)}


def test_akshare_spot_data(symbol: str):
    """测试AKShare获取北交所股票实时行情"""
    print(f"\n[测试] AKShare - 实时行情 ({symbol})")
    try:
        from network_optimizer import network_optimizer
        
        with network_optimizer.apply():
            # 方法1: 使用stock_zh_a_spot_em（包含京A股）
            try:
                df_all = ak.stock_zh_a_spot_em()
                if df_all is not None and not df_all.empty:
                    df_stock = df_all[df_all['代码'] == symbol]
                    if not df_stock.empty:
                        print(f"  ✅ 方法1(stock_zh_a_spot_em)成功: 找到股票数据")
                        print(f"     名称: {df_stock.iloc[0].get('名称', 'N/A')}")
                        print(f"     最新价: {df_stock.iloc[0].get('最新价', 'N/A')}")
                        return {"success": True, "method": "stock_zh_a_spot_em", "data": df_stock}
                    else:
                        print(f"  ⚠️ 方法1: 未在实时行情中找到该股票")
                else:
                    print(f"  ⚠️ 方法1: 返回空数据")
            except Exception as e:
                print(f"  ⚠️ 方法1失败: {str(e)}")
            
            # 方法2: 使用stock_individual_info_em（个股信息）
            try:
                df_info = ak.stock_individual_info_em(symbol=symbol)
                if df_info is not None and not df_info.empty:
                    print(f"  ✅ 方法2(stock_individual_info_em)成功")
                    print(f"     字段数: {len(df_info)}")
                    return {"success": True, "method": "stock_individual_info_em", "data": df_info}
                else:
                    print(f"  ⚠️ 方法2: 返回空数据")
            except Exception as e:
                print(f"  ⚠️ 方法2失败: {str(e)}")
            
            # 方法3: 使用stock_zh_a_hist（历史行情）
            try:
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
                df_hist = ak.stock_zh_a_hist(
                    symbol=symbol,
                    period="daily",
                    start_date=start_date.replace('-', ''),
                    end_date=end_date.replace('-', ''),
                    adjust=""
                )
                if df_hist is not None and not df_hist.empty:
                    print(f"  ✅ 方法3(stock_zh_a_hist)成功: {len(df_hist)} 条数据")
                    print(f"     最新收盘价: {df_hist.iloc[-1].get('收盘', 'N/A') if len(df_hist) > 0 else 'N/A'}")
                    return {"success": True, "method": "stock_zh_a_hist", "count": len(df_hist), "data": df_hist}
                else:
                    print(f"  ⚠️ 方法3: 返回空数据")
            except Exception as e:
                print(f"  ⚠️ 方法3失败: {str(e)}")
            
            return {"success": False, "reason": "所有方法均失败"}
    except Exception as e:
        error_msg = str(e)
        print(f"  ❌ 异常: {type(e).__name__} - {error_msg}")
        traceback.print_exc()
        return {"success": False, "reason": error_msg}


def test_akshare_financial_data(symbol: str):
    """测试AKShare获取北交所股票财务数据"""
    print(f"\n[测试] AKShare - 财务数据 ({symbol})")
    try:
        from network_optimizer import network_optimizer
        
        with network_optimizer.apply():
            # 测试资产负债表（北交所）
            try:
                df_balance = ak.stock_balance_sheet_by_report_em(
                    symbol=symbol
                )
                if df_balance is not None and not df_balance.empty:
                    print(f"  ✅ 资产负债表成功: {len(df_balance)} 条")
                    return {"success": True, "type": "balance_sheet", "count": len(df_balance)}
                else:
                    print(f"  ⚠️ 资产负债表为空")
            except Exception as e:
                print(f"  ⚠️ 资产负债表失败: {str(e)}")
            
            # 测试利润表
            try:
                df_income = ak.stock_profit_sheet_by_report_em(
                    symbol=symbol
                )
                if df_income is not None and not df_income.empty:
                    print(f"  ✅ 利润表成功: {len(df_income)} 条")
                    return {"success": True, "type": "income_statement", "count": len(df_income)}
                else:
                    print(f"  ⚠️ 利润表为空")
            except Exception as e:
                print(f"  ⚠️ 利润表失败: {str(e)}")
            
            # 测试现金流量表
            try:
                df_cashflow = ak.stock_cash_flow_sheet_by_report_em(
                    symbol=symbol
                )
                if df_cashflow is not None and not df_cashflow.empty:
                    print(f"  ✅ 现金流量表成功: {len(df_cashflow)} 条")
                    return {"success": True, "type": "cashflow", "count": len(df_cashflow)}
                else:
                    print(f"  ⚠️ 现金流量表为空")
            except Exception as e:
                print(f"  ⚠️ 现金流量表失败: {str(e)}")
            
            return {"success": False, "reason": "所有财务表均失败"}
    except Exception as e:
        error_msg = str(e)
        print(f"  ❌ 异常: {type(e).__name__} - {error_msg}")
        return {"success": False, "reason": error_msg}


def test_unified_access(symbol: str):
    """测试统一数据访问接口"""
    print(f"\n[测试] UnifiedDataAccess - 综合测试 ({symbol})")
    try:
        fetcher = UnifiedDataAccess()
        
        # 测试基本信息
        print(f"  [1] 测试基本信息...")
        basic_info = fetcher.get_stock_basic_info(symbol)
        if basic_info:
            print(f"      ✅ 成功: {basic_info.get('name', 'N/A')}")
        else:
            print(f"      ❌ 失败")
        
        # 测试历史数据
        print(f"  [2] 测试历史数据...")
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
        hist_data = fetcher.get_stock_hist_data(symbol, start_date=start_date, end_date=end_date)
        if hist_data is not None and not hist_data.empty:
            print(f"      ✅ 成功: {len(hist_data)} 条")
        else:
            print(f"      ❌ 失败")
        
        # 测试财务数据
        print(f"  [3] 测试财务数据...")
        financial_data = fetcher.get_financial_data(symbol)
        if financial_data and isinstance(financial_data, dict):
            has_data = any([
                financial_data.get('income_statement'),
                financial_data.get('balance_sheet'),
                financial_data.get('cash_flow')
            ])
            if has_data:
                print(f"      ✅ 成功")
            else:
                print(f"      ⚠️ 返回结构但无数据")
        else:
            print(f"      ❌ 失败")
        
        return {"success": True}
    except Exception as e:
        print(f"  ❌ 异常: {type(e).__name__} - {str(e)}")
        return {"success": False, "reason": str(e)}


def main():
    """主函数"""
    print_header("Tushare和AKShare对北交所股票数据支持情况测试")
    print(f"\n测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试股票: {', '.join(BSE_TEST_STOCKS)}")
    print(f"\n参考文档:")
    print(f"  - Tushare: https://tushare.pro/document/")
    print(f"  - AKShare: https://akshare.akfamily.xyz/data/index.html")
    
    # 汇总结果
    summary = {
        "tushare": {"basic_info": [], "daily_data": []},
        "akshare": {"spot_data": [], "financial_data": []},
        "unified": []
    }
    
    # 测试第一只股票作为示例
    test_symbol = BSE_TEST_STOCKS[0]
    
    print_header(f"详细测试: {test_symbol}")
    
    # Tushare测试
    print_header("Tushare接口测试")
    summary["tushare"]["basic_info"].append(test_tushare_basic_info(test_symbol))
    summary["tushare"]["daily_data"].append(test_tushare_daily_data(test_symbol))
    
    # AKShare测试
    print_header("AKShare接口测试")
    summary["akshare"]["spot_data"].append(test_akshare_spot_data(test_symbol))
    summary["akshare"]["financial_data"].append(test_akshare_financial_data(test_symbol))
    
    # 统一接口测试
    print_header("统一数据访问接口测试")
    summary["unified"].append(test_unified_access(test_symbol))
    
    # 批量测试所有股票（简化版）
    print_header("批量测试所有股票")
    akshare_success_count = 0
    tushare_success_count = 0
    
    for symbol in BSE_TEST_STOCKS:
        print(f"\n股票: {symbol}")
        
        # 快速测试AKShare实时行情
        try:
            from network_optimizer import network_optimizer
            with network_optimizer.apply():
                df_all = ak.stock_zh_a_spot_em()
                if df_all is not None and not df_all.empty:
                    df_stock = df_all[df_all['代码'] == symbol]
                    if not df_stock.empty:
                        print(f"  ✅ AKShare实时行情: 找到 ({df_stock.iloc[0].get('名称', 'N/A')})")
                        akshare_success_count += 1
                    else:
                        print(f"  ❌ AKShare实时行情: 未找到")
                else:
                    print(f"  ❌ AKShare实时行情: 数据为空")
        except Exception as e:
            print(f"  ❌ AKShare实时行情: {str(e)}")
        
        # 快速测试Tushare日线数据
        try:
            if data_source_manager.tushare_available:
                ts_code = f"{symbol}.BJ"
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=5)).strftime('%Y%m%d')
                df = data_source_manager.tushare_api.daily(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date
                )
                if df is not None and not df.empty:
                    print(f"  ✅ Tushare日线数据: 成功 ({len(df)} 条)")
                    tushare_success_count += 1
                else:
                    print(f"  ❌ Tushare日线数据: 返回空")
            else:
                print(f"  ⚠️ Tushare未初始化")
        except Exception as e:
            print(f"  ❌ Tushare日线数据: {str(e)}")
    
    # 打印汇总
    print_header("测试结果汇总")
    print(f"\nTushare支持情况:")
    print(f"  基本信息接口: {sum(1 for r in summary['tushare']['basic_info'] if r.get('success'))}/{len(summary['tushare']['basic_info'])} 成功")
    print(f"  日线数据接口: {sum(1 for r in summary['tushare']['daily_data'] if r.get('success'))}/{len(summary['tushare']['daily_data'])} 成功")
    print(f"  批量测试: {tushare_success_count}/{len(BSE_TEST_STOCKS)} 成功")
    
    print(f"\nAKShare支持情况:")
    print(f"  实时行情接口: {sum(1 for r in summary['akshare']['spot_data'] if r.get('success'))}/{len(summary['akshare']['spot_data'])} 成功")
    print(f"  财务数据接口: {sum(1 for r in summary['akshare']['financial_data'] if r.get('success'))}/{len(summary['akshare']['financial_data'])} 成功")
    print(f"  批量测试: {akshare_success_count}/{len(BSE_TEST_STOCKS)} 成功")
    
    print(f"\n结论:")
    if tushare_success_count > 0:
        print(f"  ✅ Tushare部分支持北交所股票数据")
    else:
        print(f"  ❌ Tushare不支持或支持有限北交所股票数据")
    
    if akshare_success_count > 0:
        print(f"  ✅ AKShare支持北交所股票数据（推荐使用）")
    else:
        print(f"  ⚠️ AKShare对北交所股票数据支持需要验证")
    
    print(f"\n详细日志请查看: debug.log")
    print(f"测试完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()

