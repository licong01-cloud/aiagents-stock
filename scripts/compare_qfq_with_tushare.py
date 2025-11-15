import datetime as dt
import os
import sys
from typing import Dict, List

import pandas as pd
import psycopg2
import psycopg2.extras as pgx
import tushare as ts
from dotenv import load_dotenv


def _load_config() -> Dict[str, str]:
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
        print("[ERROR] TUSHARE_TOKEN not set in environment")
        sys.exit(1)
    ts.set_token(token)
    return cfg


def _fetch_db_data(conn, ts_code: str, start: str, end: str) -> pd.DataFrame:
    sql = """
        SELECT trade_date,
               open_li,
               high_li,
               low_li,
               close_li,
               volume_hand,
               amount_li
          FROM market.kline_daily_qfq
         WHERE ts_code=%s
           AND trade_date BETWEEN %s AND %s
         ORDER BY trade_date ASC
    """
    with conn.cursor(cursor_factory=pgx.RealDictCursor) as cur:
        cur.execute(sql, (ts_code, start, end))
        rows = cur.fetchall()
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")
    return df


def _fetch_tushare_data(ts_code: str, start: str, end: str) -> pd.DataFrame:
    pro = ts.pro_api()
    start_yyyymmdd = start.replace("-", "")
    end_yyyymmdd = end.replace("-", "")
    df = ts.pro_bar(ts_code=ts_code, adj="qfq", start_date=start_yyyymmdd, end_date=end_yyyymmdd)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d").dt.strftime("%Y-%m-%d")
    df = df.sort_values("trade_date").reset_index(drop=True)

    # Normalise to integer units stored in *_li fields.
    for col in ["open", "high", "low", "close"]:
        df[col + "_li"] = (df[col].astype(float) * 1000).round().astype("Int64")
    # tushare volume is reported in "手"
    df["volume_hand"] = df["vol"].round().astype("Int64")
    # amount column is in 千元 -> convert to 元 then to li (i.e. multiply by 1000)
    if "amount" in df.columns:
        df["amount_li"] = (df["amount"].astype(float) * 1000).round().astype("Int64")
    else:
        df["amount_li"] = pd.Series([pd.NA] * len(df), dtype="Int64")

    keep_cols: List[str] = [
        "trade_date",
        "open_li",
        "high_li",
        "low_li",
        "close_li",
        "volume_hand",
        "amount_li",
    ]
    return df[keep_cols]


def compare(ts_code: str) -> None:
    cfg = _load_config()
    today = dt.date.today()
    start_date = (today - dt.timedelta(days=365)).isoformat()
    end_date = today.isoformat()

    with psycopg2.connect(**cfg) as conn:
        conn.autocommit = True
        df_db = _fetch_db_data(conn, ts_code, start_date, end_date)

    df_ts = _fetch_tushare_data(ts_code, start_date, end_date)

    if df_db.empty and df_ts.empty:
        print(f"[INFO] No data found for {ts_code} in both sources within {start_date}..{end_date}.")
        return

    merged = df_db.merge(df_ts, how="outer", on="trade_date", suffixes=("_db", "_ts"), indicator=True)

    missing_in_db = merged[merged["_merge"] == "right_only"].copy()
    missing_in_ts = merged[merged["_merge"] == "left_only"].copy()

    both = merged[merged["_merge"] == "both"].copy()
    diff_cols = []
    for col in ["open_li", "high_li", "low_li", "close_li", "volume_hand", "amount_li"]:
        db_col = f"{col}_db"
        ts_col = f"{col}_ts"
        both[f"diff_{col}"] = both[db_col] - both[ts_col]
        diff_cols.append(f"diff_{col}")

    tolerance_cols = {
        "open_li": 1,
        "high_li": 1,
        "low_li": 1,
        "close_li": 1,
        "volume_hand": 0,
        "amount_li": 1000,
    }
    mismatched = both.copy()
    for col, tol in tolerance_cols.items():
        diff_col = f"diff_{col}"
        mismatched = mismatched[~(mismatched[diff_col].abs() <= tol)]
    mismatched = mismatched.sort_values("trade_date")

    print(f"Comparison for {ts_code} from {start_date} to {end_date}")
    print(f"  DB rows: {len(df_db)}")
    print(f"  Tushare rows: {len(df_ts)}")
    print(f"  Common dates: {len(both)}")
    print(f"  Missing in DB: {len(missing_in_db)}")
    if not missing_in_db.empty:
        print(missing_in_db[["trade_date"] + [c for c in missing_in_db.columns if c.endswith("_ts")]].head(5))
    print(f"  Missing in Tushare: {len(missing_in_ts)}")
    if not missing_in_ts.empty:
        print(missing_in_ts[["trade_date"] + [c for c in missing_in_ts.columns if c.endswith("_db")]].head(5))

    mismatched_count = len(mismatched)
    print(f"  Mismatched rows (beyond tolerance): {mismatched_count}")
    if mismatched_count:
        cols_to_show = [
            "trade_date",
            "open_li_db",
            "open_li_ts",
            "diff_open_li",
            "high_li_db",
            "high_li_ts",
            "diff_high_li",
            "low_li_db",
            "low_li_ts",
            "diff_low_li",
            "close_li_db",
            "close_li_ts",
            "diff_close_li",
            "volume_hand_db",
            "volume_hand_ts",
            "diff_volume_hand",
            "amount_li_db",
            "amount_li_ts",
            "diff_amount_li",
        ]
        print(mismatched[cols_to_show].head(10))
    else:
        max_diffs = {col: int(both[f"diff_{col}"] .abs().max() or 0) for col in tolerance_cols}
        print("  Maximum absolute differences within tolerance:")
        for col, val in max_diffs.items():
            print(f"    {col}: {val}")


if __name__ == "__main__":
    compare("603197.SH")
