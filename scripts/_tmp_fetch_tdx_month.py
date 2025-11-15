import argparse
import datetime as dt
import json
import os

import requests
from dotenv import load_dotenv


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch TDX daily bars for inspection")
    parser.add_argument("code", nargs="?", default=os.getenv("TDX_TEST_CODE", "603197"), help="6-digit stock code without suffix")
    parser.add_argument("--end", dest="end", default=dt.date(2025, 8, 27).isoformat(), help="End date (YYYY-MM-DD)")
    parser.add_argument("--days", dest="days", type=int, default=30, help="Number of days to look back")
    args = parser.parse_args()

    load_dotenv(override=True)

    base = os.getenv("TDX_API_BASE", "http://localhost:8080").rstrip("/")
    end = dt.date.fromisoformat(args.end)
    start = end - dt.timedelta(days=args.days)
    params = {
        "code": args.code,
        "type": "day",
        "adjust": "none",
        "start": start.isoformat(),
        "end": end.isoformat(),
    }

    resp = requests.get(base + "/api/kline", params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    rows = data.get("data", {}).get("List") or data.get("data", {}).get("list") or data.get("data") or []
    cleaned = []
    for row in rows:
        time_val = row.get("Time") or row.get("Date") or row.get("time") or row.get("date")
        row = dict(row)
        row["Time"] = str(time_val)
        cleaned.append(row)

    print(f"Fetched {len(cleaned)} rows for code {args.code} from {start} to {end}")
    print(json.dumps(cleaned, ensure_ascii=False, indent=2))

    nonzero_amount = [r for r in cleaned if (r.get("Amount") or 0) not in (0, "0", None)]
    print(f"\nRows with non-zero Amount: {len(nonzero_amount)}")
    if nonzero_amount:
        print(json.dumps(nonzero_amount, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
