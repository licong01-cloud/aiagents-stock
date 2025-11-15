import os

import psycopg2
import psycopg2.extras as pgx
from dotenv import load_dotenv


def main() -> None:
    load_dotenv(override=True)
    cfg = {
        "host": os.getenv("TDX_DB_HOST", "localhost"),
        "port": int(os.getenv("TDX_DB_PORT", "5432")),
        "user": os.getenv("TDX_DB_USER", "postgres"),
        "password": os.getenv("TDX_DB_PASSWORD", ""),
        "dbname": os.getenv("TDX_DB_NAME", "aistock"),
    }

    with psycopg2.connect(**cfg) as conn:
        conn.autocommit = True
        with conn.cursor(cursor_factory=pgx.RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM market.kline_daily_qfq")
            total_rows = cur.fetchone()["cnt"]

            cur.execute("SELECT COUNT(DISTINCT ts_code) AS codes FROM market.kline_daily_qfq")
            codes = cur.fetchone()["codes"]

            cur.execute(
                """
                SELECT pg_size_pretty(pg_total_relation_size('market.kline_daily_qfq')) AS total_size,
                       pg_size_pretty(pg_relation_size('market.kline_daily_qfq')) AS table_size,
                       pg_size_pretty(pg_indexes_size('market.kline_daily_qfq')) AS index_size
                """
            )
            sizes = cur.fetchone()

    print("kline_daily_qfq 统计：")
    print(f"  行数: {total_rows:,}")
    print(f"  覆盖股票数: {codes:,}")
    print("  存储占用:")
    print(f"    总大小: {sizes['total_size']}")
    print(f"    表大小: {sizes['table_size']}")
    print(f"    索引大小: {sizes['index_size']}")


if __name__ == "__main__":
    main()
