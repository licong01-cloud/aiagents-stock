"""Initialize TimescaleDB schema for TDX market data.

Supports phased execution via ``--phase`` argument so long-running migrations
can be split into smaller, observable steps.
"""
import sys
import time
import argparse
import psycopg2
from psycopg2 import sql

DB_CONFIG = dict(
    host="localhost",
    port=5432,
    user="postgres",
    password="lc78080808",
    dbname="aistock",
    connect_timeout=5,
    application_name="init_market_schema",
)

STATEMENTS = [
    "CREATE EXTENSION IF NOT EXISTS timescaledb;",
    "CREATE SCHEMA IF NOT EXISTS market;",
    # Dimension table
    """
    CREATE TABLE IF NOT EXISTS market.symbol_dim (
        ts_code CHAR(9) PRIMARY KEY,
        symbol CHAR(6) NOT NULL,
        exchange CHAR(2) NOT NULL CHECK (exchange IN ('SH','SZ','BJ')),
        name VARCHAR(64),
        industry VARCHAR(64),
        list_date DATE
    );
    """,
    # Daily/weekly/monthly QFQ tables
    """
    CREATE TABLE IF NOT EXISTS market.kline_daily_qfq (
        trade_date DATE NOT NULL,
        ts_code CHAR(9) NOT NULL,
        open_li INT4 NOT NULL,
        high_li INT4 NOT NULL,
        low_li INT4 NOT NULL,
        close_li INT4 NOT NULL,
        volume_hand INT8 NOT NULL,
        amount_li INT8 NOT NULL,
        adjust_type CHAR(3) NOT NULL DEFAULT 'qfq' CHECK (adjust_type='qfq'),
        source VARCHAR(16) NOT NULL CHECK (source IN ('tdx_api','tdx_vipdoc')),
        PRIMARY KEY (ts_code, trade_date)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS market.kline_weekly_qfq (
        week_end_date DATE NOT NULL,
        ts_code CHAR(9) NOT NULL,
        open_li INT4 NOT NULL,
        high_li INT4 NOT NULL,
        low_li INT4 NOT NULL,
        close_li INT4 NOT NULL,
        volume_hand INT8 NOT NULL,
        amount_li INT8 NOT NULL,
        adjust_type CHAR(3) NOT NULL DEFAULT 'qfq' CHECK (adjust_type='qfq'),
        source VARCHAR(16) NOT NULL CHECK (source IN ('tdx_api','tdx_vipdoc')),
        PRIMARY KEY (ts_code, week_end_date)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS market.kline_monthly_qfq (
        month_end_date DATE NOT NULL,
        ts_code CHAR(9) NOT NULL,
        open_li INT4 NOT NULL,
        high_li INT4 NOT NULL,
        low_li INT4 NOT NULL,
        close_li INT4 NOT NULL,
        volume_hand INT8 NOT NULL,
        amount_li INT8 NOT NULL,
        adjust_type CHAR(3) NOT NULL DEFAULT 'qfq' CHECK (adjust_type='qfq'),
        source VARCHAR(16) NOT NULL CHECK (source IN ('tdx_api','tdx_vipdoc')),
        PRIMARY KEY (ts_code, month_end_date)
    );
    """,
    # Daily RAW and HFQ tables
    """
    CREATE TABLE IF NOT EXISTS market.kline_daily_raw (
        trade_date DATE NOT NULL,
        ts_code CHAR(9) NOT NULL,
        open_li INT4 NOT NULL,
        high_li INT4 NOT NULL,
        low_li INT4 NOT NULL,
        close_li INT4 NOT NULL,
        volume_hand INT8 NOT NULL,
        amount_li INT8 NOT NULL,
        adjust_type CHAR(4) NOT NULL DEFAULT 'none' CHECK (adjust_type='none'),
        source VARCHAR(16) NOT NULL CHECK (source IN ('tdx_api','tdx_vipdoc')),
        PRIMARY KEY (ts_code, trade_date)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS market.kline_daily_hfq (
        trade_date DATE NOT NULL,
        ts_code CHAR(9) NOT NULL,
        open_li INT4 NOT NULL,
        high_li INT4 NOT NULL,
        low_li INT4 NOT NULL,
        close_li INT4 NOT NULL,
        volume_hand INT8 NOT NULL,
        amount_li INT8 NOT NULL,
        adjust_type CHAR(3) NOT NULL DEFAULT 'hfq' CHECK (adjust_type='hfq'),
        source VARCHAR(16) NOT NULL CHECK (source IN ('tdx_api','tdx_vipdoc')),
        PRIMARY KEY (ts_code, trade_date)
    );
    """,
    # Minute and tick tables
    """
    CREATE TABLE IF NOT EXISTS market.kline_minute_raw (
        trade_time TIMESTAMPTZ NOT NULL,
        ts_code CHAR(9) NOT NULL,
        freq VARCHAR(8) NOT NULL CHECK (freq='1m'),
        open_li INT4,
        high_li INT4,
        low_li INT4,
        close_li INT4 NOT NULL,
        volume_hand INT8,
        amount_li INT8,
        adjust_type CHAR(4) NOT NULL DEFAULT 'none' CHECK (adjust_type='none'),
        source VARCHAR(16) NOT NULL CHECK (source IN ('tdx_api','tdx_vipdoc')),
        PRIMARY KEY (ts_code, trade_time, freq)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS market.tick_trade_raw (
        trade_time TIMESTAMPTZ NOT NULL,
        ts_code CHAR(9) NOT NULL,
        price_li INT4 NOT NULL,
        volume_hand INT4 NOT NULL,
        status SMALLINT NOT NULL DEFAULT -1,
        source VARCHAR(16) NOT NULL DEFAULT 'tdx_api' CHECK (source='tdx_api'),
        PRIMARY KEY (ts_code, trade_time, price_li, volume_hand, status)
    );
    """,
    # Index K-line
    """
    CREATE TABLE IF NOT EXISTS market.index_kline_daily_qfq (
        trade_date DATE NOT NULL,
        code VARCHAR(16) NOT NULL,
        open_li INT4 NOT NULL,
        high_li INT4 NOT NULL,
        low_li INT4 NOT NULL,
        close_li INT4 NOT NULL,
        volume_hand INT8,
        amount_li INT8,
        up_count INT4,
        down_count INT4,
        adjust_type CHAR(3) NOT NULL DEFAULT 'qfq' CHECK (adjust_type='qfq'),
        source VARCHAR(16) NOT NULL CHECK (source IN ('tdx_api','tdx_vipdoc')),
        PRIMARY KEY (code, trade_date)
    );
    """,
    # Snapshots
    """
    CREATE TABLE IF NOT EXISTS market.stock_info (
        ts_code CHAR(9) PRIMARY KEY,
        name VARCHAR(64),
        industry VARCHAR(64),
        market VARCHAR(16),
        area VARCHAR(32),
        list_date DATE,
        ext_json JSONB,
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS market.quote_snapshot (
        snapshot_time TIMESTAMPTZ NOT NULL,
        ts_code CHAR(9) NOT NULL,
        last_li INT4,
        open_li INT4,
        high_li INT4,
        low_li INT4,
        close_li INT4,
        total_hand INT8,
        amount_li INT8,
        inside_dish INT8,
        outer_disc INT8,
        intuition INT8,
        server_time_ts TIMESTAMPTZ,
        buy_levels JSONB,
        sell_levels JSONB,
        PRIMARY KEY (ts_code, snapshot_time)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS market.market_stats_snapshot (
        snapshot_time TIMESTAMPTZ PRIMARY KEY,
        stats JSONB NOT NULL
    );
    """,
    # Control tables
    """
    CREATE TABLE IF NOT EXISTS market.ingestion_runs (
        run_id UUID PRIMARY KEY,
        mode VARCHAR(16) NOT NULL CHECK (mode IN ('full','incremental')),
        dataset VARCHAR(64),
        status VARCHAR(16) NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        started_at TIMESTAMPTZ,
        finished_at TIMESTAMPTZ,
        params JSONB,
        summary JSONB
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS market.ingestion_checkpoints (
        run_id UUID NOT NULL REFERENCES market.ingestion_runs(run_id) ON DELETE CASCADE,
        dataset VARCHAR(64) NOT NULL,
        ts_code CHAR(9),
        cursor_date DATE,
        cursor_time TIMESTAMPTZ,
        extra JSONB,
        PRIMARY KEY (run_id, dataset, ts_code)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS market.ingestion_errors (
        error_id BIGSERIAL PRIMARY KEY,
        run_id UUID REFERENCES market.ingestion_runs(run_id) ON DELETE CASCADE,
        dataset VARCHAR(64),
        ts_code CHAR(9),
        error_at TIMESTAMPTZ DEFAULT NOW(),
        message TEXT,
        detail JSONB
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS market.ingestion_jobs (
        job_id UUID PRIMARY KEY,
        job_type VARCHAR(16) NOT NULL CHECK (job_type IN ('init','incremental')),
        status VARCHAR(16) NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        started_at TIMESTAMPTZ,
        finished_at TIMESTAMPTZ,
        summary JSONB
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS market.ingestion_job_tasks (
        task_id UUID PRIMARY KEY,
        job_id UUID NOT NULL REFERENCES market.ingestion_jobs(job_id) ON DELETE CASCADE,
        dataset VARCHAR(64) NOT NULL,
        ts_code CHAR(9),
        date_from DATE,
        date_to DATE,
        status VARCHAR(16) NOT NULL,
        progress NUMERIC(5,2) DEFAULT 0,
        retries INT DEFAULT 0,
        last_error TEXT,
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS market.ingestion_state (
        dataset VARCHAR(64) NOT NULL,
        ts_code CHAR(9),
        last_success_date DATE,
        last_success_time TIMESTAMPTZ,
        extra JSONB,
        PRIMARY KEY (dataset, ts_code)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS market.ingestion_logs (
        job_id UUID NOT NULL,
        ts TIMESTAMPTZ DEFAULT NOW(),
        level VARCHAR(8) NOT NULL,
        message TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS market.trading_calendar (
        cal_date DATE PRIMARY KEY,
        is_trading BOOLEAN NOT NULL
    );
    """,
    # Sina Hotboard: intraday (hypertable) and daily tables
    """
    CREATE TABLE IF NOT EXISTS market.sina_board_intraday (
        ts TIMESTAMPTZ NOT NULL,
        cate_type SMALLINT NOT NULL,           -- 0=行业,1=概念,2=证监会行业
        board_code TEXT NOT NULL,              -- 如 gn_ldc
        board_name TEXT,
        pct_chg NUMERIC(10,4),                 -- avg_changeratio
        amount NUMERIC(28,2),                  -- 成交额
        net_inflow NUMERIC(28,2),              -- netamount
        turnover NUMERIC(18,4),                -- turnover
        ratioamount NUMERIC(18,6),             -- 净流入率
        meta JSONB,
        PRIMARY KEY (ts, cate_type, board_code)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS market.sina_board_daily (
        trade_date DATE NOT NULL,
        cate_type SMALLINT NOT NULL,           -- 0=行业,1=概念,2=证监会行业
        board_code TEXT NOT NULL,
        board_name TEXT,
        pct_chg NUMERIC(10,4),
        amount NUMERIC(28,2),
        net_inflow NUMERIC(28,2),
        turnover NUMERIC(18,4),
        ratioamount NUMERIC(18,6),
        meta JSONB,
        PRIMARY KEY (trade_date, cate_type, board_code)
    );
    """,
    # Hotboard collector config
    """
    CREATE TABLE IF NOT EXISTS market.hotboard_config (
        id SMALLINT PRIMARY KEY DEFAULT 1,
        enabled BOOLEAN NOT NULL DEFAULT TRUE,
        frequency_seconds INT NOT NULL DEFAULT 5 CHECK (frequency_seconds BETWEEN 3 AND 60),
        trading_windows JSONB,                 -- 如 ["09:25-11:35","12:55-15:05"] 上海时区
        last_run_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS market.testing_schedules (
        schedule_id UUID PRIMARY KEY,
        enabled BOOLEAN NOT NULL DEFAULT TRUE,
        frequency TEXT NOT NULL,
        options JSONB,
        last_run_at TIMESTAMPTZ,
        next_run_at TIMESTAMPTZ,
        last_status VARCHAR(16),
        last_error TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS market.testing_runs (
        run_id UUID PRIMARY KEY,
        schedule_id UUID REFERENCES market.testing_schedules(schedule_id) ON DELETE SET NULL,
        triggered_by VARCHAR(16) NOT NULL,
        status VARCHAR(16) NOT NULL,
        started_at TIMESTAMPTZ DEFAULT NOW(),
        finished_at TIMESTAMPTZ,
        summary JSONB,
        detail JSONB,
        log TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS market.ingestion_schedules (
        schedule_id UUID PRIMARY KEY,
        dataset VARCHAR(64) NOT NULL,
        mode VARCHAR(16) NOT NULL CHECK (mode IN ('init','incremental')),
        frequency TEXT NOT NULL,
        enabled BOOLEAN NOT NULL DEFAULT TRUE,
        options JSONB,
        last_run_at TIMESTAMPTZ,
        next_run_at TIMESTAMPTZ,
        last_status VARCHAR(16),
        last_error TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(dataset, mode)
    );
    """,
    # Tushare 通达信板块：基础信息（tdx_index）
    """
    CREATE TABLE IF NOT EXISTS market.tdx_board_index (
        trade_date DATE NOT NULL,
        ts_code VARCHAR(16) NOT NULL,
        name VARCHAR(128),
        idx_type VARCHAR(32),
        idx_count INT,
        PRIMARY KEY (trade_date, ts_code)
    );
    """,
    # Tushare 通达信板块：成分（tdx_member）
    """
    CREATE TABLE IF NOT EXISTS market.tdx_board_member (
        trade_date DATE NOT NULL,
        ts_code VARCHAR(16) NOT NULL,
        con_code VARCHAR(16) NOT NULL,
        con_name VARCHAR(128),
        PRIMARY KEY (trade_date, ts_code, con_code)
    );
    """,
    # Tushare 通达信板块：行情（tdx_daily）
    """
    CREATE TABLE IF NOT EXISTS market.tdx_board_daily (
        trade_date DATE NOT NULL,
        ts_code VARCHAR(16) NOT NULL,
        open NUMERIC(20,6),
        high NUMERIC(20,6),
        low NUMERIC(20,6),
        close NUMERIC(20,6),
        pre_close NUMERIC(20,6),
        change NUMERIC(20,6),
        pct_chg NUMERIC(10,4),
        vol NUMERIC(20,2),
        amount NUMERIC(28,2),
        PRIMARY KEY (trade_date, ts_code)
    );
    """,
    # 列注释：tdx_board_index
    "COMMENT ON TABLE market.tdx_board_index IS '通达信板块基础信息（Tushare tdx_index）';",
    "COMMENT ON COLUMN market.tdx_board_index.trade_date IS '数据日期（YYYY-MM-DD），接口入参 trade_date';",
    "COMMENT ON COLUMN market.tdx_board_index.ts_code IS '板块代码，如 880728.TDX';",
    "COMMENT ON COLUMN market.tdx_board_index.name IS '板块名称';",
    "COMMENT ON COLUMN market.tdx_board_index.idx_type IS '板块类型：概念/行业/风格/地域等';",
    "COMMENT ON COLUMN market.tdx_board_index.idx_count IS '板块成分数量';",
    # 列注释：tdx_board_member
    "COMMENT ON TABLE market.tdx_board_member IS '通达信板块成分（Tushare tdx_member）';",
    "COMMENT ON COLUMN market.tdx_board_member.trade_date IS '数据日期（YYYY-MM-DD），接口入参 trade_date';",
    "COMMENT ON COLUMN market.tdx_board_member.ts_code IS '板块代码，如 880728.TDX';",
    "COMMENT ON COLUMN market.tdx_board_member.con_code IS '成分证券代码（TS 标准代码）';",
    "COMMENT ON COLUMN market.tdx_board_member.con_name IS '成分证券名称';",
    # 列注释：tdx_board_daily
    "COMMENT ON TABLE market.tdx_board_daily IS '通达信板块行情（Tushare tdx_daily）';",
    "COMMENT ON COLUMN market.tdx_board_daily.trade_date IS '交易日（YYYY-MM-DD），接口入参 trade_date';",
    "COMMENT ON COLUMN market.tdx_board_daily.ts_code IS '板块代码，如 880728.TDX';",
    "COMMENT ON COLUMN market.tdx_board_daily.open IS '开盘价';",
    "COMMENT ON COLUMN market.tdx_board_daily.high IS '最高价';",
    "COMMENT ON COLUMN market.tdx_board_daily.low IS '最低价';",
    "COMMENT ON COLUMN market.tdx_board_daily.close IS '收盘价';",
    "COMMENT ON COLUMN market.tdx_board_daily.pre_close IS '前收盘价';",
    "COMMENT ON COLUMN market.tdx_board_daily.change IS '涨跌额';",
    "COMMENT ON COLUMN market.tdx_board_daily.pct_chg IS '涨跌幅（%）';",
    "COMMENT ON COLUMN market.tdx_board_daily.vol IS '成交量（手）';",
    "COMMENT ON COLUMN market.tdx_board_daily.amount IS '成交额（元）';",
]

