"""临时调试脚本：
1. 测试本地 TDX API 是否正常返回数据；
2. 检查最近一次 kline_daily_raw 初始化作业的状态和数据量；
3. 检查分钟线原始表的当前行数。

不会修改任何业务数据，只做 SELECT 查询。
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

import psycopg2
import psycopg2.extras as pgx
import requests
from dotenv import load_dotenv


def test_tdx_api() -> None:
    load_dotenv()
    base = os.getenv("TDX_API_BASE", "http://localhost:8080").rstrip("/")
    print(f"TDX_API_BASE = {base}")

    def _test(path: str, params: Dict[str, Any] | None = None) -> None:
        url = base + path
        print("\n=== GET", url, "params=", params, "===")
        try:
            resp = requests.get(url, params=params, timeout=10)
            print("status_code:", resp.status_code)
            text = resp.text
            print("body_head:", text[:400].replace("\n", " "))
        except Exception as exc:  # noqa: BLE001
            print("ERROR:", exc)

    _test("/api/codes", {"exchange": "sh"})
    _test("/api/kline-all/tdx", {"code": "600000"})


def debug_ingestion_job(job_id: str) -> None:
    load_dotenv()
    db_cfg = dict(
        host=os.getenv("TDX_DB_HOST", "localhost"),
        port=int(os.getenv("TDX_DB_PORT", "5432")),
        user=os.getenv("TDX_DB_USER", "postgres"),
        password=os.getenv("TDX_DB_PASSWORD", ""),
        dbname=os.getenv("TDX_DB_NAME", "aistock"),
    )
    print("\nDB config (masked):", {k: ("***" if k == "password" and v else v) for k, v in db_cfg.items()})

    conn = psycopg2.connect(**db_cfg)
    conn.autocommit = True
    try:
        cur = conn.cursor(cursor_factory=pgx.RealDictCursor)

        print("\n== ingestion_jobs for job_id ==")
        cur.execute(
            """SELECT job_id, job_type, status, created_at, started_at, finished_at, summary
                   FROM market.ingestion_jobs
                  WHERE job_id=%s""",
            (job_id,),
        )
        rows = cur.fetchall()
        for r in rows:
            print(json.dumps({k: str(v) for k, v in r.items()}, ensure_ascii=False))

        print("\n== ingestion_job_tasks status counts ==")
        cur.execute(
            """SELECT status, COUNT(*) AS cnt
                   FROM market.ingestion_job_tasks
                  WHERE job_id=%s
                  GROUP BY status""",
            (job_id,),
        )
        rows = cur.fetchall()
        for r in rows:
            print(json.dumps({k: str(v) for k, v in r.items()}, ensure_ascii=False))

        print("\n== kline_daily_raw rows in range 2025-11-01..2025-11-15 ==")
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM market.kline_daily_raw WHERE trade_date BETWEEN %s AND %s",
            ("2025-11-01", "2025-11-15"),
        )
        print(cur.fetchone())

        print("\n== kline_minute_raw total rows ==")
        cur.execute("SELECT COUNT(*) AS cnt FROM market.kline_minute_raw")
        print(cur.fetchone())

        cur.close()
    finally:
        conn.close()


def main() -> None:
    # 当前这次 kline_daily_raw init 的 job_id（来自你的日志）
    job_id = "d186e097-4bde-4e2a-ad79-e7734a971158"
    print("==== 1) 测试 TDX API ====")
    test_tdx_api()
    print("\n==== 2) 调试 ingestion_jobs / tasks / 数据行数 ====")
    debug_ingestion_job(job_id)


if __name__ == "__main__":
    main()
