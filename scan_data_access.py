"""
扫描所有数据获取功能，检查是否使用统一数据访问模块
"""

import sys
import os
import re
import ast

# 设置编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 统一数据访问模块的方法列表
UNIFIED_METHODS = {
    'get_stock_info',
    'get_stock_data',
    'get_stock_basic_info',
    'get_stock_hist_data',
    'get_realtime_quotes',
    'get_financial_data',
    'get_quarterly_reports',
    'get_fund_flow_data',
    'get_market_sentiment_data',
    'get_stock_news',
    'get_news_data',
    'get_risk_data',
    'get_research_reports_data',
    'get_announcement_data',
    'get_chip_distribution_data',
}

# 不应该直接使用的模块（应该通过UnifiedDataAccess）
FORBIDDEN_DIRECT_IMPORTS = [
    'data_source_manager',
    'stock_data',
    'fund_flow_akshare',
    'market_sentiment_data',
    'qstock_news_data',
    'quarterly_report_data',
    'risk_data_fetcher',
]

# 应该使用的统一接口
REQUIRED_IMPORT = 'from unified_data_access import UnifiedDataAccess'

def scan_file(filepath):
    """扫描单个文件"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        issues = []
        has_unified_import = REQUIRED_IMPORT in content or 'UnifiedDataAccess' in content
        
        # 检查是否有禁止的直接导入
        for forbidden in FORBIDDEN_DIRECT_IMPORTS:
            pattern = rf'from\s+{forbidden}\s+import|import\s+{forbidden}'
            if re.search(pattern, content):
                issues.append(f"⚠️  直接导入 {forbidden}，应该使用 UnifiedDataAccess")
        
        # 检查是否有UnifiedDataAccess的使用
        if 'UnifiedDataAccess' in content or 'unified_fetcher' in content or 'unified_data' in content:
            # 检查方法调用
            for method in UNIFIED_METHODS:
                pattern = rf'\.{method}\('
                if re.search(pattern, content):
                    issues.append(f"✅ 使用了统一接口: {method}")
        
        # 检查直接调用数据源的情况
        direct_calls = [
            (r'data_source_manager\.', 'data_source_manager'),
            (r'ak\.stock_', 'akshare直接调用'),
            (r'ak\.fund_', 'akshare直接调用'),
            (r'tushare_api\.', 'tushare直接调用'),
        ]
        
        for pattern, desc in direct_calls:
            matches = re.findall(pattern, content)
            if matches and 'UnifiedDataAccess' not in desc:
                issues.append(f"⚠️  直接调用 {desc}")
        
        return {
            'file': filepath,
            'has_unified': has_unified_import,
            'issues': issues
        }
    except Exception as e:
        return {
            'file': filepath,
            'error': str(e)
        }

def main():
    """主函数"""
    print("=" * 80)
    print("扫描数据获取功能 - 检查统一数据访问模块使用情况")
    print("=" * 80)
    print()
    
    # 要扫描的文件
    files_to_scan = [
        'app.py',
        'ai_agents.py',
        'portfolio_manager.py',
        'smart_monitor_data.py',
        'sector_strategy_data.py',
        'longhubang_data.py',
    ]
    
    results = []
    for filepath in files_to_scan:
        if os.path.exists(filepath):
            result = scan_file(filepath)
            results.append(result)
    
    # 显示结果
    print("\n扫描结果:")
    print("-" * 80)
    
    for result in results:
        print(f"\n📄 {result['file']}")
        
        if 'error' in result:
            print(f"   ❌ 扫描失败: {result['error']}")
            continue
        
        if result['has_unified']:
            print("   ✅ 使用了统一数据访问模块")
        else:
            print("   ⚠️  未检测到统一数据访问模块导入")
        
        if result['issues']:
            for issue in result['issues']:
                print(f"   {issue}")
        else:
            print("   ✅ 未发现直接调用数据源的问题")
    
    print("\n" + "=" * 80)
    print("扫描完成")
    print("=" * 80)

if __name__ == "__main__":
    main()

