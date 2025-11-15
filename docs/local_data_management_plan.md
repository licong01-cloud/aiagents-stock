# 本地数据管理（TDX）重构设计与执行计划

本文档规划“本地数据管理”模块的初始化与增量数据同步方案，基于本地 TDX 接口与 TimescaleDB。目标是：
- 初始化同步通过手动执行，支持“日线 RAW”和“1 分钟 RAW”两类；点击后可直接执行；执行时前端显示进度条（含新增记录数），每 5 秒刷新一次。
- 增量同步支持调度配置：日线每日固定时间；分钟线每天多次。与初始化复用相同入库策略，自动处理数据冲突并具备断点续传。
- 数据层新增“日线 RAW、日线 QFQ（前复权）、日线 HFQ（后复权）”，其中 QFQ/HFQ 由 RAW + Tushare adj_factor 计算生成。生成前先清理目标范围。
- 所有操作可中断后继续运行，具备完整的作业与检查点记录、可视化状态与日志。

---

## 1. 现状与缺口

- 已有：
  - 后端 FastAPI（tdx_backend.py）+ 进程内调度器（tdx_scheduler.py）+ DB 表（ingestion_* 系列、kline_daily_qfq、kline_minute_raw 等）。
  - UI（tdx_ui.py）支持“数据入库调度”的手动/调度触发，但缺少“初始化确认 + 进度条 + 5 秒轮询”。
  - 脚本：ingest_full_daily.py、ingest_full_minute.py、ingest_incremental.py（尚未全量对接进度/任务表）。
- 缺口：
  - 表：缺少 kline_daily_raw、kline_daily_hfq。
  - 端到端：初始化“手动执行 + 确认清空 + 进度条轮询”闭环；任务分片与可视化进度；断点续传状态化；复权生成管线。

---

## 2. 数据库设计（TimescaleDB）

在 scripts/init_market_schema.py 中新增：

- 表：kline_daily_raw（原始未复权）
  - 字段：
    - trade_date DATE NOT NULL
    - ts_code CHAR(9) NOT NULL
    - open_li INT4 NOT NULL
    - high_li INT4 NOT NULL
    - low_li INT4 NOT NULL
    - close_li INT4 NOT NULL
    - volume_hand INT8 NOT NULL
    - amount_li INT8 NOT NULL
    - adjust_type CHAR(4) NOT NULL DEFAULT 'none' CHECK (adjust_type='none')
    - source VARCHAR(16) NOT NULL CHECK (source IN ('tdx_api','tdx_vipdoc'))
    - PRIMARY KEY (ts_code, trade_date)
  - Hypertable: time_column = trade_date
  - 索引：ts_code, trade_date DESC
  - 压缩与保留策略：参考 kline_daily_qfq

- 表：kline_daily_hfq（后复权）
  - 字段结构与 kline_daily_qfq 一致，差异：
    - adjust_type CHAR(3) NOT NULL DEFAULT 'hfq' CHECK (adjust_type='hfq')
  - Hypertable / 索引 / 压缩与保留：同上

- 说明：
  - 继续保留 kline_daily_qfq（前复权）现有结构。
  - ingestion_runs、ingestion_checkpoints、ingestion_errors、ingestion_jobs、ingestion_job_tasks、ingestion_state、ingestion_logs 已存在，后续用于断点续传与进度追踪。

---

## 3. 数据来源与接口

- 日线与分钟线 RAW：
  - 优先 TDX 本地 API（TDX_API_BASE，默认 http://localhost:8080），接口规范参考 tdx_doc。
  - 失败时可记录错误并重试，遵循 backoff 参数（重试次数/等待）。
- 复权：
  - 使用 Tushare adj_factor（日频）进行因子换算，生成 QFQ/HFQ。
  - 需要配置 TUSHARE_TOKEN。

---

## 4. 初始化（手动执行）

- 入口：UI 新增“初始化”页签，提供两种互斥选择：
  - 初始更新：日 K 线（kline_daily_raw）
  - 初始更新：1 分钟 K 线（kline_minute_raw）
- 操作流程：
  1) 用户选择“日线”或“分钟”初始化，并选择范围（交易所/起止日期/代码范围可选）。
  2) 点击“开始初始化”→ 弹出二次确认对话框，提示“将 TRUNCATE 相关目标表（支持只清理所选代码/范围）”。
  3) 确认后，后端创建 ingestion_jobs 记录与批量 ingestion_job_tasks（按代码批 + 日期分片）。
  4) UI 展示一个进度卡片：
     - 进度条（基于任务完成数/总任务数）。
     - 新增记录计数（累计插入/更新数量）。
     - 错误计数与最近错误摘要。
  5) UI 每 5 秒轮询后端“作业状态”API 更新显示，直至“完成/失败”。
