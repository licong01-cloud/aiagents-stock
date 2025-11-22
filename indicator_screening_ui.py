from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from indicator_screening import run_open_0935_strategy
from pg_watchlist_repo import watchlist_repo
from data_source_manager import data_source_manager
from unified_data_access import unified_data_access as udao


def display_indicator_screening() -> None:
    """指标选股主界面（首个 9:35 开盘策略骨架）。

    当前实现的条件包括：
    - 当日涨跌幅区间（近似 9:35 前涨跌幅，使用日线 pct_chg）
    - 换手率 ≥ 阈值
    - 当日成交量 ≥ 阈值
    - 流通股本 / 流通市值上限
    - 股价在 20 日均线上方
    - 当日 + 近 10 日主力净流入
    其它暂未有数据源的条件会在结果中明确列为“未实现过滤”。
    """

    st.title("📊 指标选股（开盘 9:35 策略）")
    st.caption("基于 9:35 分钟线、换手率、资金流与市值等多指标的开盘选股策略，可用于盘中实盘与历史回测验证。")

    with st.form("indicator_screening_form"):
        st.subheader("参数设置")
        col_top, col_date = st.columns([1, 1])
        with col_date:
            trade_date = st.date_input(
                "交易日",
                value=dt.date.today(),
                help="策略按交易日运行，建议选择已完成的交易日用于回测。",
            )
        with col_top:
            top_n = st.number_input(
                "保留前 N 名",
                min_value=10,
                max_value=2000,
                value=100,
                step=10,
                help="最终按涨跌幅排序后保留前 N 名。",
            )

        col1, col2, col3 = st.columns(3)
        with col1:
            pct_chg_min = st.number_input("9:35 涨跌幅下限(%)", value=-1.5, step=0.1)
            turnover_min = st.number_input("换手率下限(%)", value=3.0, step=0.5)
            vol_min = st.number_input("9:35 成交量下限(手)", value=50_000, step=5_000)
        with col2:
            pct_chg_max = st.number_input("9:35 涨跌幅上限(%)", value=2.5, step=0.1)
            float_share_max_e = st.number_input("流通股本上限(亿股)", value=150.0, step=10.0)
            float_mv_max_e = st.number_input("流通市值上限(亿元)", value=500.0, step=50.0)
        with col3:
            net_today_min_w = st.number_input("当日净流入下限(万元)", value=2000.0, step=500.0)
            net_10d_min_w = st.number_input("近10日净流入下限(万元)", value=2000.0, step=500.0)
            run_btn = st.form_submit_button("🚀 执行选股", type="primary")

    # 运行策略（仅在点击按钮时），并将结果缓存到 session_state
    if run_btn:
        trade_date_str = trade_date.strftime("%Y%m%d")
        with st.spinner(f"正在执行开盘 9:35 策略 · 交易日 {trade_date_str} ..."):
            result = run_open_0935_strategy(
                trade_date_str,
                top_n=int(top_n),
                pct_chg_min=float(pct_chg_min),
                pct_chg_max=float(pct_chg_max),
                turnover_min=float(turnover_min),
                volume_hand_min=int(vol_min),
                float_share_max=float(float_share_max_e) * 1_0000_0000,
                float_mv_max=float(float_mv_max_e) * 1_0000_0000,
                net_inflow_today_min=float(net_today_min_w) * 10_000,
                net_inflow_10d_min=float(net_10d_min_w) * 10_000,
            )
        # 缓存结果和交易日字符串，后续交互时直接使用
        st.session_state["indicator_screening_result"] = result
        st.session_state["indicator_screening_trade_date"] = trade_date_str

    # 读取缓存结果（无论是否刚刚点击按钮）
    result = st.session_state.get("indicator_screening_result")
    trade_date_str = st.session_state.get("indicator_screening_trade_date", "")

    if result is None:
        st.info("请选择参数并点击“执行选股”以运行策略。")
        return

    if not result.success:
        st.error(f"选股执行失败：{result.error}")
        if result.filters_applied or result.filters_skipped:
            with st.expander("调试信息（已应用/未应用条件）", expanded=False):
                st.write("**已应用条件：**")
                for f in result.filters_applied:
                    st.markdown(f"- {f}")
                st.write("**未应用条件/未实现部分：**")
                for f in result.filters_skipped:
                    st.markdown(f"- {f}")
        return

    st.success(
        f"策略执行成功：候选 {result.total_candidates} 只，最终筛选 {result.selected_count} 只。"
    )

    with st.expander("查看策略过滤条件说明", expanded=True):
        st.write("**已应用条件：**")
        if result.filters_applied:
            for f in result.filters_applied:
                st.markdown(f"- {f}")
        else:
            st.markdown("- （无）")

        st.write("**未应用条件 / 当前未实现部分：**")
        if result.filters_skipped:
            for f in result.filters_skipped:
                st.markdown(f"- {f}")
        else:
            st.markdown("- （无）")

    if result.df is None or result.df.empty:
        st.warning("过滤后没有满足条件的股票。")
        return

    df: pd.DataFrame = result.df.copy()

    # 通过统一数据接口补全股票名称
    if "ts_code" in df.columns:
        # 若缺少 name 列或存在空值，则尝试补全
        if "name" not in df.columns or df["name"].isna().any():
            codes = df["ts_code"].dropna().astype(str).unique().tolist()
            name_map: Dict[str, str] = {}
            for ts_code in codes:
                try:
                    base_code = data_source_manager._convert_from_ts_code(ts_code) if "." in ts_code else ts_code
                    # 1) 统一数据接口，传入 6 位代码
                    info = udao.get_stock_basic_info(base_code) or {}
                    nm = info.get("name") or info.get("stock_name")
                    # 若统一接口未返回名称，直接通过数据源管理器兜底
                    if not nm:
                        # 2) 统一接口尝试使用 ts_code 本身
                        info2 = udao.get_stock_basic_info(ts_code) or {}
                        nm = info2.get("name") or info2.get("stock_name")
                    if not nm:
                        # 3) 直接通过数据源管理器
                        raw_info = data_source_manager.get_stock_basic_info(base_code) or {}
                        nm = raw_info.get("name") or raw_info.get("stock_name")
                    if nm:
                        name_map[ts_code] = str(nm)
                except Exception:
                    continue
            if "name" not in df.columns:
                df["name"] = df["ts_code"].map(name_map)
            else:
                df["name"] = df["name"].fillna(df["ts_code"].map(name_map))

    # 若仍不存在 name 列，则用代码占位，保证前端一定有“名称”列
    if "name" not in df.columns:
        if "ts_code" in df.columns:
            df["name"] = df["ts_code"].astype(str)
        else:
            df["name"] = ""

    # 显示中文列名并加入选择列
    col_map = {
        "ts_code": "代码",
        "name": "名称",
        "pct_chg": "涨跌幅%",
        "pct_chg_0935": "9:35涨跌幅%",
        "turnover_rate": "换手率%",
        "vol": "成交量(手)",
        "vol_0935": "9:35成交量(手)",
        "float_share": "流通股本(股)",
        "circ_mv": "流通市值(万元)",
        "close": "收盘价",
        "ma20": "20日均价",
        "net_mf_today": "当日主力净流入",
        "net_mf_10d": "近10日主力净流入",
        "volume_ratio_0935": "9:35量比",
    }

    df_display = df.copy()
    df_display.insert(0, "选择", False)
    for k, v in col_map.items():
        if k in df_display.columns:
            df_display.rename(columns={k: v}, inplace=True)

    # 若中文列名中不存在“名称”，则用代码列复制一份，保证界面一定有名称列
    if "名称" not in df_display.columns:
        code_col = None
        if "代码" in df_display.columns:
            code_col = "代码"
        elif "ts_code" in df_display.columns:
            code_col = "ts_code"
        if code_col is not None:
            df_display.insert(1, "名称", df_display[code_col].astype(str))
    else:
        # 已存在“名称”列但可能为空，使用代码列兜底填充
        code_col = "代码" if "代码" in df_display.columns else ("ts_code" if "ts_code" in df_display.columns else None)
        if code_col is not None:
            df_display["名称"] = df_display["名称"].fillna(df_display[code_col].astype(str))

    # 保证列顺序：选择, 名称, 代码, 其余列保持原有顺序
    cols = list(df_display.columns)
    new_order = []
    for fixed in ["选择", "名称", "代码"]:
        if fixed in cols and fixed not in new_order:
            new_order.append(fixed)
    for c in cols:
        if c not in new_order:
            new_order.append(c)
    df_display = df_display[new_order]

    st.markdown("### 📄 筛选结果一览")
    edited = st.data_editor(
        df_display,
        use_container_width=True,
        num_rows="fixed",
        key="indicator_screening_result_editor",
    )

    selected_idx: List[int] = []
    if "选择" in edited.columns:
        selected_idx = [i for i, flag in enumerate(edited["选择"].tolist()) if bool(flag)]

    # 导出 CSV
    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="💾 导出为 CSV",
        data=csv_bytes,
        file_name=f"indicator_screening_{trade_date_str}.csv",
        mime="text/csv",
    )

    # 批量操作区
    st.markdown("---")
    st.subheader("批量操作")
    if not selected_idx:
        st.info("在上表中勾选多只股票后，再点击下面的批量操作按钮。")

    selected_df = df.iloc[selected_idx].copy() if selected_idx else df.iloc[0:0].copy()
    ts_codes = selected_df.get("ts_code") if not selected_df.empty else None
    ts_codes_list: List[str] = [str(x) for x in ts_codes.tolist()] if ts_codes is not None else []

    # 加入自选股
    cats = watchlist_repo.list_categories()
    cat_map = {c["name"]: c["id"] for c in cats}
    cat_options = ["默认"] + [c["name"] for c in cats if c["name"] != "默认"] + ["新建分类..."]
    col_w1, col_w2 = st.columns([2, 1])
    with col_w1:
        target_cat = st.selectbox("选择自选股分类", options=cat_options, key="indicator_watchlist_cat")
        new_cat_name = ""
        if target_cat == "新建分类...":
            new_cat_name = st.text_input("新建分类名称", key="indicator_watchlist_new_cat")
    with col_w2:
        if st.button("⭐ 加入自选股", key="indicator_add_to_watchlist"):
            try:
                if not ts_codes_list:
                    st.warning("选中行缺少 ts_code，无法加入自选股。")
                else:
                    if target_cat == "新建分类...":
                        new_cat_name = (new_cat_name or "").strip()
                        if not new_cat_name:
                            st.warning("请输入新建分类名称")
                            st.stop()
                        cat_id = watchlist_repo.create_category(new_cat_name, None)
                    else:
                        if target_cat == "默认":
                            if "默认" in cat_map:
                                cat_id = cat_map["默认"]
                            else:
                                cat_id = watchlist_repo.create_category("默认", "默认分类")
                        else:
                            cat_id = cat_map.get(target_cat) or watchlist_repo.create_category(target_cat, None)

                    names_map: Dict[str, str] = {}
                    if "name" in selected_df.columns:
                        for _, row in selected_df.iterrows():
                            code = str(row.get("ts_code"))
                            nm = str(row.get("name")) if row.get("name") is not None else code
                            names_map[code] = nm
                    watchlist_repo.add_items_bulk(ts_codes_list, cat_id, on_conflict="ignore", names=names_map)
                    st.success(f"已将 {len(ts_codes_list)} 只股票加入自选股")
            except Exception as e:
                st.error(f"加入自选股失败: {e}")

    # 批量分析导入
    st.markdown("")
    col_b1, col_b2 = st.columns([2, 1])
    with col_b1:
        st.caption("将所选股票导入首页批量分析输入框")
    with col_b2:
        if st.button("📊 批量分析选中股票", key="indicator_batch_analysis"):
            try:
                if not ts_codes_list:
                    st.warning("请先在表格中勾选要批量分析的股票。")
                else:
                    codes_for_batch: List[str] = []
                    for ts_code in ts_codes_list:
                        base_code = data_source_manager._convert_from_ts_code(ts_code) if "." in ts_code else ts_code
                        codes_for_batch.append(base_code)
                    st.session_state["prefill_batch_codes"] = "\n".join(codes_for_batch)
                    st.success("已将选中股票代码写入批量分析预填，切换到首页“批量分析”模式即可使用。")
            except Exception as e:
                st.error(f"批量分析导入失败: {e}")