HYPERTABLE_SQL = [
    "SELECT create_hypertable('market.kline_daily_qfq', 'trade_date', if_not_exists => TRUE);",
    "SELECT create_hypertable('market.kline_weekly_qfq', 'week_end_date', if_not_exists => TRUE);",
    "SELECT create_hypertable('market.kline_monthly_qfq', 'month_end_date', if_not_exists => TRUE);",
    "SELECT create_hypertable('market.kline_daily_raw', 'trade_date', if_not_exists => TRUE);",
    "SELECT create_hypertable('market.kline_daily_hfq', 'trade_date', if_not_exists => TRUE);",
    "SELECT create_hypertable('market.kline_minute_raw', 'trade_time', partitioning_column => 'ts_code', number_partitions => 16, chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);",
    "SELECT create_hypertable('market.tick_trade_raw', 'trade_time', if_not_exists => TRUE);",
    "SELECT create_hypertable('market.index_kline_daily_qfq', 'trade_date', if_not_exists => TRUE);",
    "SELECT create_hypertable('market.tdx_board_daily', 'trade_date', if_not_exists => TRUE);",
    "SELECT create_hypertable('market.sina_board_intraday', 'ts', if_not_exists => TRUE);",
    "SELECT create_hypertable('market.sina_board_daily', 'trade_date', if_not_exists => TRUE);",
]

INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_kline_minute_ts ON market.kline_minute_raw (ts_code, trade_time DESC);",
    "CREATE INDEX IF NOT EXISTS idx_kline_daily_ts ON market.kline_daily_qfq (ts_code, trade_date DESC);",
    "CREATE INDEX IF NOT EXISTS idx_kline_daily_raw_ts ON market.kline_daily_raw (ts_code, trade_date DESC);",
    "CREATE INDEX IF NOT EXISTS idx_kline_daily_hfq_ts ON market.kline_daily_hfq (ts_code, trade_date DESC);",
    "CREATE INDEX IF NOT EXISTS idx_kline_weekly_ts ON market.kline_weekly_qfq (ts_code, week_end_date DESC);",
    "CREATE INDEX IF NOT EXISTS idx_kline_monthly_ts ON market.kline_monthly_qfq (ts_code, month_end_date DESC);",
    "CREATE INDEX IF NOT EXISTS idx_kline_daily_code ON market.kline_daily_qfq (ts_code);",
    "CREATE INDEX IF NOT EXISTS idx_kline_daily_raw_code ON market.kline_daily_raw (ts_code);",
    "CREATE INDEX IF NOT EXISTS idx_kline_daily_hfq_code ON market.kline_daily_hfq (ts_code);",
    "CREATE INDEX IF NOT EXISTS idx_kline_minute_code ON market.kline_minute_raw (ts_code);",
    "CREATE INDEX IF NOT EXISTS idx_tick_trade_ts ON market.tick_trade_raw (ts_code, trade_time DESC);",
    "CREATE INDEX IF NOT EXISTS idx_testing_runs_schedule ON market.testing_runs (schedule_id);",
    "CREATE INDEX IF NOT EXISTS idx_ingestion_schedules_dataset ON market.ingestion_schedules (dataset, mode);",
    # tdx_board_* indexes
    "CREATE INDEX IF NOT EXISTS idx_tdx_board_index_ts ON market.tdx_board_index (ts_code);",
    "CREATE INDEX IF NOT EXISTS idx_tdx_board_index_date ON market.tdx_board_index (trade_date DESC);",
    "CREATE INDEX IF NOT EXISTS idx_tdx_board_member_board ON market.tdx_board_member (ts_code);",
    "CREATE INDEX IF NOT EXISTS idx_tdx_board_member_con ON market.tdx_board_member (con_code);",
    "CREATE INDEX IF NOT EXISTS idx_tdx_board_member_date ON market.tdx_board_member (trade_date DESC);",
    "CREATE INDEX IF NOT EXISTS idx_tdx_board_daily_ts ON market.tdx_board_daily (ts_code, trade_date DESC);",
    # sina board indexes
    "CREATE INDEX IF NOT EXISTS idx_sina_board_intraday_ts ON market.sina_board_intraday (ts DESC);",
    "CREATE INDEX IF NOT EXISTS idx_sina_board_intraday_board ON market.sina_board_intraday (cate_type, board_code, ts DESC);",
    "CREATE INDEX IF NOT EXISTS idx_sina_board_daily_board ON market.sina_board_daily (cate_type, board_code, trade_date DESC);",
]

