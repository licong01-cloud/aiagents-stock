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


def _parse_date(s: Any):
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(str(s), fmt).date()
        except Exception:
            continue
    return None


def row_get(r: sqlite3.Row, key: str, default=None):
    try:
        if key in r.keys():
            return r[key]
        return default
    except Exception:
        return default


def _num(v):
    if v is None:
        return None
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except Exception:
        return None


def _int(v):
    if v is None:
        return None
    try:
        return int(v)
    except Exception:
        try:
            f = float(v)
            if math.isnan(f) or math.isinf(f):
                return None
            return int(f)
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


def migrate_monitor_tasks(sqlite_path: str, batch: int) -> int:
    conn_s = sqlite3.connect(sqlite_path)
    conn_s.row_factory = sqlite3.Row
    total = 0
    try:
        cur_s = conn_s.cursor()
        cur_s.execute("SELECT * FROM monitor_tasks ORDER BY id ASC")
        while True:
            rows = cur_s.fetchmany(batch)
            if not rows:
                break
            values: List[Tuple[Any, ...]] = []
            for r in rows:
                values.append(
                    (
                        r["task_name"],
                        r["stock_code"],
                        row_get(r, "stock_name"),
                        bool(row_get(r, "enabled", 0)),
                        _int(row_get(r, "check_interval", 300)) or 300,
                        bool(row_get(r, "auto_trade", 0)),
                        _num(row_get(r, "position_size_pct")),
                        _num(row_get(r, "stop_loss_pct")),
                        _num(row_get(r, "take_profit_pct")),
                        row_get(r, "qmt_account_id"),
                        row_get(r, "notify_email"),
                        row_get(r, "notify_webhook"),
                        bool(row_get(r, "has_position", 0)),
                        _num(row_get(r, "position_cost", 0)),
                        _int(row_get(r, "position_quantity", 0)) or 0,
                        _parse_date(row_get(r, "position_date")),
                    )
                )
            with psycopg2.connect(**_pg_conn_params()) as conn:
                with conn.cursor() as cur:
                    pg_extras.execute_values(
                        cur,
                        "INSERT INTO app.monitor_tasks (task_name, stock_code, stock_name, enabled, check_interval, auto_trade, position_size_pct, stop_loss_pct, take_profit_pct, qmt_account_id, notify_email, notify_webhook, has_position, position_cost, position_quantity, position_date) VALUES %s ON CONFLICT (stock_code) DO UPDATE SET task_name=EXCLUDED.task_name, stock_name=EXCLUDED.stock_name, enabled=EXCLUDED.enabled, check_interval=EXCLUDED.check_interval, auto_trade=EXCLUDED.auto_trade, position_size_pct=EXCLUDED.position_size_pct, stop_loss_pct=EXCLUDED.stop_loss_pct, take_profit_pct=EXCLUDED.take_profit_pct, qmt_account_id=EXCLUDED.qmt_account_id, notify_email=EXCLUDED.notify_email, notify_webhook=EXCLUDED.notify_webhook, has_position=EXCLUDED.has_position, position_cost=EXCLUDED.position_cost, position_quantity=EXCLUDED.position_quantity, position_date=EXCLUDED.position_date, updated_at=now()",
                        values,
                        page_size=batch,
                    )
                conn.commit()
            total += len(values)
    finally:
        conn_s.close()
    return total


def migrate_ai_decisions(sqlite_path: str, batch: int) -> int:
    conn_s = sqlite3.connect(sqlite_path)
    conn_s.row_factory = sqlite3.Row
    total = 0
    try:
        cur_s = conn_s.cursor()
        cur_s.execute("SELECT * FROM ai_decisions ORDER BY id ASC")
        while True:
            rows = cur_s.fetchmany(batch)
            if not rows:
                break
            values: List[Tuple[Any, ...]] = []
            for r in rows:
                values.append(
                    (
                        r["stock_code"],
                        row_get(r, "stock_name"),
                        _parse_dt(r["decision_time"]),
                        row_get(r, "trading_session"),
                        r["action"],
                        _int(row_get(r, "confidence")),
                        row_get(r, "reasoning"),
                        _num(row_get(r, "position_size_pct")),
                        _num(row_get(r, "stop_loss_pct")),
                        _num(row_get(r, "take_profit_pct")),
                        row_get(r, "risk_level"),
                        pg_extras.Json(_to_json(row_get(r, "key_price_levels")) or {}),
                        pg_extras.Json(_to_json(row_get(r, "market_data")) or {}),
                        pg_extras.Json(_to_json(row_get(r, "account_info")) or {}),
                        bool(row_get(r, "executed", 0)),
                        row_get(r, "execution_result"),
                    )
                )
            with psycopg2.connect(**_pg_conn_params()) as conn:
                with conn.cursor() as cur:
                    pg_extras.execute_values(
                        cur,
                        "INSERT INTO app.ai_decisions (stock_code, stock_name, decision_time, trading_session, action, confidence, reasoning, position_size_pct, stop_loss_pct, take_profit_pct, risk_level, key_price_levels, market_data, account_info, executed, execution_result) VALUES %s",
                        values,
                        page_size=batch,
                    )
                conn.commit()
            total += len(values)
    finally:
        conn_s.close()
    return total


