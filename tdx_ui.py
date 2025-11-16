from __future__ import annotations
import os
import time
from datetime import datetime, timezone
import datetime as dt
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv(override=True)

def _render_init_tab() -> None:
    st.subheader("🚀 初始化同步")
    # 数据源选择放在表单之外，切换时触发重绘
    ds_source = st.selectbox("数据源", options=["TDX", "Tushare"], index=0, key="init_src")
    with st.form("init_form"):
        if ds_source == "TDX":
            dataset_labels = {
                "kline_daily_raw": "日线（未复权 RAW）",
                "kline_minute_raw": "1 分钟（原始 RAW）",
            }
        else:
            dataset_labels = {
                "tdx_board_all": "通达信板块（信息+成分+行情）",
                "tdx_board_index": "通达信板块信息",
                "tdx_board_member": "通达信板块成分",
                "tdx_board_daily": "通达信板块行情",
                "tushare_trade_cal": "交易日历（Tushare trade_cal 同步）",
            }
        dataset = st.selectbox(
            "目标数据集",
            options=list(dataset_labels.keys()),
            format_func=lambda k: f"{k} · {dataset_labels[k]}",
            key=f"init_dataset_{ds_source}"
        )
        col1, col2 = st.columns(2)
        with col1:
            if ds_source == "TDX":
                start_date = st.text_input("开始日期", value="1990-01-01")
            else:
                start_date = st.text_input("开始日期", value=(dt.date.today() - dt.timedelta(days=365)).isoformat())
        with col2:
            end_date = st.text_input("结束日期", value=dt.date.today().isoformat())
        exchanges = st.text_input("交易所(逗号分隔)", value="sh,sz,bj") if ds_source == "TDX" else ""
        # Tushare 日历专用参数
        cal_exchange = None
        if ds_source == "Tushare" and dataset == "tushare_trade_cal":
            cal_exchange = st.selectbox("交易所(用于Tushare日历)", options=["SSE", "SZSE"], index=0, key="init_cal_exch")
        truncate = st.checkbox("初始化前清空目标表(或目标范围)", value=True) if ds_source == "TDX" else False
        confirm = st.checkbox("我已知晓清空数据的风险，并确认继续") if ds_source == "TDX" else True
        submitted = st.form_submit_button("开始初始化", type="primary")
        if submitted:
            if ds_source == "TDX" and truncate and not confirm:
                st.warning("请先勾选确认或取消清空选项后再继续")
            else:
                try:
                    if ds_source == "TDX":
                        opts: Dict[str, Any] = {
                            "exchanges": [s.strip() for s in exchanges.split(",") if s.strip()],
                            "start_date": start_date,
                            "end_date": end_date,
                            "batch_size": 100,
                            "truncate": bool(truncate),
                        }
                        payload = {"dataset": dataset, "options": opts}
                        resp = _backend_request("POST", "/api/ingestion/init", json=payload)
                        # 记录作业 ID，便于下方统一使用 /api/ingestion/job/{job_id} 轮询进度
                        st.session_state["init_job_id"] = resp.get("job_id")
                        st.session_state["init_auto_refresh"] = True
                        st.success("初始化任务已提交")
                        st.rerun()
                    else:
                        if dataset == "tushare_trade_cal":
                            # 交易日历同步
                            payload = {"start_date": start_date, "end_date": end_date, "exchange": cal_exchange or "SSE"}
                            resp = _backend_request("POST", "/api/calendar/sync", json=payload)
                            st.success(f"已同步：{int(resp.get('inserted_or_updated') or 0)} 条")
                        else:
                            opts = {
                                "start_date": start_date,
                                "end_date": end_date,
                                "batch_size": 200,
                            }
                            payload = {"dataset": dataset, "mode": "init", "options": opts}
                            resp = _backend_request("POST", "/api/ingestion/run", json=payload)
                            st.session_state["init_job_id"] = resp.get("job_id")
                            st.session_state["init_auto_refresh"] = True
                            st.success("初始化任务已提交")
                            st.rerun()
                except Exception as exc:  # noqa: BLE001
                    _render_backend_error(exc)

    job_id = st.session_state.get("init_job_id")
    if job_id:
        st.markdown(f"当前作业ID：`{job_id}`")
        try:
            job = _backend_request("GET", f"/api/ingestion/job/{job_id}")
            percent = int(job.get("progress") or 0)
            counters = job.get("counters") or {}
            colp, colt = st.columns([3, 1])
            with colp:
                st.progress(percent / 100.0, text=f"进度 {percent}% · 完成 {counters.get('done', 0)}/{counters.get('total', 0)} · 新增 {counters.get('inserted_rows', 0)} 条")
                st.caption(
                    f"总数 {counters.get('total', 0)} · 已完成 {counters.get('done', 0)} · 运行中 {counters.get('running', 0)} · 排队 {counters.get('pending', 0)} · 成功 {counters.get('success', 0)} · 失败 {counters.get('failed', 0)}"
                )
                logs = job.get("logs") or []
                if logs:
                    st.markdown("最近日志：")
                    for m in logs:
                        st.code(str(m))
            with colt:
                auto = st.checkbox("自动刷新", value=st.session_state.get("init_auto_refresh", True), key="init_auto_refresh")
            st.write(job)
            status = (job.get("status") or "").lower()
            if status in {"success", "failed", "canceled"}:
                if status == "success":
                    st.success("初始化完成")
                else:
                    st.error(f"初始化结束，状态：{status}")
                st.session_state.pop("init_job_id", None)
            else:
                if auto:
                    time.sleep(5)
                    st.rerun()
        except Exception as exc:  # noqa: BLE001
            _render_backend_error(exc)

