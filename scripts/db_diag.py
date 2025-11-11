import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv


def _load_env() -> None:
    project_root = Path(__file__).resolve().parent.parent
    dotenv_path = project_root / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path)


_load_env()


CFG = dict(
    host=os.getenv("TDX_DB_HOST", "localhost"),
    port=int(os.getenv("TDX_DB_PORT", "5432")),
    dbname=os.getenv("TDX_DB_NAME", "aistock"),
    user=os.getenv("TDX_DB_USER", "postgres"),
    password=os.getenv("TDX_DB_PASSWORD", ""),
)

SQLS = [
    ("current_database", "SELECT current_database()"),
    ("current_user", "SELECT current_user"),
    ("search_path", "SHOW search_path"),
    ("schemas", "SELECT schema_name FROM information_schema.schemata ORDER BY schema_name"),
    ("market_tables", "SELECT table_name FROM information_schema.tables WHERE table_schema='market' ORDER BY table_name"),
    ("symbol_dim_any", "SELECT ts_code, name FROM market.symbol_dim LIMIT 3"),
    ("stock_info_any", "SELECT ts_code, name FROM market.stock_info LIMIT 3"),
    ("daily_any", "SELECT ts_code::text, trade_date FROM market.kline_daily_qfq LIMIT 3"),
    ("minute_any", "SELECT ts_code::text, trade_time FROM market.kline_minute_raw LIMIT 3"),
]


def main():
    with psycopg2.connect(**CFG) as conn:
        with conn.cursor() as cur:
            for label, sql in SQLS:
                try:
                    cur.execute(sql)
                    rows = cur.fetchall()
                    print(f"[{label}] -> {rows}")
                except Exception as e:
                    print(f"[{label}] ERROR: {e}")


if __name__ == '__main__':
    main()