def migrate_trade_records(sqlite_path: str, batch: int) -> int:
    conn_s = sqlite3.connect(sqlite_path)
    conn_s.row_factory = sqlite3.Row
    total = 0
    try:
        cur_s = conn_s.cursor()
        cur_s.execute("SELECT * FROM trade_records ORDER BY id ASC")
        while True:
            rows = cur_s.fetchmany(batch)
            if not rows:
                break
            values: List[Tuple[Any, ...]] = []
            for r in rows:
                values.append(
                    (
                        r["stock_code"],
                        row_get(r, "stock_name"),
                        r["trade_type"],
                        _int(row_get(r, "quantity")),
                        _num(row_get(r, "price")),
                        _num(row_get(r, "amount")),
                        row_get(r, "order_id"),
                        row_get(r, "order_status"),
                        _int(row_get(r, "ai_decision_id")),
                        _parse_dt(r["trade_time"]),
                        _num(row_get(r, "commission", 0)),
                        _num(row_get(r, "tax", 0)),
                        _num(row_get(r, "profit_loss", 0)),
                    )
                )
            with psycopg2.connect(**_pg_conn_params()) as conn:
                with conn.cursor() as cur:
                    pg_extras.execute_values(
                        cur,
                        "INSERT INTO app.trade_records (stock_code, stock_name, trade_type, quantity, price, amount, order_id, order_status, ai_decision_id, trade_time, commission, tax, profit_loss) VALUES %s",
                        values,
                        page_size=batch,
                    )
                conn.commit()
            total += len(values)
    finally:
        conn_s.close()
    return total


def migrate_position_monitor(sqlite_path: str, batch: int) -> int:
    conn_s = sqlite3.connect(sqlite_path)
    conn_s.row_factory = sqlite3.Row
    total = 0
    try:
        cur_s = conn_s.cursor()
        cur_s.execute("SELECT * FROM position_monitor ORDER BY id ASC")
        while True:
            rows = cur_s.fetchmany(batch)
            if not rows:
                break
            values: List[Tuple[Any, ...]] = []
            for r in rows:
                values.append(
                    (
                        r["stock_code"],
                        row_get(r, "stock_name"),
                        _int(row_get(r, "quantity")),
                        _num(row_get(r, "cost_price")),
                        _num(row_get(r, "current_price")),
                        _num(row_get(r, "profit_loss")),
                        _num(row_get(r, "profit_loss_pct")),
                        _int(row_get(r, "holding_days")),
                        row_get(r, "buy_date"),
                        _num(row_get(r, "stop_loss_price")),
                        _num(row_get(r, "take_profit_price")),
                        _parse_dt(row_get(r, "last_check_time")),
                        row_get(r, "status", "holding"),
                    )
                )
            with psycopg2.connect(**_pg_conn_params()) as conn:
                with conn.cursor() as cur:
                    pg_extras.execute_values(
                        cur,
                        "INSERT INTO app.position_monitor (stock_code, stock_name, quantity, cost_price, current_price, profit_loss, profit_loss_pct, holding_days, buy_date, stop_loss_price, take_profit_price, last_check_time, status) VALUES %s ON CONFLICT (stock_code) DO UPDATE SET stock_name=EXCLUDED.stock_name, quantity=EXCLUDED.quantity, cost_price=EXCLUDED.cost_price, current_price=EXCLUDED.current_price, profit_loss=EXCLUDED.profit_loss, profit_loss_pct=EXCLUDED.profit_loss_pct, holding_days=EXCLUDED.holding_days, buy_date=EXCLUDED.buy_date, stop_loss_price=EXCLUDED.stop_loss_price, take_profit_price=EXCLUDED.take_profit_price, last_check_time=EXCLUDED.last_check_time, updated_at=now(), status=EXCLUDED.status",
                        values,
                        page_size=batch,
                    )
                conn.commit()
            total += len(values)
    finally:
        conn_s.close()
    return total