COMPRESSION_SQL = [
    "ALTER TABLE market.kline_minute_raw SET (timescaledb.compress, timescaledb.compress_orderby='trade_time', timescaledb.compress_segmentby='ts_code,freq');",
    "ALTER TABLE market.tick_trade_raw SET (timescaledb.compress, timescaledb.compress_orderby='trade_time', timescaledb.compress_segmentby='ts_code');",
    "ALTER TABLE market.kline_daily_qfq SET (timescaledb.compress, timescaledb.compress_orderby='trade_date', timescaledb.compress_segmentby='ts_code');",
    "ALTER TABLE market.kline_daily_raw SET (timescaledb.compress, timescaledb.compress_orderby='trade_date', timescaledb.compress_segmentby='ts_code');",
    "ALTER TABLE market.kline_daily_hfq SET (timescaledb.compress, timescaledb.compress_orderby='trade_date', timescaledb.compress_segmentby='ts_code');",
    "ALTER TABLE market.kline_weekly_qfq SET (timescaledb.compress, timescaledb.compress_orderby='week_end_date', timescaledb.compress_segmentby='ts_code');",
    "ALTER TABLE market.kline_monthly_qfq SET (timescaledb.compress, timescaledb.compress_orderby='month_end_date', timescaledb.compress_segmentby='ts_code');",
    "ALTER TABLE market.index_kline_daily_qfq SET (timescaledb.compress, timescaledb.compress_orderby='trade_date', timescaledb.compress_segmentby='code');",
    "ALTER TABLE market.tdx_board_daily SET (timescaledb.compress, timescaledb.compress_orderby='trade_date', timescaledb.compress_segmentby='ts_code');",
]

