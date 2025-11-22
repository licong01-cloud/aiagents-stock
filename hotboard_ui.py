from __future__ import annotations
import os
import time
import datetime as dt
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st
import plotly.express as px
import requests

from pg_watchlist_repo import watchlist_repo
from data_source_manager import data_source_manager

# optional click events
try:
    from streamlit_plotly_events import plotly_events  # type: ignore
except Exception:  # noqa: BLE001
    plotly_events = None  # type: ignore

BACKEND_BASE = os.getenv("TDX_BACKEND_BASE", "http://localhost:9000").rstrip("/")

MAPPING_SCHEMES = {
    "涨幅着色 · 流入定尺": {"color": "chg", "size": "flow"},
    "流入着色 · 涨幅定尺": {"color": "flow", "size": "chg"},
    "复合着色(α) · 流入定尺": {"color": "combo", "size": "flow"},
}

TDX_IDX_TYPES: List[str] = ["行业指数", "概念指数", "风格指数", "地域指数"]

COLOR_SCALE = ["#d73027", "#ffffff", "#1a9850"]  # 红-白-绿，0中心白（最高红、最低绿）


def _backend_get(path: str, **params) -> Dict[str, Any]:
    url = f"{BACKEND_BASE}{path}"
    q = {k: v for k, v in params.items() if v is not None and v != ""}
    r = requests.get(url, params=q, timeout=10)
    r.raise_for_status()
    return r.json() if r.content else {}


@st.cache_data(ttl=600, show_spinner=False)
def _cached_tdx_daily(date: str, idx_type: Optional[str]) -> Dict[str, Any]:
    return _backend_get("/api/hotboard/tdx/daily", date=date, idx_type=idx_type)


@st.cache_data(ttl=600, show_spinner=False)
def _cached_tdx_top_stocks(board_code: str, date: str, metric: str, limit: int) -> Dict[str, Any]:
    return _backend_get(
        "/api/hotboard/top-stocks/tdx",
        board_code=board_code,
        date=date,
        metric=metric,
        limit=limit,
    )