def migrate_notifications(sqlite_path: str, batch: int) -> int:
    conn_s = sqlite3.connect(sqlite_path)
    conn_s.row_factory = sqlite3.Row
    total = 0
    try:
        cur_s = conn_s.cursor()
        cur_s.execute("SELECT * FROM notifications ORDER BY id ASC")
        while True:
            rows = cur_s.fetchmany(batch)
            if not rows:
                break
            values: List[Tuple[Any, ...]] = []
            for r in rows:
                values.append(
                    (
                        row_get(r, "stock_code"),
                        row_get(r, "notify_type") or row_get(r, "type"),
                        row_get(r, "notify_target"),
                        row_get(r, "subject"),
                        row_get(r, "content") or row_get(r, "message"),
                        row_get(r, "status", "pending"),
                        _parse_dt(row_get(r, "sent_at")) if row_get(r, "sent_at") else None,
                        _parse_dt(row_get(r, "created_at")) if row_get(r, "created_at") else datetime.now(timezone.utc),
                    )
                )
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


def migrate_system_logs(sqlite_path: str, batch: int) -> int:
    conn_s = sqlite3.connect(sqlite_path)
    conn_s.row_factory = sqlite3.Row
    total = 0
    try:
        cur_s = conn_s.cursor()
        cur_s.execute("SELECT * FROM system_logs ORDER BY id ASC")
        while True:
            rows = cur_s.fetchmany(batch)
            if not rows:
                break
            values: List[Tuple[Any, ...]] = []
            for r in rows:
                values.append(
                    (
                        row_get(r, "log_level"),
                        row_get(r, "module"),
                        row_get(r, "message"),
                        row_get(r, "details"),
                        _parse_dt(row_get(r, "created_at")),
                    )
                )
            with psycopg2.connect(**_pg_conn_params()) as conn:
                with conn.cursor() as cur:
                    pg_extras.execute_values(
                        cur,
                        "INSERT INTO app.system_logs (log_level, module, message, details, created_at) VALUES %s",
                        values,
                        page_size=batch,
                    )
                conn.commit()
            total += len(values)
    finally:
        conn_s.close()
    return total


def main():
    parser = argparse.ArgumentParser(description="Migrate smart_monitor.db (SQLite) to TimescaleDB app schema")
    parser.add_argument("--sqlite", default="smart_monitor.db", help="Path to SQLite file (default: smart_monitor.db)")
    parser.add_argument("--batch-size", type=int, default=1000, help="Batch size for migration")
    parser.add_argument("--truncate-first", action="store_true", help="TRUNCATE destination tables before migration (DANGEROUS)")
    parser.add_argument("--dry-run", action="store_true", help="Only show counts and exit")
    args = parser.parse_args()

    tables_sqlite = [
        ("monitor_tasks", "app.monitor_tasks"),
        ("ai_decisions", "app.ai_decisions"),
        ("trade_records", "app.trade_records"),
        ("position_monitor", "app.position_monitor"),
        ("notifications", "app.notifications"),
        ("system_logs", "app.system_logs"),
    ]

    print("Counts (SQLite -> PG):")
    for s, p in tables_sqlite:
        sc = _count_sqlite(args.sqlite, s)
        pc = _count_pg(p)
        print(f"- {s} -> {p}: {sc} -> {pc}")

    if args.dry_run:
        print("Dry run: no data migrated.")
        return

    if args.truncate_first:
        with psycopg2.connect(**_pg_conn_params()) as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE app.monitor_tasks RESTART IDENTITY CASCADE")
                cur.execute("TRUNCATE app.ai_decisions RESTART IDENTITY CASCADE")
                cur.execute("TRUNCATE app.trade_records RESTART IDENTITY CASCADE")
                cur.execute("TRUNCATE app.position_monitor RESTART IDENTITY CASCADE")
                cur.execute("TRUNCATE app.notifications RESTART IDENTITY CASCADE")
                cur.execute("TRUNCATE app.system_logs RESTART IDENTITY CASCADE")
            conn.commit()

    total = 0
    total += migrate_monitor_tasks(args.sqlite, args.batch_size)
    print(f"migrated monitor_tasks: {total}")
    total = migrate_ai_decisions(args.sqlite, args.batch_size)
    print(f"migrated ai_decisions: {total}")
    total = migrate_trade_records(args.sqlite, args.batch_size)
    print(f"migrated trade_records: {total}")
    total = migrate_position_monitor(args.sqlite, args.batch_size)
    print(f"migrated position_monitor: {total}")
    total = migrate_notifications(args.sqlite, args.batch_size)
    print(f"migrated notifications: {total}")
    total = migrate_system_logs(args.sqlite, args.batch_size)
    print(f"migrated system_logs: {total}")

    print("Done.")


if __name__ == "__main__":
    main()
