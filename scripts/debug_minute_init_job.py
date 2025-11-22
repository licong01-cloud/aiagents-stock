"""调试当前 kline_minute_raw init 任务的状态。

只读以下内容：
1. ingestion_jobs 中该 job 的状态和 summary；
2. ingestion_job_tasks 中该 job 的任务状态分布；
3. kline_minute_raw 在指定日期范围内的行数。

不会修改任何业务数据。
"""
from __future__ import annotations

import json
from typing import Any, Dict

import psycopg2
import psycopg2.extras as pgx
from dotenv import load_dotenv

from cleanup_ingestion_meta import _int_from_env, _str_from_env


def main() -> None:
    load_dotenv()

    db_cfg: Dict[str, Any] = {
        "host": _str_from_env("TDX_DB_HOST", "localhost"),
        "port": _int_from_env("TDX_DB_PORT", 5432),
        "user": _str_from_env("TDX_DB_USER", "postgres"),
        "password": _str_from_env("TDX_DB_PASSWORD", ""),
        "dbname": _str_from_env("TDX_DB_NAME", "aistock"),
    }
    print("DB config (masked):", {k: ("***" if k == "password" and v else v) for k, v in db_cfg.items()})

    # 当前这次 kline_minute_raw init 的 job_id（来自你刚刚的日志）
    job_id = "d1984907-9992-4fc5-ab0c-12ac8a065272"

    conn = psycopg2.connect(**db_cfg)
    conn.autocommit = True
    try:
        cur = conn.cursor(cursor_factory=pgx.RealDictCursor)

        print("\n== ingestion_jobs ==")
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

        print("\n== kline_minute_raw rows in 2025-11-03..2025-11-15 ==")
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM market.kline_minute_raw WHERE trade_time::date BETWEEN %s AND %s",
            ("2025-11-03", "2025-11-15"),
        )
        print(cur.fetchone())

        cur.close()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
