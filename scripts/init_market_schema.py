"""Initialize TimescaleDB schema for TDX market data."""
import psycopg2
from psycopg2 import sql

DB_CONFIG = dict(
    host="localhost",
    port=5432,
    user="postgres",
    password="lc78080808",
    dbname="aistock",
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
]

HYPERTABLE_SQL = [
    "SELECT create_hypertable('market.kline_daily_qfq', 'trade_date', if_not_exists => TRUE);",
    "SELECT create_hypertable('market.kline_weekly_qfq', 'week_end_date', if_not_exists => TRUE);",
    "SELECT create_hypertable('market.kline_monthly_qfq', 'month_end_date', if_not_exists => TRUE);",
    "SELECT create_hypertable('market.kline_minute_raw', 'trade_time', partitioning_column => 'ts_code', number_partitions => 16, chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);",
    "SELECT create_hypertable('market.tick_trade_raw', 'trade_time', if_not_exists => TRUE);",
    "SELECT create_hypertable('market.index_kline_daily_qfq', 'trade_date', if_not_exists => TRUE);",
]

INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_kline_minute_ts ON market.kline_minute_raw (ts_code, trade_time DESC);",
    "CREATE INDEX IF NOT EXISTS idx_kline_daily_ts ON market.kline_daily_qfq (ts_code, trade_date DESC);",
    "CREATE INDEX IF NOT EXISTS idx_kline_weekly_ts ON market.kline_weekly_qfq (ts_code, week_end_date DESC);",
    "CREATE INDEX IF NOT EXISTS idx_kline_monthly_ts ON market.kline_monthly_qfq (ts_code, month_end_date DESC);",
    "CREATE INDEX IF NOT EXISTS idx_kline_daily_code ON market.kline_daily_qfq (ts_code);",
    "CREATE INDEX IF NOT EXISTS idx_kline_minute_code ON market.kline_minute_raw (ts_code);",
    "CREATE INDEX IF NOT EXISTS idx_tick_trade_ts ON market.tick_trade_raw (ts_code, trade_time DESC);",
    "CREATE INDEX IF NOT EXISTS idx_testing_runs_schedule ON market.testing_runs (schedule_id);",
    "CREATE INDEX IF NOT EXISTS idx_ingestion_schedules_dataset ON market.ingestion_schedules (dataset, mode);",
]

COMPRESSION_SQL = [
    "ALTER TABLE market.kline_minute_raw SET (timescaledb.compress, timescaledb.compress_orderby='trade_time', timescaledb.compress_segmentby='ts_code,freq');",
    "ALTER TABLE market.tick_trade_raw SET (timescaledb.compress, timescaledb.compress_orderby='trade_time', timescaledb.compress_segmentby='ts_code');",
    "ALTER TABLE market.kline_daily_qfq SET (timescaledb.compress, timescaledb.compress_orderby='trade_date', timescaledb.compress_segmentby='ts_code');",
    "ALTER TABLE market.kline_weekly_qfq SET (timescaledb.compress, timescaledb.compress_orderby='week_end_date', timescaledb.compress_segmentby='ts_code');",
    "ALTER TABLE market.kline_monthly_qfq SET (timescaledb.compress, timescaledb.compress_orderby='month_end_date', timescaledb.compress_segmentby='ts_code');",
    "ALTER TABLE market.index_kline_daily_qfq SET (timescaledb.compress, timescaledb.compress_orderby='trade_date', timescaledb.compress_segmentby='code');",
]

COMPRESSION_POLICY_SQL = [
    "SELECT add_compression_policy('market.kline_minute_raw', INTERVAL '7 days', if_not_exists => TRUE);",
    "SELECT add_compression_policy('market.tick_trade_raw', INTERVAL '7 days', if_not_exists => TRUE);",
    "SELECT add_compression_policy('market.kline_daily_qfq', INTERVAL '30 days', if_not_exists => TRUE);",
    "SELECT add_compression_policy('market.kline_weekly_qfq', INTERVAL '30 days', if_not_exists => TRUE);",
    "SELECT add_compression_policy('market.kline_monthly_qfq', INTERVAL '30 days', if_not_exists => TRUE);",
    "SELECT add_compression_policy('market.index_kline_daily_qfq', INTERVAL '30 days', if_not_exists => TRUE);",
]

RETENTION_POLICY_SQL = [
    "SELECT add_retention_policy('market.kline_minute_raw', INTERVAL '5 years', if_not_exists => TRUE);",
    "SELECT add_retention_policy('market.tick_trade_raw', INTERVAL '180 days', if_not_exists => TRUE);",
    "SELECT add_retention_policy('market.kline_daily_qfq', INTERVAL '20 years', if_not_exists => TRUE);",
    "SELECT add_retention_policy('market.kline_weekly_qfq', INTERVAL '20 years', if_not_exists => TRUE);",
    "SELECT add_retention_policy('market.kline_monthly_qfq', INTERVAL '20 years', if_not_exists => TRUE);",
    "SELECT add_retention_policy('market.index_kline_daily_qfq', INTERVAL '20 years', if_not_exists => TRUE);",
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


def execute_batch(cur, statements):
    for sql in statements:
        cur.execute(sql)


def main():
    # Ensure target database exists; if not, create it using the default 'postgres' database
    ensure_database()

    with psycopg2.connect(**DB_CONFIG) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            execute_batch(cur, STATEMENTS)
            execute_batch(cur, HYPERTABLE_SQL)
            execute_batch(cur, INDEX_SQL)
            execute_batch(cur, COMPRESSION_SQL)
            execute_batch(cur, COMPRESSION_POLICY_SQL)
            execute_batch(cur, RETENTION_POLICY_SQL)
            execute_batch(cur, CAGG_SQL)
            execute_batch(cur, CAGG_POLICY_SQL)
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
    print("✅ TimescaleDB schema initialized successfully.")


if __name__ == "__main__":
    main()
