import time
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional

import streamlit as st
import pandas as pd

from pg_watchlist_repo import watchlist_repo
from data_source_manager import data_source_manager


REALTIME_FIELDS = {
    "last": "最新价",
    "pct_change": "涨幅%",
    "open": "开盘",
    "prev_close": "昨收",
    "high": "最高",
    "low": "最低",
    "volume_hand": "成交量(手)",
    "amount": "成交额",
}

PERSISTENT_SORT_FIELDS = {
    "code": "代码",
    "name": "名称",
    "category": "分类",
    "created_at": "加入时间",
    "updated_at": "更新时间",
    "last_analysis_time": "最近分析时间",
    "last_rating": "投资评级",
}


@st.cache_data(ttl=3.0, show_spinner=False)
def _fetch_quotes_cached(codes: List[str]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for ts_code in codes:
        try:
            # 将 ts_code 转为6位代码以适配TDX实时接口
            base_code = data_source_manager._convert_from_ts_code(ts_code) if "." in str(ts_code) else ts_code
            q = data_source_manager.get_realtime_quotes(base_code)
        except Exception:
            q = {}
        out[ts_code] = q or {}
    return out


def _compute_realtime_fields(q: Dict[str, Any]) -> Dict[str, Optional[float]]:
    price = q.get("price")
    pre_close = q.get("pre_close")
    open_ = q.get("open")
    high = q.get("high")
    low = q.get("low")
    volume = q.get("volume")
    amount = q.get("amount")

    pct = None
    if isinstance(price, (int, float)) and isinstance(pre_close, (int, float)) and pre_close not in (0, None):
        try:
            pct = (price - pre_close) / pre_close * 100.0
        except Exception:
            pct = None

    volume_hand = volume / 100.0 if isinstance(volume, (int, float)) else None
    # amount 为 元

    return {
        "last": price,
        "pct_change": pct,
        "open": open_,
        "prev_close": pre_close,
        "high": high,
        "low": low,
        "volume_hand": volume_hand,
        "amount": amount,
    }

def _format_amount(amount: Optional[float]) -> str:
    if amount is None:
        return "-"
    try:
        v = float(amount)
    except Exception:
        return "-"
    if v >= 100_000_000:
        return f"{v/100_000_000:.2f}亿"
    return f"{v/10_000:.2f}万"


def _format_datetime(value: Any) -> str:
    if value in (None, "", "N/A"):
        return "N/A"
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return "N/A"
        text = text.replace("T", " ")
        if text.endswith("Z"):
            text = text[:-1]
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
                try:
                    dt = datetime.strptime(text, fmt)
                    break
                except ValueError:
                    dt = None
            if dt is None:
                return text
    else:
        return str(value)
    return dt.strftime("%Y-%m-%d:%H:%M:%S")


def _fetch_quotes_live(codes: List[str]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for ts_code in codes:
        try:
            base_code = data_source_manager._convert_from_ts_code(ts_code) if "." in str(ts_code) else ts_code
            q = data_source_manager.get_realtime_quotes(base_code)
        except Exception:
            q = {}
        out[ts_code] = q or {}
    return out


def _sort_items_persistent(items: List[Dict[str, Any]], sort_by: str, sort_dir: str) -> List[Dict[str, Any]]:
    key = str(sort_by)
    reverse = (str(sort_dir).lower() == "desc")
    def key_fn(it: Dict[str, Any]):
        if key == "category":
            v = it.get("category_names")
        else:
            v = it.get(key)
        if v is None:
            return (1, "")
        try:
            s = str(v).lower()
        except Exception:
            s = ""
        return (0, s)
    return sorted(items, key=key_fn, reverse=reverse)


def _to_date_only(value: Any) -> Optional[str]:
    if value in (None, "", "N/A"):
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    try:
        s = str(value)
        if "T" in s:
            s = s.split("T", 1)[0]
        else:
            s = s[:10]
        if not s:
            return None
        return s
    except Exception:
        return None


def _display_code(code: str) -> str:
    """将内部存储的代码（ts_code 或 6位）规范为前端展示用的 6 位代码。"""
    code = (code or "").strip()
    if not code:
        return ""
    return data_source_manager._convert_from_ts_code(code) if "." in code else code


def _cmp_numeric(val: Optional[float], op: str, target: Optional[float]) -> bool:
    if target is None:
        return True
    if val is None:
        return False
    try:
        v = float(val)
        t = float(target)
    except Exception:
        return False
    if op == ">=":
        return v >= t
    if op == "<=":
        return v <= t
    if op == ">":
        return v > t
    if op == "<":
        return v < t
    return v == t


def _cmp_date(val_iso: Optional[str], op: str, target_date: Optional[Any]) -> bool:
    if target_date is None:
        return True
    if val_iso is None:
        return False
    try:
        v = _to_date_only(val_iso)
        t = target_date.strftime("%Y-%m-%d")
    except Exception:
        return False
    if op == ">=":
        return v >= t
    if op == "<=":
        return v <= t
    if op == ">":
        return v > t
    if op == "<":
        return v < t
    return v == t


def _normalize_code_for_storage(code: str) -> Optional[str]:
    code = (code or "").strip().upper()
    if not code:
        return None
    if "." in code:
        return code
    try:
        return data_source_manager._convert_to_ts_code(code)
    except Exception:
        return None


@lru_cache(maxsize=512)
def _get_stock_name_cached(code: str) -> Optional[str]:
    code = (code or "").strip()
    if not code:
        return None
    base_code = data_source_manager._convert_from_ts_code(code) if "." in code else code
    try:
        info = data_source_manager.get_stock_basic_info(base_code)
    except Exception:
        info = {}
    if isinstance(info, dict):
        name = info.get("name") or info.get("stock_name")
        if name and name not in {"-", "未知", "None"}:
            return str(name)
    return None


def _sort_items(items: List[Dict[str, Any]], quotes: Dict[str, Dict[str, Any]], sort_by: str, sort_dir: str) -> List[Dict[str, Any]]:
    # 仅对实时字段做页内排序；持久字段服务端已排序
    if sort_by not in REALTIME_FIELDS:
        return items

    # 先按代码升序（低优先级稳定因子）
    base_sorted = sorted(items, key=lambda x: x.get("code") or "")

    reverse = (str(sort_dir).lower() == "desc")

    def key_tuple(it: Dict[str, Any]):
        code = it.get("code")
        q = quotes.get(code, {})
        fields = _compute_realtime_fields(q)
        val = fields.get(sort_by)
        # None 值最后；数值根据方向调整，避免影响二级代码排序
        is_null = (val is None)
        adj = 0.0
        if not is_null:
            try:
                fv = float(val)
                adj = -fv if reverse else fv
            except Exception:
                adj = 0.0
        return (is_null, adj)

    # 使用稳定排序：先按代码排好，再按实时字段排序
    return sorted(base_sorted, key=key_tuple, reverse=False)


def display_watchlist_manager():
    st.markdown(
        """
        <style>
        /* 仅限右侧动作面板内按钮样式（Windows灰色），不影响全局 */
        .watchlist-table {
            border: 1px solid #e4e7ec;
            border-radius: 12px;
            padding: 0.3rem 0.2rem;
            background: #ffffff;
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06);
        }
        .watchlist-table div[data-testid="stHorizontalBlock"] {
            gap: 0 !important;
        }
        .watchlist-table div[data-testid="column"] {
            padding-left: 0 !important;
            padding-right: 0 !important;
        }
        .watchlist-row, .watchlist-header-row {
            display: flex;
        }
        .watchlist-cell {
            border-right: 1px solid #edf1f5;
            padding: 0.22rem 0.4rem;
            font-size: 0.92rem;
            color: #1f2933;
            min-height: 2.15rem;
            display: flex;
            align-items: center;
            background: #ffffff;
        }
        .watchlist-cell:last-child {
            border-right: none;
        }
        .watchlist-header {
            font-weight: 600;
            background: #f5f7fb;
            color: #27364b;
        }
        .watchlist-row-wrapper {
            border-bottom: 1px solid #edf1f5;
        }
        .watchlist-row-wrapper:nth-child(even) .watchlist-cell {
            background: #fafbff;
        }
        .watchlist-row-wrapper:last-child {
            border-bottom: none;
        }
        .watchlist-code {
            font-family: "Consolas", "Roboto Mono", monospace;
            font-size: 0.95rem;
            color: #1f2933;
        }
        /* Data Editor: hide checkbox visuals but keep click target */
        div[data-testid="stDataEditor"] td [data-testid="stCheckbox"] {
            position: absolute !important;
            inset: 0 !important;
            opacity: 0 !important;
            width: 100% !important;
            height: 100% !important;
            margin: 0 !important;
            cursor: pointer !important;
        }
        /* 左侧 data_editor: 将第15/16列渲染为灰色按钮（历史/分析） */
        div[data-testid="stDataEditor"] table tbody tr td:nth-child(15) {
            text-align: center;
            position: relative;
            cursor: pointer;
        }
        /* 用内层容器绘制按钮文案 */
        div[data-testid="stDataEditor"] table tbody tr td:nth-child(15) > div::after {
            content: '历史';
            display: inline-block;
            padding: 0 6px;
            height: 22px;
            line-height: 20px;
            border-radius: 4px;
            background: #f2f2f2;
            color: #2b2f36;
            border: 1px solid #c9cdd3;
            font-size: inherit;
            pointer-events: none;
        }
        /* 选中态轻微压暗 */
        div[data-testid="stDataEditor"] table tbody tr td:nth-child(15):has(input[type="checkbox"]:checked) > div::after {
            filter: brightness(0.96);
        }
        /* 分析列(第16列)灰色按钮 */
        div[data-testid="stDataEditor"] table tbody tr td:nth-child(16) {
            text-align: center;
            position: relative;
            cursor: pointer;
        }
        div[data-testid="stDataEditor"] table tbody tr td:nth-child(16) > div::after {
            content: '分析';
            display: inline-block;
            padding: 0 6px;
            height: 22px;
            line-height: 20px;
            border-radius: 4px;
            background: #f2f2f2;
            color: #2b2f36;
            border: 1px solid #c9cdd3;
            font-size: inherit;
            pointer-events: none;
        }
        div[data-testid="stDataEditor"] table tbody tr td:nth-child(16):has(input[type="checkbox"]:checked) > div::after {
            filter: brightness(0.96);
        }
        /* 右侧操作 data_editor（仅两列）：将复选框渲染为按钮外观 */
        .action-table div[data-testid="stDataEditor"] td [data-testid="stCheckbox"] {
            position: absolute !important;
            inset: 0 !important;
            opacity: 0 !important;
            width: 100% !important;
            height: 100% !important;
            margin: 0 !important;
            cursor: pointer !important;
        }
        .action-table div[data-testid="stDataEditor"] table tbody tr td:nth-child(1),
        .action-table div[data-testid="stDataEditor"] table tbody tr td:nth-child(2) {
            text-align: center; position: relative; cursor: pointer; font-size: inherit;
        }
        .action-table div[data-testid="stDataEditor"] table tbody tr td:nth-child(1) > div::after {
            content: '历史'; display: inline-block; padding: 0 8px; height: 24px; line-height: 22px; border-radius: 8px;
            background: linear-gradient(135deg, #6a8cff 0%, #3b5bdb 100%); color: #fff; font-size: inherit; pointer-events: none;
        }
        .action-table div[data-testid="stDataEditor"] table tbody tr td:nth-child(1):has(input[type="checkbox"]:checked) > div::after {
            filter: brightness(0.92);
        }
        .action-table div[data-testid="stDataEditor"] table tbody tr td:nth-child(2) > div::after {
            content: '分析'; display: inline-block; padding: 0 8px; height: 24px; line-height: 22px; border-radius: 8px;
            background: linear-gradient(135deg, #7c3aed 0%, #4f46e5 100%); color: #fff; font-size: inherit; pointer-events: none;
        }
        .action-table div[data-testid="stDataEditor"] table tbody tr td:nth-child(2):has(input[type="checkbox"]:checked) > div::after {
            filter: brightness(0.92);
        }
        .action-table { border: 1px solid #e4e7ec; border-radius: 12px; background:#ffffff; box-shadow: 0 2px 6px rgba(15,23,42,0.04); font-size: 0.875rem; margin-top: 6px; }
        /* 右侧容器内：去除纵向间距，压缩每行高度并水平居中 */
        .action-table [data-testid="stVerticalBlock"]{ gap:0 !important; padding:0 !important; margin:0 !important; }
        .action-table [data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"]{
            gap:0 !important; margin:0 !important; padding:0 6px !important;
            height:36px !important; min-height:36px !important; align-items:center !important;
            border-bottom:1px solid #edf1f5;
        }
        .action-table [data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"]:last-child{ border-bottom:none; }
        .action-table div[data-testid="column"]{ padding:0 !important; margin:0 !important; display:flex !important; align-items:center !important; justify-content:center !important; }
        .action-header { font-weight:600; background:#f5f7fb; color:#27364b; height:36px; padding:0 6px; border-bottom:1px solid #edf1f5; display:flex; align-items:center; }
        .action-row { border-bottom:1px solid #edf1f5; display:flex; align-items:center; height:36px; padding:0 6px; }
        .action-row * { margin:0 !important; }
        .action-row [data-testid="column"]{ display:flex !important; align-items:center !important; justify-content:center !important; }
        .action-row:last-child { border-bottom:none; }
        /* 按钮尺寸与表格文字一致，去阴影、去外边距 */
        .action-table .stButton { margin:0 !important; }
        .action-table .stButton>button,
        .action-table div[data-testid="stButton"]>button{
            font-size:0.875rem !important;
            padding:0 8px !important;
            margin:0 !important;
            line-height:22px !important;
            height:24px !important;
            min-height:24px !important;
            border-radius:8px !important;
            box-shadow:none !important;
            align-self:center !important;
        }
        /* 右侧操作表（data_editor 两列）：灰色按钮风格，隐藏表头，保证与左表逐行对齐 */
        .action-table{ border:1px solid #e4e7ec; border-radius:12px; background:#ffffff; box-shadow:0 2px 6px rgba(15,23,42,0.04);
            font-size:0.875rem; margin-top:36px; }
        .action-table div[data-testid="stDataEditor"] table thead{ display:none !important; }
        .action-table div[data-testid="stDataEditor"] table tbody tr{ height:36px !important; }
        .action-table div[data-testid="stDataEditor"] td [data-testid="stCheckbox"]{
            position:absolute !important; inset:0 !important; opacity:0 !important; width:100% !important; height:100% !important; margin:0 !important; cursor:pointer !important;
        }
        .action-table div[data-testid="stDataEditor"] table tbody tr td:nth-child(1),
        .action-table div[data-testid="stDataEditor"] table tbody tr td:nth-child(2){ text-align:center; position:relative; cursor:pointer; font-size:inherit; }
        .action-table div[data-testid="stDataEditor"] table tbody tr td:nth-child(1) > div::after{
            content:'历史'; display:inline-block; padding:0 6px; height:22px; line-height:20px; border-radius:4px; background:#f2f2f2; color:#2b2f36; border:1px solid #c9cdd3; font-size:inherit; pointer-events:none;
        }
        .action-table div[data-testid="stDataEditor"] table tbody tr td:nth-child(2) > div::after{
            content:'分析'; display:inline-block; padding:0 6px; height:22px; line-height:20px; border-radius:4px; background:#f2f2f2; color:#2b2f36; border:1px solid #c9cdd3; font-size:inherit; pointer-events:none;
        }
        .action-table div[data-testid="stDataEditor"] table tbody tr td:nth-child(1):has(input[type="checkbox"]:checked) > div::after,
        .action-table div[data-testid="stDataEditor"] table tbody tr td:nth-child(2):has(input[type="checkbox"]:checked) > div::after{
            filter:brightness(0.96);
        }

        /* 列表控制条容器内的 刷新 按钮与下拉框等高，灰色风格 */
        div[data-testid="stVerticalBlock"]:has(> #watchlist-controls) .stButton>button{
            font-size:0.875rem !important; font-weight:400 !important;
            height:36px !important; min-height:36px !important; line-height:34px !important; padding:0 12px !important;
            background:#f2f2f2 !important; color:#2b2f36 !important; border:1px solid #c9cdd3 !important; border-radius:6px !important;
            box-shadow:none !important;
        }
        #watchlist-pagination .stButton>button,
        #watchlist-bulk-actions .stButton>button {
            color:#ffffff !important;
        }
        /* force all buttons within the watchlist page to white text for clarity */
        #watchlist-root .stButton>button { color:#ffffff !important; }
        /* shrink operator selectboxes width in search area */
        #watchlist-search div[data-testid="stSelectbox"] > div{ min-width:64px !important; max-width:72px !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("⭐ 自选股票池")
    st.markdown("<div id='watchlist-root'>", unsafe_allow_html=True)

    # 初始化状态
    st.session_state.setdefault("watchlist_sort_by", "updated_at")
    st.session_state.setdefault("watchlist_sort_dir", "desc")
    st.session_state.setdefault("watchlist_page", 1)
    st.session_state.setdefault("watchlist_page_size", 20)
    st.session_state.setdefault("watchlist_category_id", None)
    st.session_state.setdefault("watchlist_auto_refresh", False)
    st.session_state.setdefault("watchlist_search_active", False)

    # 分类区
    cats = watchlist_repo.list_categories()
    cat_map = {c["id"]: c["name"] for c in cats}
    name_to_cat = {c["name"]: c["id"] for c in cats}
    # 旧的分类按钮已移除；分类选择将放在“自选股票列表”上方的下拉框中

    # 分类管理
    with st.expander("🗂️ 分类管理", expanded=False):
        col_m1, col_m2, col_m3 = st.columns([1.2, 1.2, 1.2])
        # 新建分类
        with col_m1:
            st.caption("新建分类")
            new_cat = st.text_input("分类名称", key="mgmt_new_cat_name")
            new_desc = st.text_input("描述(可选)", key="mgmt_new_cat_desc")
            if st.button("创建", key="mgmt_create_btn", disabled=(not (new_cat or "").strip())):
                try:
                    cid = watchlist_repo.create_category(new_cat.strip(), new_desc.strip() or None)
                    st.success(f"已创建分类: {new_cat}")
                    st.rerun()
                except Exception as e:
                    st.error(f"创建失败: {e}")
        # 重命名分类（不含默认/持仓股票）
        with col_m2:
            st.caption("重命名分类")
            rename_opts = [c for c in cats if c["name"] not in ("默认", "持仓股票")]
            sel_rename = st.selectbox("选择分类", options=[c["name"] for c in rename_opts] or ["(无可重命名)"], key="mgmt_sel_rename")
            new_name = st.text_input("新名称", key="mgmt_new_name")
            new_desc2 = st.text_input("新描述(可选)", key="mgmt_new_desc")
            if st.button("重命名", key="mgmt_rename_btn", disabled=(not rename_opts or not (new_name or "").strip())):
                cat = next((c for c in rename_opts if c["name"] == sel_rename), None)
                if cat:
                    ok = watchlist_repo.rename_category(cat["id"], new_name.strip(), new_desc2.strip() or None)
                    if ok:
                        st.success("已重命名")
                        st.rerun()
                    else:
                        st.error("重命名失败")
        # 删除分类（需为空，不含默认/持仓股票）
        with col_m3:
            st.caption("删除分类（需为空）")
            del_opts = [c for c in cats if c["name"] not in ("默认", "持仓股票")]
            sel_del = st.selectbox("选择分类", options=[c["name"] for c in del_opts] or ["(无可删除)"], key="mgmt_sel_delete")
            if st.button("删除", key="mgmt_delete_btn", disabled=(not del_opts)):
                cat = next((c for c in del_opts if c["name"] == sel_del), None)
                if cat:
                    ok = watchlist_repo.delete_category(cat["id"]) 
                    if ok:
                        st.success("已删除分类")
                        # 如当前筛选在该分类，切回全部
                        if st.session_state.watchlist_category_id == cat["id"]:
                            st.session_state.watchlist_category_id = None
                        st.rerun()
                    else:
                        st.warning("删除失败：分类需为空")

    st.divider()

    # 添加区域
    with st.expander("➕ 添加到自选", expanded=False):
        st.markdown("**单个添加**")
        col1, col2 = st.columns([2, 2])
        with col1:
            code = st.text_input("股票代码", placeholder="如 600519", key="add_single_code")
        with col2:
            name = st.text_input("名称(可选)", key="add_single_name")

        mode = st.radio("分类方式", options=["已有(可多选)", "新建"], horizontal=True, key="add_single_mode")
        selected_existing: List[str] = []
        new_cat_name = ""
        if mode == "已有(可多选)":
            selected_existing = st.multiselect("选择分类(可多选，不选则默认加入“默认”)", options=[c["name"] for c in cats], key="add_single_existing_cats")
        else:
            new_cat_name = st.text_input("新建分类名称(单个)", placeholder="例如：科技成长", key="add_single_new_cat")

        if st.button("添加", key="add_single_submit"):
            if not code:
                st.warning("请输入股票代码")
            else:
                try:
                    code_norm = _normalize_code_for_storage(code)
                    if not code_norm:
                        raise ValueError("无法识别的股票代码")
                    display_name = name or _get_stock_name_cached(code_norm) or _get_stock_name_cached(code)
                    if not display_name:
                        base_code = data_source_manager._convert_from_ts_code(code_norm)
                        display_name = _get_stock_name_cached(base_code) or code_norm

                    # 确定主分类与附加分类
                    primary_cid: Optional[int] = None
                    extra_cids: List[int] = []
                    if mode == "新建":
                        new_cat_name = (new_cat_name or "").strip()
                        if not new_cat_name:
                            st.warning("请输入新建分类名称")
                            st.stop()
                        primary_cid = watchlist_repo.create_category(new_cat_name, None)
                    else:
                        picked = [name_to_cat[n] for n in selected_existing if n in name_to_cat]
                        if not picked:
                            # 默认分类
                            default_cid = name_to_cat.get("默认")
                            if not default_cid:
                                default_cid = watchlist_repo.create_category("默认", "默认分类")
                                # 刷新本地映射
                                name_to_cat["默认"] = default_cid
                            picked = [default_cid]
                        primary_cid = picked[0]
                        extra_cids = picked[1:]

                    # 先创建/更新条目，并绑定主分类
                    item_id = watchlist_repo.add_item(code_norm, display_name, primary_cid)
                    # 如有附加分类，补充映射
                    if extra_cids:
                        watchlist_repo.add_categories_to_items([item_id], extra_cids)

                    st.success(f"已添加: {code}")
                    st.session_state.watchlist_page = 1
                    st.rerun()
                except Exception as e:
                    st.error(f"添加失败: {e}")

        st.divider()

        st.markdown("**批量添加**")
        codes_str = st.text_area("批量添加(逗号分隔)", key="batch_add_codes")
        colb1, colb2 = st.columns([2, 1])
        with colb1:
            batch_options = ["默认"] + [c["name"] for c in cats if c["name"] != "默认"] + ["新建分类..."]
            batch_cat_choice = st.selectbox("分类(批量)", options=batch_options, key="batch_add_cat")
        with colb2:
            move_if_exists = st.checkbox("存在则移动到此分类", value=False, key="batch_move_if_exists")

        batch_new_cat_name = ""
        if batch_cat_choice == "新建分类...":
            batch_new_cat_name = st.text_input("新建分类名称(批量)", placeholder="例如：白马股", key="batch_add_new_cat")
        else:
            if "batch_add_new_cat" in st.session_state:
                del st.session_state["batch_add_new_cat"]

        if st.button("批量添加", key="batch_add_submit"):
            code_list_raw = [c.strip() for c in (codes_str or "").replace("\n", ",").split(",") if c.strip()]
            if not code_list_raw:
                st.warning("请输入至少一个股票代码")
            else:
                try:
                    if batch_cat_choice == "新建分类...":
                        batch_new_cat_name = (batch_new_cat_name or "").strip()
                        if not batch_new_cat_name:
                            st.warning("请输入新建分类名称")
                            st.stop()
                        cid = watchlist_repo.create_category(batch_new_cat_name, None)
                        target_cat_id = cid
                    else:
                        target = next((c for c in cats if c["name"] == batch_cat_choice), None)
                        if not target:
                            cid = watchlist_repo.create_category(batch_cat_choice, None)
                            target_cat_id = cid
                        else:
                            target_cat_id = target["id"]

                    names_map: Dict[str, str] = {}
                    code_list: List[str] = []
                    for raw in code_list_raw:
                        ts_code = _normalize_code_for_storage(raw)
                        if not ts_code:
                            continue
                        base_code = data_source_manager._convert_from_ts_code(ts_code)
                        display_name = (
                            _get_stock_name_cached(ts_code)
                            or _get_stock_name_cached(base_code)
                            or ts_code
                        )
                        names_map[ts_code] = display_name
                        code_list.append(ts_code)
                    result = watchlist_repo.add_items_bulk(
                        code_list,
                        target_cat_id,
                        on_conflict=("move" if move_if_exists else "ignore"),
                        names=names_map,
                    )
                    st.success(f"批量添加完成: 新增 {result['added']} 条，跳过 {result['skipped']} 条，移动 {result['moved']} 条")
                    st.session_state.watchlist_page = 1
                    st.rerun()
                except Exception as e:
                    st.error(f"批量添加失败: {e}")

    st.divider()

    # 列表控制条
    st.markdown("<div id='watchlist-controls' class='watchlist-controls'>", unsafe_allow_html=True)
    colc1, colc2, colc3, colc4, colc5 = st.columns([2, 2, 2, 2, 2])
    with colc1:
        sort_by = st.selectbox("排序字段", options=list(PERSISTENT_SORT_FIELDS.keys()) + list(REALTIME_FIELDS.keys()), format_func=lambda k: PERSISTENT_SORT_FIELDS.get(k, REALTIME_FIELDS.get(k, k)), index=(list(PERSISTENT_SORT_FIELDS.keys()).index(st.session_state.watchlist_sort_by) if st.session_state.watchlist_sort_by in PERSISTENT_SORT_FIELDS else len(PERSISTENT_SORT_FIELDS)))
    with colc2:
        sort_dir = st.selectbox("方向", options=["desc", "asc"], index=(0 if st.session_state.watchlist_sort_dir == "desc" else 1))
    with colc3:
        page_size = st.selectbox("每页条数", options=[10, 20, 50, 100], index=[10, 20, 50, 100].index(st.session_state.watchlist_page_size))
    with colc4:
        auto_refresh = st.toggle("自动刷新", value=st.session_state.watchlist_auto_refresh)
    with colc5:
        if st.button("刷新"):
            st.cache_data.clear()
    st.markdown("</div>", unsafe_allow_html=True)

    # 保存状态
    st.session_state.watchlist_sort_by = sort_by
    st.session_state.watchlist_sort_dir = sort_dir
    st.session_state.watchlist_page_size = page_size
    st.session_state.watchlist_auto_refresh = auto_refresh

    # 分类选择（放在表格上方）
    st.markdown("#### 选择分类")
    cat_labels = ["全部"] + [c["name"] for c in cats]
    # 计算当前 index
    current_label = "全部"
    if st.session_state.watchlist_category_id is not None:
        current_label = cat_map.get(st.session_state.watchlist_category_id, "全部")
    try:
        current_index = cat_labels.index(current_label)
    except ValueError:
        current_index = 0
    sel_label = st.selectbox("分类", options=cat_labels, index=current_index, key="watchlist_cat_dropdown")
    new_cat_id = None if sel_label == "全部" else name_to_cat.get(sel_label)
    if new_cat_id != st.session_state.watchlist_category_id:
        st.session_state.watchlist_category_id = new_cat_id
        st.session_state.watchlist_page = 1

    # 搜索（高级）
    with st.expander("🔎 搜索", expanded=False):
        st.markdown("<div id='watchlist-search'>", unsafe_allow_html=True)
        st.caption("文字类为包含匹配，数字/日期支持比较条件；留空表示不筛选")
        # 文本条件
        colt1, colt2, colt3, colt4 = st.columns(4)
        with colt1:
            sc_code = st.text_input("代码包含", key="search_code_like")
        with colt2:
            sc_name = st.text_input("名称包含", key="search_name_like")
        with colt3:
            sc_cat = st.text_input("分类包含", key="search_cat_like")
        with colt4:
            sc_rating = st.text_input("投资评级包含", key="search_rating_like")

        # 数值条件：操作符 + 值（仅数字输入），配合启用开关
        num_ops = [">=", "<=", ">", "<", "="]
        coln1, coln2, coln3, coln4 = st.columns(4)
        with coln1:
            op_last = st.selectbox("最新价", options=num_ops, key="search_op_last")
            en_last = st.toggle("启用", value=False, key="search_en_last")
            v_last = st.number_input(" ", key="search_v_last", value=0.0, step=0.01)
        with coln2:
            op_pct = st.selectbox("涨幅%", options=num_ops, key="search_op_pct")
            en_pct = st.toggle("启用", value=False, key="search_en_pct")
            v_pct = st.number_input("  ", key="search_v_pct", value=0.0, step=0.01)
        with coln3:
            op_open = st.selectbox("开盘", options=num_ops, key="search_op_open")
            en_open = st.toggle("启用", value=False, key="search_en_open")
            v_open = st.number_input("   ", key="search_v_open", value=0.0, step=0.01)
        with coln4:
            op_prev = st.selectbox("昨收", options=num_ops, key="search_op_prev")
            en_prev = st.toggle("启用", value=False, key="search_en_prev")
            v_prev = st.number_input("    ", key="search_v_prev", value=0.0, step=0.01)

        coln5, coln6, coln7, coln8 = st.columns(4)
        with coln5:
            op_high = st.selectbox("最高", options=num_ops, key="search_op_high")
            en_high = st.toggle("启用", value=False, key="search_en_high")
            v_high = st.number_input("     ", key="search_v_high", value=0.0, step=0.01)
        with coln6:
            op_low = st.selectbox("最低", options=num_ops, key="search_op_low")
            en_low = st.toggle("启用", value=False, key="search_en_low")
            v_low = st.number_input("      ", key="search_v_low", value=0.0, step=0.01)
        with coln7:
            op_vol = st.selectbox("成交量(手)", options=num_ops, key="search_op_vol")
            en_vol = st.toggle("启用", value=False, key="search_en_vol")
            v_vol = st.number_input("       ", key="search_v_vol", value=0.0, step=1.0)
        with coln8:
            op_amt = st.selectbox("成交额(元)", options=num_ops, key="search_op_amt")
            en_amt = st.toggle("启用", value=False, key="search_en_amt")
            v_amt = st.number_input("        ", key="search_v_amt", value=0.0, step=1.0)

        # 日期条件（仅日期输入），配合启用开关
        date_ops = [">=", "<=", ">", "<", "="]
        cold1, cold2 = st.columns(2)
        with cold1:
            op_join = st.selectbox("加入时间", options=date_ops, key="search_op_join")
            en_join = st.toggle("启用", value=False, key="search_en_join")
            d_join = st.date_input(" ", key="search_d_join", value=datetime.today().date())
        with cold2:
            op_ana = st.selectbox("分析时间", options=date_ops, key="search_op_ana")
            en_ana = st.toggle("启用", value=False, key="search_en_ana")
            d_ana = st.date_input("  ", key="search_d_ana", value=datetime.today().date())

        colb1, colb2 = st.columns([1,1])
        with colb1:
            if st.button("执行搜索", key="watchlist_do_search"):
                st.session_state.watchlist_search_active = True
                st.session_state.watchlist_search_filters = {
                    "code": sc_code or "",
                    "name": sc_name or "",
                    "cat": sc_cat or "",
                    "rating": sc_rating or "",
                    "num": {
                        "last": (op_last, v_last if en_last else None),
                        "pct_change": (op_pct, v_pct if en_pct else None),
                        "open": (op_open, v_open if en_open else None),
                        "prev_close": (op_prev, v_prev if en_prev else None),
                        "high": (op_high, v_high if en_high else None),
                        "low": (op_low, v_low if en_low else None),
                        "volume_hand": (op_vol, v_vol if en_vol else None),
                        "amount": (op_amt, v_amt if en_amt else None),
                    },
                    "date": {
                        "created_at": (op_join, d_join if en_join else None),
                        "last_analysis_time": (op_ana, d_ana if en_ana else None),
                    },
                }
                st.session_state.watchlist_page = 1
                st.rerun()
        with colb2:
            if st.button("清空搜索", key="watchlist_reset_search"):
                st.session_state.watchlist_search_active = False
                st.session_state.watchlist_search_filters = {}
                st.session_state.watchlist_page = 1
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # 拉取数据（服务端排序仅对持久字段；搜索时客户端过滤/排序）
    persistent_sort = sort_by in PERSISTENT_SORT_FIELDS
    page = st.session_state.watchlist_page
    resp = watchlist_repo.list_items(
        category_id=st.session_state.watchlist_category_id,
        page=page,
        page_size=page_size,
        sort_by=(sort_by if persistent_sort else "updated_at"),
        sort_dir=(sort_dir if persistent_sort else "desc"),
    )
    total = resp.get("total", 0)
    items = resp.get("items", [])

    # 搜索逻辑：取全量数据（当前分类），实时行情刷新后在客户端过滤
    if st.session_state.get("watchlist_search_active"):
        # 拉全量
        all_items: List[Dict[str, Any]] = []
        ps = 1000
        p = 1
        while True:
            r = watchlist_repo.list_items(
                category_id=st.session_state.watchlist_category_id,
                page=p,
                page_size=ps,
                sort_by="updated_at",
                sort_dir="desc",
            )
            batch = r.get("items", [])
            all_items.extend(batch)
            if len(all_items) >= int(r.get("total", 0)) or not batch:
                break
            p += 1
        # 实时行情（全量）
        all_codes = [it["code"] for it in all_items]
        quotes_live = _fetch_quotes_live(all_codes)
        # 过滤
        f = st.session_state.get("watchlist_search_filters", {})
        t_code = (f.get("code") or "").strip().lower()
        t_name = (f.get("name") or "").strip().lower()
        t_cat = (f.get("cat") or "").strip().lower()
        t_rating = (f.get("rating") or "").strip().lower()
        num_f = f.get("num", {})
        date_f = f.get("date", {})

        def ok_text(it: Dict[str, Any]) -> bool:
            # 代码过滤：既支持按 ts_code，也支持按 6 位代码过滤
            code_ts = str(it.get("code") or "")
            code6 = _display_code(code_ts)
            if t_code and (t_code not in code6.lower()) and (t_code not in code_ts.lower()):
                return False
            if t_name and t_name not in str(it.get("name") or "").lower():
                return False
            if t_cat and t_cat not in str(it.get("category_names") or "").lower():
                return False
            if t_rating and t_rating not in str(it.get("last_rating") or "").lower():
                return False
            return True

        def ok_numeric(code: str, it: Dict[str, Any]) -> bool:
            q = quotes_live.get(code, {})
            rt = _compute_realtime_fields(q)
            for k, (op, val) in num_f.items():
                if val is None or val == "":
                    continue
                if not _cmp_numeric(rt.get(k), op, val):
                    return False
            return True

        def ok_date(it: Dict[str, Any]) -> bool:
            created = it.get("created_at")
            last_an = it.get("last_analysis_time")
            op1, d1 = date_f.get("created_at", (None, None))
            op2, d2 = date_f.get("last_analysis_time", (None, None))
            if d1:
                if not _cmp_date(created, op1, d1):
                    return False
            if d2:
                if not _cmp_date(last_an, op2, d2):
                    return False
            return True

        filtered = [it for it in all_items if ok_text(it) and ok_numeric(it.get("code"), it) and ok_date(it)]

        # 排序（全量）
        if sort_by in PERSISTENT_SORT_FIELDS:
            sorted_all = _sort_items_persistent(filtered, sort_by, sort_dir)
        else:
            sorted_all = _sort_items(filtered, quotes_live, sort_by, sort_dir)

        # 分页（客户端）
        total = len(sorted_all)
        start = max(0, (page - 1) * page_size)
        end = start + page_size
        items = sorted_all[start:end]
        # 当前页行情
        page_codes = [it["code"] for it in items]
        quotes = {c: quotes_live.get(c, {}) for c in page_codes}
        # 页内二次排序（实时字段稳定性）
        items_display = _sort_items(items, quotes, sort_by, sort_dir)
    else:
        # 常规分页数据
        codes = [it["code"] for it in items]
        quotes = _fetch_quotes_cached(codes)
        items_display = _sort_items(items, quotes, sort_by, sort_dir)

    # 自动刷新
    if auto_refresh:
        st.rerun()

    st.markdown("#### 自选股票列表")
    # 单列布局：左表包含 历史/分析 两列
    st.session_state.watchlist_items_current = items_display
    with st.container():
        # 构建 DataFrame（仅含表内选择列）
        selected_ids_prev: List[int] = st.session_state.get("watchlist_selected_ids", [])
        rows: List[Dict[str, Any]] = []
        for it in items_display:
            q = quotes.get(it["code"], {})
            rt = _compute_realtime_fields(q)
            created_iso = it.get("created_at")
            join_date = "-"
            if created_iso:
                try:
                    # created_at is ISO string like 'YYYY-MM-DDTHH:MM:SS'
                    join_date = str(created_iso)[:10]
                except Exception:
                    join_date = str(created_iso)
            rows.append({
                "选择": it["id"] in selected_ids_prev,
                "代码": _display_code(it["code"]),
                "名称": it["name"],
                "分类": it.get("category_names") or "-",
                "最新价": None if rt["last"] is None else float(f"{rt['last']:.2f}"),
                "涨幅%": None if rt["pct_change"] is None else float(f"{rt['pct_change']:.2f}"),
                "开盘": None if rt["open"] is None else float(f"{rt['open']:.2f}"),
                "昨收": None if rt["prev_close"] is None else float(f"{rt['prev_close']:.2f}"),
                "最高": None if rt["high"] is None else float(f"{rt['high']:.2f}"),
                "最低": None if rt["low"] is None else float(f"{rt['low']:.2f}"),
                "成交量(手)": None if rt["volume_hand"] is None else float(f"{rt['volume_hand']:.0f}"),
                "成交额": _format_amount(rt.get("amount")),
                "投资评级": it.get("last_rating") or "N/A",
                "加入时间": join_date,
                "分析时间": _format_datetime(it.get("last_analysis_time")),
                "历史": False,
                "分析": False,
            })
        df = pd.DataFrame(rows)
        editor_key = f"watchlist_editor_{st.session_state.get('watchlist_editor_key', 0)}"
        edited = st.data_editor(
            df,
            column_config={
                "选择": st.column_config.CheckboxColumn("选择"),
                "代码": st.column_config.TextColumn("代码", width="small"),
                "名称": st.column_config.TextColumn("名称", width="small"),
                "分类": st.column_config.TextColumn("分类", width="small"),
                "最新价": st.column_config.NumberColumn("最新价", format="%.2f"),
                "涨幅%": st.column_config.NumberColumn("涨幅%", format="%.2f"),
                "开盘": st.column_config.NumberColumn("开盘", format="%.2f"),
                "昨收": st.column_config.NumberColumn("昨收", format="%.2f"),
                "最高": st.column_config.NumberColumn("最高", format="%.2f"),
                "最低": st.column_config.NumberColumn("最低", format="%.2f"),
                "成交量(手)": st.column_config.NumberColumn("成交量(手)", format="%.0f"),
                "成交额": st.column_config.TextColumn("成交额"),
                "投资评级": st.column_config.TextColumn("投资评级"),
                "加入时间": st.column_config.TextColumn("加入时间", width="small"),
                "分析时间": st.column_config.TextColumn("分析时间"),
                "历史": st.column_config.CheckboxColumn("历史"),
                "分析": st.column_config.CheckboxColumn("分析"),
            },
            disabled=["代码","名称","分类","最新价","涨幅%","开盘","昨收","最高","最低","成交量(手)","成交额","投资评级","加入时间","分析时间"],
            hide_index=True,
            use_container_width=True,
            key=editor_key,
        )
        # 更新选择结果 & 触发行内动作
        new_selected_ids: List[int] = []
        for idx, row in edited.iterrows():
            if bool(row.get("选择")):
                new_selected_ids.append(items_display[idx]["id"])
            if bool(row.get("历史")):
                code = items_display[idx]["code"]
                code6 = data_source_manager._convert_from_ts_code(code) if "." in code else code
                st.session_state.show_history = True
                st.session_state.history_search_term = code6
                st.session_state['watchlist_editor_key'] = int(time.time())
                st.rerun()
            if bool(row.get("分析")):
                code = items_display[idx]["code"]
                code6 = data_source_manager._convert_from_ts_code(code) if "." in code else code
                for k in [
                    'show_watchlist','show_history','show_monitor','show_config','show_sector_strategy',
                    'show_longhubang','show_portfolio','show_local_data','show_smart_monitor','show_main_force'
                ]:
                    if k in st.session_state:
                        del st.session_state[k]
                st.session_state.prefill_stock_code = code6
                st.session_state['watchlist_editor_key'] = int(time.time())
                st.rerun()
        st.session_state.watchlist_selected_ids = new_selected_ids

    # 分页器
    total_pages = max(1, (total + page_size - 1) // page_size)
    st.markdown("<div id='watchlist-pagination' style='color: white'>", unsafe_allow_html=True)
    colp1, colp2, colp3 = st.columns([1, 2, 1])
    with colp1:
        if st.button("上一页", disabled=(page <= 1)):
            st.session_state.watchlist_page = max(1, page - 1)
            st.rerun()
    with colp2:
        st.write(f"第 {page} / {total_pages} 页 (共 {total} 条)")
    with colp3:
        if st.button("下一页", disabled=(page >= total_pages)):
            st.session_state.watchlist_page = min(total_pages, page + 1)
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    st.divider()

    # 选中项
    selected_ids: List[int] = st.session_state.get("watchlist_selected_ids", [])

    # 批量操作
    st.markdown("#### 批量操作")
    st.markdown("<div id='watchlist-bulk-actions'>", unsafe_allow_html=True)
    col_op1, col_op2, col_op3 = st.columns([2, 2, 2])
    with col_op1:
        op = st.selectbox("操作类型", options=["新增", "修改分类", "添加到分类", "从分类移除", "删除", "批量分析"], key="bulk_op_type")
    with col_op2:
        target = None
        add_new_cat_name = None
        cats_to_add: List[str] = []
        cats_to_remove: List[str] = []
        if op == "修改分类":
            cat_options = [c["name"] for c in cats]
            target = st.selectbox("选择分类(替换)", options=cat_options, key="bulk_cat_sel")
        elif op == "新增":
            cat_options = [c["name"] for c in cats] + ["新建分类..."]
            target = st.selectbox("选择分类", options=cat_options, key="bulk_cat_sel")
            if target == "新建分类...":
                add_new_cat_name = st.text_input("新建分类名称", key="bulk_add_new_cat_name", placeholder="例如：科技成长")
        elif op == "添加到分类":
            cats_to_add = st.multiselect("选择分类(可多选)", options=[c["name"] for c in cats], key="bulk_add_to_cats")
        elif op == "从分类移除":
            cats_to_remove = st.multiselect("选择分类(可多选)", options=[c["name"] for c in cats], key="bulk_remove_from_cats")
        else:
            st.caption(" ")
    # 新增操作的代码输入
    add_codes = None
    if op == "新增":
        add_codes = st.text_input("股票代码(逗号分隔)", key="bulk_add_codes", placeholder="如 600519,000001")
    with col_op3:
        disabled = False
        if op == "修改分类":
            disabled = (not selected_ids or not target)
        elif op == "添加到分类":
            disabled = (not selected_ids or not cats_to_add)
        elif op == "从分类移除":
            disabled = (not selected_ids or not cats_to_remove)
        elif op == "删除":
            disabled = (not selected_ids)
        elif op == "批量分析":
            disabled = (not selected_ids)
        elif op == "新增":
            need_cat_name = (target == "新建分类...")
            disabled = ((not target) or (not (add_codes or "").strip()) or (need_cat_name and not (add_new_cat_name or "").strip()))
        do_it = st.button("执行", disabled=disabled)
        if do_it:
            if op == "新增":
                # 解析并归一化为 ts_code
                raw_list = [c.strip() for c in (add_codes or "").replace("\n", ",").split(",") if c.strip()]
                names_map: Dict[str, str] = {}
                norm_codes: List[str] = []
                for raw in raw_list:
                    ts_code = _normalize_code_for_storage(raw)
                    if not ts_code:
                        continue
                    base_code = data_source_manager._convert_from_ts_code(ts_code)
                    display_name = (
                        _get_stock_name_cached(ts_code)
                        or _get_stock_name_cached(base_code)
                        or ts_code
                    )
                    names_map[ts_code] = display_name
                    norm_codes.append(ts_code)
                target_cat = None
                if target == "新建分类...":
                    cid = watchlist_repo.create_category(add_new_cat_name.strip(), None)
                    target_cat = {"id": cid, "name": add_new_cat_name.strip()}
                    primary_cid = target_cat["id"]
                    extra_cids: List[int] = []
                else:
                    target_cat = next((c for c in cats if c["name"] == target), None)
                    if not target_cat and target:
                        cid = watchlist_repo.create_category(target, None)
                        target_cat = {"id": cid, "name": target}
                    primary_cid = target_cat["id"] if target_cat else None
                    extra_cids = []
                if primary_cid and norm_codes:
                    res = watchlist_repo.add_items_bulk(norm_codes, primary_cid, on_conflict="ignore", names=names_map)
                    # 无额外分类
                    st.success(f"新增完成：新增 {res['added']}，跳过 {res['skipped']}，移动 {res['moved']}")
                    st.rerun()
            elif op == "修改分类":
                target_cat = next((c for c in cats if c["name"] == target), None)
                if target_cat:
                    cnt = watchlist_repo.update_item_category(selected_ids, target_cat["id"]) 
                    st.success(f"已修改 {cnt} 条")
                    st.rerun()
            elif op == "添加到分类":
                cid_list = [name_to_cat[n] for n in cats_to_add if n in name_to_cat]
                if cid_list:
                    cnt = watchlist_repo.add_categories_to_items(selected_ids, cid_list)
                    st.success(f"已添加到分类，受影响映射数约 {cnt}")
                    st.rerun()
            elif op == "从分类移除":
                cid_list = [name_to_cat[n] for n in cats_to_remove if n in name_to_cat]
                if cid_list:
                    cnt = watchlist_repo.remove_categories_from_items(selected_ids, cid_list)
                    st.success(f"已从分类移除，受影响映射行 {cnt}")
                    st.rerun()
            elif op == "删除":
                cnt = watchlist_repo.delete_items(selected_ids)
                st.success(f"已删除 {cnt} 条")
                st.rerun()
            elif op == "批量分析":
                # 将 ts_code 转为6位代码，符合主力选股批量分析期望
                codes_for_batch = []
                id_set = set(selected_ids)
                for it in items:
                    if it["id"] in id_set:
                        code6 = data_source_manager._convert_from_ts_code(it["code"]) if "." in str(it["code"]) else it["code"]
                        codes_for_batch.append(code6)
                st.session_state.main_force_batch_codes = codes_for_batch
                st.session_state.main_force_batch_trigger = True
                # 清除其他页面标志，切换到主力选股
                for k in [
                    'show_watchlist','show_history','show_monitor','show_config','show_sector_strategy',
                    'show_longhubang','show_portfolio','show_local_data','show_smart_monitor'
                ]:
                    if k in st.session_state:
                        del st.session_state[k]
                st.session_state.show_main_force = True
                if 'main_force_batch_auto_start' in st.session_state:
                    del st.session_state.main_force_batch_auto_start
                st.rerun()
