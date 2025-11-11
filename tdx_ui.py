from __future__ import annotations

"""Streamlit UI components for managing TDX testing & ingestion scheduling."""

import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv(override=True)

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
}


def _backend_request(method: str, path: str, **kwargs) -> Dict[str, Any]:
    base = os.getenv("TDX_BACKEND_BASE", "http://localhost:8080").rstrip("/")
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


def _render_ingestion_logs(logs: List[Dict[str, Any]]) -> None:
    if not logs:
        st.info("暂无入库日志")
        return
    df = pd.DataFrame(
        [
            {
                "日志时间": _iso(item.get("timestamp")),
                "级别": item.get("level"),
                "运行ID": item.get("run_id"),
                "数据集": (item.get("payload") or {}).get("summary", {}).get("dataset"),
                "模式": (item.get("payload") or {}).get("summary", {}).get("mode"),
                "状态": (item.get("payload") or {}).get("status"),
                "备注": (item.get("payload") or {}).get("error") or (item.get("payload") or {}).get("summary"),
            }
            for item in logs
        ]
    )
    st.dataframe(df, use_container_width=True)


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
        schedules_payload = _backend_request("GET", "/api/testing/schedule")
        runs_payload = _backend_request("GET", "/api/testing/runs", params={"limit": 50})
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
        schedules_payload = _backend_request("GET", "/api/ingestion/schedule")
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
        testing_runs = _backend_request("GET", "/api/testing/runs", params={"limit": 30})
        ingestion_logs = _backend_request("GET", "/api/ingestion/logs", params={"limit": int(logs_limit)})
    except Exception as exc:  # noqa: BLE001
        _render_backend_error(exc)
        return

    st.markdown("### 测试执行记录")
    _render_testing_runs(testing_runs.get("items", []))

    st.markdown("### 入库运行日志")
    _render_ingestion_logs(ingestion_logs.get("items", []))


def show_local_data_management() -> None:
    """Render the Local Data Management dashboard."""
    st.title("🗄️ 本地数据管理")
    st.caption("集中管理 TDX 接口测试与数据入库调度，支持手动与自动执行。")
    backend_base = os.getenv("TDX_BACKEND_BASE", "http://localhost:8080")
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
        st.caption("提示：服务启动命令 `uvicorn tdx_backend:app --host 0.0.0.0 --port 8080`")

    tabs = st.tabs(["数据源测试", "数据入库调度", "运行日志"])
    with tabs[0]:
        _render_testing_tab()
    with tabs[1]:
        _render_ingestion_tab()
    with tabs[2]:
        _render_logs_tab()