"""Streamlit UI components for managing TDX testing & ingestion scheduling."""

CHINA_TZ = ZoneInfo("Asia/Shanghai")

FREQUENCY_CHOICES: List[tuple[str, str]] = [
    ("手动 (不调度)", ""),
    ("5 分钟", "5m"),
    ("10 分钟", "10m"),
    ("15 分钟", "15m"),
    ("30 分钟", "30m"),
    ("1 小时", "1h"),
    ("每日", "daily"),
]

INGESTION_DATASETS: Dict[str, str] = {
    "kline_daily_qfq": "日线（前复权）",
    "kline_minute_raw": "1 分钟原始",
    "tdx_board_all": "通达信板块（信息+成分+行情）",
    "tdx_board_index": "通达信板块信息",
    "tdx_board_member": "通达信板块成分",
    "tdx_board_daily": "通达信板块行情",
}


def _backend_request(method: str, path: str, **kwargs) -> Dict[str, Any]:
    base = os.getenv("TDX_BACKEND_BASE", "http://localhost:9000").rstrip("/")
    url = base + path
    timeout = kwargs.pop("timeout", 30)
    resp = requests.request(method, url, timeout=timeout, **kwargs)
    resp.raise_for_status()
    if resp.content:
        return resp.json()
    return {}


def _frequency_label(value: str) -> str:
    for label, freq in FREQUENCY_CHOICES:
        if freq == (value or ""):
            return label
    return value or "手动"


def _iso(value: Optional[str]) -> str:
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(CHINA_TZ).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return value


def _render_backend_error(exc: Exception) -> None:
    if isinstance(exc, requests.exceptions.ConnectionError):
        st.error(
            "无法连接调度服务，请确认后端已启动且地址正确。\n"
            f"错误详情：{exc}"
        )
    elif isinstance(exc, requests.exceptions.Timeout):
        st.error("后端请求超时，请稍后重试或检查网络。")
    else:
        st.error(f"后端请求失败: {exc}")
    # 展示详细异常堆栈，避免页面空白
    st.exception(exc)


def _render_testing_runs(runs: List[Dict[str, Any]]) -> None:
    if not runs:
        st.info("暂无测试执行记录")
        return
    df = pd.DataFrame(
        [
            {
                "执行ID": item.get("run_id"),
                "调度": item.get("schedule_id") or "手动",
                "发起者": item.get("triggered_by"),
                "状态": item.get("status"),
                "开始时间": _iso(item.get("started_at")),
                "结束时间": _iso(item.get("finished_at")),
                "成功数": (item.get("summary") or {}).get("success"),
                "失败数": (item.get("summary") or {}).get("failed"),
            }
            for item in runs
        ]
    )
    st.dataframe(df, use_container_width=True)