- 重要约束：
  - 初始化只能手动执行（后端校验：mode == init 时仅接受 UI 触发，不从 schedule 驱动）。
  - TRUNCATE/清理策略：
    - 全量初始化：TRUNCATE 目标表；
    - 范围初始化：DELETE 目标范围（如 ts_code in (...) 且 trade_date between ...）。
  - 幂等 UPSERT：避免重复写导致冲突（ON CONFLICT UPDATE）。

---

## 5. 增量（调度与手动）

- 日线：每日固定时间（如交易日 18:00）运行一次。
- 分钟：每日多次（例如每 30 分钟一次），非交易时段自跳过。
- 后端：沿用 ingestion_schedules 表 + tdx_scheduler 周期触发；同时保留“立即执行”手动触发。
- 策略：
  - 使用 ingestion_state 记录 last_success_date/last_success_time（dataset+ts_code 粒度）。
  - 每次增量：从上次成功断点向后对齐补齐；分钟线支持“max_empty N 天后停止”策略。
  - 冲突处理：全量使用 UPSERT；严格比较（如时间戳 + ts_code + freq/日期）作为主键。

---

## 6. 复权生成（RAW -> QFQ/HFQ）

- 输入：kline_daily_raw 与 Tushare adj_factor（ts_code + trade_date + adj_factor）。
- 输出：kline_daily_qfq、kline_daily_hfq。
- 策略：
  - QFQ：使用“前复权”规则。常见实现：
    - 设当日因子为 F(t)，基准为最新交易日因子 F(T)。
    - 价格前复权：P_qfq(t) = P_raw(t) × F(t) / F(T)。
  - HFQ：使用“后复权”规则（相反方向）：
    - 价格后复权：P_hfq(t) = P_raw(t) × F(t) / F(t0)，t0 为最早交易日因子或另一定义基准。
  - 体积与金额：通常不复权（可保留 RAW 数值）。
- 流程：
  1) 选择代码范围与时间范围；
  2) 删除目标范围在 qfq/hfq 表的旧数据；
  3) 计算生成并批量 UPSERT；
  4) 记录生成摘要与错误；
- 增量：按更新到的新 RAW 日期范围 + 最新 adj_factor 变化范围计算；支持全量重算某一代码。

---

## 7. 后端 API 设计

可复用既有 /api/ingestion/run + /api/ingestion/schedule，新增/扩展：

- 运行初始化：POST /api/ingestion/run
  - body: { dataset: 'kline_daily_raw'|'kline_minute_raw', mode: 'init', options: { exchanges, start_date, end_date, limit_codes, truncate: true|false } }
  - 返回：{ run_id, job_id }
- 作业状态：GET /api/ingestion/job/{job_id}
  - 返回：
    - meta：job_id、status（queued|running|success|failed|canceled）、created/started/finished
    - progress：total_tasks、done_tasks、failed_tasks、percent
    - counters：inserted_rows、updated_rows、skipped_rows、error_rows
    - recent_errors：最近 N 条
- 断点续传：
  - 在任务级别：ingestion_job_tasks.status + progress + retries
  - 在数据级别：ingestion_state（dataset+ts_code 的 last_success_date/time）
- 清理/复权：
  - POST /api/adjust/rebuild
    - body: { ts_codes: [...], date_from, date_to, mode: 'qfq'|'hfq'|'both', truncate_target_first: true }
    - 后端将生成一个作业（job）并提供 /api/ingestion/job/{job_id} 状态查询

---

## 8. 入库脚本与调度器对接

- ingest_full_daily.py / ingest_full_minute.py：
  - 接收 options，分批处理（代码批×日期分片），每批完成后：
    - 更新 ingestion_job_tasks 进度与结果计数；
    - 必要时写入 ingestion_checkpoints；
  - 进程结束时汇总写入 ingestion_jobs.summary；
- ingest_incremental.py：
  - 读取 ingestion_state 断点，按 dataset+ts_code 动态确定起点；
  - 完成后更新 ingestion_state。
