#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Beta系数和52周高低位数据集成
验证数据是否正确获取并填充到stock_info中
"""

import sys
import io
from unified_data_access import unified_data_access

# Windows控制台UTF-8编码支持
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_beta_and_52week():
    """测试Beta和52周数据获取"""
    print("=" * 60)
    print("测试Beta系数和52周高低位数据集成")
    print("=" * 60)
    
    # 测试股票代码（A股）
    test_symbols = ['000001', '600000', '000002']
    
    for symbol in test_symbols:
        print(f"\n{'=' * 60}")
        print(f"测试股票: {symbol}")
        print(f"{'=' * 60}")
        
        # 1. 获取stock_info
        print(f"\n[1/2] 获取stock_info...")
        try:
            stock_info = unified_data_access.get_stock_info(symbol)
            
            # 检查Beta系数
            print(f"\n  Beta系数:")
            print(f"    值: {stock_info.get('beta', 'N/A')}")
            print(f"    类型: {type(stock_info.get('beta', 'N/A'))}")
            if stock_info.get('beta') != 'N/A':
                print(f"    ✅ Beta数据获取成功")
            else:
                print(f"    ⚠️ Beta数据为N/A（可能Tushare不可用或数据获取失败）")
            
            # 检查52周高低位
            print(f"\n  52周高低位:")
            print(f"    52周高: {stock_info.get('52_week_high', 'N/A')}")
            print(f"    52周低: {stock_info.get('52_week_low', 'N/A')}")
            print(f"    当前价格: {stock_info.get('current_price', 'N/A')}")
            
            if stock_info.get('52_week_high') != 'N/A' and stock_info.get('52_week_low') != 'N/A':
                print(f"    ✅ 52周数据获取成功")
            else:
                print(f"    ⚠️ 52周数据为N/A（可能Tushare不可用或数据获取失败）")
            
            # 2. 单独测试Beta系数获取
            print(f"\n[2/2] 单独测试Beta系数获取方法...")
            try:
                beta = unified_data_access.get_beta_coefficient(symbol)
                if beta is not None:
                    print(f"    ✅ Beta系数方法返回: {beta:.4f}")
                else:
                    print(f"    ⚠️ Beta系数方法返回None")
            except Exception as e:
                print(f"    ❌ Beta系数方法调用失败: {e}")
            
            # 3. 单独测试52周高低位获取
            print(f"\n[3/3] 单独测试52周高低位获取方法...")
            try:
                week52_data = unified_data_access.get_52week_high_low(symbol)
                if week52_data and week52_data.get('success'):
                    print(f"    ✅ 52周数据方法返回成功")
                    print(f"       高: {week52_data.get('high_52w')}")
                    print(f"       低: {week52_data.get('low_52w')}")
                    print(f"       当前: {week52_data.get('current_price')}")
                    print(f"       位置: {week52_data.get('position_percent'):.1f}%")
                else:
                    print(f"    ⚠️ 52周数据方法返回失败: {week52_data.get('success', False) if week52_data else 'None'}")
            except Exception as e:
                print(f"    ❌ 52周数据方法调用失败: {e}")
            
        except Exception as e:
            print(f"  ❌ 获取stock_info失败: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'=' * 60}")
    print("测试完成")
    print(f"{'=' * 60}")
    
    print(f"\n💡 提示:")
    print(f"  1. 如果Beta和52周数据都是N/A，请检查Tushare Token是否配置")
    print(f"  2. 如果Beta和52周数据获取失败，请检查网络连接和Tushare API权限")
    print(f"  3. 确保股票代码是A股格式（6位数字）")


if __name__ == '__main__':
    test_beta_and_52week()

