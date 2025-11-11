# TimescaleDB 统一存储设计方案（SQLite → TimescaleDB）

## 背景与目标
- **目标**：将程序中所有本地化数据存储统一迁移至 TimescaleDB（PostgreSQL）。
- **范围**：替换现有 SQLite 存储（analysis_records、智能盯盘、交易记录、通知/日志等）为 TimescaleDB；保留市场行情相关表在 `market.*`，新增应用侧表在 `app.*`。
- **要求**：
  - 有明确时间线（历史/事件/指标序列）的表使用 TimescaleDB hypertable。
  - 无明显时间线（配置/持仓快照等）的表使用普通表（regular table）。
  - 暂不使用外键（后续可引入）。

## 设计原则
- **一致性**：所有数据访问统一走 TimescaleDB，使用 `.env` 中的 `TDX_DB_*` 连接参数。
- **可演进**：面向 append-only 的历史数据使用 hypertable，方便扩展压缩、保留策略和连续聚合。
- **可回溯**：所有时间字段使用 `TIMESTAMPTZ`（带时区），默认以 UTC 存储，UI 按需转换（如 Asia/Shanghai）。
- **简单安全**：暂不引入外键，先落地统一存储与读写路径；后续再增强约束与引用完整性。

## 数据库与 Schema
- 继续使用现有数据库（例如 `.env` 中 `TDX_DB_NAME=aistock`）。
- 新增应用 Schema：`app`（应用/智能盯盘/分析/通知/日志等）。
- 行情相关数据仍在 `market.*`（已存在且稳定）。

## 表设计（app.*）

下列 DDL 为建议实现，可在脚本中执行（见“初始化与迁移”章节）。

### 1) 分析记录（hypertable）
用于替代 SQLite `database.py` 中的 `analysis_records`。

```sql
CREATE SCHEMA IF NOT EXISTS app;

CREATE TABLE IF NOT EXISTS app.analysis_records (
  id              BIGSERIAL PRIMARY KEY,
  ts_code         TEXT,                  -- 原 symbol，可与 market.symbol_dim 对齐（暂不加 FK）
  stock_name      TEXT,
  period          TEXT NOT NULL,
  analysis_date   TIMESTAMPTZ NOT NULL,  -- 业务时间
  stock_info      JSONB,
  agents_results  JSONB,
  discussion_result JSONB,
  final_decision  JSONB,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Hypertable 按 created_at 建：更利于统一查询与保留策略
SELECT create_hypertable('app.analysis_records', 'created_at', if_not_exists => TRUE);

-- 索引建议
CREATE INDEX IF NOT EXISTS idx_ar_ts_code_created ON app.analysis_records (ts_code, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ar_created ON app.analysis_records (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ar_analysis_date ON app.analysis_records (analysis_date DESC);
CREATE INDEX IF NOT EXISTS idx_ar_final_decision_gin ON app.analysis_records USING GIN (final_decision);
```

### 2) 智能盯盘：AI 决策（hypertable）
替代 `smart_monitor_db.py` 中 `ai_decisions`。

```sql
CREATE TABLE IF NOT EXISTS app.ai_decisions (
  id                BIGSERIAL PRIMARY KEY,
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
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
SELECT create_hypertable('app.ai_decisions', 'decision_time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_aid_stock_time ON app.ai_decisions (stock_code, decision_time DESC);
CREATE INDEX IF NOT EXISTS idx_aid_created ON app.ai_decisions (created_at DESC);
```

### 3) 智能盯盘：交易记录（hypertable）
替代 `smart_monitor_db.py` 中 `trade_records`。

```sql
CREATE TABLE IF NOT EXISTS app.trade_records (
  id            BIGSERIAL PRIMARY KEY,
  stock_code    TEXT NOT NULL,
  stock_name    TEXT,
  trade_type    TEXT NOT NULL,
  quantity      INT,
  price         NUMERIC,
  amount        NUMERIC,
  order_id      TEXT,
  order_status  TEXT,
  ai_decision_id BIGINT,                -- 暂不加 FK
  trade_time    TIMESTAMPTZ NOT NULL,
  commission    NUMERIC DEFAULT 0,
  tax           NUMERIC DEFAULT 0,
  profit_loss   NUMERIC DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
SELECT create_hypertable('app.trade_records', 'trade_time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_tr_stock_time ON app.trade_records (stock_code, trade_time DESC);
CREATE INDEX IF NOT EXISTS idx_tr_created ON app.trade_records (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tr_order ON app.trade_records (order_id);
```

