"""调试 ingestion 相关 SQL：

只做三件事：
1. 查看指定 job_id 在 ingestion_jobs 中的状态和 summary；
2. 统计该 job 的 ingestion_job_tasks 各状态数量；
3. 统计给定日期范围内 kline_daily_raw 的行数。

不会修改任何数据。
"""
from __future__ import annotations

import argparse
import json
from typing import Any, Dict

import psycopg2
import psycopg2.extras as pgx
from dotenv import load_dotenv

from cleanup_ingestion_meta import _int_from_env, _str_from_env


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Debug ingestion job/logs/errors")
    parser.add_argument("--job-id", required=True, help="Target ingestion_jobs.job_id")
    parser.add_argument("--date-from", default="2025-11-01", help="Date-from for kline_daily_raw stats (YYYY-MM-DD)")
    parser.add_argument("--date-to", default="2025-11-15", help="Date-to for kline_daily_raw stats (YYYY-MM-DD)")
    parser.add_argument("--log-limit", type=int, default=50, help="Max number of ingestion_logs rows to print")
    args = parser.parse_args()

    db_cfg: Dict[str, Any] = {
        "host": _str_from_env("TDX_DB_HOST", "localhost"),
        "port": _int_from_env("TDX_DB_PORT", 5432),
        "user": _str_from_env("TDX_DB_USER", "postgres"),
        "password": _str_from_env("TDX_DB_PASSWORD", ""),
        "dbname": _str_from_env("TDX_DB_NAME", "aistock"),
    }
    print("DB config (masked):", {k: ("***" if k == "password" and v else v) for k, v in db_cfg.items()})

    job_id = args.job_id

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

        # 最近日志
        print("\n== ingestion_logs (recent) ==")
        cur.execute(
            """SELECT ts, level, message
                   FROM market.ingestion_logs
                  WHERE job_id=%s
               ORDER BY ts DESC
                  LIMIT %s""",
            (job_id, args.log_limit),
        )
        rows = cur.fetchall()
        for r in rows:
            print(json.dumps({k: str(v) for k, v in r.items()}, ensure_ascii=False))

        # 找到与该 job 相关的 run（增量脚本会把 job_id 写入 params.job_id）
        print("\n== ingestion_runs (by params->>job_id) ==")
        cur.execute(
            """SELECT run_id, dataset, status, created_at, finished_at, params
                   FROM market.ingestion_runs
                  WHERE params->>'job_id' = %s
               ORDER BY created_at DESC
                  LIMIT 3""",
            (str(job_id),),
        )
        run_rows = cur.fetchall()
        for r in run_rows:
            print(json.dumps({k: str(v) for k, v in r.items()}, ensure_ascii=False))

        # 对每个 run 打印错误样本
        for r in run_rows:
            run_id = r["run_id"]
            print(f"\n== ingestion_errors for run {run_id} ==")
            cur.execute(
                """SELECT dataset, ts_code, message, detail
                       FROM market.ingestion_errors
                      WHERE run_id=%s
                   ORDER BY ts_code NULLS LAST
                      LIMIT 50""",
                (run_id,),
            )
            err_rows = cur.fetchall()
            for er in err_rows:
                print(json.dumps({k: str(v) for k, v in er.items()}, ensure_ascii=False))

        print(f"\n== kline_daily_raw rows in {args.date_from}..{args.date_to} ==")
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM market.kline_daily_raw WHERE trade_date BETWEEN %s AND %s",
            (args.date_from, args.date_to),
        )
        print(cur.fetchone())

        cur.close()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
