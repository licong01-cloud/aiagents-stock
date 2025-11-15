from __future__ import annotations
import argparse
import datetime as dt
import os
import psycopg2
import psycopg2.extras as pgx
from dotenv import load_dotenv

load_dotenv(override=True)
pgx.register_uuid()

DB_CFG = dict(
    host=os.getenv("TDX_DB_HOST", "localhost"),
    port=int(os.getenv("TDX_DB_PORT", "5432")),
    user=os.getenv("TDX_DB_USER", "postgres"),
    password=os.getenv("TDX_DB_PASSWORD", "lc78080808"),
    dbname=os.getenv("TDX_DB_NAME", "aistock"),
)


def _pro_api():
    import importlib
    token = os.getenv("TUSHARE_TOKEN")
    if not token:
        raise RuntimeError("TUSHARE_TOKEN not set")
    ts = importlib.import_module("tushare")
    return ts.pro_api(token)


def upsert_calendar(conn, rows: list[tuple[str, bool]]):
    if not rows:
        return 0
    with conn.cursor() as cur:
        pgx.execute_values(
            cur,
            """
            INSERT INTO market.trading_calendar(cal_date, is_trading)
            VALUES %s
            ON CONFLICT (cal_date) DO UPDATE SET is_trading = EXCLUDED.is_trading
            """,
            rows,
        )
    return len(rows)


def fetch_trade_cal(start_date: str, end_date: str, exchange: str = "SSE") -> list[tuple[str, bool]]:
    pro = _pro_api()
    df = pro.trade_cal(exchange=exchange, start_date=start_date.replace("-", ""), end_date=end_date.replace("-", ""))
    out: list[tuple[str, bool]] = []
    if df is not None and not df.empty:
        for _, r in df.iterrows():
            cal_date = str(r.get("cal_date"))
            if len(cal_date) == 8:
                cal_date = f"{cal_date[:4]}-{cal_date[4:6]}-{cal_date[6:8]}"
            is_open = bool(int(r.get("is_open") or 0))
            out.append((cal_date, is_open))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-date", default=(dt.date.today() - dt.timedelta(days=365)).isoformat())
    ap.add_argument("--end-date", default=(dt.date.today() + dt.timedelta(days=30)).isoformat())
    ap.add_argument("--exchange", default="SSE")
    args = ap.parse_args()

    with psycopg2.connect(**DB_CFG) as conn:
        conn.autocommit = True
        rows = fetch_trade_cal(args.start_date, args.end_date, args.exchange)
        upsert_calendar(conn, rows)


if __name__ == "__main__":
    main()
