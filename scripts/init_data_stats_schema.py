"""Initialize data statistics schema for local database monitoring.

This script creates:
- market.data_stats_config: configuration of which tables/columns to track
- market.data_stats: aggregated statistics per data_kind
- market.refresh_data_stats(): function to refresh the statistics

Run this script manually when you want to set up or update the statistics schema.
It does NOT change any existing business tables.
"""

import os
import sys
from typing import Any

import psycopg2

from tdx_scheduler import DEFAULT_DB_CFG


def _db_cfg() -> dict[str, Any]:
    """Build DB config from env/DEFAULT_DB_CFG (same pattern as tdx_backend)."""

    return {
        "host": os.getenv("TDX_DB_HOST", DEFAULT_DB_CFG["host"]),
        "port": int(os.getenv("TDX_DB_PORT", DEFAULT_DB_CFG["port"])),
        "user": os.getenv("TDX_DB_USER", DEFAULT_DB_CFG["user"]),
        "password": os.getenv("TDX_DB_PASSWORD", DEFAULT_DB_CFG["password"]),
        "dbname": os.getenv("TDX_DB_NAME", DEFAULT_DB_CFG["dbname"]),
    }


DDL_SQL = r"""
CREATE TABLE IF NOT EXISTS market.data_stats_config (
    data_kind      text PRIMARY KEY,                 -- logical dataset key, e.g. kline_daily_qfq
    table_name     text NOT NULL,                    -- physical table, e.g. market.kline_daily_qfq
    date_column    text NOT NULL,                    -- main date/time column for min/max range
    updated_column text,                             -- optional column used to infer last_updated_at
    enabled        boolean NOT NULL DEFAULT true,    -- whether to include in refresh
    extra_info     jsonb                             -- optional extra config
);

CREATE TABLE IF NOT EXISTS market.data_stats (
    id               bigserial PRIMARY KEY,
    data_kind        text NOT NULL UNIQUE,
    table_name       text NOT NULL,
    min_date         date,
    max_date         date,
    row_count        bigint,
    table_bytes      bigint,
    index_bytes      bigint,
    last_updated_at  timestamptz,
    stat_generated_at timestamptz NOT NULL DEFAULT now(),
    extra_info       jsonb
);

CREATE OR REPLACE FUNCTION market.refresh_data_stats()
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    cfg           RECORD;
    sql_range     text;
    sql_updated   text;
    v_cnt         bigint;
    v_min_date    date;
    v_max_date    date;
    v_last_update timestamptz;
    v_tbl_bytes   bigint;
    v_idx_bytes   bigint;
BEGIN
    FOR cfg IN
        SELECT * FROM market.data_stats_config WHERE enabled
    LOOP
        -- build and execute range/count SQL
        sql_range := format(
            'SELECT COUNT(*), MIN(%1$I)::date, MAX(%1$I)::date FROM %2$s',
            cfg.date_column,
            cfg.table_name
        );
        EXECUTE sql_range INTO v_cnt, v_min_date, v_max_date;

        -- last_updated_at (optional)
        v_last_update := NULL;
        IF cfg.updated_column IS NOT NULL AND cfg.updated_column <> '' THEN
            sql_updated := format(
                'SELECT MAX(%1$I) FROM %2$s',
                cfg.updated_column,
                cfg.table_name
            );
            EXECUTE sql_updated INTO v_last_update;
        END IF;

        -- table & index sizes
        SELECT pg_total_relation_size(cfg.table_name),
               pg_indexes_size(cfg.table_name)
          INTO v_tbl_bytes, v_idx_bytes;

        INSERT INTO market.data_stats (
            data_kind,
            table_name,
            min_date,
            max_date,
            row_count,
            table_bytes,
            index_bytes,
            last_updated_at,
            stat_generated_at,
            extra_info
        ) VALUES (
            cfg.data_kind,
            cfg.table_name,
            v_min_date,
            v_max_date,
            v_cnt,
            v_tbl_bytes,
            v_idx_bytes,
            v_last_update,
            now(),
            cfg.extra_info
        )
        ON CONFLICT (data_kind) DO UPDATE
           SET table_name       = EXCLUDED.table_name,
               min_date         = EXCLUDED.min_date,
               max_date         = EXCLUDED.max_date,
               row_count        = EXCLUDED.row_count,
               table_bytes      = EXCLUDED.table_bytes,
               index_bytes      = EXCLUDED.index_bytes,
               last_updated_at  = EXCLUDED.last_updated_at,
               stat_generated_at= EXCLUDED.stat_generated_at,
               extra_info       = EXCLUDED.extra_info;
    END LOOP;
END;
$$;
"""


DEFAULT_CONFIG_SQL = r"""
INSERT INTO market.data_stats_config (data_kind, table_name, date_column, updated_column, enabled, extra_info)
VALUES
    -- 对于日线/分钟线，没有单独的 updated_at 列，这里直接使用日期字段作为“最后更新时间”统计依据
    ('kline_daily_raw',  'market.kline_daily_raw',  'trade_date', 'trade_date', true, jsonb_build_object('desc','原始日线，未复权')),
    ('kline_daily_qfq',  'market.kline_daily_qfq',  'trade_date', 'trade_date', true, jsonb_build_object('desc','前复权日线')),
    ('kline_minute_raw', 'market.kline_minute_raw', 'trade_time', 'trade_time', true, jsonb_build_object('desc','原始分钟线')),
    -- Sina 板块资金
    ('sina_board_intraday', 'market.sina_board_intraday', 'ts',   NULL, true, jsonb_build_object('desc','Sina 板块资金分时')),
    ('sina_board_daily',    'market.sina_board_daily',    'trade_date', NULL, true, jsonb_build_object('desc','Sina 板块资金日统计')),
    -- TDX 板块数据（来自 Tushare tdx_* 接口）
    ('tdx_board_index',  'market.tdx_board_index',  'trade_date', 'trade_date', true, jsonb_build_object('desc','TDX 板块基础信息')),
    ('tdx_board_member', 'market.tdx_board_member', 'trade_date', 'trade_date', true, jsonb_build_object('desc','TDX 板块成分')),
    ('tdx_board_daily',  'market.tdx_board_daily',  'trade_date', 'trade_date', true, jsonb_build_object('desc','TDX 板块行情')),
    -- 交易日历
    ('trading_calendar', 'market.trading_calendar', 'cal_date',   'cal_date',   true, jsonb_build_object('desc','交易日历（是否交易日）'))
ON CONFLICT (data_kind) DO UPDATE
    SET table_name     = EXCLUDED.table_name,
        date_column    = EXCLUDED.date_column,
        updated_column = EXCLUDED.updated_column,
        enabled        = EXCLUDED.enabled,
        extra_info     = EXCLUDED.extra_info;
"""


def main() -> None:
    cfg = _db_cfg()
    print("Connecting to DB:", cfg)
    conn = psycopg2.connect(**cfg)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            print("Applying DDL for data_stats schema ...")
            cur.execute(DDL_SQL)
            print("Upserting default data_stats_config entries ...")
            cur.execute(DEFAULT_CONFIG_SQL)
        print("Done. You can now call SELECT market.refresh_data_stats(); to populate statistics.")
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print("[ERROR] init_data_stats_schema failed:", exc)
        sys.exit(1)
