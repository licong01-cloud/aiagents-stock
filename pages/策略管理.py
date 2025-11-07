"""
策略管理UI模块
提供策略创建、回测、查看等功能的独立页面
"""

import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
import uuid

# 导入策略模块（独立模块，不影响现有功能）
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy_db import StrategyDB, BacktestDB, init_database, get_db
from strategy_backtest_engine import BacktestEngine


# 页面配置
st.set_page_config(
    page_title="策略管理",
    page_icon="📊",
    layout="wide"
)

# 初始化数据库
@st.cache_resource
def initialize_database():
    """初始化策略数据库（独立数据库）"""
    try:
        get_db()
        return True
    except:
        return init_database()

initialize_database()

# Session State 初始化（使用独立命名空间）
if 'strategy_mgmt_current_view' not in st.session_state:
    st.session_state.strategy_mgmt_current_view = '策略列表'

if 'strategy_mgmt_selected_strategy_id' not in st.session_state:
    st.session_state.strategy_mgmt_selected_strategy_id = None


def show_strategy_list():
    """显示策略列表"""
    st.header("📋 策略列表")
    
    # 筛选器
    col1, col2, col3 = st.columns(3)
    with col1:
        filter_type = st.selectbox("策略类型", ["全部", "选股策略", "交易策略"])
    with col2:
        filter_status = st.selectbox("状态", ["全部", "激活", "停用", "测试中"])
    with col3:
        st.write("")  # 占位
    
    # 构建筛选条件
    filters = {}
    if filter_type != "全部":
        filters['type'] = 'selection' if filter_type == "选股策略" else 'trading'
    if filter_status != "全部":
        status_map = {"激活": "active", "停用": "inactive", "测试中": "testing"}
        filters['status'] = status_map[filter_status]
    
    # 获取策略列表
    result = StrategyDB.list_strategies(filters)
    
    if result['success'] and result['strategies']:
        strategies = result['strategies']
        
        # 显示为表格
        display_data = []
        for s in strategies:
            display_data.append({
                'ID': s['id'],
                '策略名称': s['name'],
                '类型': '选股策略' if s['type'] == 'selection' else '交易策略',
                '状态': {'active': '✅激活', 'inactive': '⏸️停用', 'testing': '🧪测试中'}.get(s['status'], s['status']),
                '回测次数': s['total_backtests'],
                '平均收益': f"{s['avg_return']*100:.2f}%" if s['avg_return'] else '-',
                '胜率': f"{s['avg_win_rate']*100:.2f}%" if s['avg_win_rate'] else '-',
                '创建时间': s['created_at'][:10] if s['created_at'] else '-'
            })
        
        df = pd.DataFrame(display_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # 操作按钮
        st.write("---")
        col1, col2, col3 = st.columns([1, 1, 3])
        with col1:
            selected_id = st.number_input("选择策略ID", min_value=1, value=1, step=1)
        with col2:
            if st.button("🔍 查看详情"):
                st.session_state.strategy_mgmt_selected_strategy_id = selected_id
                st.session_state.strategy_mgmt_current_view = '策略详情'
                st.rerun()
        with col3:
            if st.button("🗑️ 删除策略"):
                result = StrategyDB.delete_strategy(selected_id)
                if result['success']:
                    st.success(f"✅ 策略 {selected_id} 已删除")
                    st.rerun()
                else:
                    st.error(f"❌ 删除失败: {result.get('error')}")
    else:
        st.info("📭 暂无策略，点击下方按钮创建新策略")
    
    # 创建新策略按钮
    st.write("---")
    if st.button("➕ 创建新策略", type="primary"):
        st.session_state.strategy_mgmt_current_view = '创建策略'
        st.rerun()


def show_create_strategy():
    """显示创建策略界面"""
    st.header("➕ 创建新策略")
    
    with st.form("create_strategy_form"):
        # 基本信息
        st.subheader("📝 基本信息")
        col1, col2 = st.columns(2)
        with col1:
            strategy_name = st.text_input("策略名称*", placeholder="例如：均线金叉策略")
            strategy_type = st.selectbox("策略类型*", ["交易策略", "选股策略"])
        with col2:
            strategy_category = st.text_input("分类", placeholder="例如：趋势跟踪")
            strategy_status = st.selectbox("状态", ["激活", "测试中", "停用"])
        
        strategy_description = st.text_area("策略描述*", placeholder="描述策略的核心逻辑...")
        
        # 入场条件
        st.subheader("📈 入场条件")
        st.write("**简单条件输入**（后续版本将提供可视化构建器）")
        
        entry_logic = st.radio("入场逻辑", ["AND（所有条件满足）", "OR（任一条件满足）"], horizontal=True)
        
        num_entry_conditions = st.number_input("入场条件数量", min_value=1, max_value=5, value=1)
        entry_conditions_list = []
        
        for i in range(num_entry_conditions):
            st.write(f"**条件 {i+1}**")
            col1, col2, col3 = st.columns(3)
            with col1:
                left = st.text_input(f"左值", key=f"entry_left_{i}", placeholder="例如：ma5")
            with col2:
                operator = st.selectbox(
                    f"运算符",
                    [">", "<", ">=", "<=", "==", "!=", "cross_above", "cross_below"],
                    key=f"entry_op_{i}"
                )
            with col3:
                right = st.text_input(f"右值", key=f"entry_right_{i}", placeholder="例如：ma20 或 50")
            
            if left and right:
                entry_conditions_list.append({
                    'left': left,
                    'operator': operator,
                    'right': right
                })
        
        # 退出条件
        st.subheader("📉 退出条件（可选）")
        use_exit_conditions = st.checkbox("使用自定义退出条件（否则使用默认止盈止损）")
        
        exit_conditions_list = []
        exit_logic = "AND（所有条件满足）"  # 默认值
        if use_exit_conditions:
            exit_logic = st.radio("退出逻辑", ["AND（所有条件满足）", "OR（任一条件满足）"], horizontal=True, key="exit_logic")
            num_exit_conditions = st.number_input("退出条件数量", min_value=1, max_value=5, value=1)
            
            for i in range(num_exit_conditions):
                st.write(f"**条件 {i+1}**")
                col1, col2, col3 = st.columns(3)
                with col1:
                    left = st.text_input(f"左值", key=f"exit_left_{i}", placeholder="例如：ma5")
                with col2:
                    operator = st.selectbox(
                        f"运算符",
                        [">", "<", ">=", "<=", "==", "!=", "cross_above", "cross_below"],
                        key=f"exit_op_{i}"
                    )
                with col3:
                    right = st.text_input(f"右值", key=f"exit_right_{i}", placeholder="例如：ma20")
                
                if left and right:
                    exit_conditions_list.append({
                        'left': left,
                        'operator': operator,
                        'right': right
                    })
        
        # 提交按钮
        submitted = st.form_submit_button("✅ 创建策略", type="primary")
        
        if submitted:
            if not strategy_name or not strategy_description:
                st.error("❌ 请填写策略名称和描述")
            elif not entry_conditions_list:
                st.error("❌ 请至少添加一个入场条件")
            else:
                # 构建策略数据
                strategy_data = {
                    'uuid': str(uuid.uuid4()),
                    'name': strategy_name,
                    'type': 'trading' if strategy_type == "交易策略" else 'selection',
                    'category': strategy_category if strategy_category else None,
                    'description': strategy_description,
                    'logic_description': strategy_description,  # 简化版本
                    'status': {'激活': 'active', '测试中': 'testing', '停用': 'inactive'}[strategy_status],
                    'entry_conditions': {
                        'operator': 'AND' if entry_logic.startswith('AND') else 'OR',
                        'conditions': entry_conditions_list
                    },
                    'exit_conditions': {
                        'operator': 'AND' if use_exit_conditions and exit_logic.startswith('AND') else 'OR',
                        'conditions': exit_conditions_list
                    } if use_exit_conditions else {},
                    'required_indicators': list(set([c['left'] for c in entry_conditions_list if isinstance(c['left'], str) and not c['left'].replace('.','').isdigit()])),
                    'parameters': {}
                }
                
                # 保存策略
                result = StrategyDB.create_strategy(strategy_data)
                if result['success']:
                    st.success(f"✅ 策略创建成功！ID: {result['strategy_id']}")
                    st.balloons()
                    st.session_state.strategy_mgmt_selected_strategy_id = result['strategy_id']
                    
                    # 延迟跳转
                    import time
                    time.sleep(1)
                    st.session_state.strategy_mgmt_current_view = '策略详情'
                    st.rerun()
                else:
                    st.error(f"❌ 创建失败: {result.get('error')}")
    
    # 返回按钮
    if st.button("⬅️ 返回列表"):
        st.session_state.strategy_mgmt_current_view = '策略列表'
        st.rerun()


def show_strategy_detail():
    """显示策略详情"""
    strategy_id = st.session_state.strategy_mgmt_selected_strategy_id
    
    if not strategy_id:
        st.error("❌ 未选择策略")
        if st.button("⬅️ 返回列表"):
            st.session_state.strategy_mgmt_current_view = '策略列表'
            st.rerun()
        return
    
    # 获取策略详情
    result = StrategyDB.get_strategy(strategy_id)
    if not result['success']:
        st.error(f"❌ 策略不存在: {result.get('error')}")
        if st.button("⬅️ 返回列表"):
            st.session_state.strategy_mgmt_current_view = '策略列表'
            st.rerun()
        return
    
    strategy = result['strategy']
    
    # 显示策略信息
    st.header(f"📋 {strategy['name']}")
    
    # 基本信息
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("策略ID", strategy['id'])
    with col2:
        st.metric("类型", "交易策略" if strategy['type'] == 'trading' else "选股策略")
    with col3:
        st.metric("状态", {'active': '✅激活', 'inactive': '⏸️停用', 'testing': '🧪测试中'}.get(strategy['status']))
    with col4:
        st.metric("回测次数", strategy['total_backtests'])
    
    # 统计指标
    if strategy['total_backtests'] > 0:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("平均收益率", f"{strategy['avg_return']*100:.2f}%" if strategy['avg_return'] else "0%")
        with col2:
            st.metric("平均胜率", f"{strategy['avg_win_rate']*100:.2f}%" if strategy['avg_win_rate'] else "0%")
        with col3:
            st.metric("平均最大回撤", f"{strategy['avg_max_drawdown']*100:.2f}%" if strategy['avg_max_drawdown'] else "0%")
    
    # 策略描述
    with st.expander("📝 策略描述", expanded=True):
        st.write(strategy['description'])
    
    # 入场条件
    with st.expander("📈 入场条件", expanded=True):
        entry = strategy['entry_conditions']
        st.write(f"**逻辑**: {entry.get('operator', 'AND')}")
        for i, cond in enumerate(entry.get('conditions', []), 1):
            st.write(f"{i}. `{cond['left']}` {cond['operator']} `{cond['right']}`")
    
    # 退出条件
    with st.expander("📉 退出条件"):
        exit_cond = strategy.get('exit_conditions', {})
        if exit_cond and exit_cond.get('conditions'):
            st.write(f"**逻辑**: {exit_cond.get('operator', 'AND')}")
            for i, cond in enumerate(exit_cond.get('conditions', []), 1):
                st.write(f"{i}. `{cond['left']}` {cond['operator']} `{cond['right']}`")
        else:
            st.info("使用默认止盈止损：止盈10%，止损5%")
    
    # 回测按钮
    st.write("---")
    st.subheader("🧪 执行回测")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        stock_code = st.text_input("股票代码*", placeholder="例如：600519")
    with col2:
        start_date = st.date_input("开始日期", value=datetime.now() - timedelta(days=365))
    with col3:
        end_date = st.date_input("结束日期", value=datetime.now())
    with col4:
        initial_capital = st.number_input("初始资金", value=100000, step=10000)
    
    if st.button("🚀 开始回测", type="primary"):
        if not stock_code:
            st.error("❌ 请输入股票代码")
        else:
            with st.spinner("回测进行中..."):
                engine = BacktestEngine()
                backtest_result = engine.run_backtest(
                    strategy_id=strategy_id,
                    stock_code=stock_code,
                    start_date=start_date.strftime('%Y%m%d'),
                    end_date=end_date.strftime('%Y%m%d'),
                    initial_capital=initial_capital
                )
            
            if backtest_result['success']:
                st.success("✅ 回测完成！")
                
                # 显示回测结果
                st.write("---")
                st.subheader("📊 回测结果")
                
                # 核心指标
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("总收益率", f"{backtest_result['total_return']*100:.2f}%")
                with col2:
                    st.metric("年化收益", f"{backtest_result['annual_return']*100:.2f}%")
                with col3:
                    st.metric("最大回撤", f"{backtest_result['max_drawdown']*100:.2f}%")
                with col4:
                    st.metric("夏普比率", f"{backtest_result['sharpe_ratio']:.2f}")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("交易次数", backtest_result['total_trades'])
                with col2:
                    st.metric("胜率", f"{backtest_result['win_rate']*100:.2f}%")
                with col3:
                    st.metric("盈亏比", f"{backtest_result['profit_loss_ratio']:.2f}")
                with col4:
                    st.metric("平均持仓", f"{backtest_result['avg_holding_days']:.1f}天")
                
                # 交易明细
                with st.expander("📜 交易明细", expanded=False):
                    if backtest_result['trade_details']:
                        trades_df = pd.DataFrame(backtest_result['trade_details'])
                        st.dataframe(trades_df, use_container_width=True)
                    else:
                        st.info("无交易记录")
                
            else:
                st.error(f"❌ 回测失败: {backtest_result.get('error')}")
    
    # 返回按钮
    st.write("---")
    if st.button("⬅️ 返回列表"):
        st.session_state.strategy_mgmt_current_view = '策略列表'
        st.rerun()


# 主界面
def main():
    """主界面"""
    st.title("📊 策略管理系统")
    st.caption("独立的量化策略回测与管理平台")
    
    # 侧边栏导航
    with st.sidebar:
        st.write("### 🗂️ 功能导航")
        view = st.radio(
            "选择功能",
            ['策略列表', '创建策略'],
            index=['策略列表', '创建策略'].index(st.session_state.strategy_mgmt_current_view) 
                if st.session_state.strategy_mgmt_current_view in ['策略列表', '创建策略'] else 0
        )
        
        st.session_state.strategy_mgmt_current_view = view
        
        st.write("---")
        st.info("💡 **提示**\n\n本模块完全独立运行，不影响系统其他功能。")
    
    # 根据当前视图显示对应界面
    if st.session_state.strategy_mgmt_current_view == '策略列表':
        show_strategy_list()
    elif st.session_state.strategy_mgmt_current_view == '创建策略':
        show_create_strategy()
    elif st.session_state.strategy_mgmt_current_view == '策略详情':
        show_strategy_detail()


if __name__ == '__main__':
    main()
