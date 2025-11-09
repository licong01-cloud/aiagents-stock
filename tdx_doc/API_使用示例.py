#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TDX股票数据API使用示例

演示如何使用所有API接口获取股票数据
"""

import requests
import json
from datetime import datetime

# 配置
BASE_URL = "http://localhost:8080"  # 修改为你的服务器地址

class StockAPI:
    """股票数据API客户端"""
    
    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url
    
    def get_quote(self, code):
        """获取五档行情"""
        url = f"{self.base_url}/api/quote?code={code}"
        response = requests.get(url)
        data = response.json()
        if data['code'] == 0:
            return data['data']
        return None
    
    def get_kline(self, code, ktype='day', limit=100):
        """获取K线数据"""
        url = f"{self.base_url}/api/kline?code={code}&type={ktype}"
        response = requests.get(url)
        data = response.json()
        if data['code'] == 0:
            return data['data']['List']
        return None
    
    def get_minute(self, code, date=None):
        """获取分时数据"""
        url = f"{self.base_url}/api/minute?code={code}"
        if date:
            url += f"&date={date}"
        response = requests.get(url)
        data = response.json()
        if data['code'] == 0:
            return data['data']['List']
        return None
    
    def get_trade(self, code, date=None):
        """获取分时成交"""
        url = f"{self.base_url}/api/trade?code={code}"
        if date:
            url += f"&date={date}"
        response = requests.get(url)
        data = response.json()
        if data['code'] == 0:
            return data['data']['List']
        return None
    
    def search(self, keyword):
        """搜索股票"""
        url = f"{self.base_url}/api/search?keyword={keyword}"
        response = requests.get(url)
        data = response.json()
        if data['code'] == 0:
            return data['data']
        return None
    
    def get_stock_info(self, code):
        """获取股票综合信息"""
        url = f"{self.base_url}/api/stock-info?code={code}"
        response = requests.get(url)
        data = response.json()
        if data['code'] == 0:
            return data['data']
        return None
    
    def get_all_codes(self, exchange='all'):
        """获取股票代码列表"""
        url = f"{self.base_url}/api/codes?exchange={exchange}"
        response = requests.get(url)
        data = response.json()
        if data['code'] == 0:
            return data['data']
        return None
    
    def batch_get_quote(self, codes):
        """批量获取行情"""
        url = f"{self.base_url}/api/batch-quote"
        response = requests.post(url, json={'codes': codes})
        data = response.json()
        if data['code'] == 0:
            return data['data']
        return None


def example1_get_quote():
    """示例1: 获取实时行情"""
    print("\n" + "="*50)
    print("示例1: 获取实时行情")
    print("="*50)
    
    api = StockAPI()
    quote = api.get_quote("000001")
    
    if quote and len(quote) > 0:
        q = quote[0]
        last_price = q['K']['Close'] / 1000  # 转为元
        open_price = q['K']['Open'] / 1000
        high_price = q['K']['High'] / 1000
        low_price = q['K']['Low'] / 1000
        
        print(f"股票代码: {q['Code']}")
        print(f"最新价: {last_price:.2f}元")
        print(f"开盘价: {open_price:.2f}元")
        print(f"最高价: {high_price:.2f}元")
        print(f"最低价: {low_price:.2f}元")
        print(f"成交量: {q['TotalHand']}手")
        print(f"成交额: {q['Amount']/1000:.2f}元")
        
        print("\n买五档:")
        for i, level in enumerate(q['BuyLevel']):
            price = level['Price'] / 1000
            volume = level['Number'] / 100
            print(f"  买{i+1}: {price:.2f}元  {volume:.0f}手")
        
        print("\n卖五档:")
        for i, level in enumerate(q['SellLevel']):
            price = level['Price'] / 1000
            volume = level['Number'] / 100
            print(f"  卖{i+1}: {price:.2f}元  {volume:.0f}手")


def example2_get_kline():
    """示例2: 获取K线数据并分析"""
    print("\n" + "="*50)
    print("示例2: 获取K线数据")
    print("="*50)
    
    api = StockAPI()
    klines = api.get_kline("000001", "day")
    
    if klines and len(klines) > 0:
        print(f"获取到 {len(klines)} 条日K线数据")
        
        # 显示最近5天的数据
        print("\n最近5天K线:")
        for k in klines[:5]:
            date = k['Time'][:10]
            open_p = k['Open'] / 1000
            close_p = k['Close'] / 1000
            high_p = k['High'] / 1000
            low_p = k['Low'] / 1000
            volume = k['Volume']
            
            change = close_p - open_p
            change_pct = (change / open_p * 100) if open_p > 0 else 0
            
            print(f"{date}: 开{open_p:.2f} 收{close_p:.2f} "
                  f"高{high_p:.2f} 低{low_p:.2f} "
                  f"量{volume}手 {change_pct:+.2f}%")
        
        # 计算简单移动平均线
        if len(klines) >= 5:
            ma5 = sum([k['Close'] for k in klines[:5]]) / 5 / 1000
            print(f"\nMA5: {ma5:.2f}元")


def example3_search_stock():
    """示例3: 搜索股票"""
    print("\n" + "="*50)
    print("示例3: 搜索股票")
    print("="*50)
    
    api = StockAPI()
    results = api.search("平安")
    
    if results:
        print(f"找到 {len(results)} 只股票:")
        for stock in results:
            print(f"  {stock['code']} - {stock['name']}")


def example4_batch_quote():
    """示例4: 批量获取行情"""
    print("\n" + "="*50)
    print("示例4: 批量获取行情")
    print("="*50)
    
    api = StockAPI()
    codes = ["000001", "600519", "601318"]
    quotes = api.batch_get_quote(codes)
    
    if quotes:
        print("批量行情数据:")
        for q in quotes:
            code = q['Code']
            price = q['K']['Close'] / 1000
            volume = q['TotalHand']
            print(f"  {code}: {price:.2f}元, 成交量{volume}手")


def example5_market_analysis():
    """示例5: 市场分析（涨跌统计）"""
    print("\n" + "="*50)
    print("示例5: 市场分析")
    print("="*50)
    
    api = StockAPI()
    
    # 获取部分股票进行分析
    all_codes = api.get_all_codes('sh')
    if all_codes:
        print(f"上海市场共 {all_codes['exchanges']['sh']} 只股票")
        
        # 随机取10只股票分析
        sample_codes = [c['code'] for c in all_codes['codes'][:10]]
        quotes = api.batch_get_quote(sample_codes)
        
        if quotes:
            up_count = 0
            down_count = 0
            flat_count = 0
            
            for q in quotes:
                last = q['K']['Last']
                close = q['K']['Close']
                
                if close > last:
                    up_count += 1
                elif close < last:
                    down_count += 1
                else:
                    flat_count += 1
            
            print(f"\n样本分析（{len(quotes)}只）:")
            print(f"  上涨: {up_count}只")
            print(f"  下跌: {down_count}只")
            print(f"  平盘: {flat_count}只")


def example6_technical_analysis():
    """示例6: 技术分析示例"""
    print("\n" + "="*50)
    print("示例6: 技术分析")
    print("="*50)
    
    api = StockAPI()
    klines = api.get_kline("000001", "day")
    
    if klines and len(klines) >= 20:
        # 计算MA5, MA10, MA20
        closes = [k['Close'] / 1000 for k in klines]
        
        ma5 = sum(closes[:5]) / 5
        ma10 = sum(closes[:10]) / 10
        ma20 = sum(closes[:20]) / 20
        
        current_price = closes[0]
        
        print("技术指标:")
        print(f"  当前价: {current_price:.2f}元")
        print(f"  MA5:   {ma5:.2f}元")
        print(f"  MA10:  {ma10:.2f}元")
        print(f"  MA20:  {ma20:.2f}元")
        
        # 简单趋势判断
        if ma5 > ma10 > ma20:
            print("\n趋势判断: 多头排列 📈")
        elif ma5 < ma10 < ma20:
            print("\n趋势判断: 空头排列 📉")
        else:
            print("\n趋势判断: 震荡盘整 ➡️")


def example7_realtime_monitor():
    """示例7: 实时监控（模拟）"""
    print("\n" + "="*50)
    print("示例7: 实时监控")
    print("="*50)
    
    api = StockAPI()
    watchlist = ["000001", "600519", "601318"]
    
    print(f"监控股票: {', '.join(watchlist)}")
    print("\n实时行情（刷新一次）:")
    
    quotes = api.batch_get_quote(watchlist)
    if quotes:
        print(f"{'代码':<10} {'最新价':<10} {'涨跌幅':<10} {'成交量'}")
        print("-" * 50)
        
        for q in quotes:
            code = q['Code']
            last = q['K']['Last'] / 1000
            close = q['K']['Close'] / 1000
            volume = q['TotalHand']
            
            change_pct = ((close - last) / last * 100) if last > 0 else 0
            
            print(f"{code:<10} {close:<10.2f} {change_pct:+.2f}%  {volume:>10}手")


def main():
    """主函数"""
    print("""
╔════════════════════════════════════════╗
║   TDX股票数据API使用示例               ║
║   演示所有API接口的使用方法             ║
╚════════════════════════════════════════╝
    """)
    
    try:
        # 运行所有示例
        example1_get_quote()
        example2_get_kline()
        example3_search_stock()
        example4_batch_quote()
        example5_market_analysis()
        example6_technical_analysis()
        example7_realtime_monitor()
        
        print("\n" + "="*50)
        print("所有示例运行完成！")
        print("="*50)
        
    except requests.exceptions.ConnectionError:
        print("\n❌ 无法连接到API服务器")
        print(f"   请确保服务运行在 {BASE_URL}")
        print("   启动命令: docker-compose up -d")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")


if __name__ == "__main__":
    main()

