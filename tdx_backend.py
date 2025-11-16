"""FastAPI backend service for TDX testing and ingestion scheduling.

This service exposes endpoints used by the Streamlit front-end (or other
clients) to trigger test scripts, manage schedules, and start ingestion jobs.
It relies on :mod:`tdx_scheduler` for background execution and the tables
created by ``scripts/init_market_schema.py`` for persistence.

Run with::

    uvicorn tdx_backend:app --host 0.0.0.0 --port 9000

"""
from __future__ import annotations

import datetime as dt
import json
import os
import uuid
from contextlib import contextmanager
from typing import Any, Dict, List, Optional
import threading
import time
import requests
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras as pgx
from fastapi import FastAPI, HTTPException, Path, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from tdx_scheduler import DEFAULT_DB_CFG, scheduler
from data_source_manager import data_source_manager

pgx.register_uuid()

load_dotenv(override=True)
HOTBOARD_PERF = os.getenv("HOTBOARD_PERF_DEBUG", "0").lower() in {"1", "true", "yes", "on"}


def _perf_log_hotboard(name: str, **kwargs: Any) -> None:
    if not HOTBOARD_PERF:
        return
    parts = " ".join(f"{k}={v}" for k, v in kwargs.items())
    print(f"[PERF hotboard:{name}] {parts}")
API_TITLE = "TDX Scheduling Backend"
API_VERSION = "0.1.0"
DEFAULT_TRIGGERED_BY = "api"

SUPPORTED_INGESTION_MODES = {"init", "incremental"}


