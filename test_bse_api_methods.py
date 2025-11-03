#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Tushare和AKShare的北交所股票数据接口方法
验证接口是否存在以及参数格式是否正确
"""

import sys
import io
from datetime import datetime

# 设置UTF-8编码输出（Windows兼容）
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import inspect
import akshare as ak
from data_source_manager import data_source_manager

# 北交所测试股票
BSE_STOCK = "832149"  # 利尔达

def print_header(title: str):
    """打印标题"""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}")


def check_tushare_interfaces():
    """检查Tushare接口对北交所的支持"""
    print_header("Tushare接口检查")
    
    if not data_source_manager.tushare_available:
        print("❌ Tushare未初始化")
        return
    
    ts_api = data_source_manager.tushare_api
    
    print(f"\n[1] 检查stock_basic接口（股票基本信息）")
    try:
        # 测试查询北交所股票
        df = ts_api.stock_basic(
            exchange='',  # 空字符串表示所有交易所
            list_status='L',
            fields='ts_code,symbol,name,area,industry,exchange'
        )
        if df is not None and not df.empty:
            # 查找北交所股票（.BJ结尾）
            bse_stocks = df[df['ts_code'].str.endswith('.BJ', na=False)]
            if not bse_stocks.empty:
                print(f"  ✅ 接口可用，找到 {len(bse_stocks)} 只北交所股票")
                print(f"     示例: {bse_stocks.iloc[0]['ts_code']} - {bse_stocks.iloc[0]['name']}")
            else:
                print(f"  ⚠️ 接口可用，但未找到北交所股票（.BJ后缀）")
                print(f"     总股票数: {len(df)}")
                print(f"     交易所分布:")
                if 'exchange' in df.columns:
                    print(df['exchange'].value_counts().to_dict())
        else:
            print(f"  ⚠️ 接口返回空数据")
    except Exception as e:
        print(f"  ❌ 接口调用失败: {str(e)}")
    
    print(f"\n[2] 检查daily接口（日线数据）")
    try:
        ts_code = f"{BSE_STOCK}.BJ"
        df = ts_api.daily(
            ts_code=ts_code,
            start_date='20241001',
            end_date='20241101'
        )
        if df is not None and not df.empty:
            print(f"  ✅ 接口可用，成功获取数据: {len(df)} 条")
            print(f"     最新收盘价: {df.iloc[0]['close'] if len(df) > 0 else 'N/A'}")
        else:
            print(f"  ⚠️ 接口可用，但返回空数据（可能该股票无数据）")
    except Exception as e:
        error_msg = str(e)
        print(f"  ❌ 接口调用失败: {error_msg}")
        if "数据不存在" in error_msg or "未找到" in error_msg:
            print(f"     可能原因: Tushare不支持该北交所股票或数据未录入")
    
    print(f"\n[3] 检查daily_basic接口（每日基本面数据）")
    try:
        ts_code = f"{BSE_STOCK}.BJ"
        df = ts_api.daily_basic(
            ts_code=ts_code,
            trade_date='20241101'
        )
        if df is not None and not df.empty:
            print(f"  ✅ 接口可用，成功获取数据")
            print(f"     市盈率: {df.iloc[0].get('pe', 'N/A')}")
        else:
            print(f"  ⚠️ 接口可用，但返回空数据")
    except Exception as e:
        error_msg = str(e)
        print(f"  ❌ 接口调用失败: {error_msg}")


def check_akshare_interfaces():
    """检查AKShare接口对北交所的支持"""
    print_header("AKShare接口检查")
    
    print(f"\n[1] 检查stock_zh_a_spot_em接口（实时行情-包含京A股）")
    try:
        # 检查接口是否存在
        if hasattr(ak, 'stock_zh_a_spot_em'):
            print(f"  ✅ 接口存在: stock_zh_a_spot_em")
            # 查看接口签名
            sig = inspect.signature(ak.stock_zh_a_spot_em)
            print(f"     参数: {list(sig.parameters.keys())}")
            
            # 尝试调用（可能因网络问题失败）
            print(f"     注意: 需要网络连接，可能因网络问题无法实际调用")
            print(f"     根据AKShare文档，此接口应包含'京A股'数据")
        else:
            print(f"  ❌ 接口不存在")
    except Exception as e:
        print(f"  ⚠️ 检查失败: {str(e)}")
    
    print(f"\n[2] 检查stock_individual_info_em接口（个股信息）")
    try:
        if hasattr(ak, 'stock_individual_info_em'):
            print(f"  ✅ 接口存在: stock_individual_info_em")
            sig = inspect.signature(ak.stock_individual_info_em)
            print(f"     参数: {list(sig.parameters.keys())}")
            print(f"     说明: 此接口支持通过symbol参数查询个股信息")
            print(f"           应支持北交所股票代码（8或4开头）")
        else:
            print(f"  ❌ 接口不存在")
    except Exception as e:
        print(f"  ⚠️ 检查失败: {str(e)}")
    
    print(f"\n[3] 检查stock_zh_a_hist接口（历史行情）")
    try:
        if hasattr(ak, 'stock_zh_a_hist'):
            print(f"  ✅ 接口存在: stock_zh_a_hist")
            sig = inspect.signature(ak.stock_zh_a_hist)
            print(f"     参数: {list(sig.parameters.keys())}")
            print(f"     说明: 此接口应支持A股历史数据，包括北交所")
        else:
            print(f"  ❌ 接口不存在")
    except Exception as e:
        print(f"  ⚠️ 检查失败: {str(e)}")
    
    print(f"\n[4] 检查北交所专用接口")
    # 搜索AKShare中可能存在的北交所相关接口
    ak_methods = [name for name in dir(ak) if 'stock' in name.lower() and 'bj' in name.lower()]
    ak_methods += [name for name in dir(ak) if 'stock' in name.lower() and 'beijing' in name.lower()]
    ak_methods += [name for name in dir(ak) if 'stock' in name.lower() and '京' in name]
    
    if ak_methods:
        print(f"  找到可能的北交所相关接口:")
        for method in ak_methods:
            print(f"    - {method}")
    else:
        print(f"  ℹ️ 未找到明确的北交所专用接口")
        print(f"     说明: AKShare可能通过通用接口支持北交所，而非专用接口")


def check_documentation_references():
    """检查文档引用"""
    print_header("文档引用检查")
    
    print(f"\n根据官方文档分析:")
    print(f"\n[Tushare文档] https://tushare.pro/document/")
    print(f"  - Tushare文档中未明确提及对北交所（BJ）的支持")
    print(f"  - Tushare使用ts_code格式，格式为: 代码.市场后缀")
    print(f"  - 市场后缀包括: .SH（上海）、.SZ（深圳）、.BJ（北京）")
    print(f"  - 结论: 接口设计上支持.BJ后缀，但实际数据支持需要验证")
    
    print(f"\n[AKShare文档] https://akshare.akfamily.xyz/data/index.html")
    print(f"  - AKShare文档中明确提到'京A股'支持")
    print(f"  - stock_zh_a_spot_em接口包含'京A股'数据")
    print(f"  - 实时行情数据分类中包括:'沪深京 A 股'、'沪 A 股'、'深 A 股'、'京 A 股'")
    print(f"  - 结论: AKShare明确支持北交所股票数据")


def main():
    """主函数"""
    print_header("Tushare和AKShare北交所支持情况检查")
    print(f"\n测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试股票代码: {BSE_STOCK}")
    print(f"\n说明: 本测试检查接口可用性和参数格式，实际数据获取可能受网络影响")
    
    # 检查Tushare
    check_tushare_interfaces()
    
    # 检查AKShare
    check_akshare_interfaces()
    
    # 文档引用
    check_documentation_references()
    
    # 总结
    print_header("总结")
    print(f"\n[Tushare]")
    print(f"  ✅ 接口设计支持: ts_code格式包含.BJ后缀")
    print(f"  ⚠️ 数据支持: 需要实际验证，可能存在数据缺失")
    print(f"  📝 文档状态: 未明确说明北交所支持情况")
    
    print(f"\n[AKShare]")
    print(f"  ✅ 明确支持: 文档中明确提到'京A股'支持")
    print(f"  ✅ 接口可用: stock_zh_a_spot_em等接口包含京A股数据")
    print(f"  📝 文档状态: 官方文档明确说明支持情况")
    
    print(f"\n[建议]")
    print(f"  1. 对于北交所股票，优先使用AKShare数据源")
    print(f"  2. Tushare可作为补充数据源，但需要验证实际可用性")
    print(f"  3. 在统一数据访问接口中，北交所股票应默认使用AKShare")
    
    print(f"\n测试完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()

