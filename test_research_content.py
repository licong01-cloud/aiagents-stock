#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试研报内容获取，检查Tushare report_rc接口的字段
"""
import sys
import io

# Windows控制台UTF-8支持
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from data_source_manager import data_source_manager
from datetime import datetime, timedelta
import pandas as pd

def test_report_rc_fields(symbol='603197'):
    """测试report_rc接口的返回字段"""
    print("=" * 60)
    print(f"测试股票代码: {symbol}")
    print("=" * 60)
    
    if not data_source_manager.tushare_available:
        print("❌ Tushare不可用")
        return
    
    try:
        # 转换股票代码
        from unified_data_access import unified_data_access
        ts_code = unified_data_access._convert_to_ts_code(symbol)
        print(f"\n[1] 转换后的Tushare代码: {ts_code}")
        
        # 计算日期范围（6个月）
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=180)).strftime('%Y%m%d')
        print(f"[2] 日期范围: {start_date} 至 {end_date}")
        
        # 获取数据
        print(f"\n[3] 调用 report_rc 接口...")
        df_reports = data_source_manager.tushare_api.report_rc(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date
        )
        
        if df_reports is None or df_reports.empty:
            print("❌ 未获取到数据")
            return
        
        print(f"✓ 获取到 {len(df_reports)} 条数据")
        
        # 显示所有列名
        print(f"\n[4] 所有列名:")
        for i, col in enumerate(df_reports.columns.tolist(), 1):
            print(f"   {i}. {col}")
        
        # 显示第一条数据的所有字段
        print(f"\n[5] 第一条数据的所有字段值:")
        if len(df_reports) > 0:
            first_row = df_reports.iloc[0]
            for col in df_reports.columns:
                value = first_row.get(col, '')
                # 只显示非空字段，且限制长度
                if pd.notna(value) and str(value).strip():
                    value_str = str(value)
                    if len(value_str) > 100:
                        value_str = value_str[:100] + '...'
                    print(f"   {col}: {value_str}")
        
        # 检查是否有类似内容的字段
        print(f"\n[6] 检查可能的内容字段:")
        content_like_cols = [col for col in df_reports.columns if 
                           any(keyword in col.lower() for keyword in ['content', 'text', 'abstract', 'summary', 'desc', 'note'])]
        if content_like_cols:
            print(f"   找到可能的内容字段: {content_like_cols}")
            for col in content_like_cols:
                non_null_count = df_reports[col].notna().sum()
                print(f"   - {col}: {non_null_count}/{len(df_reports)} 条非空")
        else:
            print("   ⚠️ 未找到明显的内容字段")
        
        # 显示字段类型
        print(f"\n[7] 字段类型信息:")
        print(df_reports.dtypes)
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_report_rc_fields('603197')

