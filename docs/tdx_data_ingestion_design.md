# TDX 数据入库与增量同步设计方案（TDX-only）

> 版本：v1.0（仅文档，未执行）
> 范围：仅使用 TDX 作为数据源；初始化覆盖所有可用的 TDX 数据集；分钟线以 1 分钟原始为事实层，5/15/60 分钟由连续聚合生成；接口聚合 K 线镜像保存为可选（默认关闭）。

## 1. 概述与默认参数
- **数据源**：TDX 本地服务（Base URL 由环境配置 `TDX_API_BASE` 提供）
- **数据库**：TimescaleDB（PostgreSQL）
- **默认参数**：
  - DB：localhost:5432 / aistock / postgres / lc78080808 / schema=market / sslmode=disable
  - 并发=6，批量=2000，API 超时=10s，重试=3
  - 时区：Asia/Shanghai
  - 分钟线初始化范围：优先 VIPDOC 回填 + API 补齐；若无 VIPDOC，则近 3 年
  - 逐笔初始化范围：近 60 个交易日

## 2. 单位与口径
- 价格/金额：厘（int）；1 元 = 1000 厘
- 成交量：手（int）；1 手 = 100 股
- 日/周/月 K 线：前复权（QFQ），固定 `adjust_type='qfq'`
- 分钟线与逐笔：不复权（raw），固定 `adjust_type='none'`
- 对外查询可提供“规范化视图”（厘→元、手→股），避免重复存储

## 3. 数据模型（schema=market）

### 3.1 维表
- **symbol_dim**
  - ts_code char(9) PK（如 000001.SZ）
  - symbol char(6)、exchange char(2) IN ('SH','SZ','BJ')
  - name varchar(64)、industry varchar(64)、list_date date（可选）

### 3.2 K 线表（前复权 QFQ）
- **kline_daily_qfq / kline_weekly_qfq / kline_monthly_qfq**
  - 日期键：trade_date / week_end_date / month_end_date（Hypertable 时间键）
  - 列：open_li/high_li/low_li/close_li int4、volume_hand int8、amount_li int8
  - adjust_type char(3) = 'qfq'（CHECK）
  - source varchar(16) IN ('tdx_api','tdx_vipdoc')
  - 约束：PK(ts_code, 日期键)；索引：(ts_code, 日期键 DESC)
  - 策略：30 天后压缩；长期保留

### 3.3 分钟线（1m 原始，不复权）
- **kline_minute_raw**
  - trade_time timestamptz（Hypertable 时间键）
  - ts_code char(9)、freq='1m'
  - open_li/high_li/low_li/close_li int4（至少 close_li 非空）
  - volume_hand int8、amount_li int8（可空）
  - adjust_type='none'，source IN ('tdx_api','tdx_vipdoc')
  - 唯一：PK(ts_code, trade_time, freq)
  - 分区：chunk_time_interval=1 day；space partition：ts_code，number_partitions=16～32
  - 索引：(ts_code, trade_time DESC)；压缩：7 天后；保留：3～5 年

### 3.4 逐笔成交（不复权）
- **tick_trade_raw**
  - trade_time timestamptz、ts_code char(9)
  - price_li int4、volume_hand int4、status smallint（可空）
  - source='tdx_api'
  - 幂等键：ts_code+trade_time+price_li+volume_hand+coalesce(status,-1)
  - Hypertable；建议 180 天～1 年保留，7～14 天后压缩

### 3.5 指数 K 线（前复权 QFQ）
- **index_kline_daily_qfq / weekly_qfq / monthly_qfq**
  - 同日/周/月表，增加 up_count、down_count

### 3.6 快照表
- **stock_info**：ts_code PK、name、industry、market、area?、list_date?、ext_json jsonb、updated_at
- **quote_snapshot**：snapshot_time、ts_code、last_li/open_li/high_li/low_li/close_li、total_hand、amount_li、inside_dish、outer_disc、intuition、server_time_ts?、buy_levels jsonb、sell_levels jsonb；PK(ts_code, snapshot_time)
- **market_stats_snapshot**：snapshot_time PK、stats jsonb

