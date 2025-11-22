"""列出最近一次 kline_minute_raw init 任务中失败的代码和错误原因。

逻辑：
1. 找出 ingestion_jobs 中最近一条 dataset='kline_minute_raw', mode='init' 的 job；
2. 通过 ingestion_runs 找到该 job 下所有 run_id；
3. 在 ingestion_errors 中筛选这些 run_id，对应 dataset='kline_minute_raw' 的错误；
4. 打印 ts_code、错误信息和 detail（包含日期等）。

只读查询，不修改任何数据。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

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

    conn = psycopg2.connect(**db_cfg)
    conn.autocommit = True
    try:
        cur = conn.cursor(cursor_factory=pgx.RealDictCursor)

        # 1) 找最近一次 kline_minute_raw init 的 job
        print("\n== latest kline_minute_raw init job ==")
        cur.execute(
            """
            SELECT job_id, job_type, status, created_at, started_at, finished_at, summary
              FROM market.ingestion_jobs
             WHERE (summary->>'dataset' = 'kline_minute_raw'
                 OR job_type = 'init')
             ORDER BY created_at DESC
             LIMIT 5
            """
        )
        jobs: List[Dict[str, Any]] = cur.fetchall()
        if not jobs:
            print("(no ingestion_jobs found for kline_minute_raw)")
            return
        # 选择第一条作为最近一次（你也可以根据需要手动挑）
        job = jobs[0]
        job_id = str(job["job_id"])
        print(json.dumps({k: str(v) for k, v in job.items()}, ensure_ascii=False))

        # 2) 找出该 job 对应的 run_id 列表
        print("\n== ingestion_runs for this job ==")
        cur.execute(
            """
            SELECT run_id, dataset, status, created_at, started_at, finished_at, params
              FROM market.ingestion_runs
             WHERE params->>'job_id' = %s
             ORDER BY created_at
            """,
            (job_id,),
        )
        runs: List[Dict[str, Any]] = cur.fetchall()
        if not runs:
            print("(no ingestion_runs for this job)")
            return
        for r in runs:
            print(json.dumps({k: str(v) for k, v in r.items()}, ensure_ascii=False))
        run_ids = [str(r["run_id"]) for r in runs]

        # 3) 列出这些 run_id 在 ingestion_errors 中的错误（仅 kline_minute_raw）
        print("\n== ingestion_errors for this job (kline_minute_raw) ==")
        cur.execute(
            """
            SELECT e.run_id,
                   e.ts_code,
                   e.message,
                   e.detail
              FROM market.ingestion_errors e
              JOIN market.ingestion_runs r ON r.run_id = e.run_id
             WHERE r.params->>'job_id' = %s
               AND r.dataset = 'kline_minute_raw'
             ORDER BY e.run_id, e.ts_code
            """,
            (job_id,),
        )
        rows = cur.fetchall()
        if not rows:
            print("(no errors for this job)")
        else:
            for r in rows:
                out = {
                    "run_id": str(r.get("run_id")),
                    "ts_code": r.get("ts_code"),
                    "message": r.get("message"),
                    "detail": r.get("detail"),
                }
                print(json.dumps(out, ensure_ascii=False))

        cur.close()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
