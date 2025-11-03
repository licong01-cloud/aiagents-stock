"""
测试公告和筹码数据获取
"""
import sys
import io

# 设置标准输出编码为UTF-8（Windows兼容）
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')
    except:
        pass

from unified_data_access import UnifiedDataAccess
import traceback

def test_announcement_data():
    """测试公告数据获取"""
    print("="*60)
    print("测试公告数据获取")
    print("="*60)
    
    unified = UnifiedDataAccess()
    symbol = "000001"  # 平安银行
    
    print(f"\n正在获取 {symbol} 的公告数据（最近30天）...\n")
    
    try:
        announcement_data = unified.get_announcement_data(symbol, days=30)
        
        print(f"\n返回数据结构:")
        print(f"  data_success: {announcement_data.get('data_success', False)}")
        print(f"  count: {announcement_data.get('count', 0)}")
        print(f"  source: {announcement_data.get('source', 'N/A')}")
        print(f"  error: {announcement_data.get('error', 'None')}")
        
        if announcement_data.get('data_success'):
            print(f"\n✅ 成功获取 {announcement_data.get('count', 0)} 条公告")
            announcements = announcement_data.get('announcements', [])
            if announcements:
                print(f"\n前3条公告:")
                for i, ann in enumerate(announcements[:3], 1):
                    print(f"  {i}. {ann.get('日期', 'N/A')} - {ann.get('公告标题', 'N/A')[:50]}")
        else:
            print(f"\n❌ 未能获取公告数据")
            if announcement_data.get('error'):
                print(f"  错误: {announcement_data.get('error')}")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        traceback.print_exc()


def test_chip_data():
    """测试筹码数据获取"""
    print("\n" + "="*60)
    print("测试筹码数据获取")
    print("="*60)
    
    unified = UnifiedDataAccess()
    symbol = "000001"  # 平安银行
    
    print(f"\n正在获取 {symbol} 的筹码分布数据...\n")
    
    try:
        chip_data = unified.get_chip_distribution_data(symbol)
        
        print(f"\n返回数据结构:")
        print(f"  data_success: {chip_data.get('data_success', False)}")
        print(f"  error: {chip_data.get('error', 'None')}")
        
        if chip_data.get('data_success'):
            print(f"\n✅ 成功获取筹码分布数据")
            distribution = chip_data.get('distribution', {})
            if distribution:
                print(f"\n筹码分布信息:")
                for key, value in distribution.items():
                    print(f"  {key}: {value}")
        else:
            print(f"\n❌ 未能获取筹码数据")
            if chip_data.get('error'):
                print(f"  错误: {chip_data.get('error')}")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    print("\n开始测试公告和筹码数据获取功能...\n")
    
    # 测试公告数据
    test_announcement_data()
    
    # 测试筹码数据
    test_chip_data()
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)

