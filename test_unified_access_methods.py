"""
测试UnifiedDataAccess是否有所有必需的方法
"""

import sys
import os
import io

# 设置Windows控制台UTF-8编码
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from unified_data_access import UnifiedDataAccess

def test_methods():
    """测试所有必需的方法是否存在"""
    print("=" * 80)
    print("测试 UnifiedDataAccess 方法完整性")
    print("=" * 80)
    
    unified = UnifiedDataAccess()
    
    # 需要的方法列表（根据app.py的调用）
    required_methods = [
        'get_stock_info',           # app.py:783
        'get_stock_data',           # app.py:784
        'stock_data_fetcher',       # app.py:789 (属性)
        'get_financial_data',       # app.py:873
        '_is_chinese_stock',        # app.py:878
        'get_quarterly_reports',    # app.py:880
        'get_fund_flow_data',       # app.py:893
        'get_market_sentiment_data',# app.py:901
        'get_stock_news',           # app.py:909
        'get_risk_data',            # app.py:918
    ]
    
    print("\n检查必需方法:")
    print("-" * 80)
    
    all_ok = True
    for method_name in required_methods:
        has_method = hasattr(unified, method_name)
        status = "✅" if has_method else "❌"
        print(f"{status} {method_name:<30} {'存在' if has_method else '缺失'}")
        if not has_method:
            all_ok = False
    
    print("-" * 80)
    
    if all_ok:
        print("\n✅ 所有必需方法都存在！")
        
        # 测试 stock_data_fetcher 的方法
        print("\n检查 stock_data_fetcher 的必需方法:")
        print("-" * 80)
        
        fetcher_methods = [
            'calculate_technical_indicators',
            'get_latest_indicators'
        ]
        
        for method_name in fetcher_methods:
            has_method = hasattr(unified.stock_data_fetcher, method_name)
            status = "✅" if has_method else "❌"
            print(f"{status} stock_data_fetcher.{method_name:<30} {'存在' if has_method else '缺失'}")
        
        print("-" * 80)
        print("\n✅ 所有方法检查完成！")
    else:
        print("\n❌ 有方法缺失，请补充！")
        return False
    
    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)
    
    return True


if __name__ == "__main__":
    success = test_methods()
    sys.exit(0 if success else 1)

