import argparse
import os
import sqlite3
import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Tuple

from dotenv import load_dotenv
import psycopg2
import psycopg2.extras as pg_extras

load_dotenv(override=True)


def _pg_conn_params() -> Dict[str, Any]:
    return {
        "host": os.getenv("TDX_DB_HOST", "localhost"),
        "port": int(os.getenv("TDX_DB_PORT", "5432")),
        "dbname": os.getenv("TDX_DB_NAME", "aistock"),
        "user": os.getenv("TDX_DB_USER", "postgres"),
        "password": os.getenv("TDX_DB_PASSWORD", "lc78080808"),
    }


def _count_sqlite(sqlite_path: str) -> int:
    if not os.path.exists(sqlite_path):
        return 0
    conn = sqlite3.connect(sqlite_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM analysis_records")
        return int(cur.fetchone()[0])
    finally:
        conn.close()


def _count_pg() -> int:
    with psycopg2.connect(**_pg_conn_params()) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM app.analysis_records")
            return int(cur.fetchone()[0])


def _iter_sqlite_rows(sqlite_path: str, batch_size: int) -> Iterable[List[Tuple[Any, ...]]]:
    conn = sqlite3.connect(sqlite_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, symbol, stock_name, analysis_date, period, stock_info, agents_results, discussion_result, final_decision, created_at FROM analysis_records ORDER BY id ASC"
        )
        while True:
            rows = cur.fetchmany(batch_size)
            if not rows:
                break
            yield rows
    finally:
        conn.close()


def _parse_dt(s: str) -> datetime:
    if not s:
        return datetime.now(timezone.utc)
    # try isoformat first
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    # fallback: 'YYYY-MM-DD HH:MM:SS'
    try:
        dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _to_json(val: Any) -> Any:
    if val is None or val == "":
        return None
    if isinstance(val, (dict, list)):
        return val
    try:
        return json.loads(val)
    except Exception:
        return None


def migrate(sqlite_path: str, batch_size: int, truncate_first: bool = False) -> None:
    params = _pg_conn_params()
    with psycopg2.connect(**params) as conn:
        with conn.cursor() as cur:
            if truncate_first:
                cur.execute("TRUNCATE TABLE app.analysis_records")
        conn.commit()

    total = 0
    for rows in _iter_sqlite_rows(sqlite_path, batch_size):
        total += len(rows)
        values = []
        for r in rows:
            # r indices map to sqlite columns per SELECT order
            symbol = r[1]
            stock_name = r[2]
            analysis_date = _parse_dt(r[3])
            period = r[4]
            stock_info = _to_json(r[5])
            agents_results = _to_json(r[6])
            discussion_result = _to_json(r[7])
            final_decision = _to_json(r[8])
            created_at = _parse_dt(r[9]) if r[9] else datetime.now(timezone.utc)
            values.append(
                (
                    symbol,
                    stock_name,
                    period,
                    analysis_date,
                    pg_extras.Json(stock_info) if stock_info is not None else None,
                    pg_extras.Json(agents_results) if agents_results is not None else None,
                    pg_extras.Json(discussion_result) if discussion_result is not None else None,
                    pg_extras.Json(final_decision) if final_decision is not None else None,
                    created_at,
                )
            )
        with psycopg2.connect(**params) as conn:
            with conn.cursor() as cur:
                pg_extras.execute_values(
                    cur,
                    "INSERT INTO app.analysis_records (ts_code, stock_name, period, analysis_date, stock_info, agents_results, discussion_result, final_decision, created_at) VALUES %s",
                    values,
                    page_size=batch_size,
                )
            conn.commit()
        print(f"migrated {total} rows...")


def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite analysis_records to TimescaleDB app.analysis_records")
    parser.add_argument("--sqlite", default="stock_analysis.db", help="Path to SQLite file (default: stock_analysis.db)")
    parser.add_argument("--batch-size", type=int, default=1000, help="Batch size for migration")
    parser.add_argument("--truncate-first", action="store_true", help="Truncate destination table before migrating (DANGEROUS)")
    parser.add_argument("--dry-run", action="store_true", help="Only print counts and exit")
    args = parser.parse_args()

    src_count = _count_sqlite(args.sqlite)
    dst_count = _count_pg()
    print(f"SQLite count: {src_count}")
    print(f"TimescaleDB count: {dst_count}")

    if args.dry_run:
        print("Dry run: no data migrated.")
        return

    if src_count == 0:
        print("No source rows to migrate. Exiting.")
        return

    migrate(args.sqlite, args.batch_size, truncate_first=args.truncate_first)
    print("Done.")


if __name__ == "__main__":
    main()
