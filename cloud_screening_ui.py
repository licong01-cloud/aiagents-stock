from __future__ import annotations

from typing import Dict, List, Any

import pandas as pd
import streamlit as st

from cloud_screening import get_cloud_selector
from pg_watchlist_repo import watchlist_repo
from data_source_manager import data_source_manager


def _extract_stock_df(resp: Dict[str, Any]) -> pd.DataFrame:
    """按照 go-stock 指标选股客户端的方式，从响应中提取股票列表。

    - 只在 resp["code"] == 100 且存在 data.result.columns/dataList 时返回结果；
    - 使用 SECURITY_CODE/SECURITY_SHORT_NAME 作为 code/name 的主要来源。
    """

    if not isinstance(resp, dict):
        return pd.DataFrame()

    code_val = resp.get("code")
    # 东财有时返回字符串 "100"，有时返回整型 100，这里统一视为成功
    if str(code_val) != "100":
        return pd.DataFrame()

    data = resp.get("data") or {}
    if not isinstance(data, dict):
        return pd.DataFrame()

    result = data.get("result") or {}
    if not isinstance(result, dict):
        return pd.DataFrame()

    columns = result.get("columns") or []
    data_list = result.get("dataList") or []
    if not isinstance(columns, list) or not isinstance(data_list, list) or not data_list:
        return pd.DataFrame()

    # 构造列 key -> 显示名（参考 go-stock Python client 的逻辑，做简化）
    headers: Dict[str, str] = {}
    for col in columns:
        if not isinstance(col, dict):
            continue
        if col.get("hiddenNeed"):
            continue
        title = str(col.get("title") or "")
        unit = col.get("unit") or ""
        if unit:
            title = f"{title}[{unit}]"

        children = col.get("children")
        if not children:
            key = col.get("key")
            if key:
                headers[str(key)] = title
        else:
            for child in children:
                if not isinstance(child, dict) or child.get("hiddenNeed"):
                    continue
                child_key = child.get("key")
                if not child_key:
                    continue
                child_title = child.get("dateMsg") or title
                headers[str(child_key)] = str(child_title)

    rows: List[Dict[str, Any]] = []
    for item in data_list:
        if not isinstance(item, dict):
            continue

        # 代码/名称优先从标准字段中提取
        code = (
            item.get("SECURITY_CODE")
            or item.get("code")
            or item.get("stockCode")
            or item.get("f12")
            or ""
        )
        name = (
            item.get("SECURITY_SHORT_NAME")
            or item.get("name")
            or item.get("stockName")
            or item.get("f14")
            or ""
        )

        row: Dict[str, Any] = {
            "code": str(code),
            "name": str(name),
        }

        for key, col_name in headers.items():
            row[col_name] = item.get(key)

        rows.append(row)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).drop_duplicates(subset=["code"]).reset_index(drop=True)
    return df