def _backend_post(path: str, json_payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{BACKEND_BASE}{path}"
    payload = {k: v for k, v in (json_payload or {}).items() if v is not None}
    r = requests.post(url, json=payload, timeout=10)
    r.raise_for_status()
    return r.json() if r.content else {}


def _to_ts_code(code_or_symbol: str) -> str:
    c = str(code_or_symbol).strip()
    if "." in c:
        return c
    try:
        return data_source_manager._convert_to_ts_code(c)
    except Exception:
        return c


def _render_top20_table(items: List[Dict[str, Any]], title: str, use_realtime: bool, date: Optional[str] = None) -> None:
    st.markdown(f"### {title}")
    # normalize
    rows: List[Dict[str, Any]] = []
    codes: List[str] = []
    for it in items:
        # realtime from Sina: fields vary, ensure code + name
        code6 = str(it.get("code") or it.get("ts_code") or it.get("symbol") or "").split(".")[-1].replace("sh", "").replace("sz", "")
        ts_code = _to_ts_code(code6)
        name = it.get("name") or it.get("ts_name") or ts_code
        rec: Dict[str, Any] = {"选择": False, "代码": ts_code, "名称": name}
        rows.append(rec)
        codes.append(ts_code)

    # fetch quote or daily
    extra_map: Dict[str, Dict[str, Any]] = {}
    if use_realtime:
        for ts in codes:
            try:
                base = data_source_manager._convert_from_ts_code(ts) if "." in ts else ts
                q = data_source_manager.get_realtime_quotes(base)
            except Exception:
                q = {}
            price = q.get("price")
            pre_close = q.get("pre_close")
            pct = None
            if isinstance(price, (int, float)) and isinstance(pre_close, (int, float)) and pre_close not in (0, None):
                try:
                    pct = (price - pre_close) / pre_close * 100.0
                except Exception:
                    pct = None
            extra_map[ts] = {
                "最新价": None if price is None else float(f"{price:.2f}"),
                "涨幅%": None if pct is None else float(f"{pct:.2f}"),
                "成交量(手)": q.get("volume") and float(q.get("volume") / 100.0) or None,
                "成交额": q.get("amount"),
                "开盘": q.get("open"),
                "昨收": q.get("pre_close"),
                "最高": q.get("high"),
                "最低": q.get("low"),
            }
    else:
        # historical daily from local K-line
        d = date or dt.date.today().isoformat()
        # query backend to get TDX top stocks already returns fields; if we call this function, items likely have computed pct_chg/amount
        for it in items:
            ts = it.get("ts_code") or _to_ts_code(it.get("code") or "")
            extra_map[ts] = {
                "最新价": None,
                "涨幅%": it.get("pct_chg"),
                "成交量(手)": it.get("volume_hand"),
                "成交额": it.get("amount"),
                "开盘": it.get("open_li"),
                "昨收": None,
                "最高": it.get("high_li"),
                "最低": it.get("low_li"),
            }

    # build DataFrame
    for r in rows:
        ex = extra_map.get(r["代码"], {})
        r.update(ex)
    df = pd.DataFrame(rows)
    edited = st.data_editor(
        df,
        column_config={
            "选择": st.column_config.CheckboxColumn("选择"),
            "代码": st.column_config.TextColumn("代码", width="small"),
            "名称": st.column_config.TextColumn("名称", width="small"),
            "最新价": st.column_config.NumberColumn("最新价", format="%.3f"),
            "涨幅%": st.column_config.NumberColumn("涨幅%", format="%.3f"),
            "开盘": st.column_config.NumberColumn("开盘", format="%.3f"),
            "昨收": st.column_config.NumberColumn("昨收", format="%.3f"),
            "最高": st.column_config.NumberColumn("最高", format="%.3f"),
            "最低": st.column_config.NumberColumn("最低", format="%.3f"),
            "成交量(手)": st.column_config.NumberColumn("成交量(手)", format="%.0f"),
            "成交额": st.column_config.NumberColumn("成交额", format="%.0f"),
        },
        disabled=["代码", "名称", "最新价", "涨幅%", "开盘", "昨收", "最高", "最低", "成交量(手)", "成交额"],
        hide_index=True,
        use_container_width=True,
        key=f"top20_{title}_{int(time.time())}"
    )

    # selection
    selected_codes: List[str] = []
    for idx, row in edited.iterrows():
        if bool(row.get("选择")):
            selected_codes.append(edited.iloc[idx]["代码"])  # ts_code

    st.markdown("#### 添加到自选股票池")
    cats = watchlist_repo.list_categories()
    name_to_cat = {c["name"]: c["id"] for c in cats}
    mode = st.radio("分类方式", options=["已有分类", "新建分类"], horizontal=True, key=f"wl_mode_{title}")
    target_cid: Optional[int] = None
    if mode == "新建分类":
        new_name = st.text_input("新建分类名称", key=f"wl_newcat_{title}")
        if st.button("创建并加入", disabled=(not selected_codes or not (new_name or "").strip()), key=f"wl_create_add_{title}"):
            try:
                cid = watchlist_repo.create_category(new_name.strip(), None)
                target_cid = cid
                _add_to_watchlist(selected_codes, target_cid)
                st.success("已加入自选")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"失败: {e}")
    else:
        sel = st.selectbox("选择已有分类", options=[c["name"] for c in cats] or ["默认"], key=f"wl_selcat_{title}")
        if st.button("加入所选分类", disabled=(not selected_codes or not sel), key=f"wl_add_{title}"):
            try:
                target_cid = name_to_cat.get(sel)
                if not target_cid:
                    target_cid = watchlist_repo.create_category(sel, None)
                _add_to_watchlist(selected_codes, target_cid)
                st.success("已加入自选")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"失败: {e}")


def _add_to_watchlist(ts_codes: List[str], category_id: int) -> None:
    if not ts_codes:
        return
    names_map: Dict[str, str] = {}
    for ts in ts_codes:
        base = data_source_manager._convert_from_ts_code(ts) if "." in ts else ts
        name = data_source_manager.get_stock_basic_info(base).get("name") if hasattr(data_source_manager, "get_stock_basic_info") else ts
        names_map[ts] = name or ts
    watchlist_repo.add_items_bulk(ts_codes, category_id, on_conflict="ignore", names=names_map)