COMPRESSION_POLICY_SQL = [
    "SELECT add_compression_policy('market.kline_minute_raw', INTERVAL '7 days', if_not_exists => TRUE);",
    "SELECT add_compression_policy('market.tick_trade_raw', INTERVAL '7 days', if_not_exists => TRUE);",
    "SELECT add_compression_policy('market.kline_daily_qfq', INTERVAL '30 days', if_not_exists => TRUE);",
    "SELECT add_compression_policy('market.kline_daily_raw', INTERVAL '30 days', if_not_exists => TRUE);",
    "SELECT add_compression_policy('market.kline_daily_hfq', INTERVAL '30 days', if_not_exists => TRUE);",
    "SELECT add_compression_policy('market.kline_weekly_qfq', INTERVAL '30 days', if_not_exists => TRUE);",
    "SELECT add_compression_policy('market.kline_monthly_qfq', INTERVAL '30 days', if_not_exists => TRUE);",
    "SELECT add_compression_policy('market.index_kline_daily_qfq', INTERVAL '30 days', if_not_exists => TRUE);",
    "SELECT add_compression_policy('market.tdx_board_daily', INTERVAL '30 days', if_not_exists => TRUE);",
]

RETENTION_POLICY_SQL = [
    "SELECT add_retention_policy('market.kline_minute_raw', INTERVAL '5 years', if_not_exists => TRUE);",
    "SELECT add_retention_policy('market.tick_trade_raw', INTERVAL '180 days', if_not_exists => TRUE);",
    "SELECT add_retention_policy('market.kline_daily_qfq', INTERVAL '20 years', if_not_exists => TRUE);",
    "SELECT add_retention_policy('market.kline_daily_raw', INTERVAL '20 years', if_not_exists => TRUE);",
    "SELECT add_retention_policy('market.kline_daily_hfq', INTERVAL '20 years', if_not_exists => TRUE);",
    "SELECT add_retention_policy('market.kline_weekly_qfq', INTERVAL '20 years', if_not_exists => TRUE);",
    "SELECT add_retention_policy('market.kline_monthly_qfq', INTERVAL '20 years', if_not_exists => TRUE);",
    "SELECT add_retention_policy('market.index_kline_daily_qfq', INTERVAL '20 years', if_not_exists => TRUE);",
    "SELECT add_retention_policy('market.tdx_board_daily', INTERVAL '20 years', if_not_exists => TRUE);",
]