def _render_incremental_tab() -> None:
    st.subheader("🔄 增量更新")
    # 数据源选择放在表单之外，切换时触发重绘
    ds_source = st.selectbox("数据源", options=["TDX", "Tushare"], index=0, key="incr_src")
    with st.form("incremental_form"):
        if ds_source == "TDX":
            dataset_labels = {
                "kline_daily_qfq": "日线（前复权 QFQ）",
                "kline_minute_raw": "1 分钟（原始 RAW）",
            }
        else:
            dataset_labels = {
                "tdx_board_all": "通达信板块（信息+成分+行情）",
                "tdx_board_index": "通达信板块信息",
                "tdx_board_member": "通达信板块成分",
                "tdx_board_daily": "通达信板块行情",
                "tushare_trade_cal": "交易日历（Tushare trade_cal 同步）",
            }
        dataset = st.selectbox(
            "目标数据集",
            options=list(dataset_labels.keys()),
            format_func=lambda k: f"{k} · {dataset_labels[k]}",
            key=f"incr_dataset_{ds_source}"
        )
        col1, col2 = st.columns(2)
        with col1:
            date = st.text_input("目标日期", value=dt.date.today().isoformat())
        with col2:
            start_date = st.text_input("覆盖起始日期(可选)", value="")
        exchanges = st.text_input("交易所(逗号分隔)", value="sh,sz,bj") if ds_source == "TDX" else ""
        # Tushare 日历专用参数
        incr_cal_start = incr_cal_end = None
        incr_cal_exchange = None
        if ds_source == "Tushare" and dataset == "tushare_trade_cal":
            cc1, cc2 = st.columns(2)
            with cc1:
                incr_cal_start = st.text_input("开始日期", value=(dt.date.today() - dt.timedelta(days=365)).isoformat(), key="incr_cal_start")
            with cc2:
                incr_cal_end = st.text_input("结束日期", value=dt.date.today().isoformat(), key="incr_cal_end")
            incr_cal_exchange = st.selectbox("交易所(用于Tushare日历)", options=["SSE", "SZSE"], index=0, key="incr_cal_exch")
        batch_size = st.number_input("批大小", min_value=10, max_value=2000, value=100, step=10)
        submitted = st.form_submit_button("开始增量", type="primary")
        if submitted:
            try:
                if ds_source == "TDX":
                    opts: Dict[str, Any] = {
                        "date": date,
                        "start_date": (start_date or None),
                        "exchanges": [s.strip() for s in exchanges.split(",") if s.strip()],
                        "batch_size": int(batch_size),
                    }
                    payload = {"dataset": dataset, "mode": "incremental", "options": opts}
                    resp = _backend_request("POST", "/api/ingestion/run", json=payload)
                else:
                    if dataset == "tushare_trade_cal":
                        payload = {"start_date": incr_cal_start, "end_date": incr_cal_end, "exchange": incr_cal_exchange or "SSE"}
                        resp = _backend_request("POST", "/api/calendar/sync", json=payload)
                        st.success(f"已同步：{int(resp.get('inserted_or_updated') or 0)} 条")
                    else:
                        opts = {
                            "start_date": (start_date or None),
                            "end_date": date,
                            "batch_size": int(batch_size),
                        }
                        payload = {"dataset": dataset, "mode": "incremental", "options": opts}
                        resp = _backend_request("POST", "/api/ingestion/run", json=payload)
                        st.session_state["incr_job_id"] = resp.get("job_id")
                        st.session_state["incr_auto_refresh"] = True
                        st.success("增量任务已提交")
                        st.rerun()
            except Exception as exc:  # noqa: BLE001
                _render_backend_error(exc)

    job_id = st.session_state.get("incr_job_id")
    if job_id:
        st.markdown(f"当前作业ID：`{job_id}`")
        try:
            job = _backend_request("GET", f"/api/ingestion/job/{job_id}")
            percent = int(job.get("progress") or 0)
            counters = job.get("counters") or {}
            colp, colt = st.columns([3, 1])
            with colp:
                st.progress(percent / 100.0, text=f"进度 {percent}% · 完成 {counters.get('done', 0)}/{counters.get('total', 0)} · 新增 {counters.get('inserted_rows', 0)} 条")
                st.caption(
                    f"总数 {counters.get('total', 0)} · 已完成 {counters.get('done', 0)} · 运行中 {counters.get('running', 0)} · 排队 {counters.get('pending', 0)} · 成功 {counters.get('success', 0)} · 失败 {counters.get('failed', 0)}"
                )
                logs = job.get("logs") or []
                if logs:
                    st.markdown("最近日志：")
                    for m in logs:
                        st.code(str(m))
            with colt:
                auto = st.checkbox("自动刷新", value=st.session_state.get("incr_auto_refresh", True), key="incr_auto_refresh")
            status = (job.get("status") or "").lower()
            if status in {"success", "failed", "canceled"}:
                if status == "success":
                    st.success("增量更新完成")
                else:
                    st.error(f"增量结束，状态：{status}")
                st.session_state.pop("incr_job_id", None)
            else:
                if auto:
                    time.sleep(5)
                    st.rerun()
        except Exception as exc:  # noqa: BLE001
            _render_backend_error(exc)


