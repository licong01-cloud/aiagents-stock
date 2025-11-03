#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试研报数据获取，检查重复问题并验证内容获取
"""
import sys
import io

# Windows控制台UTF-8支持
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from unified_data_access import unified_data_access
from datetime import datetime
import pandas as pd

def test_research_reports(symbol='603197'):
    """测试研报数据获取"""
    print("=" * 60)
    print(f"测试股票代码: {symbol}")
    print("=" * 60)
    
    # 获取研报数据
    print(f"\n[1] 开始获取研报数据（过去6个月）...")
    research_data = unified_data_access.get_research_reports_data(symbol, days=180)
    
    if not research_data:
        print("❌ 未获取到研报数据")
        return
    
    print(f"\n[2] 检查数据获取结果...")
    print(f"   - 数据获取成功: {research_data.get('data_success', False)}")
    print(f"   - 数据源: {research_data.get('source', 'N/A')}")
    print(f"   - 研报数量: {research_data.get('report_count', 0)}")
    
    # 检查重复问题
    print(f"\n[3] 检查重复研报...")
    reports = research_data.get('research_reports', [])
    
    if not reports:
        print("   ⚠️ 研报列表为空")
        return
    
    print(f"   - 原始研报数量: {len(reports)}")
    
    # 使用标题+日期+机构作为唯一标识
    seen = set()
    duplicates = []
    unique_reports = []
    
    for report in reports:
        title = report.get('研报标题', '')
        date = report.get('日期', '')
        org = report.get('机构名称', '')
        key = f"{date}_{org}_{title}"
        
        if key in seen:
            duplicates.append(report)
        else:
            seen.add(key)
            unique_reports.append(report)
    
    print(f"   - 去重后数量: {len(unique_reports)}")
    print(f"   - 重复数量: {len(duplicates)}")
    
    if duplicates:
        print(f"\n   发现重复研报:")
        for idx, dup in enumerate(duplicates[:5], 1):  # 只显示前5条
            print(f"     {idx}. [{dup.get('日期', '')}] {dup.get('机构名称', '')} - {dup.get('研报标题', '')[:50]}")
    
    # 检查研报内容
    print(f"\n[4] 检查研报内容获取...")
    reports_with_content = [r for r in unique_reports if r.get('研报内容') and r.get('研报内容').strip()]
    reports_with_summary = [r for r in unique_reports if r.get('内容摘要') and r.get('内容摘要').strip()]
    
    print(f"   - 包含完整内容的研报: {len(reports_with_content)}")
    print(f"   - 包含内容摘要的研报: {len(reports_with_summary)}")
    
    if reports_with_content:
        print(f"\n   前3条包含内容的研报:")
        for idx, report in enumerate(reports_with_content[:3], 1):
            content = report.get('研报内容', '')
            content_length = len(content)
            print(f"     {idx}. [{report.get('日期', '')}] {report.get('研报标题', '')}")
            print(f"        机构: {report.get('机构名称', '')}")
            print(f"        内容长度: {content_length} 字符")
            print(f"        内容预览: {content[:100]}...")
    else:
        print("   ⚠️ 没有获取到研报内容")
    
    # 检查内容分析
    print(f"\n[5] 检查内容分析结果...")
    content_analysis = research_data.get('content_analysis', {})
    if content_analysis:
        print(f"   - 包含内容分析的研报数: {content_analysis.get('total_reports_with_content', 0)}")
        print(f"   - 总字符数: {content_analysis.get('total_length', 0)}")
        print(f"   - 平均字符数: {content_analysis.get('avg_length', 0)}")
        
        key_topics = content_analysis.get('key_topics', [])
        if key_topics:
            print(f"   - 关键词: {', '.join(key_topics[:10])}")
        
        sentiment = content_analysis.get('sentiment_analysis', {})
        if sentiment:
            print(f"   - 情感倾向: {sentiment.get('sentiment', 'N/A')}")
            print(f"   - 情感得分: {sentiment.get('sentiment_score', 0)}")
            print(f"   - 正面信号: {sentiment.get('positive_signals', 0)}")
            print(f"   - 负面信号: {sentiment.get('negative_signals', 0)}")
    else:
        print("   ⚠️ 没有内容分析结果")
    
    # 显示统计分析摘要
    print(f"\n[6] 统计分析摘要...")
    summary = research_data.get('analysis_summary', {})
    if summary:
        rating_dist = summary.get('rating_distribution', {})
        if rating_dist:
            print(f"   - 评级分布:")
            for rating, count in list(rating_dist.items())[:5]:
                print(f"     {rating}: {count}")
        
        top_orgs = summary.get('top_institutions', {})
        if top_orgs:
            print(f"   - Top机构 (前5):")
            for org, count in list(top_orgs.items())[:5]:
                print(f"     {org}: {count}条研报")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == '__main__':
    # 测试单个股票
    test_research_reports('603197')
    
    print("\n\n")
    
    # 可选：测试其他股票
    # test_research_reports('000001')

