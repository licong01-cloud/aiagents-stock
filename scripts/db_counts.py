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
    host=os.getenv('TDX_DB_HOST', 'localhost'),
    port=int(os.getenv('TDX_DB_PORT', '5432')),
    dbname=os.getenv('TDX_DB_NAME', 'aistock'),
    user=os.getenv('TDX_DB_USER', 'postgres'),
    password=os.getenv('TDX_DB_PASSWORD', ''),
)
SAMPLES = ("000001.SZ", "600000.SH")

def main():
    with psycopg2.connect(**CFG) as conn:
        with conn.cursor() as cur:
            # base dims
            cur.execute("SELECT count(*) FROM market.symbol_dim")
            print('symbol_dim_total:', cur.fetchone()[0])
            cur.execute("SELECT count(*) FROM market.stock_info")
            print('stock_info_total:', cur.fetchone()[0])

            # totals
            cur.execute("SELECT count(*) FROM market.kline_daily_qfq")
            print('daily_qfq_total:', cur.fetchone()[0])
            cur.execute("SELECT count(*) FROM market.kline_minute_raw")
            print('minute_1m_total:', cur.fetchone()[0])

            # sample filter with char(9) -> text cast to avoid padding mismatch
            cur.execute("SELECT count(*) FROM market.kline_daily_qfq WHERE ts_code::text = ANY(%s)", (list(SAMPLES),))
            print('daily_qfq_samples:', cur.fetchone()[0])
            cur.execute("SELECT count(*) FROM market.kline_minute_raw WHERE ts_code::text = ANY(%s)", (list(SAMPLES),))
            print('minute_1m_samples:', cur.fetchone()[0])

            # Optional: cagg rows if views exist
            for label in ('kline_5m', 'kline_15m', 'kline_60m'):
                try:
                    cur.execute("SELECT to_regclass('market." + label + "') IS NOT NULL")
                    if cur.fetchone()[0]:
                        cur.execute(f"SELECT count(*) FROM market.{label}")
                        print(f'{label}_total:', cur.fetchone()[0])
                        cur.execute(f"SELECT count(*) FROM market.{label} WHERE ts_code::text = ANY(%s)", (list(SAMPLES),))
                        print(f'{label}_samples:', cur.fetchone()[0])
                except Exception:
                    pass

if __name__ == '__main__':
    main()
