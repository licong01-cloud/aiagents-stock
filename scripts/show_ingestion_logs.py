"""Print recent entries from market.ingestion_logs."""
from __future__ import annotations

import argparse
import os
from typing import Any

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
    parser = argparse.ArgumentParser(description="Show recent ingestion logs")
    parser.add_argument("--limit", type=int, default=20, help="Number of log rows to display")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with psycopg2.connect(**DB_CFG) as conn:
        conn.autocommit = True
        with conn.cursor(cursor_factory=pgx.DictCursor) as cur:
            cur.execute(
                """
                SELECT job_id, ts, level, message
                  FROM market.ingestion_logs
                 ORDER BY ts DESC
                 LIMIT %s
                """,
                (args.limit,),
            )
            rows = cur.fetchall()
    if not rows:
        print("No logs found.")
        return
    for row in rows:
        job_id = row["job_id"]
        ts = row["ts"]
        level = row["level"]
        message = row["message"]
        print(f"{ts} {level:<5} job={job_id} {message}")


if __name__ == "__main__":
    main()