### 4) 智能盯盘：监控任务（regular table）
替代 `smart_monitor_db.py` 中 `monitor_tasks`（配置型，无明显时间线）。

```sql
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
);

CREATE INDEX IF NOT EXISTS idx_mt_enabled ON app.monitor_tasks (enabled);
```

> 如需保留历史变更，可新增 `app.monitor_task_history`（hypertable）。当前按需求保留为普通表。

### 5) 智能盯盘：持仓监控（regular table）
替代 `smart_monitor_db.py` 中 `position_monitor`（当前持仓快照，不走时间序列）。

```sql
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
);

CREATE INDEX IF NOT EXISTS idx_pm_status ON app.position_monitor (status);
```

### 6) 通知（hypertable）
替代 `smart_monitor_db.py` 中 `notifications`（事件型）。

```sql
CREATE TABLE IF NOT EXISTS app.notifications (
  id            BIGSERIAL PRIMARY KEY,
  stock_code    TEXT,
  notify_type   TEXT NOT NULL,
  notify_target TEXT,
  subject       TEXT,
  content       TEXT,
  status        TEXT DEFAULT 'pending',
  error_msg     TEXT,
  sent_at       TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
SELECT create_hypertable('app.notifications', 'created_at', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_ntf_status_created ON app.notifications (status, created_at DESC);
```

### 7) 系统日志（hypertable）
替代 `smart_monitor_db.py` 中 `system_logs`（日志事件）。

```sql
CREATE TABLE IF NOT EXISTS app.system_logs (
  id         BIGSERIAL PRIMARY KEY,
  log_level  TEXT,
  module     TEXT,
  message    TEXT,
  details    TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
SELECT create_hypertable('app.system_logs', 'created_at', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_log_level_created ON app.system_logs (log_level, created_at DESC);
```

### 8) 组合/持仓（regular tables）
替代潜在的 `portfolio_db.py` 等（无明确时间线的当前状态）。

```sql
CREATE TABLE IF NOT EXISTS app.portfolios (
  id          BIGSERIAL PRIMARY KEY,
  name        TEXT NOT NULL UNIQUE,
  owner       TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.portfolio_positions (
  id            BIGSERIAL PRIMARY KEY,
  portfolio_id  BIGINT NOT NULL,    -- 暂不加 FK
  ts_code       TEXT NOT NULL,
  quantity      NUMERIC NOT NULL,
  cost_price    NUMERIC,
  last_updated  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (portfolio_id, ts_code)
);

CREATE INDEX IF NOT EXISTS idx_pos_portfolio ON app.portfolio_positions (portfolio_id);
```

### 9) 行业/策略信号（hypertable）
替代 `sector_strategy_db.py` 等中按时间生成的信号类数据。

```sql
CREATE TABLE IF NOT EXISTS app.sector_signals (
  id           BIGSERIAL PRIMARY KEY,
  sector_code  TEXT NOT NULL,
  signal_time  TIMESTAMPTZ NOT NULL,
  score        NUMERIC,
  payload      JSONB,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
SELECT create_hypertable('app.sector_signals', 'signal_time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_ss_sector_time ON app.sector_signals (sector_code, signal_time DESC);
```

### 10) 龙虎榜（hypertable）
替代 `longhubang_db.py` 等。

```sql
CREATE TABLE IF NOT EXISTS app.longhubang (
  id          BIGSERIAL PRIMARY KEY,
  ts_code     TEXT NOT NULL,
  trade_date  DATE NOT NULL,
  direction   TEXT,
  amount      NUMERIC,
  ratio       NUMERIC,
  payload     JSONB,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
SELECT create_hypertable('app.longhubang', 'created_at', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_lhb_code_date ON app.longhubang (ts_code, trade_date DESC);
```