def _render_adjust_tab() -> None:
    st.subheader("🛠️ 复权生成（RAW → QFQ/HFQ）")
    with st.form("adjust_rebuild_form"):
        which = st.selectbox("生成类型", options=["both", "qfq", "hfq"], format_func=lambda x: {"both": "QFQ+HFQ", "qfq": "仅QFQ", "hfq": "仅HFQ"}[x])
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.text_input("开始日期", value="1990-01-01")
        with col2:
            end_date = st.text_input("结束日期", value=dt.date.today().isoformat())
        exchanges = st.text_input("交易所(逗号分隔)", value="sh,sz,bj")
        workers = st.selectbox("并行度", options=[1, 2, 4, 8], index=0, format_func=lambda x: f"{x} 线程")
        truncate = st.checkbox("生成前清理目标表/范围", value=False)
        confirm = st.checkbox("我已知晓清理数据的风险，并确认继续")
        submitted = st.form_submit_button("开始生成", type="primary")
        if submitted:
            if truncate and not confirm:
                st.warning("请先勾选确认或取消清理选项后再继续")
            else:
                try:
                    opts: Dict[str, Any] = {
                        "which": which,
                        "start_date": start_date,
                        "end_date": end_date,
                        "exchanges": [s.strip() for s in exchanges.split(",") if s.strip()],
                        "workers": int(workers),
                        "truncate": bool(truncate),
                    }
                    resp = _backend_request("POST", "/api/adjust/rebuild", json={"options": opts})
                    st.session_state["adjust_job_id"] = resp.get("job_id")
                    st.session_state["adjust_auto_refresh"] = True
                    st.success("复权生成任务已提交")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    _render_backend_error(exc)

    job_id = st.session_state.get("adjust_job_id")
    if job_id:
        st.markdown(f"当前作业ID：`{job_id}`")
        try:
            job = _backend_request("GET", f"/api/ingestion/job/{job_id}")
            percent = int(job.get("progress") or 0)
            counters = job.get("counters") or {}
            colp, colt = st.columns([3, 1])
            with colp:
                st.progress(percent / 100.0, text=f"进度 {percent}% · 完成 {counters.get('done', 0)}/{counters.get('total', 0)} · 新增 {counters.get('inserted_rows', 0)} 条")
                st.caption(
                    f"总数 {counters.get('total', 0)} · 已完成 {counters.get('done', 0)} · 运行中 {counters.get('running', 0)} · 排队 {counters.get('pending', 0)} · 成功 {counters.get('success', 0)} · 失败 {counters.get('failed', 0)}"
                )
                logs = job.get("logs") or []
                if logs:
                    st.markdown("最近日志：")
                    for m in logs:
                        st.code(str(m))
            with colt:
                auto = st.checkbox("自动刷新", value=st.session_state.get("adjust_auto_refresh", True), key="adjust_auto_refresh")
            status = (job.get("status") or "").lower()
            if status in {"success", "failed", "canceled"}:
                if status == "success":
                    st.success("复权生成完成")
                else:
                    st.error(f"复权生成结束，状态：{status}")
                st.session_state.pop("adjust_job_id", None)
            else:
                if auto:
                    time.sleep(5)
                    st.rerun()
        except Exception as exc:  # noqa: BLE001
            _render_backend_error(exc)


def _render_ingestion_logs(logs: List[Dict[str, Any]]) -> None:
    if not logs:
        st.info("暂无入库日志")
        return
    rows: List[Dict[str, Any]] = []
    for item in logs:
        payload = item.get("payload") or {}
        summary = payload.get("summary") or {}
        dataset = summary.get("dataset")
        # 兼容早期日志：数据集可能存放在 datasets 列表中
        if dataset is None:
            datasets = summary.get("datasets")
            if isinstance(datasets, list) and datasets:
                dataset = datasets[0]
        # 再次兜底：从原始文本中提取首个词作为任务内容
        if dataset is None:
            raw = payload.get("raw")
            if isinstance(raw, str) and raw.strip():
                dataset = raw.split()[0]
        mode = summary.get("mode") or payload.get("status")
        dataset_label = str(dataset) if dataset is not None else "—"
        task_label = dataset_label
        if isinstance(mode, str) and mode:
            task_label = f"{dataset_label} · {mode}"
        note: Optional[str] = None
        if payload.get("error") is not None:
            note = str(payload.get("error"))
        elif payload.get("summary") is not None:
            note = str(payload.get("summary"))
        else:
            raw_val = payload.get("raw")
            if isinstance(raw_val, str) and raw_val.strip():
                note = raw_val
        # 若以上均为空，则尝试从 logs 字段中提取部分错误输出
        if note is None:
            logs_text = payload.get("logs")
            if isinstance(logs_text, str) and logs_text.strip():
                # 只展示最后 300 个字符，避免页面过长
                snippet = logs_text.strip()
                if len(snippet) > 300:
                    snippet = "..." + snippet[-300:]
                note = snippet
        rows.append(
            {
                "任务内容": task_label,
                "运行ID": item.get("run_id"),
                "日志时间": _iso(item.get("timestamp")),
                "级别": item.get("level"),
                "数据集": dataset_label,
                "模式": mode,
                "状态": payload.get("status"),
                "备注": note,
            }
        )
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)