def _parse_hot_strategies(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从热门策略接口返回数据中解析出策略列表。

    返回元素包含：id, name, desc, keyword。
    """

    if not isinstance(raw, dict):
        return []

    data = raw.get("data")
    items: List[Dict[str, Any]] = []
    if isinstance(data, list):
        items = [it for it in data if isinstance(it, dict)]
    elif isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                items = [it for it in v if isinstance(it, dict)]
                break

    strategies: List[Dict[str, Any]] = []
    for idx, it in enumerate(items):
        # 东财热门策略核心字段：question（完整策略描述）
        question = it.get("question")

        # 名称字段尽量多兜底
        name = (
            question
            or it.get("name")
            or it.get("strategyName")
            or it.get("title")
            or it.get("label")
            or it.get("tagName")
            or it.get("desc")
            or it.get("description")
            or f"策略{idx+1}"
        )

        # 描述字段也多尝试几种
        desc = (
            question
            or it.get("desc")
            or it.get("description")
            or it.get("subTitle")
            or it.get("subtitle")
            or it.get("reason")
            or it.get("reasonDesc")
            or it.get("content")
            or it.get("remark")
            or it.get("tip")
            or ""
        )

        # 关键词：优先用 question，其次用专门字段和名称类字段
        keyword = (
            question
            or it.get("keyWord")
            or it.get("keyword")
            or it.get("words")
            or it.get("query")
            or it.get("name")
            or it.get("strategyName")
            or it.get("title")
            or it.get("label")
            or ""
        )

        sid = it.get("id") or it.get("strategyId") or it.get("code") or name
        strategies.append({
            "id": sid,
            "name": str(name),
            "desc": str(desc),
            "keyword": str(keyword),
        })

    return strategies


def display_cloud_screening() -> None:
    """云选股界面：直接调用东财智能选股接口（实验性）。"""

    st.title("☁ 云选股（东方财富智能选股）")
    st.caption("基于东方财富智能选股/热门策略接口，仅作为策略参考，与本地指标选股互不影响。")

    selector = get_cloud_selector()

    col_left, col_right = st.columns([2, 1])
    with col_left:
        keyword = st.text_input("自定义选股关键词/策略描述", value="", placeholder="例如：高成长、银行、半导体、人气龙头等")
    with col_right:
        page_size = st.number_input("返回数量", min_value=10, max_value=500, value=100, step=10)

    # 自定义策略：缓存在 session_state
    saved_strategies: List[Dict[str, Any]] = st.session_state.get("cloud_saved_strategies", [])

    with st.expander("自定义云选股策略", expanded=False):
        col_s1, col_s2 = st.columns([2, 1])
        with col_s1:
            new_strategy_name = st.text_input("当前条件保存为策略名称", value="", key="cloud_new_strategy_name")
        with col_s2:
            if st.button("💾 保存当前条件", key="cloud_save_strategy_btn"):
                k = (keyword or "").strip()
                n = (new_strategy_name or "").strip()
                if not k:
                    st.warning("请输入要保存的选股条件文本。")
                elif not n:
                    st.warning("请输入策略名称。")
                else:
                    # 追加或覆盖同名策略
                    updated: List[Dict[str, Any]] = []
                    replaced = False
                    for it in saved_strategies:
                        if it.get("name") == n:
                            updated.append({"name": n, "keyword": k})
                            replaced = True
                        else:
                            updated.append(it)
                    if not replaced:
                        updated.append({"name": n, "keyword": k})
                    st.session_state["cloud_saved_strategies"] = updated
                    saved_strategies = updated
                    st.success("已保存自定义策略，可在下拉菜单中选用。")

        # 自定义策略下拉选择
        custom_options = ["不使用自定义策略"] + [s["name"] for s in saved_strategies]
        selected_custom_name = st.selectbox("选择自定义云选股策略（可选）", options=custom_options, key="cloud_custom_strategy_select")
        selected_custom_strategy = None
        if selected_custom_name != "不使用自定义策略":
            for s in saved_strategies:
                if s["name"] == selected_custom_name:
                    selected_custom_strategy = s
                    break

    # 热门策略数据：缓存到 session_state
    hot_strategies: List[Dict[str, Any]] = st.session_state.get("cloud_hot_strategies", [])

    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        run_btn = st.button("🚀 执行云选股", type="primary")
    with col_btn2:
        refresh_hot_btn = st.button("🔥 刷新热门云策略")

    if refresh_hot_btn or not hot_strategies:
        try:
            hot_resp = selector.get_hot_strategies(limit=20)
            # 保存原始热门策略返回，方便调试字段
            st.session_state["cloud_hot_raw"] = hot_resp
            hot_strategies = _parse_hot_strategies(hot_resp)
            st.session_state["cloud_hot_strategies"] = hot_strategies
        except Exception as e:
            st.warning(f"获取热门策略失败：{e}")

    # 热门策略区
    with st.expander("热门云选股策略（来自东方财富）", expanded=False):
        if hot_strategies:
            for idx, it in enumerate(hot_strategies, start=1):
                title = it.get("name") or f"策略 {idx}"
                desc = it.get("desc") or ""
                st.markdown(f"**{idx}. {title}**  ")
                if desc:
                    st.markdown(f"{desc}")
        else:
            st.info("暂无热门策略列表，可直接使用自定义关键词进行云选股。")

    # 热门策略下拉框
    strategy_options = ["不使用热门策略"]
    if hot_strategies:
        strategy_options += [f"{i+1}. {s['name']}" for i, s in enumerate(hot_strategies)]
    selected_idx = st.selectbox(
        "选择热门云选股策略（可选）",
        options=list(range(len(strategy_options))),
        format_func=lambda i: strategy_options[i],
    )
    selected_strategy = None
    if selected_idx > 0 and hot_strategies:
        selected_strategy = hot_strategies[selected_idx - 1]

    # 选中策略的详细说明（对齐 go-stock 行为）
    if selected_strategy is not None:
        st.markdown(
            f"**已选择策略：{selected_strategy.get('name', '')}**"
        )
        desc_text = (selected_strategy.get("desc") or "").strip()
        if desc_text:
            st.caption(desc_text)

    df: pd.DataFrame | None = None

    if run_btn:
        # 优先顺序：输入框关键词 > 自定义策略 > 热门策略
        effective_keyword = keyword.strip()
        if not effective_keyword and selected_custom_strategy is not None:
            effective_keyword = (selected_custom_strategy.get("keyword") or "").strip()
        if not effective_keyword and selected_strategy is not None:
            effective_keyword = (selected_strategy.get("keyword") or selected_strategy.get("name") or "").strip()

        if not effective_keyword:
            st.warning("请输入自定义关键词或选择一个热门策略。")
        else:
            with st.spinner("正在调用东财云选股接口..."):
                try:
                    resp = selector.search(effective_keyword, int(page_size))
                    # 保存原始搜索返回，方便调试字段
                    st.session_state["cloud_search_raw"] = resp
                    df = _extract_stock_df(resp)
                    st.session_state["cloud_screening_df"] = df
                    st.session_state["cloud_screening_keyword"] = effective_keyword
                except Exception as e:
                    st.error(f"云选股接口调用失败：{e}")
                    return

    if df is None:
        df = st.session_state.get("cloud_screening_df")

    # 可选调试信息：展示东财原始返回前几条，便于确认字段名（需要时展开即可）
    with st.expander("调试：查看东财原始返回(可忽略)", expanded=False):
        raw_hot = st.session_state.get("cloud_hot_raw")
        raw_search = st.session_state.get("cloud_search_raw")
        if raw_hot is not None:
            st.markdown("**热门策略原始返回（最多前 5 条）**")
            try:
                data = raw_hot.get("data") if isinstance(raw_hot, dict) else None
                if isinstance(data, list):
                    st.json(data[:5])
                elif isinstance(data, dict):
                    # 取第一个 list 字段
                    lst = None
                    for v in data.values():
                        if isinstance(v, list):
                            lst = v
                            break
                    if lst is not None:
                        st.json(lst[:5])
            except Exception:
                st.write("热门策略原始结构：")
                st.json(raw_hot)

        if raw_search is not None:
            st.markdown("**搜索结果原始返回（最多前 5 条）**")
            try:
                data = raw_search.get("data") if isinstance(raw_search, dict) else None
                if isinstance(data, list):
                    st.json(data[:5])
                elif isinstance(data, dict):
                    lst = None
                    for v in data.values():
                        if isinstance(v, list):
                            lst = v
                            break
                    if lst is not None:
                        st.json(lst[:5])
            except Exception:
                st.write("搜索原始结构：")
                st.json(raw_search)

    # 若仍然没有可用股票结果，则给出提示后返回
    if df is None or df.empty:
        st.info("尚无云选股结果，请输入关键词或选择热门策略后点击“执行云选股”。")
        return

    st.success(f"云选股返回 {len(df)} 只股票（去重后）。")

    df_display = df.copy()
    df_display.insert(0, "选择", False)

    # 统一中文列名，避免重复：
    # - 若已有 "代码"/"名称" 列，则不再从 code/name 重命名；
    # - 若同时存在 code 和 代码，则优先保留 "代码" 并删除 "code"；name 同理。
    cols = list(df_display.columns)
    if "代码" in cols and "code" in cols:
        df_display.drop(columns=["code"], inplace=True)
        cols = list(df_display.columns)
    if "名称" in cols and "name" in cols:
        df_display.drop(columns=["name"], inplace=True)
        cols = list(df_display.columns)

    if "代码" not in df_display.columns and "code" in df_display.columns:
        df_display.rename(columns={"code": "代码"}, inplace=True)
    if "名称" not in df_display.columns and "name" in df_display.columns:
        df_display.rename(columns={"name": "名称"}, inplace=True)

    # 保证列顺序：选择, 名称, 代码
    cols = list(df_display.columns)
    new_order = []
    for fixed in ["选择", "名称", "代码"]:
        if fixed in cols and fixed not in new_order:
            new_order.append(fixed)
    for c in cols:
        if c not in new_order:
            new_order.append(c)
    df_display = df_display[new_order]

    st.markdown("### 📄 云选股结果")
    edited = st.data_editor(
        df_display,
        use_container_width=True,
        num_rows="fixed",
        key="cloud_screening_result_editor",
    )

    selected_idx: List[int] = []
    if "选择" in edited.columns:
        selected_idx = [i for i, flag in enumerate(edited["选择"].tolist()) if bool(flag)]

    selected_df = df.iloc[selected_idx].copy() if selected_idx else df.iloc[0:0].copy()

    # 批量操作区
    st.markdown("---")
    st.subheader("批量操作")

    # 导出 CSV
    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="💾 导出为 CSV",
        data=csv_bytes,
        file_name="cloud_screening_result.csv",
        mime="text/csv",
    )

    if selected_df.empty:
        st.info("在上表中勾选多只股票后，再点击下面的批量操作按钮。")
        return

    # 规范化代码：使用 data_source_manager 转为 ts_code
    ts_codes_list: List[str] = []
    names_map: Dict[str, str] = {}
    for _, row in selected_df.iterrows():
        base_code = str(row.get("code") or row.get("代码") or "").strip()
        if not base_code:
            continue
        try:
            ts_code = data_source_manager._convert_to_ts_code(base_code)
        except Exception:
            ts_code = base_code
        ts_codes_list.append(ts_code)
        nm = str(row.get("name") or row.get("名称") or base_code)
        names_map[ts_code] = nm

    # 加入自选股
    cats = watchlist_repo.list_categories()
    cat_map = {c["name"]: c["id"] for c in cats}
    cat_options = ["默认"] + [c["name"] for c in cats if c["name"] != "默认"] + ["新建分类..."]
    col_w1, col_w2 = st.columns([2, 1])
    with col_w1:
        target_cat = st.selectbox("选择自选股分类", options=cat_options, key="cloud_watchlist_cat")
        new_cat_name = ""
        if target_cat == "新建分类...":
            new_cat_name = st.text_input("新建分类名称", key="cloud_watchlist_new_cat")
    with col_w2:
        if st.button("⭐ 加入自选股", key="cloud_add_to_watchlist"):
            try:
                if not ts_codes_list:
                    st.warning("选中行缺少代码，无法加入自选股。")
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
        if st.button("📊 批量分析选中股票", key="cloud_batch_analysis"):
            try:
                if not ts_codes_list:
                    st.warning("请先在表格中勾选要批量分析的股票。")
                else:
                    # 批量分析使用基础代码格式
                    codes_for_batch: List[str] = [
                        str(r.get("code") or r.get("代码") or "").strip() for _, r in selected_df.iterrows()
                    ]
                    codes_for_batch = [c for c in codes_for_batch if c]
                    st.session_state["prefill_batch_codes"] = "\n".join(codes_for_batch)
                    st.success("已将选中股票代码写入批量分析预填，切换到首页“批量分析”模式即可使用。")
            except Exception as e:
                st.error(f"批量分析导入失败: {e}")