CAGG_SQL = [
    """
    CREATE MATERIALIZED VIEW IF NOT EXISTS market.kline_5m
    WITH (timescaledb.continuous) AS
    SELECT
      ts_code,
      time_bucket('5 minutes', trade_time) AS bucket,
      '5m'::VARCHAR(8) AS freq,
      first(open_li, trade_time) AS open_li,
      max(high_li) AS high_li,
      min(low_li) AS low_li,
      last(close_li, trade_time) AS close_li,
      sum(volume_hand) AS volume_hand,
      sum(amount_li) AS amount_li
    FROM market.kline_minute_raw
    GROUP BY ts_code, bucket
    WITH NO DATA;
    """,
    """
    CREATE MATERIALIZED VIEW IF NOT EXISTS market.kline_15m
    WITH (timescaledb.continuous) AS
    SELECT
      ts_code,
      time_bucket('15 minutes', trade_time) AS bucket,
      '15m'::VARCHAR(8) AS freq,
      first(open_li, trade_time) AS open_li,
      max(high_li) AS high_li,
      min(low_li) AS low_li,
      last(close_li, trade_time) AS close_li,
      sum(volume_hand) AS volume_hand,
      sum(amount_li) AS amount_li
    FROM market.kline_minute_raw
    GROUP BY ts_code, bucket
    WITH NO DATA;
    """,
    """
    CREATE MATERIALIZED VIEW IF NOT EXISTS market.kline_60m
    WITH (timescaledb.continuous) AS
    SELECT
      ts_code,
      time_bucket('60 minutes', trade_time) AS bucket,
      '60m'::VARCHAR(8) AS freq,
      first(open_li, trade_time) AS open_li,
      max(high_li) AS high_li,
      min(low_li) AS low_li,
      last(close_li, trade_time) AS close_li,
      sum(volume_hand) AS volume_hand,
      sum(amount_li) AS amount_li
    FROM market.kline_minute_raw
    GROUP BY ts_code, bucket
    WITH NO DATA;
    """,
]

