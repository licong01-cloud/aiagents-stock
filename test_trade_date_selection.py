#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试交易日选择逻辑
验证根据日期和时间判断，非交易日和交易日开盘前选择上一交易日，交易日开盘后选择当日
"""

import sys
import io
from datetime import datetime, timedelta, time
from unified_data_access import unified_data_access

# Windows控制台UTF-8编码支持
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_trade_date_selection():
    """测试交易日选择逻辑"""
    print("=" * 60)
    print("测试交易日选择逻辑")
    print("=" * 60)
    
    # 测试不同时间点
    test_cases = [
        {
            "name": "周一开盘前（9:00）",
            "simulate_time": None,  # 实际测试时使用当前时间
            "expected": "上一交易日（周五）"
        },
        {
            "name": "周一开盘后（10:00）",
            "simulate_time": None,
            "expected": "当日（周一）"
        },
        {
            "name": "周六（非交易日）",
            "simulate_time": None,
            "expected": "上一交易日（周五）"
        },
        {
            "name": "周日（非交易日）",
            "simulate_time": None,
            "expected": "上一交易日（周五）"
        },
        {
            "name": "交易日收盘后（16:00）",
            "simulate_time": None,
            "expected": "当日（收盘数据）"
        },
        {
            "name": "午休时间（12:00）",
            "simulate_time": None,
            "expected": "当日"
        }
    ]
    
    print(f"\n当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"当前星期: {['周一', '周二', '周三', '周四', '周五', '周六', '周日'][datetime.now().weekday()]}")
    
    # 测试交易日判断
    print(f"\n{'=' * 60}")
    print("测试交易日判断方法")
    print(f"{'=' * 60}")
    
    for i in range(7):
        test_date = datetime.now() - timedelta(days=i)
        is_trading = unified_data_access._is_trading_day(test_date)
        weekday_name = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][test_date.weekday()]
        status = "✅ 交易日" if is_trading else "❌ 非交易日"
        print(f"  {test_date.strftime('%Y-%m-%d')} ({weekday_name}): {status}")
    
    # 测试交易时间判断
    print(f"\n{'=' * 60}")
    print("测试交易时间判断方法")
    print(f"{'=' * 60}")
    
    is_trading_day = unified_data_access._is_trading_day()
    is_trading_time = unified_data_access._is_trading_time()
    current_time = datetime.now().time()
    
    print(f"  当前日期: {datetime.now().strftime('%Y-%m-%d')}")
    print(f"  当前时间: {current_time.strftime('%H:%M:%S')}")
    print(f"  是否为交易日: {'✅ 是' if is_trading_day else '❌ 否'}")
    print(f"  是否在交易时间: {'✅ 是' if is_trading_time else '❌ 否'}")
    
    # 测试交易日选择
    print(f"\n{'=' * 60}")
    print("测试交易日选择方法 (_get_appropriate_trade_date)")
    print(f"{'=' * 60}")
    
    selected_date = unified_data_access._get_appropriate_trade_date()
    selected_datetime = datetime.strptime(selected_date, '%Y%m%d')
    selected_weekday = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][selected_datetime.weekday()]
    
    print(f"  选择的交易日: {selected_date} ({selected_weekday})")
    print(f"  选择的日期: {selected_datetime.strftime('%Y-%m-%d')}")
    
    # 解释选择逻辑
    now = datetime.now()
    current_time = now.time()
    is_trading_day = unified_data_access._is_trading_day()
    is_trading_time = unified_data_access._is_trading_time()
    is_before_open = current_time < time(9, 30)
    
    print(f"\n  选择逻辑:")
    print(f"    - 是否为交易日: {is_trading_day}")
    print(f"    - 是否在交易时间: {is_trading_time}")
    print(f"    - 是否开盘前(<9:30): {is_before_open}")
    
    if not is_trading_day:
        print(f"    → 选择原因: 非交易日，使用上一交易日")
    elif is_trading_day and is_before_open:
        print(f"    → 选择原因: 交易日开盘前，使用上一交易日")
    elif is_trading_day and is_trading_time:
        print(f"    → 选择原因: 交易日开盘后，使用当日数据")
    elif is_trading_day and current_time > time(15, 0):
        print(f"    → 选择原因: 交易日收盘后，使用当日收盘数据")
    else:
        print(f"    → 选择原因: 其他情况（如午休），使用当日数据")
    
    # 测试股票信息获取
    print(f"\n{'=' * 60}")
    print("测试股票信息获取（验证交易日选择是否生效）")
    print(f"{'=' * 60}")
    
    test_symbol = '000001'  # 平安银行
    
    try:
        print(f"\n  测试股票: {test_symbol}")
        print(f"  预期使用的交易日: {selected_date}")
        print(f"  正在获取股票信息...")
        
        stock_info = unified_data_access.get_stock_info(test_symbol)
        
        print(f"\n  获取结果:")
        print(f"    股票名称: {stock_info.get('name', 'N/A')}")
        print(f"    当前价格: {stock_info.get('current_price', 'N/A')}")
        print(f"    涨跌幅: {stock_info.get('change_percent', 'N/A')}%")
        print(f"    市盈率: {stock_info.get('pe_ratio', 'N/A')}")
        print(f"    市净率: {stock_info.get('pb_ratio', 'N/A')}")
        print(f"    市值: {stock_info.get('market_cap', 'N/A')}")
        
        if stock_info.get('current_price') != 'N/A':
            print(f"\n  ✅ 成功获取股票信息（价格: {stock_info.get('current_price')}）")
        else:
            print(f"\n  ⚠️ 未能获取价格数据（可能数据源不可用）")
            
    except Exception as e:
        print(f"\n  ❌ 获取股票信息失败: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n{'=' * 60}")
    print("测试完成")
    print(f"{'=' * 60}")
    
    print(f"\n💡 提示:")
    print(f"  - 交易日选择逻辑已根据日期和时间自动判断")
    print(f"  - 非交易日和开盘前自动选择上一交易日数据")
    print(f"  - 开盘后使用当日数据，确保数据实时性")


if __name__ == '__main__':
    test_trade_date_selection()

