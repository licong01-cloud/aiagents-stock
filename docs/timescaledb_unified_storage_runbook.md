# TimescaleDB 统一存储迁移执行步骤（Runbook）

本 Runbook 按《docs/timescaledb_unified_storage_design.md》设计严格拆解执行步骤，细化每步的范围、目标、前置条件、执行动作、校验与回滚指引。完成后，程序的本地化数据全部统一存储到 TimescaleDB（PostgreSQL），取消 SQLite 的读写路径。

---

## M0. 盘点与冻结（Inventory & Freeze）
- **范围**
  - 所有仍在使用 SQLite 的模块：
    - database.py（analysis_records）
    - smart_monitor_db.py（monitor_tasks、ai_decisions、trade_records、position_monitor、notifications、system_logs）
    - 其他：monitor_db.py、portfolio_db.py、sector_strategy_db.py、longhubang_db.py、main_force_batch_db.py（含 backup_* 可忽略）
- **目标**
  - 明确所有 SQLite 写入点并短暂冻结写入（在迁移期间避免新数据落入 SQLite）。
- **前置条件**
  - 了解运行中的服务/计划任务，安排维护窗口或只读模式。
- **执行动作**
  - 将可能写 SQLite 的功能临时关闭或改为只读（例如在 UI 隐藏提交按钮）。
  - 备份所有 .db 文件到 backup/sqlite/YYYYMMDD/。
- **校验**
  - 确认迁移期间没有新的 SQLite 文件增长（文件时间戳不变）。
- **回滚**
  - 如需回滚，恢复前端按钮与原先的 SQLite 写路径。

---

## M1. 初始化 Schema（app.*）与 DDL 落地
- **范围**
  - 在现有数据库中创建 `app` schema 及所有应用侧表；历史/事件/信号类建为 hypertable，配置/持仓快照类为普通表（regular）。
- **目标**
  - 《设计》文档中列出的 DDL 全部在数据库创建成功。
- **前置条件**
  - `.env` 中 `TDX_DB_HOST/PORT/NAME/USER/PASSWORD` 正确可连；TimescaleDB 可用。
- **执行动作（二选一）**
  - 方案A：临时使用 psql 手工执行 DDL（推荐在维护窗口内）
    1. 使用 psql 连接到 DB：
       ```bash
       psql -h $TDX_DB_HOST -p $TDX_DB_PORT -U $TDX_DB_USER -d $TDX_DB_NAME
       ```
    2. 依次执行《设计》文档中 app.* 的 DDL 片段：
       - app.analysis_records（hypertable: created_at）
       - app.ai_decisions（hypertable: decision_time）
       - app.trade_records（hypertable: trade_time）
       - app.monitor_tasks（regular table）
       - app.position_monitor（regular table）
       - app.notifications（hypertable: created_at）
       - app.system_logs（hypertable: created_at）
       - app.portfolios、app.portfolio_positions（regular）
       - app.sector_signals（hypertable: signal_time）
       - app.longhubang（hypertable: created_at）
  - 方案B：在后续我将提供 `scripts/init_app_schema.py`，可一键创建上述对象。
- **校验**
  - 表存在：
    ```sql
    SELECT table_schema, table_name
    FROM information_schema.tables
    WHERE table_schema='app'
    ORDER BY table_name;
    ```
  - hypertable 状态：
    ```sql
    SELECT hypertable_name, schema_name, table_name
    FROM timescaledb_information.hypertables
    WHERE schema_name='app';
    ```
- **回滚**
  - 如需回滚，仅删除刚创建的 app.* 表（DROP TABLE … CASCADE）。注意不要影响 market.*。

---

## M2. 统一数据访问层（DAL）
- **范围**
  - 新增基于 psycopg2 的 Postgres DAL 模块（如 `app_pg.py` 或 `db_pg.py`）。
- **目标**
  - 提供 `fetch_all/execute/execute_values` 等方法；所有连接读取 `.env` 的 `TDX_DB_*`，无硬编码。
- **前置条件**
  - M1 已完成。
- **执行动作**
  - 新建模块：读取 `.env`，创建连接（可先简单直连，后续引入连接池）。
  - 暴露统一 API：
    - `fetch_all(sql, params)` 返回 RealDictCursor 结果
    - `execute(sql, params)` 单条写
    - `execute_values(sql, seq_of_params)` 批量写
  - 编写最小化健康检查（连通性、简单查询）。
- **校验**
  - 执行 DAL 健康检查 SQL 成功；无异常报错。
- **回滚**
  - 保留该模块但暂不在业务路径引用；原逻辑不变。

---

## M3. 替换 analysis_records 存取（SQLite → TimescaleDB）
- **范围**
  - `database.py` 中 `StockAnalysisDatabase` 功能迁移为 Timescale 实现（新建 `PgStockAnalysisRepository`）。
- **目标**
  - 保持原方法签名：`save_analysis/get_all_records/get_record_by_id/delete_record/get_record_count`；底层改用 TimescaleDB 的 app.analysis_records。
