import datetime as dt
import os
from typing import Dict, Optional

import pandas as pd
import psycopg2
import psycopg2.extras as pgx
import tushare as ts
from dotenv import load_dotenv

DATE = "2025-08-27"
TS_CODE = "603197.SH"

PRICE_COLUMNS = ["open_li", "high_li", "low_li", "close_li"]
VALUE_COLUMNS = PRICE_COLUMNS + ["volume_hand", "amount_li"]


def _load_db_cfg() -> Dict[str, str]:
    load_dotenv(override=True)
    cfg = {
        "host": os.getenv("TDX_DB_HOST", "localhost"),
        "port": int(os.getenv("TDX_DB_PORT", "5432")),
        "user": os.getenv("TDX_DB_USER", "postgres"),
        "password": os.getenv("TDX_DB_PASSWORD", ""),
        "dbname": os.getenv("TDX_DB_NAME", "aistock"),
    }
    token = os.getenv("TUSHARE_TOKEN")
    if not token:
        raise RuntimeError("TUSHARE_TOKEN not set in environment")
    ts.set_token(token)
    return cfg


def _query_single_row(conn, table: str) -> Optional[pd.Series]:
    sql = (
        f"SELECT trade_date, {', '.join(VALUE_COLUMNS)}, adjust_type, source "
        f"FROM {table} WHERE ts_code=%s AND trade_date=%s"
    )
    with conn.cursor(cursor_factory=pgx.RealDictCursor) as cur:
        cur.execute(sql, (TS_CODE, DATE))
        row = cur.fetchone()
    if not row:
        return None
    row["trade_date"] = row["trade_date"].isoformat()
    return pd.Series(row)


def _fetch_tushare(adj: Optional[str]) -> Optional[pd.Series]:
    start = DATE.replace("-", "")
    end = start
    df = ts.pro_bar(ts_code=TS_CODE, adj=adj, start_date=start, end_date=end)
    if df is None or df.empty:
        return None
    df = df.sort_values("trade_date", ascending=True).reset_index(drop=True)
    row = df.iloc[0].copy()
    row["trade_date"] = dt.datetime.strptime(row["trade_date"], "%Y%m%d").date().isoformat()
    for col in ["open", "high", "low", "close"]:
        row[col + "_li"] = int(round(float(row[col]) * 1000)) if pd.notna(row[col]) else None
    row["volume_hand"] = int(round(float(row["vol"])) if pd.notna(row["vol"]) else 0)
    amount = float(row.get("amount") or 0.0)
    row["amount_li"] = int(round(amount * 1000))
    keep = {"trade_date", "open_li", "high_li", "low_li", "close_li", "volume_hand", "amount_li"}
    return pd.Series({k: row.get(k) for k in keep})


def _format_series(title: str, series: Optional[pd.Series]) -> None:
    print(f"\n{title}")
    if series is None:
        print("  (no row)")
        return
    for col in VALUE_COLUMNS:
        val = series.get(col)
        if val is None:
            display = "None"
        elif col in PRICE_COLUMNS:
            display = f"{val} (¥{val / 1000:.3f})"
        elif col == "amount_li":
            display = f"{val} (¥{val / 1000:.2f})"
        else:
            display = str(val)
        print(f"  {col:>12}: {display}")
    extra_cols = [c for c in series.index if c not in VALUE_COLUMNS + ["trade_date"]]
    for col in extra_cols:
        print(f"  {col:>12}: {series[col]}")


def main() -> None:
    cfg = _load_db_cfg()
    with psycopg2.connect(**cfg) as conn:
        conn.autocommit = True
        raw_row = _query_single_row(conn, "market.kline_daily_raw")
        qfq_row = _query_single_row(conn, "market.kline_daily_qfq")

    ts_raw = _fetch_tushare(adj=None)
    ts_qfq = _fetch_tushare(adj="qfq")

    print(f"Inspection for {TS_CODE} on {DATE}")
    _format_series("DB raw (market.kline_daily_raw)", raw_row)
    _format_series("DB QFQ (market.kline_daily_qfq)", qfq_row)
    _format_series("Tushare raw (adj=None)", ts_raw)
    _format_series("Tushare QFQ (adj='qfq')", ts_qfq)

    if raw_row is not None and qfq_row is not None:
        ratios = {}
        for col in PRICE_COLUMNS:
            raw_val = raw_row.get(col)
            qfq_val = qfq_row.get(col)
            if raw_val and raw_val != 0:
                ratios[col] = qfq_val / raw_val
        if ratios:
            print("\nPrice ratios (QFQ / RAW):")
            for col, ratio in ratios.items():
                print(f"  {col.replace('_li', ''):>8}: {ratio:.6f}")

    if qfq_row is not None and ts_qfq is not None:
        print("\nDifferences: DB QFQ minus Tushare QFQ")
        for col in VALUE_COLUMNS:
            db_val = qfq_row.get(col)
            ts_val = ts_qfq.get(col)
            if db_val is None or ts_val is None:
                diff = None
            else:
                diff = db_val - ts_val
            print(f"  {col:>12}: {diff}")


if __name__ == "__main__":
    main()
