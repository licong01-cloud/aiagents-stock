"""Display ingestion run statuses, checkpoints, and recent errors."""
from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras as pgx

pgx.register_uuid()

DB_CFG = dict(
    host=os.getenv("TDX_DB_HOST", "localhost"),
    port=int(os.getenv("TDX_DB_PORT", "5432")),
    user=os.getenv("TDX_DB_USER", "postgres"),
    password=os.getenv("TDX_DB_PASSWORD", ""),
    dbname=os.getenv("TDX_DB_NAME", "aistock"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show ingestion status")
    parser.add_argument("--dataset", type=str, default=None, help="Filter by dataset name")
    parser.add_argument("--limit", type=int, default=10, help="Number of runs to display")
    parser.add_argument("--show-checkpoints", action="store_true", help="Show checkpoints for displayed runs")
    parser.add_argument("--show-errors", action="store_true", help="Show recent errors for displayed runs")
    parser.add_argument("--show-jobs", action="store_true", help="Also display recent ingestion jobs and tasks")
    return parser.parse_args()


def fetch_runs(conn, dataset: Optional[str], limit: int) -> List[Dict[str, Any]]:
    query = """
        SELECT run_id, dataset, mode, status, created_at, started_at, finished_at, params, summary
          FROM market.ingestion_runs
         {where}
         ORDER BY created_at DESC
         LIMIT %s
    """
    where_clause = ""
    params: List[Any] = []
    if dataset:
        where_clause = "WHERE dataset = %s"
        params.append(dataset)
    sql = query.format(where=where_clause)
    params.append(limit)
    with conn.cursor() as cur:
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
    result = []
    for row in rows:
        run = dict(
            run_id=row[0],
            dataset=row[1],
            mode=row[2],
            status=row[3],
            created_at=row[4],
            started_at=row[5],
            finished_at=row[6],
            params=row[7],
            summary=row[8],
        )
        result.append(run)
    return result


def fetch_jobs(conn, limit: int = 10) -> List[Dict[str, Any]]:
    query = """
        SELECT job_id, job_type, status, created_at, started_at, finished_at, summary
          FROM market.ingestion_jobs
         ORDER BY created_at DESC
         LIMIT %s
    """
    with conn.cursor() as cur:
        cur.execute(query, (limit,))
        rows = cur.fetchall()
    jobs: List[Dict[str, Any]] = []
    for row in rows:
        jobs.append(
            dict(
                job_id=row[0],
                job_type=row[1],
                status=row[2],
                created_at=row[3],
                started_at=row[4],
                finished_at=row[5],
                summary=row[6],
            )
        )
    return jobs


def fetch_job_tasks(conn, job_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    if not job_ids:
        return {}
    query = """
        SELECT job_id, task_id, dataset, ts_code, date_from, date_to, status, progress, retries, last_error, updated_at
          FROM market.ingestion_job_tasks
         WHERE job_id = ANY(%s)
         ORDER BY created_at DESC
    """
    with conn.cursor() as cur:
        cur.execute(query, (job_ids,))
        rows = cur.fetchall()
    result: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        job_id = str(row[0])
        result.setdefault(job_id, []).append(
            dict(
                task_id=row[1],
                dataset=row[2],
                ts_code=row[3],
                date_from=row[4],
                date_to=row[5],
                status=row[6],
                progress=row[7],
                retries=row[8],
                last_error=row[9],
                updated_at=row[10],
            )
        )
    return result


def fetch_checkpoints(conn, run_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    if not run_ids:
        return {}
    query = """
        SELECT run_id, dataset, ts_code, cursor_date, cursor_time, extra
          FROM market.ingestion_checkpoints
         WHERE run_id = ANY(%s)
         ORDER BY run_id, dataset, ts_code
    """
    with conn.cursor() as cur:
        cur.execute(query, (run_ids,))
        rows = cur.fetchall()
    result: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        run_id = str(row[0])
        result.setdefault(run_id, []).append(
            dict(
                dataset=row[1],
                ts_code=row[2],
                cursor_date=row[3],
                cursor_time=row[4],
                extra=row[5],
            )
        )
    return result


def fetch_errors(conn, run_ids: List[str], limit: int = 50) -> Dict[str, List[Dict[str, Any]]]:
    if not run_ids:
        return {}
    query = """
        SELECT run_id, dataset, ts_code, error_at, message, detail
          FROM market.ingestion_errors
         WHERE run_id = ANY(%s)
         ORDER BY error_at DESC
         LIMIT %s
    """
    with conn.cursor() as cur:
        cur.execute(query, (run_ids, limit))
        rows = cur.fetchall()
    result: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        run_id = str(row[0])
        result.setdefault(run_id, []).append(
            dict(
                dataset=row[1],
                ts_code=row[2],
                error_at=row[3],
                message=row[4],
                detail=row[5],
            )
        )
    return result


def fmt_json(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def main() -> None:
    args = parse_args()
    with psycopg2.connect(**DB_CFG) as conn:
        conn.autocommit = True
        runs = fetch_runs(conn, args.dataset, args.limit)
        if not runs:
            print("No ingestion runs found.")
            return
        run_ids = [run["run_id"] for run in runs]
        checkpoints = fetch_checkpoints(conn, run_ids) if args.show_checkpoints else {}
        errors = fetch_errors(conn, run_ids) if args.show_errors else {}

        for run in runs:
            run_id_str = str(run["run_id"])
            print("=" * 80)
            print(f"run_id={run_id_str} dataset={run['dataset']} mode={run['mode']} status={run['status']}")
            print(f"created_at={run['created_at']} started_at={run['started_at']} finished_at={run['finished_at']}")
            print(f"params={fmt_json(run['params'])}")
            print(f"summary={fmt_json(run['summary'])}")
            if args.show_checkpoints and run_id_str in checkpoints:
                print("-- checkpoints --")
                for ckpt in checkpoints[run_id_str]:
                    print(
                        f"  dataset={ckpt['dataset']} ts_code={ckpt['ts_code']} cursor_date={ckpt['cursor_date']} "
                        f"cursor_time={ckpt['cursor_time']} extra={fmt_json(ckpt['extra'])}"
                    )
            if args.show_errors and run_id_str in errors:
                print("-- errors --")
                for err in errors[run_id_str]:
                    print(
                        f"  {err['error_at']} dataset={err['dataset']} ts_code={err['ts_code']} "
                        f"message={err['message']} detail={fmt_json(err['detail'])}"
                    )
        print("=" * 80)


if __name__ == "__main__":
    main()