CAGG_POLICY_SQL = [
    "SELECT add_continuous_aggregate_policy('market.kline_5m', start_offset => INTERVAL '2 days', end_offset => INTERVAL '1 hour', schedule_interval => INTERVAL '15 minutes', if_not_exists => TRUE);",
    "SELECT add_continuous_aggregate_policy('market.kline_15m', start_offset => INTERVAL '3 days', end_offset => INTERVAL '1 hour', schedule_interval => INTERVAL '30 minutes', if_not_exists => TRUE);",
    "SELECT add_continuous_aggregate_policy('market.kline_60m', start_offset => INTERVAL '7 days', end_offset => INTERVAL '1 hour', schedule_interval => INTERVAL '60 minutes', if_not_exists => TRUE);",
]


def _print(*args):
    print(*args)
    sys.stdout.flush()


def execute_batch(cur, statements):
    total = len(statements)
    for i, s in enumerate(statements, 1):
        label = str(s).strip().split("\n", 1)[0][:80]
        _print(f"[{i}/{total}] Executing: {label} ...")
        t0 = time.time()
        cur.execute(s)
        dt = time.time() - t0
        _print(f" -> OK ({dt:.2f}s)")


def main(phase: str = "all"):
    """Run schema initialization for a specific *phase*.

    Phases:
      - schema:       base tables, control tables, trading_calendar, etc.
      - hypertable:   create_hypertable() calls
      - indexes:      secondary indexes
      - compression:  compression + retention policies
      - cagg:         continuous aggregates + their policies
      - all:          run all of the above in order (default)
    """
    phase = phase.lower()
    valid = {"schema", "hypertable", "indexes", "compression", "cagg", "all"}
    if phase not in valid:
        raise SystemExit(f"Invalid phase '{phase}', must be one of: {sorted(valid)}")

    t_start = time.time()
    _print(f"Starting TimescaleDB schema initialization, phase={phase!r} ...")
    ensure_database()

    with psycopg2.connect(**DB_CONFIG) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SET client_min_messages TO NOTICE;")
            cur.execute("SET statement_timeout TO '120s';")
            cur.execute("SET lock_timeout TO '10s';")

            if phase in {"schema", "all"}:
                _print("=== Phase: schema (tables & control objects) ===")
                execute_batch(cur, STATEMENTS)

            if phase in {"hypertable", "all"}:
                _print("=== Phase: hypertable (create_hypertable) ===")
                execute_batch(cur, HYPERTABLE_SQL)

            if phase in {"indexes", "all"}:
                _print("=== Phase: indexes ===")
                execute_batch(cur, INDEX_SQL)

            if phase in {"compression", "all"}:
                _print("=== Phase: compression & retention policies ===")
                execute_batch(cur, COMPRESSION_SQL)
                execute_batch(cur, COMPRESSION_POLICY_SQL)
                execute_batch(cur, RETENTION_POLICY_SQL)

            if phase in {"cagg", "all"}:
                _print("=== Phase: continuous aggregates & policies ===")
                execute_batch(cur, CAGG_SQL)
                execute_batch(cur, CAGG_POLICY_SQL)

    _print(f"Done (phase={phase}). Elapsed: {time.time() - t_start:.2f}s")
def ensure_database():
    """Ensure the target database exists; create it if missing."""
    target_db = DB_CONFIG["dbname"]
    try:
        # Try connect directly
        with psycopg2.connect(**DB_CONFIG):
            return
    except Exception as e:
        # Fallback: connect to 'postgres' and create the database if needed
        admin_cfg = DB_CONFIG.copy()
        admin_cfg["dbname"] = "postgres"
        admin_cfg["connect_timeout"] = 5
        with psycopg2.connect(**admin_cfg) as admin_conn:
            admin_conn.autocommit = True
            with admin_conn.cursor() as cur:
                cur.execute(
                    sql.SQL("SELECT 1 FROM pg_database WHERE datname = %s"),
                    [target_db],
                )
                exists = cur.fetchone() is not None
                if not exists:
                    cur.execute(sql.SQL("CREATE DATABASE {}" ).format(sql.Identifier(target_db)))
    _print("✅ TimescaleDB schema initialized successfully.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Init TimescaleDB schema for TDX data")
    parser.add_argument(
        "--phase",
        default="all",
        choices=["schema", "hypertable", "indexes", "compression", "cagg", "all"],
        help="Run only a specific phase of the migration (default: all)",
    )
    args = parser.parse_args()
    main(phase=args.phase)
