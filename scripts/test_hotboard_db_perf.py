from __future__ import annotations

"""Measure DB performance for Hotboard-related queries.

This script focuses on three things:
- PostgreSQL connection creation time
- Realtime hotboard snapshot query (market.sina_board_intraday)
- TDX daily hotboard snapshot query (market.tdx_board_daily + tdx_board_index)

Run from project root:

    python scripts/test_hotboard_db_perf.py

It uses the same DB config as tdx_scheduler / tdx_backend (TDX_DB_* env vars
with DEFAULT_DB_CFG fallback).
"""

import os
import sys
import time
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List

import psycopg2

# Ensure project root (parent of scripts/) is on sys.path so we can import tdx_scheduler
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tdx_scheduler import DEFAULT_DB_CFG


def build_db_cfg() -> Dict[str, Any]:
    """Build DB config using TDX_DB_* env or DEFAULT_DB_CFG."""
    return {
        "host": os.getenv("TDX_DB_HOST", DEFAULT_DB_CFG["host"]),
        "port": int(os.getenv("TDX_DB_PORT", str(DEFAULT_DB_CFG["port"]))),
        "user": os.getenv("TDX_DB_USER", DEFAULT_DB_CFG["user"]),
        "password": os.getenv("TDX_DB_PASSWORD", DEFAULT_DB_CFG["password"]),
        "dbname": os.getenv("TDX_DB_NAME", DEFAULT_DB_CFG["dbname"]),
    }


def _print_stats(label: str, samples: List[float]) -> None:
    if not samples:
        print(f"[{label}] no samples")
        return
    ms = [s * 1000 for s in samples]
    print(
        f"[{label}] runs={len(samples)} "
        f"min={min(ms):.1f} ms avg={mean(ms):.1f} ms max={max(ms):.1f} ms"
    )


def measure_connection_only(cfg: Dict[str, Any], runs: int = 10) -> None:
    """Measure pure connection creation+close cost."""
    samples: List[float] = []
    for _ in range(runs):
        t0 = time.perf_counter()
        conn = psycopg2.connect(**cfg)
        t1 = time.perf_counter()
        conn.close()
        t2 = time.perf_counter()
        samples.append(t1 - t0)  # focus on connect cost
    _print_stats("connect_only", samples)


def measure_hotboard_intraday(cfg: Dict[str, Any], runs: int = 5) -> None:
    """Measure realtime hotboard snapshot query performance.

    Mirrors the core SQL of /api/hotboard/realtime:
    - SELECT latest ts from market.sina_board_intraday
    - SELECT all rows for that ts
    """
    connect_times: List[float] = []
    exec_times: List[float] = []
    fetch_times: List[float] = []
    row_counts: List[int] = []

    for _ in range(runs):
        t0 = time.perf_counter()
        conn = psycopg2.connect(**cfg)
        t1 = time.perf_counter()
        with conn.cursor() as cur:
            # Build single query that uses latest ts
            sql = (
                "SELECT cate_type, board_code, board_name, pct_chg, amount, net_inflow, "
                "turnover, ratioamount "
                "FROM market.sina_board_intraday "
                "WHERE ts = (SELECT MAX(ts) FROM market.sina_board_intraday) "
                "ORDER BY cate_type ASC, board_code ASC"
            )
            t2 = time.perf_counter()
            cur.execute(sql)
            t3 = time.perf_counter()
            rows = cur.fetchall()
            t4 = time.perf_counter()
        conn.close()
        t5 = time.perf_counter()

        connect_times.append(t1 - t0)
        exec_times.append(t3 - t2)
        fetch_times.append(t4 - t3)
        row_counts.append(len(rows))

    print("\n[hotboard_intraday] row_counts per run:", row_counts)
    _print_stats("hotboard_intraday.connect", connect_times)
    _print_stats("hotboard_intraday.execute", exec_times)
    _print_stats("hotboard_intraday.fetchall", fetch_times)


def measure_tdx_daily(cfg: Dict[str, Any], runs: int = 5) -> None:
    """Measure TDX daily hotboard snapshot query performance.

    Approximate /api/hotboard/tdx/daily by:
    - finding the latest trade_date in market.tdx_board_daily
    - running the same CTE+JOIN query as the backend for that date
    """
    connect_times: List[float] = []
    exec_times: List[float] = []
    fetch_times: List[float] = []
    row_counts: List[int] = []

    for _ in range(runs):
        t0 = time.perf_counter()
        conn = psycopg2.connect(**cfg)
        t1 = time.perf_counter()
        with conn.cursor() as cur:
            # find latest date with data
            cur.execute("SELECT MAX(trade_date) FROM market.tdx_board_daily")
            row = cur.fetchone()
            latest_date = row[0] if row else None
            if not latest_date:
                print("[tdx_daily] no data in market.tdx_board_daily, skip.")
                conn.close()
                return

            sql = (
                "WITH i2 AS ("
                "    SELECT DISTINCT ON (ts_code) ts_code, name, idx_type "
                "      FROM market.tdx_board_index "
                "     WHERE trade_date IS NULL OR trade_date <= %s "
                "     ORDER BY ts_code, trade_date DESC NULLS LAST"
                ") "
                "SELECT d.trade_date, d.ts_code AS board_code, i2.name AS board_name, i2.idx_type, "
                "       d.pct_chg, d.amount "
                "  FROM market.tdx_board_daily d "
                "  JOIN i2 ON i2.ts_code = d.ts_code "
                " WHERE d.trade_date = %s "
                " ORDER BY i2.idx_type, d.amount DESC NULLS LAST"
            )
            params = (latest_date, latest_date)
            t2 = time.perf_counter()
            cur.execute(sql, params)
            t3 = time.perf_counter()
            rows = cur.fetchall()
            t4 = time.perf_counter()
        conn.close()
        t5 = time.perf_counter()

        connect_times.append(t1 - t0)
        exec_times.append(t3 - t2)
        fetch_times.append(t4 - t3)
        row_counts.append(len(rows))

    print("\n[tdx_daily] row_counts per run:", row_counts)
    _print_stats("tdx_daily.connect", connect_times)
    _print_stats("tdx_daily.execute", exec_times)
    _print_stats("tdx_daily.fetchall", fetch_times)


def main() -> None:
    cfg = build_db_cfg()
    print("Using DB config: host={host} port={port} dbname={dbname} user={user}".format(**cfg))

    print("\n[1] Measuring connection-only cost...")
    measure_connection_only(cfg, runs=10)

    print("\n[2] Measuring realtime hotboard snapshot query (sina_board_intraday)...")
    measure_hotboard_intraday(cfg, runs=5)

    print("\n[3] Measuring TDX daily hotboard snapshot query (tdx_board_daily)...")
    measure_tdx_daily(cfg, runs=5)


if __name__ == "__main__":
    main()