- **前置条件**
  - M1、M2 完成。
- **执行动作**
  1. 新建 `PgStockAnalysisRepository`：
     - 写入：JSON -> JSONB，datetime -> TIMESTAMPTZ（UTC）
     - 读取：与原返回结构保持一致
  2. 代码替换：将引用 `database.db` 的调用点切换到新仓库实现。
  3. 迁移历史数据：
     - 从 SQLite 读取 `analysis_records` 所有行
     - 字段转换后批量写入 `app.analysis_records`
- **校验**
  - 行数对比：迁移前后计数一致；抽样核对 JSON 内容与时间字段。
  - 业务回归：页面列表与详情接口正常。
- **回滚**
  - 切回旧的 SQLite 实现（保留开关/分支）；或临时屏蔽写入，仅读取 SQLite 备份。

---

## M4. 替换智能盯盘存取（SQLite → TimescaleDB）
- **范围**
  - `smart_monitor_db.py` 全量替换（或新建 `PgSmartMonitorRepository`）：
    - monitor_tasks（regular）
    - ai_decisions（hypertable）
    - trade_records（hypertable）
    - position_monitor（regular）
    - notifications（hypertable）
    - system_logs（hypertable）
- **目标**
  - 对外方法与返回结构保持不变；只替换存取后端。
- **前置条件**
  - M1、M2 完成。
- **执行动作**
  1. 新建 `PgSmartMonitorRepository`，将各表 CRUD 切换到 app.*。
  2. 编写迁移脚本：按表顺序迁移，字段转换（TEXT→JSONB/TIMESTAMPTZ，布尔值/数值类型校正）。
  3. 替换调用点。
- **校验**
  - 各表行数与抽样记录一致；UI 功能（添加任务、记录决策、写入交易、通知、日志）均正常。
- **回滚**
  - 暂时切回 SQLite 实现；保留 TimescaleDB 中已导入数据以备后续重试。

---

## M5. 替换其余 SQLite 模块
- **范围**
  - monitor_db.py、portfolio_db.py、sector_strategy_db.py、longhubang_db.py、main_force_batch_db.py 等。
- **目标**
  - 所有读写统一到 `app.*`，遵循“历史/事件 → hypertable；配置/当前状态 → regular”。
- **前置条件**
  - M1、M2 完成；模块具体表结构与字段对齐。
- **执行动作**
  - 逐模块迁移与替换；统一 DAL；编写一次性数据迁移；按模块回归。
- **校验**
  - 行数与关键字段一致；功能回归通过。
- **回滚**
  - 模块级别回滚到 SQLite；不影响已完成的其他模块。

---

## M6. 性能、索引与保留（可选增强）
- **范围**
  - 高吞吐表（notifications、system_logs、ai_decisions、trade_records 等）。
- **目标**
  - 通过索引、压缩、保留策略提升查询/存储效率。
- **前置条件**
  - 核心业务已切换到 TimescaleDB 并稳定运行。
- **执行动作**
  - 按《设计》添加/优化索引（如 `(key, time DESC)`、JSONB GIN）。
  - TimescaleDB 压缩与保留策略（按业务周期设置）。
- **校验**
  - 关键查询延迟与资源占用达标。
- **回滚**
  - 可关闭压缩/保留策略或回退索引变更。

---

## 验收清单（Acceptance Checklist）
- [ ] app.* 表全部创建成功，hypertable 正常（timescaledb_information.hypertables 可见）。
- [ ] DAL 连接 `.env` 的 TDX_DB_*，健康检查通过。
- [ ] analysis_records 读写切换至 TimescaleDB，功能回归通过。
- [ ] 智能盯盘六类表迁移与替换完成，功能回归通过。
- [ ] 其余模块迁移完成（如适用）。
- [ ] SQLite 写路径全部移除/停用，历史 .db 已归档备份。

---

## 参考命令与校验
- 查看 app.* 表：
  ```sql
  SELECT table_name FROM information_schema.tables WHERE table_schema='app' ORDER BY table_name;
  ```
- 查看 hypertable：
  ```sql
  SELECT hypertable_name FROM timescaledb_information.hypertables WHERE schema_name='app';
  ```
- 统计样例：
  ```sql
  SELECT count(*) FROM app.analysis_records;
  SELECT count(*) FROM app.ai_decisions;
  SELECT count(*) FROM app.trade_records;
  SELECT count(*) FROM app.notifications;
  SELECT count(*) FROM app.system_logs;
  ```

---

## 回滚策略（全局）
- 任一步骤失败：
  - 立即停止新写入；
  - 切回原 SQLite 存取实现（保留分支/特性开关）；
  - 保留已导入的 TimescaleDB 数据以供排查；
  - 修复后重复执行该步骤的“执行动作”与“校验”。

---

## 备注
- 本 Runbook 与《设计》文档配套执行，建议先在测试库验证再切换生产环境。
- 后续我会根据本 Runbook 逐步提交：DDL 初始化脚本、DAL 模块、模块替换与迁移脚本。
