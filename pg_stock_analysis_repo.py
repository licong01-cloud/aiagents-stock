import os
import json
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
import psycopg2
import psycopg2.extras as pg_extras

from app_pg import get_conn

load_dotenv(override=True)


class PgStockAnalysisRepository:
    def _sanitize_json(self, obj: Any) -> Any:
        try:
            import numpy as np  # type: ignore
            np_available = True
        except Exception:
            np_available = False

        if isinstance(obj, dict):
            return {k: self._sanitize_json(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            t = [self._sanitize_json(v) for v in obj]
            return type(obj)(t) if isinstance(obj, tuple) else t
        # numpy scalars
        if np_available:
            import numpy as np  # type: ignore
            if isinstance(obj, np.floating):
                if np.isnan(obj) or np.isinf(obj):
                    return None
                return float(obj)
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.bool_):
                return bool(obj)
        # python floats
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        return obj

    def _safe_dumps(self, payload: Any) -> str:
        cleaned = self._sanitize_json(payload)
        # allow_nan=False ensures不产生 NaN/Infinity JSON
        return json.dumps(cleaned, ensure_ascii=False, allow_nan=False, default=str)

    def save_analysis(self, symbol: str, stock_name: str, period: str, stock_info: Dict[str, Any],
                      agents_results: Dict[str, Any], discussion_result: Dict[str, Any],
                      final_decision: Dict[str, Any]) -> int:
        analysis_dt = datetime.now(timezone.utc)
        sql = (
            "INSERT INTO app.analysis_records (ts_code, stock_name, period, analysis_date, "
            "stock_info, agents_results, discussion_result, final_decision) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id"
        )
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        symbol,
                        stock_name,
                        period,
                        analysis_dt,
                        pg_extras.Json(stock_info, dumps=self._safe_dumps),
                        pg_extras.Json(agents_results, dumps=self._safe_dumps),
                        pg_extras.Json(discussion_result, dumps=self._safe_dumps),
                        pg_extras.Json(final_decision, dumps=self._safe_dumps),
                    ),
                )
                rid = cur.fetchone()[0]
                return rid

    def get_all_records(self) -> List[Dict[str, Any]]:
        sql = (
            "SELECT id, ts_code, stock_name, analysis_date, period, final_decision, created_at "
            "FROM app.analysis_records ORDER BY created_at DESC"
        )
        out: List[Dict[str, Any]] = []
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                for r in cur.fetchall():
                    fid = r[0]
                    symbol = r[1] or ""
                    stock_name = r[2] or ""
                    analysis_date = r[3]
                    period = r[4] or ""
                    final_decision = r[5]
                    created_at = r[6]
                    rating = "未知"
                    if isinstance(final_decision, dict):
                        rating = final_decision.get("rating", "未知")
                    out.append(
                        {
                            "id": fid,
                            "symbol": symbol,
                            "stock_name": stock_name,
                            "analysis_date": analysis_date.isoformat() if analysis_date else None,
                            "period": period,
                            "rating": rating,
                            "created_at": created_at.isoformat() if created_at else None,
                        }
                    )
        return out

    def get_record_count(self) -> int:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM app.analysis_records")
                return int(cur.fetchone()[0])

    def get_record_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        sql = "SELECT id, ts_code, stock_name, analysis_date, period, stock_info, agents_results, discussion_result, final_decision, created_at FROM app.analysis_records WHERE id = %s ORDER BY created_at DESC LIMIT 1"
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (record_id,))
                r = cur.fetchone()
                if not r:
                    return None
                return {
                    "id": r[0],
                    "symbol": r[1],
                    "stock_name": r[2],
                    "analysis_date": r[3].isoformat() if r[3] else None,
                    "period": r[4],
                    "stock_info": r[5] if isinstance(r[5], dict) else {},
                    "agents_results": r[6] if isinstance(r[6], dict) else {},
                    "discussion_result": r[7] if isinstance(r[7], dict) else {},
                    "final_decision": r[8] if isinstance(r[8], dict) else {},
                    "created_at": r[9].isoformat() if r[9] else None,
                }

    def delete_record(self, record_id: int) -> bool:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM app.analysis_records WHERE id = %s", (record_id,))
                return cur.rowcount > 0


# global instance compatible with existing import name

db = PgStockAnalysisRepository()
