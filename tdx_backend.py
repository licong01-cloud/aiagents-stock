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

import psycopg2
import psycopg2.extras as pgx
from fastapi import FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from tdx_scheduler import DEFAULT_DB_CFG, scheduler

pgx.register_uuid()

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


def get_app() -> FastAPI:
    app = FastAPI(title=API_TITLE, version=API_VERSION)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def _startup() -> None:  # noqa: D401
        """Start the background scheduler on service boot."""
        scheduler.start()

    @app.on_event("shutdown")
    def _shutdown() -> None:  # noqa: D401
        """Stop the background scheduler."""
        scheduler.shutdown(wait=False)

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
    @app.post("/api/ingestion/run")
    def trigger_ingestion_run(payload: IngestionRunRequest) -> Dict[str, Any]:
        payload.validate_mode()
        run_id = scheduler.run_ingestion_now(
            dataset=payload.dataset,
            mode=payload.mode,
            triggered_by=payload.triggered_by,
            options=payload.options,
        )
        return {"run_id": str(run_id)}

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
    def list_ingestion_logs(limit: int = 50) -> Dict[str, Any]:
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

    return app


app = get_app()
