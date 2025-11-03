"""
测试筹码分布数据获取（使用Tushare cyq_perf和cyq_chips接口）
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

def test_chip_distribution():
    """测试筹码分布数据获取"""
    print("="*60)
    print("测试筹码分布数据获取（Tushare cyq_perf + cyq_chips）")
    print("="*60)
    
    unified = UnifiedDataAccess()
    symbol = "000001"  # 平安银行
    
    print(f"\n正在获取 {symbol} 的筹码分布数据...\n")
    
    try:
        chip_data = unified.get_chip_distribution_data(symbol)
        
        print(f"\n返回数据结构:")
        print(f"  data_success: {chip_data.get('data_success', False)}")
        print(f"  source: {chip_data.get('source', 'N/A')}")
        print(f"  latest_date: {chip_data.get('latest_date', 'N/A')}")
        print(f"  error: {chip_data.get('error', 'None')}")
        
        if chip_data.get('data_success'):
            print(f"\n✅ 成功获取筹码分布数据")
            
            # 显示cyq_perf数据
            if chip_data.get('cyq_perf'):
                perf = chip_data['cyq_perf']
                print(f"\n📊 cyq_perf数据（筹码分布及胜率）:")
                print(f"  数据条数: {perf.get('count', 0)}")
                if perf.get('latest'):
                    latest = perf['latest']
                    print(f"  最新数据日期: {latest.get('trade_date', 'N/A')}")
                    print(f"  最新数据字段: {list(latest.keys())[:10]}")
                    # 显示部分关键字段
                    for key in ['trade_date', 'concentration', 'win_rate', 'avg_cost']:
                        if key in latest:
                            print(f"  {key}: {latest[key]}")
            
            # 显示cyq_chips数据
            if chip_data.get('cyq_chips'):
                chips = chip_data['cyq_chips']
                print(f"\n🎯 cyq_chips数据（每日筹码分布）:")
                print(f"  数据条数: {chips.get('count', 0)}")
                print(f"  交易日期: {chips.get('trade_date', 'N/A')}")
                if chips.get('data'):
                    print(f"  第一条数据字段: {list(chips['data'][0].keys())[:10]}")
            
            # 显示汇总信息
            if chip_data.get('summary'):
                print(f"\n📋 汇总信息:")
                for key, value in chip_data['summary'].items():
                    print(f"  {key}: {value}")
        else:
            print(f"\n❌ 未能获取筹码分布数据")
            if chip_data.get('error'):
                print(f"  错误: {chip_data.get('error')}")
                
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    print("\n开始测试筹码分布数据获取功能...\n")
    
    # 测试筹码数据
    test_chip_distribution()
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)

