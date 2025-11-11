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


def _exec_all(cur, statements: List[str]):
    for sql in statements:
        cur.execute(sql)


def main():
    ddl: List[str] = [
        "CREATE EXTENSION IF NOT EXISTS timescaledb",
        "CREATE SCHEMA IF NOT EXISTS app",
        # ensure clean slate for first run if a prior attempt created a non-compliant table
        "DROP TABLE IF EXISTS app.analysis_records CASCADE",
        # monitored_stocks (regular)
        """
        CREATE TABLE IF NOT EXISTS app.monitored_stocks (
          id                    BIGSERIAL PRIMARY KEY,
          symbol                TEXT NOT NULL,
          name                  TEXT NOT NULL,
          rating                TEXT NOT NULL,
          entry_range           JSONB,
          take_profit           NUMERIC,
          stop_loss             NUMERIC,
          current_price         NUMERIC,
          last_checked          TIMESTAMPTZ,
          check_interval        INT DEFAULT 30,
          notification_enabled  BOOLEAN DEFAULT TRUE,
          quant_enabled         BOOLEAN DEFAULT FALSE,
          quant_config          JSONB,
          created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE(symbol)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_ms_symbol ON app.monitored_stocks (symbol)",
        # price_history (hypertable)
        """
        CREATE TABLE IF NOT EXISTS app.price_history (
          id         BIGSERIAL NOT NULL,
          stock_id   BIGINT,
          price      NUMERIC NOT NULL,
          timestamp  TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (id, timestamp)
        )
        """,
        "SELECT create_hypertable('app.price_history', 'timestamp', if_not_exists => TRUE)",
        "CREATE INDEX IF NOT EXISTS idx_ph_stock_time ON app.price_history (stock_id, timestamp DESC)",
        # analysis_records
        """
        CREATE TABLE IF NOT EXISTS app.analysis_records (
          id              BIGSERIAL NOT NULL,
          ts_code         TEXT,
          stock_name      TEXT,
          period          TEXT NOT NULL,
          analysis_date   TIMESTAMPTZ NOT NULL,
          stock_info      JSONB,
          agents_results  JSONB,
          discussion_result JSONB,
          final_decision  JSONB,
          created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (id, created_at)
        )
        """,
        "SELECT create_hypertable('app.analysis_records', 'created_at', if_not_exists => TRUE)",
        "CREATE INDEX IF NOT EXISTS idx_ar_ts_code_created ON app.analysis_records (ts_code, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_ar_created ON app.analysis_records (created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_ar_analysis_date ON app.analysis_records (analysis_date DESC)",
        "CREATE INDEX IF NOT EXISTS idx_ar_final_decision_gin ON app.analysis_records USING GIN (final_decision)",
        # ai_decisions
        """
        CREATE TABLE IF NOT EXISTS app.ai_decisions (
          id                BIGSERIAL NOT NULL,
          stock_code        TEXT NOT NULL,
          stock_name        TEXT,
          decision_time     TIMESTAMPTZ NOT NULL,
          trading_session   TEXT,
          action            TEXT NOT NULL,
          confidence        INT,
          reasoning         TEXT,
          position_size_pct NUMERIC,
          stop_loss_pct     NUMERIC,
          take_profit_pct   NUMERIC,
          risk_level        TEXT,
          key_price_levels  JSONB,
          market_data       JSONB,
          account_info      JSONB,
          executed          BOOLEAN DEFAULT FALSE,
          execution_result  TEXT,
          created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (id, decision_time)
        )
        """,
        "SELECT create_hypertable('app.ai_decisions', 'decision_time', if_not_exists => TRUE)",
        "CREATE INDEX IF NOT EXISTS idx_aid_stock_time ON app.ai_decisions (stock_code, decision_time DESC)",
        "CREATE INDEX IF NOT EXISTS idx_aid_created ON app.ai_decisions (created_at DESC)",
        # trade_records
        """
        CREATE TABLE IF NOT EXISTS app.trade_records (
          id            BIGSERIAL NOT NULL,
          stock_code    TEXT NOT NULL,
          stock_name    TEXT,
          trade_type    TEXT NOT NULL,
          quantity      INT,
          price         NUMERIC,
          amount        NUMERIC,
          order_id      TEXT,
          order_status  TEXT,
          ai_decision_id BIGINT,
          trade_time    TIMESTAMPTZ NOT NULL,
          commission    NUMERIC DEFAULT 0,
          tax           NUMERIC DEFAULT 0,
          profit_loss   NUMERIC DEFAULT 0,
          created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (id, trade_time)
        )
        """,
        "SELECT create_hypertable('app.trade_records', 'trade_time', if_not_exists => TRUE)",
        "CREATE INDEX IF NOT EXISTS idx_tr_stock_time ON app.trade_records (stock_code, trade_time DESC)",
        "CREATE INDEX IF NOT EXISTS idx_tr_created ON app.trade_records (created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_tr_order ON app.trade_records (order_id)",
        # monitor_tasks
        """
        CREATE TABLE IF NOT EXISTS app.monitor_tasks (
          id                BIGSERIAL PRIMARY KEY,
          task_name         TEXT NOT NULL,
          stock_code        TEXT NOT NULL,
          stock_name        TEXT,
          enabled           BOOLEAN DEFAULT TRUE,
          check_interval    INT DEFAULT 300,
          auto_trade        BOOLEAN DEFAULT FALSE,
          position_size_pct NUMERIC DEFAULT 20,
          stop_loss_pct     NUMERIC DEFAULT 5,
          take_profit_pct   NUMERIC DEFAULT 10,
          qmt_account_id    TEXT,
          notify_email      TEXT,
          notify_webhook    TEXT,
          has_position      BOOLEAN DEFAULT FALSE,
          position_cost     NUMERIC DEFAULT 0,
          position_quantity INT DEFAULT 0,
          position_date     DATE,
          created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE(stock_code)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_mt_enabled ON app.monitor_tasks (enabled)",
        # position_monitor
        """
        CREATE TABLE IF NOT EXISTS app.position_monitor (
          id               BIGSERIAL PRIMARY KEY,
          stock_code       TEXT NOT NULL UNIQUE,
          stock_name       TEXT,
          quantity         INT,
          cost_price       NUMERIC,
          current_price    NUMERIC,
          profit_loss      NUMERIC,
          profit_loss_pct  NUMERIC,
          holding_days     INT,
          buy_date         DATE,
          stop_loss_price  NUMERIC,
          take_profit_price NUMERIC,
          last_check_time  TIMESTAMPTZ,
          status           TEXT DEFAULT 'holding',
          created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_pm_status ON app.position_monitor (status)",
        # notifications
        """
        CREATE TABLE IF NOT EXISTS app.notifications (
          id            BIGSERIAL NOT NULL,
          stock_code    TEXT,
          notify_type   TEXT NOT NULL,
          notify_target TEXT,
          subject       TEXT,
          content       TEXT,
          status        TEXT DEFAULT 'pending',
          error_msg     TEXT,
          sent_at       TIMESTAMPTZ,
          created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (id, created_at)
        )
        """,
        "SELECT create_hypertable('app.notifications', 'created_at', if_not_exists => TRUE)",
        "CREATE INDEX IF NOT EXISTS idx_ntf_status_created ON app.notifications (status, created_at DESC)",
        # system_logs
        """
        CREATE TABLE IF NOT EXISTS app.system_logs (
          id         BIGSERIAL NOT NULL,
          log_level  TEXT,
          module     TEXT,
          message    TEXT,
          details    TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (id, created_at)
        )
        """,
        "SELECT create_hypertable('app.system_logs', 'created_at', if_not_exists => TRUE)",
        "CREATE INDEX IF NOT EXISTS idx_log_level_created ON app.system_logs (log_level, created_at DESC)",
        # portfolios
        """
        CREATE TABLE IF NOT EXISTS app.portfolios (
          id          BIGSERIAL PRIMARY KEY,
          name        TEXT NOT NULL UNIQUE,
          owner       TEXT,
          created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        # portfolio_positions
        """
        CREATE TABLE IF NOT EXISTS app.portfolio_positions (
          id            BIGSERIAL PRIMARY KEY,
          portfolio_id  BIGINT NOT NULL,
          ts_code       TEXT NOT NULL,
          quantity      NUMERIC NOT NULL,
          cost_price    NUMERIC,
          last_updated  TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE (portfolio_id, ts_code)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_pos_portfolio ON app.portfolio_positions (portfolio_id)",
        # sector_signals
        """
        CREATE TABLE IF NOT EXISTS app.sector_signals (
          id           BIGSERIAL NOT NULL,
          sector_code  TEXT NOT NULL,
          signal_time  TIMESTAMPTZ NOT NULL,
          score        NUMERIC,
          payload      JSONB,
          created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (id, signal_time)
        )
        """,
        "SELECT create_hypertable('app.sector_signals', 'signal_time', if_not_exists => TRUE)",
        "CREATE INDEX IF NOT EXISTS idx_ss_sector_time ON app.sector_signals (sector_code, signal_time DESC)",
        # longhubang
        """
        CREATE TABLE IF NOT EXISTS app.longhubang (
          id          BIGSERIAL NOT NULL,
          ts_code     TEXT NOT NULL,
          trade_date  DATE NOT NULL,
          direction   TEXT,
          amount      NUMERIC,
          ratio       NUMERIC,
          payload     JSONB,
          created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (id, created_at)
        )
        """,
        "SELECT create_hypertable('app.longhubang', 'created_at', if_not_exists => TRUE)",
        "CREATE INDEX IF NOT EXISTS idx_lhb_code_date ON app.longhubang (ts_code, trade_date DESC)",
    ]

    params = _conn_params()
    with psycopg2.connect(**params) as conn:
        with conn.cursor() as cur:
            _exec_all(cur, ddl)
        conn.commit()


if __name__ == "__main__":
    main()