def _render_task_monitor() -> None:
    st.subheader("📊 任务监视器")
    cols = st.columns([1, 1, 1])
    with cols[0]:
        active_only = st.checkbox("仅显示运行中/排队", value=True, key="monitor_active_only")
    with cols[1]:
        limit = st.number_input("最多显示", min_value=10, max_value=200, value=50, step=10, key="monitor_limit")
    with cols[2]:
        auto = st.checkbox("自动刷新", value=st.session_state.get("monitor_auto", True), key="monitor_auto")
    try:
        with st.spinner("正在加载任务..."):
            payload = _backend_request(
                "GET",
                "/api/ingestion/jobs",
                params={"limit": int(limit), "active_only": bool(active_only)},
                timeout=8,
            )
            items = payload.get("items", [])
    except Exception as exc:  # noqa: BLE001
        _render_backend_error(exc)
        return
    if not items:
        st.info("暂无任务")
        return
    any_active = False
    for job in items:
        summary = job.get("summary") or {}
        dataset = summary.get("dataset") or (summary.get("datasets") or [None])[0]
        mode = (summary.get("mode") or job.get("job_type") or "").lower()
        cat = "其他"
        ds = (dataset or "").lower() if isinstance(dataset, str) else str(dataset)
        if ds in {"kline_daily_qfq", "kline_daily", "kline_daily_raw"} and mode == "init":
            cat = "日线初始化"
        elif ds in {"kline_daily_qfq", "kline_daily", "kline_daily_raw"} and mode == "incremental":
            cat = "日线增量"
        elif ds == "adjust_daily" and mode in {"rebuild", "init"}:
            cat = "复权计算"
        elif ds.startswith("tdx_board_"):
            cat = "板块数据"
        percent = int(job.get("progress") or 0)
        counters = job.get("counters") or {}
        error_samples = job.get("error_samples") or []
        status = (job.get("status") or "").lower()
        if status in {"running", "queued", "pending"}:
            any_active = True
        with st.expander(f"{cat} · 数据集: {dataset or '—'} · 模式: {summary.get('mode') or job.get('job_type') or '—'} · 状态: {job.get('status') or '—'}", expanded=False):
            st.caption(f"开始时间：{_iso(job.get('started_at'))} · 创建时间：{_iso(job.get('created_at'))}")
            st.progress(percent / 100.0, text=f"进度 {percent}% · 完成 {counters.get('done', 0)}/{counters.get('total', 0)} · 新增 {counters.get('inserted_rows', 0)} 条")
            st.caption(
                f"总数 {counters.get('total', 0)} · 已完成 {counters.get('done', 0)} · 运行中 {counters.get('running', 0)} · 排队 {counters.get('pending', 0)} · 成功 {counters.get('success', 0)} · 失败 {counters.get('failed', 0)}"
            )
            # 根据 summary 显示本任务处理的数据来源与范围，便于快速理解任务内容
            source_label = "—"
            ds_lower = (dataset or "").lower() if isinstance(dataset, str) else str(dataset or "")
            if ds_lower in {"kline_daily_qfq", "kline_daily", "kline_daily_raw"}:
                source_label = "TDX 日线行情"
            elif ds_lower in {"kline_minute_raw", "minute_1m"}:
                source_label = "TDX 分钟行情"
            elif ds_lower == "adjust_daily":
                source_label = "Tushare 复权因子"
            elif ds_lower.startswith("tdx_board_"):
                source_label = "TDX 板块数据"

            start_date = summary.get("start_date") or summary.get("start") or summary.get("date_from")
            end_date = summary.get("end_date") or summary.get("end") or summary.get("date_to")
            target_date = summary.get("date") or summary.get("target_date")
            date_range_text: Optional[str]
            if start_date or end_date:
                date_range_text = f"{start_date or '—'} .. {end_date or '—'}"
            elif target_date:
                date_range_text = str(target_date)
            else:
                date_range_text = "—"

            exchanges_val = summary.get("exchanges")
            if isinstance(exchanges_val, (list, tuple)):
                exchanges_text = ",".join(str(x) for x in exchanges_val)
            elif isinstance(exchanges_val, str):
                exchanges_text = exchanges_val
            else:
                exchanges_text = None

            extra_parts: List[str] = []
            if exchanges_text:
                extra_parts.append(f"交易所：{exchanges_text}")
            if date_range_text and date_range_text != "—":
                extra_parts.append(f"日期：{date_range_text}")
            # 复权专用的一些参数
            which_val = summary.get("which")
            if which_val:
                extra_parts.append(f"复权类型：{which_val}")
            workers_val = summary.get("workers")
            if workers_val:
                extra_parts.append(f"并行度：{workers_val}")

            range_text = " · ".join(extra_parts) if extra_parts else "—"
            st.caption(f"数据源：{source_label} · 数据集：{dataset or '—'} · 范围：{range_text}")
            # 如果有失败任务，展示一小段错误样本（代码 + 日期/范围 + 简要错误信息）
            if counters.get("failed", 0) > 0 and error_samples:
                with st.expander("查看失败明细（样本）", expanded=False):
                    for err in error_samples:
                        ts_code = err.get("ts_code") or "—"
                        detail = err.get("detail") or {}
                        # detail 中通常包含 code / trade_date 或日期范围
                        trade_date = None
                        if isinstance(detail, dict):
                            trade_date = detail.get("trade_date") or detail.get("date") or detail.get("start_date")
                        msg = str(err.get("message") or "").strip()
                        if len(msg) > 200:
                            msg = msg[:200] + "..."
                        st.markdown(
                            f"- 代码：`{ts_code}` · 日期/范围：{trade_date or '未知'}\n  \n  错误：{msg}"
                        )


    if auto and any_active:
        time.sleep(5)
        st.rerun()


