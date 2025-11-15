import os
from typing import List

from dotenv import load_dotenv
import psycopg2

load_dotenv(override=True)


def _conn_params():
    return {
        "host": os.getenv("TDX_DB_HOST", "localhost"),
        "port": int(os.getenv("TDX_DB_PORT", "5432")),
        "dbname": os.getenv("TDX_DB_NAME", "aistock"),
        "user": os.getenv("TDX_DB_USER", "postgres"),
        "password": os.getenv("TDX_DB_PASSWORD", "lc78080808"),
    }


def main():
    ddl: List[str] = [
        # ensure schema exists
        "CREATE SCHEMA IF NOT EXISTS app",
        # drop old tables (mapping first)
        "DROP TABLE IF EXISTS app.watchlist_item_categories",
        "DROP TABLE IF EXISTS app.watchlist_items",
        "DROP TABLE IF EXISTS app.watchlist_categories",
        # create categories (same as init_app_schema.py)
        """
        CREATE TABLE IF NOT EXISTS app.watchlist_categories (
          id          BIGSERIAL PRIMARY KEY,
          name        TEXT NOT NULL UNIQUE,
          description TEXT,
          created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        # items (no category_id)
        """
        CREATE TABLE IF NOT EXISTS app.watchlist_items (
          id           BIGSERIAL PRIMARY KEY,
          code         TEXT NOT NULL UNIQUE,
          name         TEXT NOT NULL,
          note         TEXT,
          created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_wi_code ON app.watchlist_items (code)",
        # mapping table
        """
        CREATE TABLE IF NOT EXISTS app.watchlist_item_categories (
          item_id     BIGINT NOT NULL REFERENCES app.watchlist_items(id) ON DELETE CASCADE,
          category_id BIGINT NOT NULL REFERENCES app.watchlist_categories(id) ON DELETE CASCADE,
          created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (item_id, category_id)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_wic_item ON app.watchlist_item_categories (item_id)",
        "CREATE INDEX IF NOT EXISTS idx_wic_cat ON app.watchlist_item_categories (category_id)",
        # default categories
        "INSERT INTO app.watchlist_categories(name, description) VALUES ('默认', '默认分类') ON CONFLICT (name) DO NOTHING",
        "INSERT INTO app.watchlist_categories(name, description) VALUES ('持仓股票', '持仓自动归类') ON CONFLICT (name) DO NOTHING",
    ]

    params = _conn_params()
    with psycopg2.connect(**params) as conn:
        with conn.cursor() as cur:
            for sql in ddl:
                cur.execute(sql)
        conn.commit()
    print("Watchlist schema reset to many-to-many and default category created.")


if __name__ == "__main__":
    main()
