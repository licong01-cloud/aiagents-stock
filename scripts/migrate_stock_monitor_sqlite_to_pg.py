import argparse
import os
import sqlite3
import json
import math
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


def _parse_dt(s: Any) -> datetime:
    if s is None or s == "":
        return datetime.now(timezone.utc)
    if isinstance(s, datetime):
        if s.tzinfo is None:
            s = s.replace(tzinfo=timezone.utc)
        return s.astimezone(timezone.utc)
    # try isoformat
    try:
        dt = datetime.fromisoformat(str(s))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    # try common format
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            dt = datetime.strptime(str(s), fmt)
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return datetime.now(timezone.utc)


def _sanitize_numbers(obj: Any) -> Any:
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, list):
        return [_sanitize_numbers(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _sanitize_numbers(v) for k, v in obj.items()}
    return obj


def _to_json(val: Any) -> Any:
    if val is None or val == "":
        return None
    if isinstance(val, (dict, list)):
        return _sanitize_numbers(val)
    try:
        data = json.loads(val, parse_constant=lambda _c: None)
        return _sanitize_numbers(data)
    except Exception:
        return None


def _count_sqlite(sqlite_path: str, table: str) -> int:
    if not os.path.exists(sqlite_path):
        return 0
    conn = sqlite3.connect(sqlite_path)
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        return int(cur.fetchone()[0])
    finally:
        conn.close()


def _count_pg(table: str) -> int:
    with psycopg2.connect(**_pg_conn_params()) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            return int(cur.fetchone()[0])


def migrate_monitored_stocks(sqlite_path: str, batch: int) -> int:
    conn_s = sqlite3.connect(sqlite_path)
    conn_s.row_factory = sqlite3.Row
    total = 0
    try:
        cur_s = conn_s.cursor()
        cur_s.execute("SELECT * FROM monitored_stocks ORDER BY id ASC")
        while True:
            rows = cur_s.fetchmany(batch)
            if not rows:
                break
            values: List[Tuple[Any, ...]] = []
            for r in rows:
                entry_range = _to_json(r["entry_range"]) or {}
                quant_config = _to_json(r["quant_config"]) or {}
                last_checked = _parse_dt(r["last_checked"]) if r["last_checked"] else None
                created_at = _parse_dt(r["created_at"]) if "created_at" in r.keys() and r["created_at"] else datetime.now(timezone.utc)
                updated_at = _parse_dt(r["updated_at"]) if "updated_at" in r.keys() and r["updated_at"] else created_at
                values.append(
                    (
                        r["symbol"],
                        r["name"],
                        r["rating"],
                        pg_extras.Json(entry_range),
                        r["take_profit"],
                        r["stop_loss"],
                        r["current_price"],
                        last_checked,
                        int(r["check_interval"]) if r["check_interval"] is not None else 30,
                        bool(r["notification_enabled"]) if r["notification_enabled"] is not None else True,
                        bool(r["quant_enabled"]) if r["quant_enabled"] is not None else False,
                        pg_extras.Json(quant_config),
                        created_at,
                        updated_at,
                    )
                )
            with psycopg2.connect(**_pg_conn_params()) as conn:
                with conn.cursor() as cur:
                    pg_extras.execute_values(
                        cur,
                        "INSERT INTO app.monitored_stocks (symbol, name, rating, entry_range, take_profit, stop_loss, current_price, last_checked, check_interval, notification_enabled, quant_enabled, quant_config, created_at, updated_at) VALUES %s ON CONFLICT (symbol) DO UPDATE SET name=EXCLUDED.name, rating=EXCLUDED.rating, entry_range=EXCLUDED.entry_range, take_profit=EXCLUDED.take_profit, stop_loss=EXCLUDED.stop_loss, current_price=EXCLUDED.current_price, last_checked=EXCLUDED.last_checked, check_interval=EXCLUDED.check_interval, notification_enabled=EXCLUDED.notification_enabled, quant_enabled=EXCLUDED.quant_enabled, quant_config=EXCLUDED.quant_config, updated_at=EXCLUDED.updated_at",
                        values,
                        page_size=batch,
                    )
                conn.commit()
            total += len(values)
    finally:
        conn_s.close()
    return total


def migrate_price_history(sqlite_path: str, batch: int) -> int:
    # Map SQLite stock_id -> symbol by reading monitored_stocks
    conn_s = sqlite3.connect(sqlite_path)
    conn_s.row_factory = sqlite3.Row
    total = 0
    try:
        id_to_symbol: Dict[int, str] = {}
        cur_s = conn_s.cursor()
        cur_s.execute("SELECT id, symbol FROM monitored_stocks")
        for r in cur_s.fetchall():
            id_to_symbol[int(r["id"])]= r["symbol"]
        # Build a lookup for PG symbol -> id
        pg_symbol_to_id: Dict[str, int] = {}
        with psycopg2.connect(**_pg_conn_params()) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, symbol FROM app.monitored_stocks")
                for rid, sym in cur.fetchall():
                    pg_symbol_to_id[sym] = rid
        # Migrate
        cur_s.execute("SELECT stock_id, price, timestamp FROM price_history ORDER BY id ASC")
        while True:
            rows = cur_s.fetchmany(batch)
            if not rows:
                break
            values: List[Tuple[Any, ...]] = []
            for r in rows:
                sid = r["stock_id"]
                sym = id_to_symbol.get(sid)
                if not sym:
                    continue
                pg_id = pg_symbol_to_id.get(sym)
                if not pg_id:
                    continue
                values.append((pg_id, r["price"], _parse_dt(r["timestamp"])) )
            if not values:
                continue
            with psycopg2.connect(**_pg_conn_params()) as conn:
                with conn.cursor() as cur:
                    pg_extras.execute_values(
                        cur,
                        "INSERT INTO app.price_history (stock_id, price, timestamp) VALUES %s",
                        values,
                        page_size=batch,
                    )
                conn.commit()
            total += len(values)
    finally:
        conn_s.close()
    return total


def migrate_notifications(sqlite_path: str, batch: int) -> int:
    # Convert stock_id to symbol and map fields
    conn_s = sqlite3.connect(sqlite_path)
    conn_s.row_factory = sqlite3.Row
    total = 0
    try:
        id_to_symbol: Dict[int, str] = {}
        cur_s = conn_s.cursor()
        cur_s.execute("SELECT id, symbol FROM monitored_stocks")
        for r in cur_s.fetchall():
            id_to_symbol[int(r["id"])]= r["symbol"]
        cur_s.execute("SELECT id, stock_id, type, message, triggered_at, sent FROM notifications ORDER BY id ASC")
        while True:
            rows = cur_s.fetchmany(batch)
            if not rows:
                break
            values: List[Tuple[Any, ...]] = []
            for r in rows:
                sym = id_to_symbol.get(r["stock_id"]) if r["stock_id"] is not None else None
                notify_type = r["type"]
                content = r["message"]
                created_at = _parse_dt(r["triggered_at"]) if r["triggered_at"] else datetime.now(timezone.utc)
                status = 'sent' if r["sent"] else 'pending'
                sent_at = created_at if r["sent"] else None
                values.append((sym, notify_type, None, None, content, status, sent_at, created_at))
            with psycopg2.connect(**_pg_conn_params()) as conn:
                with conn.cursor() as cur:
                    pg_extras.execute_values(
                        cur,
                        "INSERT INTO app.notifications (stock_code, notify_type, notify_target, subject, content, status, sent_at, created_at) VALUES %s",
                        values,
                        page_size=batch,
                    )
                conn.commit()
            total += len(values)
    finally:
        conn_s.close()
    return total


def main():
    parser = argparse.ArgumentParser(description="Migrate stock_monitor.db (SQLite) to TimescaleDB app schema")
    parser.add_argument("--sqlite", default="stock_monitor.db", help="Path to SQLite file (default: stock_monitor.db)")
    parser.add_argument("--batch-size", type=int, default=1000, help="Batch size for migration")
    parser.add_argument("--truncate-first", action="store_true", help="TRUNCATE destination tables before migration (DANGEROUS)")
    parser.add_argument("--dry-run", action="store_true", help="Only show counts and exit")
    args = parser.parse_args()

    tables = [
        ("monitored_stocks", "app.monitored_stocks"),
        ("price_history", "app.price_history"),
        ("notifications", "app.notifications"),
    ]

    print("Counts (SQLite -> PG):")
    for s, p in tables:
        sc = _count_sqlite(args.sqlite, s)
        pc = _count_pg(p)
        print(f"- {s} -> {p}: {sc} -> {pc}")

    if args.dry_run:
        print("Dry run: no data migrated.")
        return

    if args.truncate_first:
        with psycopg2.connect(**_pg_conn_params()) as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE app.monitored_stocks RESTART IDENTITY CASCADE")
                cur.execute("TRUNCATE app.price_history RESTART IDENTITY CASCADE")
                # app.notifications is shared; do not truncate unless you know it's safe
            conn.commit()

    n1 = migrate_monitored_stocks(args.sqlite, args.batch_size)
    print(f"migrated monitored_stocks: {n1}")
    n2 = migrate_price_history(args.sqlite, args.batch_size)
    print(f"migrated price_history: {n2}")
    n3 = migrate_notifications(args.sqlite, args.batch_size)
    print(f"migrated notifications: {n3}")
    print("Done.")


if __name__ == "__main__":
    main()