- tdx_scheduler：
  - 对 “init” 严格要求 only manual；
  - 对 “incremental” 按 schedule 运行（如 daily at 18:00 / every 30m）。

---

## 9. 前端 UI 交互

- 新的“本地数据管理”页签结构：
  - 初始化（Init）
    - 选择类型：日线 RAW / 1 分钟 RAW（单选）
    - 参数：交易所/日期范围/代码范围/是否 TRUNCATE（默认勾选，触发二次确认弹窗）
    - 按钮：开始初始化 → 出现进度卡片（进度条 + 计数 + 错误摘要）
    - 轮询：每 5 秒刷新一次 `/api/ingestion/job/{job_id}`
  - 增量（Incremental）
    - 配置频率：日线每日时刻；分钟线多次（下拉选 10m/30m/1h）
    - 保存生效后展示 schedule 列表；支持立即运行
  - 运行日志
    - 汇总 ingestion_logs、最近错误、进度快照

---

## 10. 冲突处理与幂等

- 主键：
  - 日线：PRIMARY KEY (ts_code, trade_date)
  - 分钟：PRIMARY KEY (ts_code, trade_time, freq)
- 写入：全部使用 INSERT ... ON CONFLICT DO UPDATE。
- 时序一致性：同一代码同一日期/时刻多次入库不影响最终结果。

---

## 11. 断点续传与失败重试

- 批任务级断点：ingestion_job_tasks.status/progress/retries。
- 数据级断点：ingestion_state.last_success_date/time。
- 重试策略：指数退避（可配置），失败 N 次后标记失败并汇总到 recent_errors；支持“仅重试失败分片”。

---

## 12. 安全与性能

- 后端：限制“init”仅接受 UI 触发（需要权限控制时可添加 token/白名单）。
- 批大小与并发：可配置（默认批 100 代码；日线按日期分段，分钟按天分段）。
- 数据库：开启压缩与保留策略、必要索引；批量写使用 execute_values。

---

## 13. 分阶段实施计划

- Phase 1（后端 + UI 基础闭环）
  - 新增表：kline_daily_raw、kline_daily_hfq（schema/索引/策略）
  - 后端：/api/ingestion/job/{job_id} 状态查询；初始化触发支持 truncate + 任务拆分
  - UI：初始化页签 + 二次确认弹窗 + 进度条/计数 + 5 秒轮询
  - 脚本：full daily/minute 接入任务表与进度更新
- Phase 2（增量与调度）
  - ingestion_state 断点接入 + incremental 脚本增强
  - UI 增量页签：调度配置、立即运行
  - 调度：日线 daily；分钟 30m（可配）
- Phase 3（复权管线）
  - /api/adjust/rebuild 实现 + UI 入口
  - 从 RAW 生成 QFQ/HFQ（全量/增量/重算），前清理目标范围
  - 校验与验收（抽样核对价格、因子一致性）

---

## 14. 交付与验收标准

- 初始化：
  - UI 操作 → 后端作业 → 进度可见（每 5 秒刷新）→ 任务完成；
  - 表数据满足主键与约束；抽样校验记录数与源端一致；
- 增量：
  - 日线每日更新一次；分钟多次；断点续传有效；
  - 冲突无异常（UPSERT 幂等）；
- 复权：
  - QFQ/HFQ 与 Tushare 样例对齐（允许极小数值差）；
  - 重算流程支持前清理；
- 文档：
  - 使用指南、常见问题（uvicorn/fastapi、Tushare Token、端口与 .env 配置）。

---

## 15. 环境与配置

- .env
  - TDX_API_BASE（默认 http://localhost:8080）
  - TDX_BACKEND_BASE（默认 http://127.0.0.1:9000）
  - TDX_DB_HOST/PORT/USER/PASSWORD/NAME
  - TUSHARE_TOKEN（复权必需）
- 依赖
  - fastapi、uvicorn、psycopg2-binary、schedule、pandas、requests、python-dotenv

---

## 16. 后续工作清单（与仓库 TODO 对应）

- 数据库：新增 RAW/HFQ 表定义与初始化脚本更新。
- 后端：初始化作业 API 与状态查询，整合任务表与断点续传。
- 脚本：full/incremental 改造为分片+进度可视；
- UI：新增“初始化/增量”页签与 5 秒轮询进度条；
- 复权：从 RAW + adj_factor 计算生成 QFQ/HFQ（前清理、UPSERT、增量/重算）；
- 文档与验收：更新 README、提供使用指导与校验方案。