### 3.7 控制与依赖表
- **ingestion_jobs / ingestion_job_tasks / ingestion_state / ingestion_logs**：作业、任务、断点续传与日志
- **trading_calendar**：cal_date PK、is_trading boolean

## 4. 连续聚合（CAGG）
- 由 1m 原始生成 `kline_5m / kline_15m / kline_60m`
- 聚合规则：
  - open_li=first(open_li, trade_time)
  - high_li=max(high_li)
  - low_li=min(low_li)
  - close_li=last(close_li, trade_time)
  - volume_hand=sum(volume_hand)、amount_li=sum(amount_li)
- 刷新：实时 + 收盘后回补最近 2 天
- 压缩：14 天后；保留：10 年

## 5. 数据源端点映射（TDX-only）
- codes → GET /api/codes?exchange=sh|sz|bj|all → symbol_dim
- stock_info → GET /api/stock-info?code → stock_info
- quote_snapshot → GET /api/quote?code 或 POST /api/batch-quote → quote_snapshot
- market_stats_snapshot → GET /api/market-stats → market_stats_snapshot
- kline_daily_qfq/weekly_qfq/monthly_qfq → GET /api/kline?type=day|week|month；增量：GET /api/kline-history?limit=30
- minute_1m → GET /api/minute?code&date=YYYYMMDD → kline_minute_raw
- tick_trade → GET /api/trade?code&date=YYYYMMDD → tick_trade_raw
- index_kline → GET /api/index?code=sh000001&type=day|week|month → index_kline_*_qfq
- 可选镜像（默认关闭）：GET /api/kline?type=minute5|minute15|minute30|hour → 镜像表
- 全量批量接口：
  - GET /api/kline-all?code=XXX&type=day&limit=200 → 加速单支股票的历史补齐（初始化阶段）
  - GET /api/index/all?code=sh000001&type=day&limit=200 → 指数历史补齐
  - GET /api/trade-history/full?code=XXX&limit=300 → 逐笔成交全量拉取
  - GET /api/workday/range?start=YYYYMMDD&end=YYYYMMDD → trading_calendar 批量写入

### 5.1 批量与全量接口策略
- **初始化阶段**：优先使用 `/api/kline-all`、`/api/index/all`、`/api/trade-history/full`、`/api/workday/range` 等批量接口，一次请求覆盖 200～300 条记录，显著减少往返次数。
- **任务划分**：按照股票代码列表切分批次（默认 2000 条/批），每批触发一组批量请求；若批量接口返回 `data.list` 结构，统一落库前先解包。
- **兼容性**：批量接口若返回空，回退至单日接口（如 `/api/kline`、`/api/trade`）确保完整性。
- **超时策略**：批量接口使用独立的 bulk timeout（默认 30s，可配置，<=0 表示不设限），成功返回数据则视为用时可接受。
- **断点续传**：`ingestion_state` 针对批量接口存储 `cursor_date/cursor_id`，遇到长列表时拆分多次调用，确保失败重试时继续剩余区间。

### 5.2 每日增量与实时更新
- **收盘后批处理**：使用 `/api/kline-history`、`/api/trade-history/full` 的 `before`/`limit` 游标参数补齐前一交易日数据；若接口提供批量历史（如 `/api/kline-all`），则传入较小 limit（如 50），在一个请求内补齐当日。
- **分钟与逐笔实时补齐**：交易时段内按 1～5 分钟频率查询 `/api/minute`、`/api/trade` 的最新片段；收盘后统一使用批量全量接口做 reconcile，发现缺口则触发补偿任务。
- **指数与市场概览**：实时更新 `/api/index`（或批量 `/api/index/all`），以及 `/api/market-count`、`/api/workday/range` 等元数据，保证 dashboard 与调度对齐。
- **任务 API 集成**：结合 `/api/tasks/*` 触发长耗时批次，前端展示进度并根据 `task_id` 轮询状态；取消任务后可由 `ingestion_state` 保障续跑。