def show_hotboard_page(embed: bool = False) -> None:
    """Render 热点板块跟踪 UI.

    When embed=True, assumes page_config 已由上层应用设置，不再调用 set_page_config。
    """
    if not embed:
        st.set_page_config(page_title="🔥 热点板块跟踪", page_icon="🔥", layout="wide")

    st.title("🔥 热点板块跟踪")

    # global controls
    col0, col1, col2 = st.columns([1, 1, 1])
    with col0:
        scheme_label = st.selectbox("映射方案", options=list(MAPPING_SCHEMES.keys()), index=2)
    with col1:
        alpha = st.slider("复合权重 α", min_value=0.0, max_value=1.0, value=0.5, step=0.05)
    with col2:
        cate_map = {"行业": 0, "概念": 1, "证监会行业": 2, "全部": None}
        cate_label = st.selectbox("板块分类", options=list(cate_map.keys()), index=3)

    scheme = MAPPING_SCHEMES[scheme_label]
    metric_for_color = scheme["color"]

    # tabs
    rtab, htab = st.tabs(["实时热点板块", "历史热点板块"])

    with rtab:
        colr1, colr2, colr3 = st.columns([1, 1, 1])
        with colr1:
            freq = st.number_input("刷新频率(秒)", min_value=3, max_value=60, value=5, step=1)
            auto = st.toggle("自动刷新", value=True)
        with colr2:
            playback = st.toggle("启用回放", value=False)
        with colr3:
            at_ts = st.text_input("固定时刻(ISO，可选)", value="")
        # timeline for playback
        picked_iso: Optional[str] = None
        if playback:
            try:
                ts_resp = _backend_get("/api/hotboard/realtime/timestamps")
                tss: List[str] = ts_resp.get("timestamps", [])
            except Exception:
                tss = []
            if tss:
                # build positions
                idx = st.slider("时间轴", min_value=0, max_value=max(0, len(tss)-1), value=len(tss)-1, step=1)
                picked_iso = tss[idx]
                st.caption(f"选择时刻: {picked_iso}")
            else:
                st.info("暂无日内时间点，回放不可用")
            # 回放时关闭自动刷新
            auto = False
        try:
            resp = _backend_get(
                "/api/hotboard/realtime",
                metric=metric_for_color,
                alpha=alpha,
                cate_type=cate_map[cate_label],
                at=(picked_iso or at_ts or None),
            )
            items = resp.get("items", [])
            ts_text = resp.get("ts")
            st.caption(f"数据时刻: {ts_text or '-'} · 数量: {len(items)}")
            if items:
                df = pd.DataFrame(items)
                net_inflow_num = pd.to_numeric(df.get("net_inflow"), errors="coerce").fillna(0.0)
                pct_chg_num = pd.to_numeric(df.get("pct_chg"), errors="coerce").fillna(0.0)
                score_num = pd.to_numeric(df.get("score"), errors="coerce").fillna(0.0)
                # area metric: 保证面积为正，避免treemap不渲染
                size_metric = scheme["size"]
                if size_metric == "flow":
                    size_values = net_inflow_num.abs() + 1e-6
                else:
                    size_values = pct_chg_num.abs() + 1e-6
                if metric_for_color == "combo":
                    color_values = score_num
                elif metric_for_color == "flow":
                    color_values = net_inflow_num
                else:
                    color_values = pct_chg_num
                df_plot = pd.DataFrame({
                    "板块": df["board_name"],
                    "code": df["board_code"],
                    "分类": df["cate_type"],
                    "面积": size_values,
                    "颜色": color_values,
                })
                try:
                    rank_series = pd.Series(color_values).fillna(0)
                    top_idx = list(rank_series.nlargest(10).index)
                except Exception:
                    top_idx = list(range(min(10, len(df))))
                info: List[str] = []
                for i in range(len(df)):
                    if i in top_idx:
                        ni_raw = float(net_inflow_num.iloc[i] or 0.0)
                        pct_raw = float(pct_chg_num.iloc[i] or 0.0)
                        info.append(f"流入: {ni_raw/1e4:,.0f} 万\n涨幅: {pct_raw:.2f}%")
                    else:
                        info.append("")
                df_plot["text"] = info
                # 对称色域，确保0为白，最高红、最低绿
                try:
                    max_absc = float(pd.Series(color_values).abs().max() or 1.0)
                except Exception:
                    max_absc = 1.0
                fig = px.treemap(
                    df_plot,
                    path=["分类", "板块"],
                    values="面积",
                    color="颜色",
                    color_continuous_scale=COLOR_SCALE,
                    color_continuous_midpoint=0,
                    range_color=[-max_absc, max_absc],
                )
                try:
                    fig.update_traces(text=df_plot["text"], texttemplate="%{label}<br>%{text}")
                except Exception:
                    pass
                if plotly_events:
                    selected_points = plotly_events(fig, click_event=True, hover_event=False, select_event=False, override_height=600, override_width="100%")
                    clicked_name = None
                    if selected_points:
                        # best effort: the last level name
                        clicked_name = selected_points[0].get("label")
                    # map to code
                    picked = None
                    if clicked_name:
                        for _, row in df.iterrows():
                            if str(row.get("board_name")) == str(clicked_name):
                                picked = str(row.get("board_code"))
                                break
                    st.markdown("#### 板块点击：" + (clicked_name or "(未选择)"))
                    if picked:
                        metric_btn = st.radio("Top20 维度", options=["按涨幅", "按资金流入"], horizontal=True)
                        m = "chg" if metric_btn == "按涨幅" else "flow"
                        data = _backend_get("/api/hotboard/top-stocks/realtime", board_code=picked, metric=m, limit=20)
                        _render_top20_table(data.get("items", []), title=f"实时Top20 - {clicked_name}", use_realtime=True)
                else:
                    st.plotly_chart(fig, use_container_width=True)
                    st.info("未安装 streamlit-plotly-events，点击选择功能降级。请在下方下拉选择板块。")
                    clicked = st.selectbox("选择板块", options=[f"{r['board_name']}|{r['board_code']}" for _, r in df.iterrows()])
                    if clicked:
                        name, code = clicked.split("|")
                        metric_btn = st.radio("Top20 维度", options=["按涨幅", "按资金流入"], horizontal=True)
                        m = "chg" if metric_btn == "按涨幅" else "flow"
                        data = _backend_get("/api/hotboard/top-stocks/realtime", board_code=code, metric=m, limit=20)
                        _render_top20_table(data.get("items", []), title=f"实时Top20 - {name}", use_realtime=True)
            else:
                st.info("暂无数据")
        except Exception as exc:  # noqa: BLE001
            st.error(f"后端错误: {exc}")
        

    with htab:
        hist_source = st.radio(
            "历史数据源",
            options=["新浪财经历史", "通达信历史"],
            horizontal=True,
            key="hotboard_hist_source",
        )

        if hist_source == "新浪财经历史":
            date = st.date_input("日期", value=dt.date.today())
            cate_hist = st.selectbox("板块分类", options=["行业", "概念", "证监会行业", "全部"], index=1, key="hist_cate")
            cate_val = {"行业": 0, "概念": 1, "证监会行业": 2, "全部": None}[cate_hist]
            try:
                data = _backend_get("/api/hotboard/daily", date=date.isoformat(), cate_type=cate_val)
                items = data.get("items", [])
                if items:
                    df = pd.DataFrame(items)
                    amount_num = pd.to_numeric(df.get("amount"), errors="coerce").fillna(0.0)
                    pct_chg_num = pd.to_numeric(df.get("pct_chg"), errors="coerce").fillna(0.0)
                    size_values = amount_num
                    color_values = pct_chg_num
                    df_plot = pd.DataFrame({
                        "板块": df["board_name"],
                        "code": df["board_code"],
                        "分类": df["cate_type"],
                        "面积": size_values,
                        "颜色": color_values,
                    })
                    try:
                        max_abs = float(pd.Series(color_values).abs().max() or 1.0)
                    except Exception:
                        max_abs = 1.0
                    fig = px.treemap(
                        df_plot,
                        path=["分类", "板块"],
                        values="面积",
                        color="颜色",
                        color_continuous_scale=COLOR_SCALE,
                        color_continuous_midpoint=0,
                        range_color=[-max_abs, max_abs],
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    st.info("新浪历史热力图暂不提供成分Top20下钻；请使用右侧“通达信历史”以获得按板块成分的Top20。")
                else:
                    st.info("无数据")
            except Exception as exc:
                st.error(f"后端错误: {exc}")
        else:
            date2 = st.date_input("日期", value=dt.date.today(), key="tdx_date")
            idx_type = st.selectbox("板块类别", options=TDX_IDX_TYPES)
            try:
                data = _cached_tdx_daily(date2.isoformat(), idx_type)
                items = data.get("items", [])
                used_date = date2.isoformat()
                if not items:
                    for back in range(1, 6):
                        d2 = (date2 - dt.timedelta(days=back)).isoformat()
                        data = _cached_tdx_daily(d2, idx_type)
                        items = data.get("items", [])
                        if items:
                            used_date = d2
                            break
                # Fallback：所选类别无数据时，取全部类型
                if not items:
                    data = _cached_tdx_daily(used_date, None)
                    items = data.get("items", [])
                if items:
                    df = pd.DataFrame(items)
                    amount_num = pd.to_numeric(df.get("amount"), errors="coerce").fillna(0.0)
                    pct_chg_num = pd.to_numeric(df.get("pct_chg"), errors="coerce").fillna(0.0)
                    size_values = amount_num
                    color_values = pct_chg_num
                    df_plot = pd.DataFrame({
                        "板块": df["board_name"],
                        "code": df["board_code"],
                        "类型": df["idx_type"],
                        "面积": size_values,
                        "颜色": color_values,
                    })
                    try:
                        max_abs2 = float(pd.Series(color_values).abs().max() or 1.0)
                    except Exception:
                        max_abs2 = 1.0
                    fig = px.treemap(
                        df_plot,
                        path=["类型", "板块"],
                        values="面积",
                        color="颜色",
                        color_continuous_scale=COLOR_SCALE,
                        color_continuous_midpoint=0,
                        range_color=[-max_abs2, max_abs2],
                    )
                    # Overlay Top10 (按颜色指标排序): 成交额(万) + 涨幅(%)
                    try:
                        rank_series = color_values.fillna(0)
                        top_idx = list(rank_series.nlargest(10).index)
                    except Exception:
                        top_idx = list(range(min(10, len(df))))
                    info2 = []
                    for i in range(len(df)):
                        if i in top_idx:
                            amt = float(amount_num.iloc[i] or 0.0)
                            pct = float(pct_chg_num.iloc[i] or 0.0)
                            info2.append(f"成交: {amt/1e4:,.0f} 万\n涨幅: {pct:.2f}%")
                        else:
                            info2.append("")
                    try:
                        fig.update_traces(text=info2, texttemplate="%{label}<br>%{text}")
                    except Exception:
                        pass
                    st.caption(f"显示日期：{used_date}")
                    if plotly_events:
                        selected_points = plotly_events(fig, click_event=True, hover_event=False, select_event=False, override_height=600, override_width="100%")
                        clicked_name = None
                        if selected_points:
                            clicked_name = selected_points[0].get("label")
                        picked = None
                        if clicked_name:
                            for _, row in df.iterrows():
                                if str(row.get("board_name")) == str(clicked_name):
                                    picked = str(row.get("board_code"))
                                    break
                        st.markdown("#### 板块点击：" + (clicked_name or "(未选择)"))
                        if picked:
                            metric_btn = st.radio("Top20 维度", options=["按涨幅", "按资金流入"], horizontal=True, key="tdx_top_metric")
                            m = "chg" if metric_btn == "按涨幅" else "flow"
                            data2 = _cached_tdx_top_stocks(picked, used_date, m, 20)
                            _render_top20_table(data2.get("items", []), title=f"历史Top20 - {clicked_name}", use_realtime=False, date=used_date)
                    else:
                        st.plotly_chart(fig, use_container_width=True)
                        st.info("未安装 streamlit-plotly-events，点击选择功能降级。请在下方下拉选择板块。")
                        clicked = st.selectbox("选择板块", options=[f"{r['board_name']}|{r['board_code']}" for _, r in df.iterrows()], key="tdx_pick")
                        if clicked:
                            name, code = clicked.split("|")
                            metric_btn = st.radio("Top20 维度", options=["按涨幅", "按资金流入"], horizontal=True, key="tdx_top_metric2")
                            m = "chg" if metric_btn == "按涨幅" else "flow"
                            data2 = _cached_tdx_top_stocks(code, used_date, m, 20)
                            _render_top20_table(data2.get("items", []), title=f"历史Top20 - {name}", use_realtime=False, date=used_date)
                else:
                    st.info("无数据")
            except Exception as exc:
                st.error(f"后端错误: {exc}")