> 以上为主要表设计；其余 SQLite 表可按相同模式映射：时间线类 → hypertable；配置/当前状态类 → regular table。

## 索引与性能
- 时间序列表：建议统一建立 `(key, time DESC)` 复合索引与 `time DESC` 索引。
- JSONB 字段：按需要建立 GIN 索引（如 `final_decision`）。
- 可选：对高频写入日志/通知表开启 TimescaleDB 压缩与保留策略（后续阶段）。

## 数据访问层（DAL）设计
- 新建模块：`app_pg.py`（或 `db_pg.py`），职责：
  - 读取 `.env` 的 `TDX_DB_*`，管理 psycopg2 连接（可选连接池）。
  - 提供 `fetch_all(sql, params)`、`execute(sql, params)`、`execute_values()` 等方法。
- 为每个原 SQLite 类提供等价的 Repository：
  - `PgStockAnalysisRepository`：`save_analysis` / `get_all_records` / `get_record_by_id` / `delete_record` / `get_record_count`。
  - `PgSmartMonitorRepository`：封装 monitor_tasks / ai_decisions / trade_records / position_monitor / notifications / system_logs 的 CRUD。
- UI/业务代码仅替换导入（从 `database.py`/`smart_monitor_db.py` 切换到对应 Pg*Repository）。

## 初始化与迁移
- 新建脚本：`scripts/init_app_schema.py`
  - 读取 `.env`，创建 `app.*` 表并执行 `create_hypertable` 与索引。
- 迁移脚本（示例）`scripts/migrate_sqlite_to_timescale.py`
  - 遍历每个 SQLite 源：读取行 → 字段转换（TEXT→JSONB、TEXT→TIMESTAMPTZ 等）→ 批量写入 TimescaleDB（`execute_values`）。
  - 优先迁移：analysis_records、ai_decisions、trade_records、notifications、system_logs。
- 校验脚本：`scripts/verify_migration.py`
  - 对比迁移前后行数、抽样对比关键字段、生成报告。

## 切换与回滚
- **切换**：
  - 部署 DAL 替换 + 执行 `init_app_schema.py` + 迁移历史数据。
  - 配置文件 `.env` 中 `TDX_DB_*` 已生效；删除/停用对 SQLite 文件的任何写入路径。
- **回滚**：
  - 保留 SQLite 文件为只读备份；若出现重大问题，临时切换回旧 DAL（不建议长期保留）。

## 任务拆分与里程碑
- **M1：Schema 与 DAL**
  - 完成 `init_app_schema.py` 和 DAL 模块；通过 db_diag 验证连通。
- **M2：替换 analysis_records**
  - 实现 `PgStockAnalysisRepository` 并替换调用点；功能回归。
- **M3：替换智能盯盘**
  - 实现 `PgSmartMonitorRepository` 并替换调用点；迁移相关数据；功能回归。
- **M4：其余 SQLite 模块**
  - 按表映射模板迁移（如 portfolio、sector、longhubang 等）；统一接入 DAL。
- **M5：性能与保留策略（可选）**
  - 针对高吞吐表配置压缩与保留；必要时加 GIN/BRIN 索引。

## 附录：类型映射与时间处理
- `INTEGER PRIMARY KEY AUTOINCREMENT` → `BIGSERIAL PRIMARY KEY`。
- `TEXT`（时间）→ `TIMESTAMPTZ`（尽量记录 UTC，前端按需转换时区）。
- `TEXT`（JSON）→ `JSONB`。
- 货币/比率 → `NUMERIC`（指定精度可后续细化）。

---

如确认本设计，我将依次提交：
- `scripts/init_app_schema.py`（DDL 初始化）
- `app_pg.py`（统一连接/DAL）
- `PgStockAnalysisRepository` 与 `PgSmartMonitorRepository` 的落地实现
- `migrate_sqlite_to_timescale.py`（迁移）与 `verify_migration.py`（校验）