## 6. 后端 API 契约（管理作业）
- POST `/api/db/config/test`：测试 DB 连接
- POST `/api/db/config/save`：保存 DB 配置
- POST `/api/ingestion/start`：启动作业
  - body：datasets、symbols/exchanges、date_range、mode=init|incremental、concurrency、batch_size、timeout、retries
  - resp：{ job_id }
- GET `/api/ingestion/status?job_id=...`：获取作业与子任务进度
- POST `/api/ingestion/cancel`：取消作业
- POST `/api/ingestion/retry`：对失败清单或整体重试
- GET `/api/ingestion/logs?job_id=...`：查询日志
- POST `/api/ingestion/schedule`：创建/更新调度任务
- GET `/api/ingestion/schedule`：查询调度配置列表（含启用状态、频率、任务类型）
- POST `/api/ingestion/schedule/{schedule_id}/toggle`：启用/停用调度任务
- POST `/api/ingestion/schedule/{schedule_id}/run`：针对既有调度立即排队执行
- GET `/api/ingestion/logs`：查询近期入库日志（结构化 JSON，有 run_id / level / payload）
- POST `/api/testing/run`：触发数据源测试脚本执行（同步或异步）
- POST `/api/testing/schedule` / GET `/api/testing/schedule` / toggle / run：管理测试脚本的定时执行与即时触发

示例请求（启动 init）：
```json
{
  "mode": "init",
  "datasets": ["codes","stock_info","kline_daily_qfq","minute_1m","index_kline","cagg_5m","cagg_15m","cagg_60m","quote_snapshot"],
  "exchanges": ["sh","sz","bj"],
  "date_range": {"from": null, "to": null},
  "concurrency": 6,
  "batch_size": 2000,
  "timeout": 10,
  "retries": 3
}
```

### 5.3 后台调度服务

- **核心组件**：
  - `tdx_scheduler.py`：基于 `schedule` + `ThreadPoolExecutor` 的统一调度器，提供手动触发、定时任务、执行状态刷新、结构化日志写入。
  - `tdx_backend.py`：FastAPI 服务，封装调度/执行 REST 接口；启动时自动拉起调度器并周期刷新数据库中的调度配置。
- **状态存储**：
  - `market.testing_schedules`：测试调度定义（frequency/options/last_run/next_run）。
  - `market.testing_runs`：测试执行记录（run_id、status、summary/detail/log）。
  - `market.ingestion_schedules`：入库调度定义（dataset/mode/frequency/options/last_run/next_run）。
  - `market.ingestion_logs`：入库过程日志（JSON payload 含 run_id、summary、error、stdout/stderr）。
- **Next Run 计算**：调度器每次载入或执行任务后会将下一次运行时间写回数据库，供前端直接展示。
- **执行命令**：默认调用 `scripts/test_tdx_all_api.py`、`scripts/ingest_incremental.py`、`scripts/ingest_full_daily.py`、`scripts/ingest_full_minute.py`，可通过调度 options 覆盖脚本路径及 CLI 参数。

> 运行方式：`uvicorn tdx_backend:app --host 0.0.0.0 --port 9000`，前端通过 `TDX_BACKEND_BASE` 环境变量访问该服务。

## 7. 幂等性、重试与断点续传
- 所有写入 UPSERT；唯一/主键与幂等键保障重复写不产生脏数据
- `ingestion_state(dataset, ts_code, last_success_date/time, cursor_payload)` 驱动断点续传；批量接口存储最后一次成功的游标（日期或 ID 列表）
- `ingestion_jobs` 记录任务配置（并发、批量大小、bulk timeout），失败后重试时读取相同配置，确保行为一致
- 失败重试：指数退避 + 最大重试次数；UI 可选择失败清单重试