def _render_testing_tab() -> None:
    st.subheader("🧪 TDX 接口自动化测试")
    col_run, col_refresh = st.columns([1, 1])
    with col_run:
        if st.button("立即执行测试", type="primary", key="testing_run_button"):
            try:
                _backend_request("POST", "/api/testing/run", json={"triggered_by": "ui"})
                st.success("测试任务已提交")
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                _render_backend_error(exc)
    with col_refresh:
        if st.button("刷新状态", key="testing_refresh_button"):
            st.rerun()

    try:
        with st.spinner("正在加载测试调度与历史..."):
            schedules_payload = _backend_request("GET", "/api/testing/schedule", timeout=8)
            runs_payload = _backend_request("GET", "/api/testing/runs", params={"limit": 50}, timeout=8)
    except Exception as exc:  # noqa: BLE001
        _render_backend_error(exc)
        return

    schedules = schedules_payload.get("items", [])
    if schedules:
        for item in schedules:
            sched_id = item.get("schedule_id")
            enabled = item.get("enabled", True)
            with st.expander(f"调度 {sched_id} · {_frequency_label(item.get('frequency'))}", expanded=False):
                st.markdown(
                    f"- 启用状态：{'🟢 启用' if enabled else '⚪️ 停用'}\n"
                    f"- 上次运行：{_iso(item.get('last_run_at'))}\n"
                    f"- 下次运行：{_iso(item.get('next_run_at'))}\n"
                    f"- 上次状态：{item.get('last_status') or '—'}\n"
                    f"- 错误信息：{item.get('last_error') or '—'}"
                )
                with st.form(f"testing_schedule_form_{sched_id}"):
                    freq_labels = [label for label, _ in FREQUENCY_CHOICES]
                    freq_values = [value for _, value in FREQUENCY_CHOICES]
                    try:
                        current_index = freq_values.index(item.get("frequency") or "")
                    except ValueError:
                        current_index = 0
                    selected = st.selectbox("调度频率", freq_labels, index=current_index, key=f"freq_{sched_id}")
                    enabled_flag = st.checkbox("启用调度", value=enabled, key=f"enabled_{sched_id}")
                    submitted = st.form_submit_button("保存")
                    if submitted:
                        try:
                            freq_value = dict(zip(freq_labels, freq_values))[selected]
                            payload = {
                                "schedule_id": sched_id,
                                "frequency": freq_value,
                                "enabled": enabled_flag,
                            }
                            _backend_request("POST", "/api/testing/schedule", json=payload)
                            st.success("调度已更新")
                            st.rerun()
                        except Exception as exc:  # noqa: BLE001
                            _render_backend_error(exc)
                cols = st.columns([1, 1, 2])
                with cols[0]:
                    if st.button("切换启用", key=f"testing_toggle_{sched_id}"):
                        try:
                            _backend_request(
                                "POST",
                                f"/api/testing/schedule/{sched_id}/toggle",
                                json={"enabled": not enabled},
                            )
                            st.rerun()
                        except Exception as exc:  # noqa: BLE001
                            _render_backend_error(exc)
                with cols[1]:
                    if st.button("立即运行", key=f"testing_run_schedule_{sched_id}"):
                        try:
                            _backend_request("POST", f"/api/testing/schedule/{sched_id}/run")
                            st.success("调度任务已排队")
                            st.rerun()
                        except Exception as exc:  # noqa: BLE001
                            _render_backend_error(exc)
    else:
        st.info("尚未配置测试调度，使用下方表单新建。")

    with st.form("testing_schedule_create"):
        st.markdown("#### 新建测试调度")
        freq_labels = [label for label, _ in FREQUENCY_CHOICES]
        freq_values = [value for _, value in FREQUENCY_CHOICES]
        selected = st.selectbox("调度频率", freq_labels, index=1)
        enabled_flag = st.checkbox("启用调度", value=True)
        submitted = st.form_submit_button("创建调度")
        if submitted:
            try:
                freq_value = dict(zip(freq_labels, freq_values))[selected]
                payload = {
                    "frequency": freq_value or "5m",
                    "enabled": enabled_flag,
                }
                _backend_request("POST", "/api/testing/schedule", json=payload)
                st.success("测试调度已创建")
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                _render_backend_error(exc)

    st.markdown("### 最近测试执行")
    _render_testing_runs(runs_payload.get("items", []))