def _json_dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def _json_load(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:  # noqa: BLE001 - fallback raw
        return value


def _isoformat(value: Optional[dt.datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc).isoformat()
    return value.astimezone(dt.timezone.utc).isoformat()


@contextmanager
def get_conn():
    db_cfg = {
        "host": os.getenv("TDX_DB_HOST", DEFAULT_DB_CFG["host"]),
        "port": int(os.getenv("TDX_DB_PORT", DEFAULT_DB_CFG["port"])),
        "user": os.getenv("TDX_DB_USER", DEFAULT_DB_CFG["user"]),
        "password": os.getenv("TDX_DB_PASSWORD", DEFAULT_DB_CFG["password"]),
        "dbname": os.getenv("TDX_DB_NAME", DEFAULT_DB_CFG["dbname"]),
    }
    conn = psycopg2.connect(**db_cfg)
    conn.autocommit = True
    try:
        yield conn
    finally:
        conn.close()


def _fetchall(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=pgx.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            return [dict(row) for row in rows]


def _execute(sql: str, params: tuple) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)


def _ensure_testing_schedule(schedule_id: uuid.UUID) -> Dict[str, Any]:
    rows = _fetchall(
        """
        SELECT schedule_id, enabled, frequency, options, last_run_at, next_run_at,
               last_status, last_error, created_at, updated_at
          FROM market.testing_schedules
         WHERE schedule_id = %s
        """,
        (schedule_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Testing schedule not found")
    return rows[0]


def _ensure_ingestion_schedule(schedule_id: uuid.UUID) -> Dict[str, Any]:
    rows = _fetchall(
        """
        SELECT schedule_id, dataset, mode, enabled, frequency, options,
               last_run_at, next_run_at, last_status, last_error,
               created_at, updated_at
          FROM market.ingestion_schedules
         WHERE schedule_id = %s
        """,
        (schedule_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Ingestion schedule not found")
    return rows[0]


def _serialize_schedule(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schedule_id": str(row.get("schedule_id")),
        "enabled": row.get("enabled", True),
        "frequency": row.get("frequency"),
        "options": _json_load(row.get("options")) or {},
        "last_run_at": _isoformat(row.get("last_run_at")),
        "next_run_at": _isoformat(row.get("next_run_at")),
        "last_status": row.get("last_status"),
        "last_error": row.get("last_error"),
        "created_at": _isoformat(row.get("created_at")),
        "updated_at": _isoformat(row.get("updated_at")),
    }


def _serialize_ingestion_schedule(row: Dict[str, Any]) -> Dict[str, Any]:
    base = _serialize_schedule(row)
    base.update({
        "dataset": row.get("dataset"),
        "mode": row.get("mode"),
    })
    return base


def _serialize_ingestion_log(row: Dict[str, Any]) -> Dict[str, Any]:
    payload = _json_load(row.get("message"))
    if not isinstance(payload, dict):
        payload = {"raw": payload}
    return {
        "run_id": str(row.get("job_id")) if row.get("job_id") else None,
        "timestamp": _isoformat(row.get("ts")),
        "level": row.get("level"),
        "payload": payload,
    }


def _create_init_job(summary: Dict[str, Any]) -> uuid.UUID:
    job_id = uuid.uuid4()
    _execute(
        """
        INSERT INTO market.ingestion_jobs (job_id, job_type, status, created_at, summary)
        VALUES (%s, 'init', 'queued', NOW(), %s)
        """,
        (job_id, _json_dump(summary)),
    )
    return job_id


def _create_job(job_type: str, summary: Dict[str, Any]) -> uuid.UUID:
    job_id = uuid.uuid4()
    _execute(
        """
        INSERT INTO market.ingestion_jobs (job_id, job_type, status, created_at, summary)
        VALUES (%s, %s, 'queued', NOW(), %s)
        """,
        (job_id, job_type, _json_dump(summary)),
    )
    return job_id


def _job_status(job_id: uuid.UUID) -> Dict[str, Any]:
    rows = _fetchall(
        """
        SELECT job_id, job_type, status, created_at, started_at, finished_at, summary
          FROM market.ingestion_jobs
         WHERE job_id=%s
        """,
        (job_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Job not found")
    job = rows[0]
    summary = _json_load(job.get("summary")) or {}
    trows = _fetchall(
        """
        SELECT status, COUNT(*) AS cnt
          FROM market.ingestion_job_tasks
         WHERE job_id=%s
         GROUP BY status
        """,
        (job_id,),
    )
    total = 0
    done = 0
    failed = 0
    success = 0
    running = 0
    pending = 0
    for r in trows:
        cnt = int(r.get("cnt") or 0)
        total += cnt
        st = (r.get("status") or "").lower()
        if st == "success":
            success += cnt
            done += cnt
        elif st == "failed":
            failed += cnt
            done += cnt
        elif st in {"running"}:
            running += cnt
        elif st in {"queued", "pending"}:
            pending += cnt
    # Compute percent with multiple fallbacks
    percent = 0
    if total > 0:
        # If tasks exist and some are done, use done/total
        if done > 0:
            percent = min(100, int((done / total) * 100))
        else:
            # No tasks done yet — use average task progress if available
            avg_rows = _fetchall(
                """
                SELECT COALESCE(AVG(progress), 0) AS avg_progress
                  FROM market.ingestion_job_tasks
                 WHERE job_id=%s
                """,
                (job_id,),
            )
            try:
                avg_progress = int(float((avg_rows[0] or {}).get("avg_progress") or 0))
            except Exception:
                avg_progress = 0
            percent = max(percent, min(100, avg_progress))
    else:
        # No tasks recorded – use summary counters if present
        stats = summary.get("stats") or {}
        total_codes = int(summary.get("total_codes") or stats.get("total_codes") or 0)
        success_codes = int(summary.get("success_codes") or stats.get("success_codes") or 0)
        failed_codes = int(summary.get("failed_codes") or stats.get("failed_codes") or 0)
        total_days = int(summary.get("total_days") or 0)
        done_days = int(summary.get("done_days") or 0)
        if total_codes > 0:
            percent = min(100, int(((success_codes + failed_codes) / total_codes) * 100))
            total = total_codes
            done = success_codes + failed_codes
            success = success_codes
            failed = failed_codes
        elif total_days > 0:
            percent = min(100, int((done_days / total_days) * 100))
            total = total_days
            done = done_days
    # recent logs for better UI feedback
    log_rows = _fetchall(
        """
        SELECT message
          FROM market.ingestion_logs
         WHERE job_id=%s
         ORDER BY ts DESC
         LIMIT 5
        """,
        (job_id,),
    )
    logs = [str(r.get("message")) for r in (log_rows or []) if r.get("message") is not None]
    # small sample of errors for UI to show failure reasons and affected codes/dates
    error_rows = _fetchall(
        """
        SELECT e.run_id, e.ts_code, e.message, e.detail
          FROM market.ingestion_errors e
          JOIN market.ingestion_runs r ON r.run_id = e.run_id
         WHERE r.params->>'job_id' = %s
         ORDER BY e.run_id, e.ts_code
         LIMIT 20
        """,
        (str(job_id),),
    )
    error_samples = []
    for r in error_rows or []:
        error_samples.append(
            {
                "run_id": str(r.get("run_id")),
                "ts_code": r.get("ts_code"),
                "message": r.get("message"),
                "detail": r.get("detail"),
            }
        )
    # Extract inserted_rows from summary (root) or nested stats
    stats = summary.get("stats") or {}
    inserted_rows = int(summary.get("inserted_rows") or stats.get("inserted_rows") or 0)
    counters = {
        "total": total,
        "done": done,
        "running": running,
        "pending": pending,
        "failed": failed,
        "success": success,
        "inserted_rows": inserted_rows,
        "success_codes": int(summary.get("success_codes") or stats.get("success_codes") or 0),
    }
    return {
        "job_id": str(job.get("job_id")),
        "job_type": job.get("job_type"),
        "status": job.get("status"),
        "created_at": _isoformat(job.get("created_at")),
        "started_at": _isoformat(job.get("started_at")),
        "finished_at": _isoformat(job.get("finished_at")),
        "summary": summary,
        "progress": percent,
        "counters": counters,
        "logs": logs,
        "error_samples": error_samples,
    }


def _serialize_testing_run(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "run_id": str(row.get("run_id")),
        "schedule_id": str(row.get("schedule_id")) if row.get("schedule_id") else None,
        "triggered_by": row.get("triggered_by"),
        "status": row.get("status"),
        "started_at": _isoformat(row.get("started_at")),
        "finished_at": _isoformat(row.get("finished_at")),
        "summary": _json_load(row.get("summary")) or {},
        "detail": _json_load(row.get("detail")) or {},
    }


class TestingRunRequest(BaseModel):
    triggered_by: str = DEFAULT_TRIGGERED_BY
    options: Dict[str, Any] = Field(default_factory=dict)


class TestingScheduleUpsertRequest(BaseModel):
    schedule_id: Optional[uuid.UUID] = None
    frequency: str
    enabled: bool = True
    options: Dict[str, Any] = Field(default_factory=dict)


class ToggleRequest(BaseModel):
    enabled: bool


class IngestionRunRequest(BaseModel):
    dataset: str
    mode: str
    triggered_by: str = DEFAULT_TRIGGERED_BY
    options: Dict[str, Any] = Field(default_factory=dict)

    def validate_mode(self) -> None:
        if self.mode not in SUPPORTED_INGESTION_MODES:
            raise HTTPException(status_code=400, detail=f"mode must be one of {sorted(SUPPORTED_INGESTION_MODES)}")


class IngestionScheduleUpsertRequest(BaseModel):
    schedule_id: Optional[uuid.UUID] = None
    dataset: str
    mode: str
    frequency: str
    enabled: bool = True
    options: Dict[str, Any] = Field(default_factory=dict)

    def validate_mode(self) -> None:
        if self.mode not in SUPPORTED_INGESTION_MODES:
            raise HTTPException(status_code=400, detail=f"mode must be one of {sorted(SUPPORTED_INGESTION_MODES)}")


class IngestionInitRequest(BaseModel):
    dataset: str
    options: Dict[str, Any] = Field(default_factory=dict)


class AdjustRebuildRequest(BaseModel):
    options: Dict[str, Any] = Field(default_factory=dict)


def get_app() -> FastAPI:
    app = FastAPI(title=API_TITLE, version=API_VERSION)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------ HOTBOARD HELPERS ------------------------
    _hotboard_stop = threading.Event()
    _hotboard_threads: List[threading.Thread] = []

    def _now_sh() -> dt.datetime:
        return dt.datetime.now(ZoneInfo("Asia/Shanghai"))

    def _time_in_windows(now: dt.datetime, windows: List[str]) -> bool:
        if not windows:
            return True
        hhmm = now.strftime("%H:%M")
        for w in windows:
            try:
                a, b = str(w).split("-", 1)
                if a <= hhmm <= b:
                    return True
            except Exception:
                continue
        return False

    def _sina_headers() -> Dict[str, str]:
        return {
            "Host": "vip.stock.finance.sina.com.cn",
            "Referer": "https://finance.sina.com.cn",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    def _sina_money_rank(fenlei: str = "1", sort: str = "netamount", page: int = 1, num: int = 200) -> List[Dict[str, Any]]:
        url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/MoneyFlow.ssl_bkzj_bk"
        try:
            r = requests.get(url, params={"page": page, "num": num, "sort": sort, "asc": 0, "fenlei": fenlei}, headers=_sina_headers(), timeout=10)
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _sina_concept_stocks(concept_code: str, page: int = 1, num: int = 200) -> List[Dict[str, Any]]:
        url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
        try:
            r = requests.get(url, params={"node": concept_code, "page": page, "num": num, "sort": "symbol", "asc": 1, "symbol": "", "_s_r_a": "page"}, headers=_sina_headers(), timeout=10)
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _insert_sina_intraday(rows: List[Dict[str, Any]], cate_type: int, ts: dt.datetime) -> int:
        if not rows:
            return 0
        vals: List[tuple] = []
        for r in rows:
            try:
                vals.append(
                    (
                        ts,
                        int(cate_type),
                        str(r.get("category") or ""),
                        r.get("name"),
                        float(r.get("avg_changeratio") or 0.0),
                        float(r.get("inamount") or 0.0) + float(r.get("outamount") or 0.0),
                        float(r.get("netamount") or 0.0),
                        float(r.get("turnover") or 0.0),
                        float(r.get("ratioamount") or 0.0),
                        json.dumps(r, ensure_ascii=False, default=str),
                    )
                )
            except Exception:
                continue
        if not vals:
            return 0
        with get_conn() as conn:
            with conn.cursor() as cur:
                pgx.execute_values(
                    cur,
                    """
                    INSERT INTO market.sina_board_intraday
                    (ts,cate_type,board_code,board_name,pct_chg,amount,net_inflow,turnover,ratioamount,meta)
                    VALUES %s
                    ON CONFLICT (ts,cate_type,board_code) DO UPDATE
                      SET board_name=EXCLUDED.board_name,
                          pct_chg=EXCLUDED.pct_chg,
                          amount=EXCLUDED.amount,
                          net_inflow=EXCLUDED.net_inflow,
                          turnover=EXCLUDED.turnover,
                          ratioamount=EXCLUDED.ratioamount,
                          meta=EXCLUDED.meta
                    """,
                    vals,
                    page_size=500,
                )
        return len(vals)

    def _insert_sina_daily(trade_date: dt.date, rows: List[Dict[str, Any]], cate_type: int) -> int:
        if not rows:
            return 0
        vals: List[tuple] = []
        for r in rows:
            try:
                vals.append(
                    (
                        trade_date,
                        int(cate_type),
                        str(r.get("category") or ""),
                        r.get("name"),
                        float(r.get("avg_changeratio") or 0.0),
                        float(r.get("inamount") or 0.0) + float(r.get("outamount") or 0.0),
                        float(r.get("netamount") or 0.0),
                        float(r.get("turnover") or 0.0),
                        float(r.get("ratioamount") or 0.0),
                        json.dumps(r, ensure_ascii=False, default=str),
                    )
                )
            except Exception:
                continue
        if not vals:
            return 0
        with get_conn() as conn:
            with conn.cursor() as cur:
                pgx.execute_values(
                    cur,
                    """
                    INSERT INTO market.sina_board_daily
                    (trade_date,cate_type,board_code,board_name,pct_chg,amount,net_inflow,turnover,ratioamount,meta)
                    VALUES %s
                    ON CONFLICT (trade_date,cate_type,board_code) DO UPDATE
                      SET board_name=EXCLUDED.board_name,
                          pct_chg=EXCLUDED.pct_chg,
                          amount=EXCLUDED.amount,
                          net_inflow=EXCLUDED.net_inflow,
                          turnover=EXCLUDED.turnover,
                          ratioamount=EXCLUDED.ratioamount,
                          meta=EXCLUDED.meta
                    """,
                    vals,
                    page_size=500,
                )
        return len(vals)

    def _recent_trading_days(n: int = 10) -> List[dt.date]:
        rows = _fetchall(
            """
            SELECT cal_date FROM market.trading_calendar WHERE is_trading
            ORDER BY cal_date DESC LIMIT %s
            """,
            (n,),
        )
        days = [r["cal_date"] for r in rows]
        if len(days) >= n:
            return days
        # fallback: try fetching from tushare for recent window if token present
        try:
            token = os.getenv("TUSHARE_TOKEN")
            if token:
                import importlib
                ts = importlib.import_module("tushare")
                pro = ts.pro_api(token)
                end = dt.date.today().strftime("%Y%m%d")
                start = (dt.date.today() - dt.timedelta(days=60)).strftime("%Y%m%d")
                df = pro.trade_cal(exchange="SSE", start_date=start, end_date=end)
                if df is not None and not df.empty:
                    upserts = []
                    for _, r in df.iterrows():
                        d = str(r.get("cal_date"))
                        if len(d) == 8:
                            d = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
                        is_open = bool(int(r.get("is_open") or 0))
                        upserts.append((d, is_open))
                    if upserts:
                        with get_conn() as conn:
                            with conn.cursor() as cur:
                                pgx.execute_values(
                                    cur,
                                    "INSERT INTO market.trading_calendar(cal_date, is_trading) VALUES %s ON CONFLICT (cal_date) DO UPDATE SET is_trading=EXCLUDED.is_trading",
                                    upserts,
                                )
                # re-read
                rows2 = _fetchall(
                    "SELECT cal_date FROM market.trading_calendar WHERE is_trading ORDER BY cal_date DESC LIMIT %s",
                    (n,),
                )
                return [r["cal_date"] for r in rows2]
        except Exception:
            pass
        return days

    def _drop_intraday_older_than(date0: dt.date) -> None:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT drop_chunks('market.sina_board_intraday', older_than => %s)",
                    (dt.datetime.combine(date0, dt.time.min, tzinfo=dt.timezone.utc),),
                )

    def _collector_loop() -> None:
        while not _hotboard_stop.is_set():
            try:
                # load config
                cfg_rows = _fetchall("SELECT enabled, frequency_seconds, trading_windows FROM market.hotboard_config WHERE id=1")
                if cfg_rows:
                    cfg = cfg_rows[0]
                    enabled = bool(cfg.get("enabled"))
                    freq = int(cfg.get("frequency_seconds") or 5)
                    windows = cfg.get("trading_windows") or ["09:25-11:35", "12:55-15:05"]
                else:
                    enabled, freq, windows = True, 5, ["09:25-11:35", "12:55-15:05"]
                now = _now_sh()
                if enabled and _time_in_windows(now, windows):
                    ts = dt.datetime.now(dt.timezone.utc)
                    total = 0
                    for cate, fenlei in ((0, "0"), (1, "1"), (2, "2")):
                        ranks = _sina_money_rank(fenlei=fenlei, sort="netamount", page=1, num=200)
                        total += _insert_sina_intraday(ranks, cate, ts)
                    with get_conn() as conn:
                        with conn.cursor() as cur:
                            cur.execute("UPDATE market.hotboard_config SET last_run_at=NOW(), updated_at=NOW() WHERE id=1")
                time.sleep(max(3, min(60, freq)))
            except Exception:
                time.sleep(5)

    def _eod_loop() -> None:
        finished_for_day: Optional[str] = None
        while not _hotboard_stop.is_set():
            try:
                now = _now_sh()
                d = now.strftime("%Y-%m-%d")
                # 15:05 ~ 16:00 finalize once
                if ("15:05" <= now.strftime("%H:%M") <= "16:00") and finished_for_day != d:
                    # only finalize trading day
                    tr_rows = _fetchall("SELECT is_trading FROM market.trading_calendar WHERE cal_date=%s", (d,))
                    if tr_rows and bool(tr_rows[0].get("is_trading")):
                        for cate, fenlei in ((0, "0"), (1, "1"), (2, "2")):
                            ranks = _sina_money_rank(fenlei=fenlei, sort="netamount", page=1, num=200)
                            _insert_sina_daily(dt.date.fromisoformat(d), ranks, cate)
                        # retention: keep last 10 trading days of intraday
                        days = _recent_trading_days(10)
                        if len(days) == 10:
                            _drop_intraday_older_than(days[-1])
                        finished_for_day = d
                time.sleep(30)
            except Exception:
                time.sleep(30)

    @app.on_event("startup")
    def _startup() -> None:  # noqa: D401
        """Start the background scheduler on service boot."""
        scheduler.start()
        if (os.getenv("TDX_CREATE_DEFAULT_SCHEDULES", "0").lower() in {"1", "true", "yes", "on"}):
            try:
                _ensure_default_ingestion_schedules()
            except Exception:
                pass
        # hotboard threads
        try:
            t1 = threading.Thread(target=_collector_loop, name="hotboard-collector", daemon=True)
            t2 = threading.Thread(target=_eod_loop, name="hotboard-eod", daemon=True)
            _hotboard_threads[:] = [t1, t2]
            for t in _hotboard_threads:
                t.start()
        except Exception:
            pass

    @app.on_event("shutdown")
    def _shutdown() -> None:  # noqa: D401
        """Stop the background scheduler."""
        scheduler.shutdown(wait=False)
        try:
            _hotboard_stop.set()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Testing endpoints
    @app.post("/api/testing/run")
    def trigger_testing_run(payload: TestingRunRequest) -> Dict[str, Any]:
        run_id = scheduler.run_testing_now(triggered_by=payload.triggered_by, options=payload.options)
        return {"run_id": str(run_id)}

    @app.get("/api/testing/runs")
    def list_testing_runs(limit: int = 20) -> Dict[str, Any]:
        rows = _fetchall(
            """
            SELECT run_id, schedule_id, triggered_by, status, started_at, finished_at, summary, detail
              FROM market.testing_runs
             ORDER BY started_at DESC
             LIMIT %s
            """,
            (limit,),
        )
        return {"items": [_serialize_testing_run(row) for row in rows]}

    @app.get("/api/testing/schedule")
    def list_testing_schedules() -> Dict[str, Any]:
        rows = _fetchall(
            """
            SELECT schedule_id, enabled, frequency, options, last_run_at, next_run_at,
                   last_status, last_error, created_at, updated_at
              FROM market.testing_schedules
             ORDER BY created_at ASC
            """
        )
        return {"items": [_serialize_schedule(row) for row in rows]}

    @app.post("/api/testing/schedule")
    def upsert_testing_schedule(payload: TestingScheduleUpsertRequest) -> Dict[str, Any]:
        schedule_id = payload.schedule_id or uuid.uuid4()
        sql = """
            INSERT INTO market.testing_schedules (
                schedule_id, enabled, frequency, options, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (schedule_id)
            DO UPDATE SET enabled=EXCLUDED.enabled,
                          frequency=EXCLUDED.frequency,
                          options=EXCLUDED.options,
                          updated_at=NOW()
        """
        _execute(sql, (schedule_id, payload.enabled, payload.frequency, _json_dump(payload.options)))
        scheduler.refresh_schedules()
        data = _ensure_testing_schedule(schedule_id)
        return _serialize_schedule(data)

    @app.post("/api/testing/schedule/{schedule_id}/toggle")
    def toggle_testing_schedule(
        payload: ToggleRequest,
        schedule_id: uuid.UUID = Path(..., description="Testing schedule identifier"),
    ) -> Dict[str, Any]:
        _ensure_testing_schedule(schedule_id)
        sql = """
            UPDATE market.testing_schedules
               SET enabled=%s, updated_at=NOW()
             WHERE schedule_id=%s
        """
        _execute(sql, (payload.enabled, schedule_id))
        scheduler.refresh_schedules()
        data = _ensure_testing_schedule(schedule_id)
        return _serialize_schedule(data)

    @app.post("/api/testing/schedule/{schedule_id}/run")
    def run_testing_schedule(schedule_id: uuid.UUID) -> Dict[str, Any]:
        data = _ensure_testing_schedule(schedule_id)
        run_id = scheduler.run_testing_for_schedule(schedule_id)
        data["last_status"] = "queued"
        return {"run_id": str(run_id), "schedule": _serialize_schedule(data)}

    # ------------------------------------------------------------------
    # Ingestion endpoints
    
    def _upsert_ingestion_schedule_entry(
        dataset: str,
        mode: str,
        frequency: str,
        enabled: bool = True,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        rows = _fetchall(
            """
            SELECT schedule_id
              FROM market.ingestion_schedules
             WHERE dataset=%s AND mode=%s
            """,
            (dataset, mode),
        )
        schedule_id = rows[0]["schedule_id"] if rows else uuid.uuid4()
        sql = """
            INSERT INTO market.ingestion_schedules (
                schedule_id, dataset, mode, enabled, frequency, options, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (schedule_id)
            DO UPDATE SET enabled=EXCLUDED.enabled,
                          frequency=EXCLUDED.frequency,
                          options=EXCLUDED.options,
                          dataset=EXCLUDED.dataset,
                          mode=EXCLUDED.mode,
                          updated_at=NOW()
        """
        _execute(
            sql,
            (
                schedule_id,
                dataset,
                mode,
                enabled,
                frequency,
                _json_dump(options or {}),
            ),
        )
        return _ensure_ingestion_schedule(schedule_id)

    def _ensure_default_ingestion_schedules() -> List[Dict[str, Any]]:
        defaults = [
            ("kline_daily_qfq", "incremental", "daily", True, {}),
            ("kline_minute_raw", "incremental", "10m", True, {}),
        ]
        items: List[Dict[str, Any]] = []
        for ds, md, freq, en, opts in defaults:
            items.append(_upsert_ingestion_schedule_entry(ds, md, freq, en, opts))
        scheduler.refresh_schedules()
        return items
    @app.post("/api/ingestion/init")
    def start_ingestion_init(payload: IngestionInitRequest) -> Dict[str, Any]:
        dataset = (payload.dataset or "").strip().lower()
        if dataset not in {"kline_daily_raw", "kline_minute_raw"}:
            raise HTTPException(status_code=400, detail="unsupported dataset for init")
        options = dict(payload.options or {})
        summary = {"datasets": [dataset], **options}
        job_id = _create_init_job(summary)
        options["job_id"] = str(job_id)
        run_id = scheduler.run_ingestion_now(dataset=dataset, mode="init", triggered_by="api", options=options)
        return {"job_id": str(job_id), "run_id": str(run_id)}

    @app.get("/api/ingestion/job/{job_id}")
    def get_ingestion_job(job_id: uuid.UUID) -> Dict[str, Any]:
        return _job_status(job_id)
    
    @app.get("/api/ingestion/jobs")
    def list_ingestion_jobs(limit: int = 50, active_only: bool = False) -> Dict[str, Any]:
        base_sql = (
            "SELECT job_id, status, created_at FROM market.ingestion_jobs "
            + ("WHERE status IN ('running','queued','pending') " if active_only else "")
            + "ORDER BY created_at DESC LIMIT %s"
        )
        rows = _fetchall(base_sql, (limit,))
        items: List[Dict[str, Any]] = []
        for r in rows:
            jid = r.get("job_id")
            try:
                items.append(_job_status(uuid.UUID(str(jid))))
            except Exception:
                # skip malformed entries
                continue
        return {"items": items}
    
    @app.post("/api/ingestion/schedule/defaults")
    def create_default_ingestion_schedules() -> Dict[str, Any]:
        items = _ensure_default_ingestion_schedules()
        return {"items": [_serialize_ingestion_schedule(row) for row in items]}
    @app.post("/api/ingestion/run")
    def trigger_ingestion_run(payload: IngestionRunRequest) -> Dict[str, Any]:
        payload.validate_mode()
        summary = {"dataset": payload.dataset, "mode": payload.mode, **(payload.options or {})}
        job_type = "init" if payload.mode == "init" else "incremental"
        job_id = _create_job(job_type, summary)
        opts = dict(payload.options or {})
        opts["job_id"] = str(job_id)
        run_id = scheduler.run_ingestion_now(
            dataset=payload.dataset,
            mode=payload.mode,
            triggered_by=payload.triggered_by,
            options=opts,
        )
        return {"run_id": str(run_id), "job_id": str(job_id)}

    @app.post("/api/adjust/rebuild")
    def trigger_adjust_rebuild(payload: AdjustRebuildRequest) -> Dict[str, Any]:
        options = dict(payload.options or {})
        summary = {"dataset": "adjust_daily", "mode": "rebuild", **options}
        job_id = _create_job("init", summary)
        options["job_id"] = str(job_id)
        run_id = scheduler.run_ingestion_now(
            dataset="adjust_daily",
            mode="rebuild",
            triggered_by="api",
            options=options,
        )
        return {"run_id": str(run_id), "job_id": str(job_id)}

    @app.get("/api/ingestion/schedule")
    def list_ingestion_schedules() -> Dict[str, Any]:
        rows = _fetchall(
            """
            SELECT schedule_id, dataset, mode, enabled, frequency, options,
                   last_run_at, next_run_at, last_status, last_error,
                   created_at, updated_at
              FROM market.ingestion_schedules
             ORDER BY dataset, mode
            """
        )
        return {"items": [_serialize_ingestion_schedule(row) for row in rows]}

    @app.post("/api/ingestion/schedule")
    def upsert_ingestion_schedule(payload: IngestionScheduleUpsertRequest) -> Dict[str, Any]:
        payload.validate_mode()
        schedule_id = payload.schedule_id
        if schedule_id is None:
            # try to locate existing schedule for dataset+mode
            rows = _fetchall(
                """
                SELECT schedule_id
                  FROM market.ingestion_schedules
                 WHERE dataset=%s AND mode=%s
                """,
                (payload.dataset, payload.mode),
            )
            schedule_id = uuid.uuid4() if not rows else rows[0]["schedule_id"]
        sql = """
            INSERT INTO market.ingestion_schedules (
                schedule_id, dataset, mode, enabled, frequency, options, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (schedule_id)
            DO UPDATE SET enabled=EXCLUDED.enabled,
                          frequency=EXCLUDED.frequency,
                          options=EXCLUDED.options,
                          dataset=EXCLUDED.dataset,
                          mode=EXCLUDED.mode,
                          updated_at=NOW()
        """
        _execute(
            sql,
            (
                schedule_id,
                payload.dataset,
                payload.mode,
                payload.enabled,
                payload.frequency,
                _json_dump(payload.options),
            ),
        )
        scheduler.refresh_schedules()
        data = _ensure_ingestion_schedule(schedule_id)
        return _serialize_ingestion_schedule(data)

    @app.post("/api/ingestion/schedule/{schedule_id}/toggle")
    def toggle_ingestion_schedule(
        payload: ToggleRequest,
        schedule_id: uuid.UUID = Path(..., description="Ingestion schedule identifier"),
    ) -> Dict[str, Any]:
        _ensure_ingestion_schedule(schedule_id)
        sql = """
            UPDATE market.ingestion_schedules
               SET enabled=%s, updated_at=NOW()
             WHERE schedule_id=%s
        """
        _execute(sql, (payload.enabled, schedule_id))
        scheduler.refresh_schedules()
        data = _ensure_ingestion_schedule(schedule_id)
        return _serialize_ingestion_schedule(data)

    @app.post("/api/ingestion/schedule/{schedule_id}/run")
    def run_ingestion_schedule(schedule_id: uuid.UUID) -> Dict[str, Any]:
        data = _ensure_ingestion_schedule(schedule_id)
        run_id = scheduler.run_ingestion_for_schedule(schedule_id, data["dataset"], data["mode"])
        data["last_status"] = "queued"
        return {"run_id": str(run_id), "schedule": _serialize_ingestion_schedule(data)}

    @app.get("/api/ingestion/logs")
    def list_ingestion_logs(limit: int = 50, job_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
        if job_id is not None:
            rows = _fetchall(
                """
                SELECT job_id, ts, level, message
                  FROM market.ingestion_logs
                 WHERE job_id=%s
                 ORDER BY ts DESC
                 LIMIT %s
                """,
                (job_id, limit),
            )
        else:
            rows = _fetchall(
                """
                SELECT job_id, ts, level, message
                  FROM market.ingestion_logs
                 ORDER BY ts DESC
                 LIMIT %s
                """,
                (limit,),
            )
        return {"items": [_serialize_ingestion_log(row) for row in rows]}

    # ------------------------------------------------------------------
    # Hotboard endpoints
    class CollectorConfig(BaseModel):
        enabled: Optional[bool] = None
        frequency_seconds: Optional[int] = Field(default=None, ge=3, le=60)
        trading_windows: Optional[List[str]] = None

    @app.post("/api/hotboard/collector/config")
    def update_hotboard_config(payload: CollectorConfig) -> Dict[str, Any]:
        rows = _fetchall("SELECT id FROM market.hotboard_config WHERE id=1")
        enabled = payload.enabled
        freq = payload.frequency_seconds
        windows = payload.trading_windows
        if not rows:
            _execute(
                """
                INSERT INTO market.hotboard_config(id, enabled, frequency_seconds, trading_windows, last_run_at, updated_at)
                VALUES (1, COALESCE(%s, TRUE), COALESCE(%s, 5), COALESCE(%s, '["09:25-11:35","12:55-15:05"]'::jsonb), NULL, NOW())
                """,
                (enabled, freq, json.dumps(windows) if windows is not None else None),
            )
        else:
            # partial update
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT enabled, frequency_seconds, trading_windows FROM market.hotboard_config WHERE id=1")
                    cur_row = cur.fetchone()
                    cur_enabled, cur_freq, cur_windows = (bool(cur_row[0]), int(cur_row[1] or 5), cur_row[2])
                    new_enabled = cur_enabled if enabled is None else enabled
                    new_freq = cur_freq if freq is None else freq
                    new_windows = cur_windows if windows is None else json.dumps(windows)
                    cur.execute(
                        "UPDATE market.hotboard_config SET enabled=%s, frequency_seconds=%s, trading_windows=%s, updated_at=NOW() WHERE id=1",
                        (new_enabled, new_freq, new_windows),
                    )
        out = _fetchall("SELECT id, enabled, frequency_seconds, trading_windows, last_run_at, updated_at FROM market.hotboard_config WHERE id=1")
        return {"config": out[0] if out else {}}

    @app.post("/api/hotboard/collector/run")
    def trigger_hotboard_once() -> Dict[str, Any]:
        ts = dt.datetime.now(dt.timezone.utc)
        total = 0
        for cate, fenlei in ((0, "0"), (1, "1"), (2, "2")):
            ranks = _sina_money_rank(fenlei=fenlei, sort="netamount", page=1, num=200)
            total += _insert_sina_intraday(ranks, cate, ts)
        return {"inserted": int(total), "ts": _isoformat(ts)}

    def _latest_intraday_ts() -> Optional[dt.datetime]:
        rows = _fetchall("SELECT MAX(ts) AS ts FROM market.sina_board_intraday")
        if rows and rows[0].get("ts"):
            return rows[0]["ts"]
        return None

    def _norm(vals: List[float]) -> List[float]:
        # simple z-score with fallback to min-max
        xs = [v for v in vals if v is not None]
        if not xs:
            return [0.0 for _ in vals]
        try:
            mu = sum(xs) / len(xs)
            var = sum((v - mu) ** 2 for v in xs) / max(1, (len(xs) - 1))
            std = var ** 0.5
            if std <= 1e-9:
                mn, mx = min(xs), max(xs)
                rng = (mx - mn) or 1.0
                return [ ( (v - mn) / rng ) * 2 - 1 if v is not None else 0.0 for v in vals ]
            return [ ( (v - mu) / std ) if v is not None else 0.0 for v in vals ]
        except Exception:
            mn, mx = min(xs), max(xs)
            rng = (mx - mn) or 1.0
            return [ ( (v - mn) / rng ) * 2 - 1 if v is not None else 0.0 for v in vals ]

    @app.get("/api/hotboard/realtime")
    def hotboard_realtime(metric: str = "combo", alpha: float = 0.5, cate_type: Optional[int] = None, at: Optional[str] = None) -> Dict[str, Any]:
        t0 = time.perf_counter()
        the_ts = None
        if at:
            try:
                the_ts = dt.datetime.fromisoformat(at.replace("Z", "+00:00"))
            except Exception:
                the_ts = None
        if the_ts is None:
            the_ts = _latest_intraday_ts()
        if the_ts is None:
            t_end = time.perf_counter()
            _perf_log_hotboard("realtime", lookup_ms=round((t_end - t0) * 1000, 1), rows=0)
            return {"ts": None, "items": []}
        where = "WHERE ts=%s"
        params: List[Any] = [the_ts]
        if cate_type is not None:
            where += " AND cate_type=%s"
            params.append(int(cate_type))
        t1 = time.perf_counter()
        rows = _fetchall(
            f"""
            SELECT cate_type, board_code, board_name, pct_chg, amount, net_inflow, turnover, ratioamount
              FROM market.sina_board_intraday
              {where}
            ORDER BY cate_type ASC, board_code ASC
            """,
            tuple(params),
        )
        t2 = time.perf_counter()
        # compute visual score
        chg = [float(r.get("pct_chg") or 0.0) for r in rows]
        flow = [float(r.get("net_inflow") or 0.0) for r in rows]
        nz_chg = _norm(chg)
        nz_flow = _norm(flow)
        score = []
        m = (metric or "combo").lower()
        for i in range(len(rows)):
            if m == "chg":
                score.append(nz_chg[i])
            elif m == "flow":
                score.append(nz_flow[i])
            else:
                a = max(0.0, min(1.0, float(alpha or 0.5)))
                score.append(a * nz_chg[i] + (1 - a) * nz_flow[i])
        for i, r in enumerate(rows):
            r["score"] = score[i]
        t3 = time.perf_counter()
        _perf_log_hotboard(
            "realtime",
            lookup_ms=round((t1 - t0) * 1000, 1),
            query_ms=round((t2 - t1) * 1000, 1),
            score_ms=round((t3 - t2) * 1000, 1),
            total_ms=round((t3 - t0) * 1000, 1),
            rows=len(rows),
        )
        return {"ts": _isoformat(the_ts), "items": rows}

    @app.get("/api/hotboard/realtime/timestamps")
    def hotboard_realtime_timestamps(date: Optional[str] = None, cate_type: Optional[int] = None) -> Dict[str, Any]:
        # default to today (Shanghai)
        if not date:
            date = _now_sh().strftime("%Y-%m-%d")
        where = "WHERE ts >= %s AND ts < %s"
        d0 = dt.datetime.fromisoformat(date) if "T" not in date else dt.datetime.fromisoformat(date.split("T",1)[0])
        start = d0.replace(tzinfo=dt.timezone.utc)
        end = (d0 + dt.timedelta(days=1)).replace(tzinfo=dt.timezone.utc)
        params: List[Any] = [start, end]
        if cate_type is not None:
            where += " AND cate_type=%s"
            params.append(int(cate_type))
        rows = _fetchall(
            f"SELECT DISTINCT ts FROM market.sina_board_intraday {where} ORDER BY ts ASC",
            tuple(params),
        )
        return {"date": date, "timestamps": [_isoformat(r.get("ts")) for r in rows]}

    @app.get("/api/hotboard/daily")
    def hotboard_daily(date: str, cate_type: Optional[int] = None) -> Dict[str, Any]:
        where = "WHERE trade_date=%s"
        params: List[Any] = [date]
        if cate_type is not None:
            where += " AND cate_type=%s"
            params.append(int(cate_type))
        t0 = time.perf_counter()
        rows = _fetchall(
            f"""
            SELECT trade_date, cate_type, board_code, board_name, pct_chg, amount, net_inflow, turnover, ratioamount
              FROM market.sina_board_daily
              {where}
            ORDER BY cate_type ASC, board_code ASC
            """,
            tuple(params),
        )
        t1 = time.perf_counter()
        _perf_log_hotboard(
            "daily",
            query_ms=round((t1 - t0) * 1000, 1),
            rows=len(rows),
        )
        return {"date": date, "items": rows}

    @app.get("/api/hotboard/tdx/types")
    def tdx_board_types() -> Dict[str, Any]:
        rows = _fetchall(
            """
            SELECT DISTINCT idx_type FROM market.tdx_board_index WHERE idx_type IS NOT NULL ORDER BY idx_type
            """
        )
        types = [r.get("idx_type") for r in rows if r.get("idx_type")]
        return {"items": types}

    @app.get("/api/hotboard/tdx/daily")
    def tdx_board_daily(date: str, idx_type: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
        # Join to the latest index row per ts_code (<= date) to avoid empty results when index table lacks same-date rows
        params: List[Any] = [date, date]
        where_extra = ""
        if idx_type:
            where_extra = " AND i2.idx_type=%s"
            params.append(idx_type)
        sql = (
            """
            WITH i2 AS (
                SELECT DISTINCT ON (ts_code) ts_code, name, idx_type
                  FROM market.tdx_board_index
                 WHERE trade_date IS NULL OR trade_date <= %s
                 ORDER BY ts_code, trade_date DESC NULLS LAST
            )
            SELECT d.trade_date, d.ts_code AS board_code, i2.name AS board_name, i2.idx_type,
                   d.pct_chg, d.amount
              FROM market.tdx_board_daily d
              JOIN i2 ON i2.ts_code = d.ts_code
             WHERE d.trade_date = %s
            """ + where_extra + """
             ORDER BY i2.idx_type, d.amount DESC NULLS LAST
             LIMIT %s
            """
        )
        t0 = time.perf_counter()
        params.append(max(1, int(limit)))
        rows = _fetchall(sql, tuple(params))
        t1 = time.perf_counter()
        _perf_log_hotboard(
            "tdx_daily",
            query_ms=round((t1 - t0) * 1000, 1),
            rows=len(rows),
        )
        return {"date": date, "items": rows}

    @app.get("/api/hotboard/top-stocks/realtime")
    def top_stocks_realtime(board_code: str, metric: str = "chg", limit: int = 20) -> Dict[str, Any]:
        """Return Top-N stocks for a Sina board code, ranked by TDX realtime metrics.

        - membership: from Sina concept stocks API (Market_Center.getHQNodeData)
        - metrics: from TDX realtime (via data_source_manager)
        """
        # gather membership (up to a few pages)
        stocks: List[Dict[str, Any]] = []
        page = 1
        t0 = time.perf_counter()
        while page <= 5 and len(stocks) < max(200, limit):
            part = _sina_concept_stocks(board_code, page=page, num=200)
            if not part:
                break
            stocks.extend(part)
            if len(part) < 200:
                break
            page += 1
        t1 = time.perf_counter()
        # build TDX metrics per code
        enriched: List[Dict[str, Any]] = []
        quote_calls = 0
        for s in stocks:
            code6 = str(s.get("code") or s.get("symbol") or "").split(".")[-1]
            if not code6 or len(code6) != 6:
                continue

            # 实时行情
            try:
                q = data_source_manager.get_realtime_quotes(code6)
            except Exception:
                q = {}
            quote_calls += 1
            price = q.get("price")
            pre_close = q.get("pre_close")
            pct = None
            if isinstance(price, (int, float)) and isinstance(pre_close, (int, float)) and pre_close not in (0, None):
                try:
                    pct = (price - pre_close) / pre_close * 100.0
                except Exception:
                    pct = None
            amount = q.get("amount")

            # 名称分级：s.name / s.ts_name -> data_source_manager -> 最后才退回代码
            name = s.get("name") or s.get("ts_name")
            if not name:
                try:
                    sec = data_source_manager.get_security_name_and_type(code6)
                except Exception:
                    sec = None
                if isinstance(sec, dict) and sec.get("name"):
                    name = sec.get("name")
            if not name:
                name = code6

            enriched.append({
                "code": code6,
                "name": name,
                "pct_change": pct,
                "amount": amount,
                "open": q.get("open"),
                "prev_close": pre_close,
                "high": q.get("high"),
                "low": q.get("low"),
                "volume": q.get("volume"),
            })
        t2 = time.perf_counter()
        # rank
        m = (metric or "chg").lower()
        def _key(it: Dict[str, Any]) -> float:
            try:
                return float(it.get("pct_change") if m == "chg" else (it.get("amount") or 0.0))
            except Exception:
                return -1e18
        ranked = sorted(enriched, key=_key, reverse=True)[: max(1, int(limit))]
        t3 = time.perf_counter()
        _perf_log_hotboard(
            "top_realtime",
            sina_ms=round((t1 - t0) * 1000, 1),
            quotes_ms=round((t2 - t1) * 1000, 1),
            rank_ms=round((t3 - t2) * 1000, 1),
            total_ms=round((t3 - t0) * 1000, 1),
            stocks=len(stocks),
            quote_calls=quote_calls,
            returned=len(ranked),
        )
        return {"items": ranked}

    @app.get("/api/hotboard/top-stocks/tdx")
    def top_stocks_tdx(board_code: str, date: str, metric: str = "chg", limit: int = 20) -> Dict[str, Any]:
        # membership on the date
        t0 = time.perf_counter()
        mem = _fetchall(
            """
            SELECT con_code FROM market.tdx_board_member
             WHERE trade_date=%s AND ts_code=%s
            """,
            (date, board_code),
        )
        codes = [r.get("con_code") for r in mem if r.get("con_code")]
        if not codes:
            t_end = time.perf_counter()
            _perf_log_hotboard(
                "top_tdx",
                membership_ms=round((t_end - t0) * 1000, 1),
                codes=0,
                rows=0,
            )
            return {"items": []}
        # join daily kline for the date (use qfq as reference)
        # compute intraday change using open/close when pre_close unavailable
        where_codes = tuple(codes)
        sql = f"""
            SELECT k.ts_code, k.open_li, k.close_li, k.high_li, k.low_li, k.volume_hand, k.amount_li
              FROM market.kline_daily_qfq k
             WHERE k.trade_date=%s AND k.ts_code = ANY(%s)
        """
        rows = []
        t1 = time.perf_counter()
        with get_conn() as conn:
            with conn.cursor(cursor_factory=pgx.RealDictCursor) as cur:
                cur.execute(sql, (date, where_codes))
                rows = [dict(r) for r in cur.fetchall()]
        t2 = time.perf_counter()
        items: List[Dict[str, Any]] = []
        for r in rows:
            try:
                open_li = float(r.get("open_li") or 0.0)
                close_li = float(r.get("close_li") or 0.0)
                pct = ((close_li - open_li) / open_li * 100.0) if open_li else None
                amt = float(r.get("amount_li") or 0.0)
                items.append({
                    "ts_code": r.get("ts_code"),
                    "pct_chg": pct,
                    "amount": amt,
                    "open_li": open_li,
                    "close_li": close_li,
                    "high_li": float(r.get("high_li") or 0.0),
                    "low_li": float(r.get("low_li") or 0.0),
                    "volume_hand": float(r.get("volume_hand") or 0.0),
                })
            except Exception:
                continue
        key = (lambda x: (x.get("pct_chg") or -1e9)) if metric == "chg" else (lambda x: (x.get("amount") or 0.0))
        items = sorted(items, key=key, reverse=True)[: max(1, int(limit))]
        t3 = time.perf_counter()
        _perf_log_hotboard(
            "top_tdx",
            membership_ms=round((t1 - t0) * 1000, 1),
            query_ms=round((t2 - t1) * 1000, 1),
            score_ms=round((t3 - t2) * 1000, 1),
            total_ms=round((t3 - t0) * 1000, 1),
            codes=len(codes),
            rows=len(rows),
            returned=len(items),
        )
        return {"date": date, "board_code": board_code, "items": items}

    # ------------------------------------------------------------------
    # Trading calendar endpoints (Tushare trade_cal)
    class CalendarSyncRequest(BaseModel):
        start_date: str
        end_date: str
        exchange: str = "SSE"

    @app.post("/api/calendar/sync")
    def calendar_sync(
        payload: Optional[CalendarSyncRequest] = Body(default=None),
        start_date: Optional[str] = Query(default=None),
        end_date: Optional[str] = Query(default=None),
        exchange: str = Query(default="SSE"),
    ) -> Dict[str, Any]:
        try:
            import importlib
            token = os.getenv("TUSHARE_TOKEN")
            if not token:
                raise RuntimeError("TUSHARE_TOKEN not set")
            ts = importlib.import_module("tushare")
            pro = ts.pro_api(token)
            # allow both JSON body and query parameters
            if payload is None:
                if not start_date or not end_date:
                    raise HTTPException(status_code=400, detail="start_date and end_date are required")
                payload = CalendarSyncRequest(
                    start_date=start_date,
                    end_date=end_date,
                    exchange=exchange or "SSE",
                )
            df = pro.trade_cal(
                exchange=payload.exchange,
                start_date=payload.start_date.replace("-", ""),
                end_date=payload.end_date.replace("-", ""),
            )
            rows: List[tuple] = []
            if df is not None and not df.empty:
                for _, r in df.iterrows():
                    d = str(r.get("cal_date"))
                    if len(d) == 8:
                        d = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
                    is_open = bool(int(r.get("is_open") or 0))
                    rows.append((d, is_open))
            if rows:
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        pgx.execute_values(
                            cur,
                            "INSERT INTO market.trading_calendar(cal_date, is_trading) VALUES %s ON CONFLICT (cal_date) DO UPDATE SET is_trading=EXCLUDED.is_trading",
                            rows,
                        )
            return {"inserted_or_updated": len(rows)}
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=str(exc))

    return app


app = get_app()
