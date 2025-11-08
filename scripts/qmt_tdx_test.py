import os
import sys
import argparse
import pandas as pd
from pytdx.reader import TdxDailyBarReader, TdxMinBarReader
from typing import Optional


def find_vipdoc(root: str) -> Optional[str]:
    """Try to locate the TDX vipdoc directory inside QMT installation root."""
    candidates = [
        os.path.join(root, "userdata_mini", "tdx", "vipdoc"),
        os.path.join(root, "userdata", "tdx", "vipdoc"),
        os.path.join(root, "tdx", "vipdoc"),
        os.path.join(root, "vipdoc"),
    ]
    for p in candidates:
        if os.path.isdir(p):
            return p
    # Fallback: deep scan (once)
    for dirpath, dirnames, filenames in os.walk(root):
        if os.path.basename(dirpath).lower() == "vipdoc":
            return dirpath
    return None


def split_ts_code(ts_code: str) -> tuple[str, str]:
    """Convert ts_code like 000001.SZ / 600000.SH to (ex, code) such as ("sz", "000001")."""
    if "." not in ts_code:
        raise ValueError("ts_code must be like 000001.SZ or 600000.SH")
    code, exch = ts_code.split(".")
    exch = exch.upper()
    if exch == "SH":
        return "sh", code
    elif exch == "SZ":
        return "sz", code
    else:
        raise ValueError(f"unsupported exchange: {exch}")


def read_daily(ts_code: str, vipdoc: str) -> pd.DataFrame:
    ex, code = split_ts_code(ts_code)
    f = os.path.join(vipdoc, ex, "lday", f"{ex}{code}.day")
    if not os.path.exists(f):
        raise FileNotFoundError(f"daily file not found: {f}")
    df = TdxDailyBarReader().get_df(f)
    # Standardize columns
    df["ts_code"] = ts_code
    df["trade_date"] = pd.to_datetime(df["date"]).dt.strftime("%Y%m%d")
    return df[["trade_date", "ts_code", "open", "high", "low", "close", "vol", "amount"]]


MIN_SUFFIX = {"1m": "lc1", "5m": "lc5", "15m": "lc15", "30m": "lc30", "60m": "lc60"}


def read_min(ts_code: str, vipdoc: str, freq: str) -> pd.DataFrame:
    if freq not in MIN_SUFFIX:
        raise ValueError(f"unsupported freq: {freq}; choose from {list(MIN_SUFFIX.keys())}")
    ex, code = split_ts_code(ts_code)
    f = os.path.join(vipdoc, ex, "fzline", f"{ex}{code}.{MIN_SUFFIX[freq]}")
    if not os.path.exists(f):
        raise FileNotFoundError(f"{freq} file not found: {f}")
    df = TdxMinBarReader().get_df(f)
    df["ts_code"] = ts_code
    df.rename(columns={"datetime": "trade_time"}, inplace=True)
    return df[["trade_time", "ts_code", "open", "high", "low", "close", "vol", "amount"]]


def main() -> int:
    parser = argparse.ArgumentParser(description="Read QMT local TDX K-line (daily/minute)")
    parser.add_argument("--root", default=r"C:\\Program Files (x86)\\国金QMT交易端模拟", help="QMT installation root")
    parser.add_argument("--ts_code", default="000001.SZ", help="e.g. 000001.SZ or 600000.SH")
    parser.add_argument(
        "--freq", default="1d", help="1d for daily; minute options: 1m,5m,15m,30m,60m"
    )
    parser.add_argument("--head", type=int, default=5, help="rows to print from head/tail")
    args = parser.parse_args()

    vipdoc = find_vipdoc(args.root)
    if not vipdoc:
        print(f"[ERROR] vipdoc not found under root: {args.root}")
        print("Hint: ensure QMT has downloaded historical data, then re-run.")
        return 2

    print(f"[INFO] vipdoc directory: {vipdoc}")

    try:
        if args.freq.lower() in ("1d", "d", "day", "daily"):
            df = read_daily(args.ts_code, vipdoc)
            print(f"[OK] daily rows: {len(df)}")
            print("[HEAD]")
            print(df.head(args.head))
            print("[TAIL]")
            print(df.tail(min(args.head, len(df))))
        else:
            df = read_min(args.ts_code, vipdoc, args.freq)
            print(f"[OK] {args.freq} rows: {len(df)}")
            print("[HEAD]")
            print(df.head(args.head))
            print("[TAIL]")
            print(df.tail(min(args.head, len(df))))
        return 0
    except FileNotFoundError as e:
        print(f"[WARN] {e}")
        print("Hint: open QMT and download the corresponding history first (daily/minute).")
        return 1
    except Exception as e:
        print(f"[ERROR] unexpected: {e}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