def _render_ingestion_tab() -> None:
    st.subheader("📥 数据入库调度")
    cols_tools = st.columns([1, 3])
    with cols_tools[0]:
        if st.button("创建默认调度", key="create_default_ingestion_schedules"):
            try:
                _backend_request("POST", "/api/ingestion/schedule/defaults", json={})
                st.success("默认调度已创建/更新")
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                _render_backend_error(exc)
    with st.form("ingestion_manual_form"):
        st.markdown("#### 手动执行入库任务")
        dataset = st.selectbox(
            "目标数据集",
            options=list(INGESTION_DATASETS.keys()),
            format_func=lambda key: f"{key} · {INGESTION_DATASETS[key]}",
        )
        mode = st.radio("执行模式", options=["incremental", "init"], format_func=lambda x: "增量" if x == "incremental" else "初始化")
        submitted = st.form_submit_button("立即执行", type="primary")
        if submitted:
            try:
                payload = {
                    "dataset": dataset,
                    "mode": mode,
                    "triggered_by": "ui",
                }
                _backend_request("POST", "/api/ingestion/run", json=payload)
                st.success("入库任务已提交")
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                _render_backend_error(exc)

    try:
        with st.spinner("正在加载入库调度..."):
            schedules_payload = _backend_request("GET", "/api/ingestion/schedule", timeout=8)
    except Exception as exc:  # noqa: BLE001
        _render_backend_error(exc)
        return

    schedules = schedules_payload.get("items", [])
    if schedules:
        for item in schedules:
            sched_id = item.get("schedule_id")
            dataset = item.get("dataset")
            mode = item.get("mode")
            enabled = item.get("enabled", True)
            label = f"{dataset} · {mode}"
            with st.expander(f"调度 {sched_id} · {label}"):
                st.markdown(
                    f"- 启用状态：{'🟢 启用' if enabled else '⚪️ 停用'}\n"
                    f"- 调度频率：{_frequency_label(item.get('frequency'))}\n"
                    f"- 上次运行：{_iso(item.get('last_run_at'))}\n"
                    f"- 下次运行：{_iso(item.get('next_run_at'))}\n"
                    f"- 上次状态：{item.get('last_status') or '—'}\n"
                    f"- 错误信息：{item.get('last_error') or '—'}"
                )
                with st.form(f"ingestion_schedule_form_{sched_id}"):
                    freq_labels = [label for label, _ in FREQUENCY_CHOICES]
                    freq_values = [value for _, value in FREQUENCY_CHOICES]
                    try:
                        current_index = freq_values.index(item.get("frequency") or "")
                    except ValueError:
                        current_index = 0
                    selected = st.selectbox("调度频率", freq_labels, index=current_index, key=f"ing_freq_{sched_id}")
                    enabled_flag = st.checkbox("启用调度", value=enabled, key=f"ing_enabled_{sched_id}")
                    submitted = st.form_submit_button("保存")
                    if submitted:
                        try:
                            freq_value = dict(zip(freq_labels, freq_values))[selected]
                            payload = {
                                "schedule_id": sched_id,
                                "dataset": dataset,
                                "mode": mode,
                                "frequency": freq_value,
                                "enabled": enabled_flag,
                            }
                            _backend_request("POST", "/api/ingestion/schedule", json=payload)
                            st.success("调度已更新")
                            st.rerun()
                        except Exception as exc:  # noqa: BLE001
                            _render_backend_error(exc)
                cols = st.columns([1, 1, 2])
                with cols[0]:
                    if st.button("切换启用", key=f"ingestion_toggle_{sched_id}"):
                        try:
                            _backend_request(
                                "POST",
                                f"/api/ingestion/schedule/{sched_id}/toggle",
                                json={"enabled": not enabled},
                            )
                            st.rerun()
                        except Exception as exc:  # noqa: BLE001
                            _render_backend_error(exc)
                with cols[1]:
                    if st.button("立即运行", key=f"ingestion_run_schedule_{sched_id}"):
                        try:
                            _backend_request("POST", f"/api/ingestion/schedule/{sched_id}/run")
                            st.success("调度任务已排队")
                            st.rerun()
                        except Exception as exc:  # noqa: BLE001
                            _render_backend_error(exc)
    else:
        st.info("尚未配置入库调度，使用下方表单新建。")

    with st.form("ingestion_schedule_create"):
        st.markdown("#### 新建入库调度")
        dataset = st.selectbox(
            "目标数据集",
            options=list(INGESTION_DATASETS.keys()),
            format_func=lambda key: f"{key} · {INGESTION_DATASETS[key]}",
            key="create_dataset",
        )
        mode = st.radio("执行模式", options=["incremental", "init"], horizontal=True, key="create_mode")
        freq_labels = [label for label, _ in FREQUENCY_CHOICES]
        freq_values = [value for _, value in FREQUENCY_CHOICES]
        selected = st.selectbox("调度频率", freq_labels, index=1, key="create_freq")
        enabled_flag = st.checkbox("启用调度", value=True, key="create_enabled")
        submitted = st.form_submit_button("创建调度")
        if submitted:
            try:
                freq_value = dict(zip(freq_labels, freq_values))[selected]
                payload = {
                    "dataset": dataset,
                    "mode": mode,
                    "frequency": freq_value or "5m",
                    "enabled": enabled_flag,
                }
                _backend_request("POST", "/api/ingestion/schedule", json=payload)
                st.success("入库调度已创建")
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                _render_backend_error(exc)