## 8. 性能与安全
- 批量：优先 COPY，降级 `execute_values`（1k～10k/批），事务控制
- 并发：默认 6；分钟/逐笔建议 3～6（按服务压力调整）。批量接口结合 worker 池（单节点多进程或多线程），任务按 `exchange`、`code_range` 分片；若使用 celery/RQ 等队列，需在任务 payload 中包含游标以便重试。
- 调度执行：
  - **Worker 池**：统一使用任务调度器（如 APScheduler + Celery/RQ）；`testing` 与 `ingestion` 作业共享 worker 池但区分队列，以保障批量接口与测试脚本不互相阻塞。
  - **资源隔离**：提供最大并发阈值、速率限制和 bulk timeout 配置，避免过度占用 TDX 服务。
- API：超时 10s；非交易日回退上一交易日；错误记录与告警
- 安全：DB 密码不回显；日志脱敏

## 9. 验收标准（DoD）
- DB 配置可保存/测试
- 初始化与增量可发起；进度/日志/结果可视化
- 失败重试与断点续传有效
- CAGG 刷新后 5/15/60m 可查
- 全链路仅依赖 TDX

## 10. 示例 SQL（示意，非迁移脚本）
```sql
-- 必要扩展
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE SCHEMA IF NOT EXISTS market;

-- 维表
CREATE TABLE IF NOT EXISTS market.symbol_dim (
  ts_code char(9) PRIMARY KEY,
  symbol char(6) NOT NULL,
  exchange char(2) NOT NULL CHECK (exchange IN ('SH','SZ','BJ')),
  name varchar(64),
  industry varchar(64),
  list_date date
);

-- 日线 QFQ（周/月同理）
CREATE TABLE IF NOT EXISTS market.kline_daily_qfq (
  trade_date date NOT NULL,
  ts_code char(9) NOT NULL,
  open_li int4 NOT NULL,
  high_li int4 NOT NULL,
  low_li  int4 NOT NULL,
  close_li int4 NOT NULL,
  volume_hand int8 NOT NULL,
  amount_li int8 NOT NULL,
  adjust_type char(3) NOT NULL DEFAULT 'qfq' CHECK (adjust_type='qfq'),
  source varchar(16) NOT NULL CHECK (source IN ('tdx_api','tdx_vipdoc')),
  PRIMARY KEY (ts_code, trade_date)
);
SELECT create_hypertable('market.kline_daily_qfq','trade_date', if_not_exists => TRUE);

-- 分钟 1m 原始
CREATE TABLE IF NOT EXISTS market.kline_minute_raw (
  trade_time timestamptz NOT NULL,
  ts_code char(9) NOT NULL,
  freq varchar(8) NOT NULL CHECK (freq='1m'),
  open_li int4,
  high_li int4,
  low_li  int4,
  close_li int4 NOT NULL,
  volume_hand int8,
  amount_li int8,
  adjust_type char(4) NOT NULL DEFAULT 'none' CHECK (adjust_type='none'),
  source varchar(16) NOT NULL CHECK (source IN ('tdx_api','tdx_vipdoc')),
  PRIMARY KEY (ts_code, trade_time, freq)
);
SELECT create_hypertable('market.kline_minute_raw','trade_time',
  chunk_time_interval => interval '1 day',
  partitioning_column => 'ts_code',
  number_partitions   => 16,
  if_not_exists       => TRUE
);
CREATE INDEX IF NOT EXISTS idx_minute_ts ON market.kline_minute_raw (ts_code, trade_time DESC);
ALTER TABLE market.kline_minute_raw SET (timescaledb.compress, compress_segmentby='ts_code,freq', compress_orderby='trade_time');

-- 逐笔原始
CREATE TABLE IF NOT EXISTS market.tick_trade_raw (
  trade_time timestamptz NOT NULL,
  ts_code char(9) NOT NULL,
  price_li int4 NOT NULL,
  volume_hand int4 NOT NULL,
  status smallint,
  source varchar(16) NOT NULL DEFAULT 'tdx_api' CHECK (source='tdx_api')
);
SELECT create_hypertable('market.tick_trade_raw','trade_time', if_not_exists => TRUE);

-- 指数日 K（周/月同理）
CREATE TABLE IF NOT EXISTS market.index_kline_daily_qfq (
  trade_date date NOT NULL,
  code varchar(16) NOT NULL,
  open_li int4 NOT NULL,
  high_li int4 NOT NULL,
  low_li  int4 NOT NULL,
  close_li int4 NOT NULL,
  volume_hand int8,
  amount_li int8,
  up_count int4,
  down_count int4,
  adjust_type char(3) NOT NULL DEFAULT 'qfq' CHECK (adjust_type='qfq'),
  source varchar(16) NOT NULL CHECK (source IN ('tdx_api','tdx_vipdoc')),
  PRIMARY KEY (code, trade_date)
);
SELECT create_hypertable('market.index_kline_daily_qfq','trade_date', if_not_exists => TRUE);

-- 快照
CREATE TABLE IF NOT EXISTS market.stock_info (
  ts_code char(9) PRIMARY KEY,
  name varchar(64), industry varchar(64), market varchar(16), area varchar(32), list_date date,
  ext_json jsonb,
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS market.quote_snapshot (
  snapshot_time timestamptz NOT NULL,
  ts_code char(9) NOT NULL,
  last_li int4, open_li int4, high_li int4, low_li int4, close_li int4,
  total_hand int8, amount_li int8,
  inside_dish int8, outer_disc int8, intuition int8,
  server_time_ts timestamptz,
  buy_levels jsonb, sell_levels jsonb,
  PRIMARY KEY (ts_code, snapshot_time)
);

CREATE TABLE IF NOT EXISTS market.market_stats_snapshot (
  snapshot_time timestamptz PRIMARY KEY,
  stats jsonb NOT NULL
);

-- 控制表（示意）
CREATE TABLE IF NOT EXISTS market.ingestion_jobs (
  job_id uuid PRIMARY KEY,
  job_type varchar(16) NOT NULL CHECK (job_type IN ('init','incremental')),
  status varchar(16) NOT NULL,
  created_at timestamptz DEFAULT now(),
  started_at timestamptz, finished_at timestamptz,
  summary jsonb
);

CREATE TABLE IF NOT EXISTS market.ingestion_job_tasks (
  task_id uuid PRIMARY KEY,
  job_id uuid NOT NULL,
  dataset varchar(64) NOT NULL,
  ts_code char(9),
  date_from date, date_to date,
  status varchar(16) NOT NULL,
  progress numeric(5,2) DEFAULT 0,
  retries int DEFAULT 0,
  last_error text,
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS market.ingestion_state (
  dataset varchar(64) NOT NULL,
  ts_code char(9),
  last_success_date date,
  last_success_time timestamptz,
  extra jsonb,
  PRIMARY KEY (dataset, ts_code)
);

CREATE TABLE IF NOT EXISTS market.ingestion_logs (
  job_id uuid NOT NULL,
  ts timestamptz DEFAULT now(),
  level varchar(8) NOT NULL,
  message text
);

CREATE TABLE IF NOT EXISTS market.trading_calendar (
  cal_date date PRIMARY KEY,
  is_trading boolean NOT NULL
);

-- 连续聚合（5m 示例；15m/60m 同理）
CREATE MATERIALIZED VIEW IF NOT EXISTS market.kline_5m
WITH (timescaledb.continuous) AS
SELECT
  ts_code,
  time_bucket('5 minutes', trade_time) AS bucket,
  '5m'::varchar(8) AS freq,
  first(open_li, trade_time)  AS open_li,
  max(high_li)                AS high_li,
  min(low_li)                 AS low_li,
  last(close_li, trade_time)  AS close_li,
  sum(volume_hand)            AS volume_hand,
  sum(amount_li)              AS amount_li
FROM market.kline_minute_raw
GROUP BY ts_code, bucket;
```
