"""
公告数据获取测试脚本
测试unified_data_access模块的公告数据获取功能
"""

import sys
import os
import io

# 设置Windows控制台UTF-8编码
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from unified_data_access import UnifiedDataAccess
import json


def test_announcement_data(symbol, days=30):
    """测试公告数据获取
    
    Args:
        symbol: 股票代码
        days: 获取最近N天的公告
    """
    print("=" * 80)
    print(f"📢 测试公告数据获取")
    print("=" * 80)
    print(f"股票代码: {symbol}")
    print(f"时间范围: 最近 {days} 天")
    print("-" * 80)
    
    # 创建统一数据访问实例
    unified_data = UnifiedDataAccess()
    
    # 获取公告数据
    print("\n开始获取公告数据...\n")
    announcement_data = unified_data.get_announcement_data(symbol, days=days)
    
    print("\n" + "=" * 80)
    print("📋 获取结果汇总")
    print("=" * 80)
    
    # 显示结果
    if announcement_data.get('data_success'):
        print(f"✅ 成功获取公告数据!")
        print(f"   数据源: {announcement_data.get('source', 'N/A')}")
        print(f"   公告数量: {announcement_data.get('count', 0)} 条")
        
        if announcement_data.get('date_range'):
            date_range = announcement_data['date_range']
            print(f"   时间范围: {date_range['start']} ~ {date_range['end']}")
        
        # 显示公告列表
        announcements = announcement_data.get('announcements', [])
        if announcements:
            print(f"\n{'=' * 80}")
            print(f"📄 公告列表 (共 {len(announcements)} 条)")
            print("=" * 80)
            
            for idx, announcement in enumerate(announcements, 1):
                print(f"\n【公告 {idx}】")
                print(f"  日期: {announcement.get('日期', 'N/A')}")
                print(f"  标题: {announcement.get('公告标题', 'N/A')}")
                print(f"  类型: {announcement.get('公告类型', 'N/A')}")
                
                if announcement.get('公告摘要'):
                    summary = announcement['公告摘要']
                    print(f"  摘要: {summary[:100]}{'...' if len(summary) > 100 else ''}")
                
                print("-" * 80)
            
            # 保存到JSON文件
            output_file = f"announcement_data_{symbol}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(announcement_data, f, ensure_ascii=False, indent=2)
            print(f"\n💾 数据已保存到: {output_file}")
            
            # 统计公告类型
            print(f"\n{'=' * 80}")
            print("📊 公告类型统计")
            print("=" * 80)
            
            type_count = {}
            for announcement in announcements:
                ann_type = announcement.get('公告类型', 'N/A')
                type_count[ann_type] = type_count.get(ann_type, 0) + 1
            
            for ann_type, count in sorted(type_count.items(), key=lambda x: x[1], reverse=True):
                print(f"  {ann_type}: {count} 条")
        
    else:
        print(f"❌ 获取公告数据失败")
        print(f"   错误信息: {announcement_data.get('error', '未知错误')}")
    
    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)
    
    return announcement_data


def test_multiple_stocks():
    """测试多只股票的公告数据获取"""
    # 测试股票列表
    test_stocks = [
        ("000001", "平安银行"),
        ("600519", "贵州茅台"),
        ("000858", "五粮液"),
        ("600036", "招商银行"),
    ]
    
    print("\n\n" + "🔍" * 40)
    print("批量测试多只股票的公告数据获取")
    print("🔍" * 40 + "\n")
    
    results = {}
    
    for symbol, name in test_stocks:
        print(f"\n{'#' * 80}")
        print(f"# 测试股票: {name} ({symbol})")
        print(f"{'#' * 80}\n")
        
        try:
            result = test_announcement_data(symbol, days=30)
            results[symbol] = {
                'name': name,
                'success': result.get('data_success', False),
                'count': result.get('count', 0),
                'error': result.get('error', None)
            }
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            results[symbol] = {
                'name': name,
                'success': False,
                'count': 0,
                'error': str(e)
            }
        
        print("\n" + "⏸️ " * 40 + "\n")
    
    # 显示汇总结果
    print("\n\n" + "=" * 80)
    print("📊 批量测试汇总")
    print("=" * 80)
    
    success_count = sum(1 for r in results.values() if r['success'])
    total_count = len(results)
    
    print(f"\n测试股票数: {total_count}")
    print(f"成功数量: {success_count}")
    print(f"失败数量: {total_count - success_count}")
    print(f"成功率: {success_count / total_count * 100:.1f}%\n")
    
    print("-" * 80)
    print(f"{'股票代码':<10} {'股票名称':<15} {'状态':<10} {'公告数量':<10}")
    print("-" * 80)
    
    for symbol, result in results.items():
        status = "✅ 成功" if result['success'] else "❌ 失败"
        print(f"{symbol:<10} {result['name']:<15} {status:<10} {result['count']:<10}")
    
    print("=" * 80)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='测试公告数据获取功能')
    parser.add_argument('--symbol', type=str, default='000001', help='股票代码 (默认: 000001)')
    parser.add_argument('--days', type=int, default=30, help='获取最近N天的公告 (默认: 30)')
    parser.add_argument('--batch', action='store_true', help='批量测试多只股票')
    
    args = parser.parse_args()
    
    if args.batch:
        # 批量测试
        test_multiple_stocks()
    else:
        # 单个测试
        test_announcement_data(args.symbol, args.days)