def _render_logs_tab() -> None:
    st.subheader("📝 执行日志")
    cols = st.columns([1, 1])
    with cols[0]:
        logs_limit = st.number_input("日志条数", min_value=10, max_value=200, value=50, step=10)
    with cols[1]:
        if st.button("刷新日志", key="refresh_logs"):
            st.rerun()
    try:
        with st.spinner("正在加载日志..."):
            testing_runs = _backend_request("GET", "/api/testing/runs", params={"limit": 30}, timeout=8)
            ingestion_logs = _backend_request("GET", "/api/ingestion/logs", params={"limit": int(logs_limit)}, timeout=8)
    except Exception as exc:  # noqa: BLE001
        _render_backend_error(exc)
        return

    st.markdown("### 测试执行记录")
    _render_testing_runs(testing_runs.get("items", []))

    st.markdown("### 入库运行日志")
    _render_ingestion_logs(ingestion_logs.get("items", []))


def _render_calendar_tab() -> None:
    st.subheader("📅 交易日历管理（Tushare trade_cal）")
    st.caption("从 Tushare 接口同步交易日历，支持手动选择起止日期。后端兜底：如表空缺，将在运行时自动拉取近60天补齐。")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        start_date = st.date_input("开始日期", value=dt.date.today() - dt.timedelta(days=365))
    with col2:
        end_date = st.date_input("结束日期", value=dt.date.today())
    with col3:
        exchange = st.selectbox("交易所", options=["SSE", "SZSE"], index=0)
    if st.button("同步交易日历", type="primary"):
        try:
            payload = {"start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "exchange": exchange}
            resp = _backend_request("POST", "/api/calendar/sync", json=payload)
            st.success(f"已同步：{int(resp.get('inserted_or_updated') or 0)} 条")
        except Exception as exc:  # noqa: BLE001
            _render_backend_error(exc)

def show_local_data_management() -> None:
    """Render the Local Data Management dashboard."""
    st.title("🗄️ 本地数据管理")
    st.caption("集中管理 TDX 接口测试与数据入库调度，支持手动与自动执行。")
    backend_base = os.getenv("TDX_BACKEND_BASE", "http://localhost:9000")
    st.info(f"当前调度后端地址：{backend_base}")

    test_col1, test_col2 = st.columns([1, 3])
    with test_col1:
        if st.button("测试连接", key="backend_ping"):
            try:
                _backend_request("GET", "/api/testing/schedule", timeout=10)
                st.success("调度后端连接成功。")
            except Exception as exc:  # noqa: BLE001
                _render_backend_error(exc)
    with test_col2:
        st.caption("提示：服务启动命令 `uvicorn tdx_backend:app --host 0.0.0.0 --port 9000`")

    tab = st.radio(
        "选择功能",
        ["初始化", "增量", "复权生成", "任务监视器", "数据源测试", "数据入库调度", "运行日志"],
        horizontal=True,
        key="local_data_tab",
    )

    if tab == "初始化":
        _render_init_tab()
    elif tab == "增量":
        _render_incremental_tab()
    elif tab == "复权生成":
        _render_adjust_tab()
    elif tab == "任务监视器":
        _render_task_monitor()
    elif tab == "数据源测试":
        _render_testing_tab()
    elif tab == "数据入库调度":
        _render_ingestion_tab()
    elif tab == "运行日志":
        _render_logs_tab()
