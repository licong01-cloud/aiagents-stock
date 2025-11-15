# 通达信板块数据（Tushare）设计与实施方案

## 目标
- 在本地数据管理中新增 Tushare 数据源，支持“通达信板块”三类数据：
  - 板块信息 tdx_index → 表 market.tdx_board_index
  - 板块成分 tdx_member → 表 market.tdx_board_member
  - 板块行情 tdx_daily → 表 market.tdx_board_daily（TimescaleDB Hypertable）
- 初始化默认日期范围为最近 1 年，可自定义；支持增量同步。
- 兼容现有任务监控、入库日志、调度体系。

## 数据库设计
- Schema：market
- 表与主键
  - tdx_board_index(trade_date, ts_code) PK
  - tdx_board_member(trade_date, ts_code, con_code) PK
  - tdx_board_daily(trade_date, ts_code) PK（Hypertable: time=trade_date）
- 字段注释
  - 已按在线文档字段解释写入 COMMENT ON COLUMN（详见 scripts/init_market_schema.py 变更）。
- 索引与压缩
  - 常用查询键（ts_code、trade_date）建立索引
  - tdx_board_daily 启用 Timescale 压缩策略（orderby=trade_date, segmentby=ts_code）及 30 天压缩策略；保留策略 20 年。

## 同步策略
- 顺序：先拉板块信息(tdx_index) → 基于当天板块列表循环拉取成分与行情
- 初始化
  - 日期范围默认近 365 天（可自定义）
  - tdx_index：按日期逐日拉取；单次 ≤1000 行
  - tdx_member：按（日期×板块）循环；单次 ≤3000 行
  - tdx_daily：按日期批量；单次 ≤3000 行
- 增量
  - 以各表 MAX(trade_date)+1 为起点滚动到目标日期/今日
  - 今日未发布数据时，提示并纳入可重试
- 速率与重试
  - 批内小休眠（0.1~0.2s）
  - 失败记录 ingestion_logs，必要信息写入 ingestion_errors（后续可扩展）
- 幂等
  - 主键 UPSERT，批量 execute_values 写入

## 组件与改动
- DB
  - scripts/init_market_schema.py 增加三张表、索引、Hypertable、压缩/保留策略与列注释
- Ingestion 脚本
  - scripts/ingest_tushare_tdx_board.py：支持 --dataset（tdx_board_index/member/daily/all）、--mode（init/incremental）、--start-date/--end-date、--job-id
  - 从环境变量读取 TUSHARE_TOKEN 与 DB 参数
- 调度器
  - tdx_scheduler.py：当 dataset 以 tdx_board_ 开头时自动映射到上述脚本，支持 init/incremental 参数拼装
- 后端
  - tdx_backend.py 已通用化，无需新增路由；/api/ingestion/run 可直接触发（mode=init/incremental, dataset=tdx_board_*）
- UI
  - tdx_ui.py：
    - 初始化与增量 Tab 增加“数据源：TDX/Tushare”选择
    - Tushare 源可选 tdx_board_all/index/member/daily；参数默认近一年
    - 任务监视器新增“板块数据”分类显示

## 测试计划
- 连通性：验证 Tushare Token 可用
- 冒烟：近 7 天
  - tdx_board_index → 计数>0
  - tdx_board_member → 若某日有板块，成员>0
  - tdx_board_daily → 返回的当日通常不一定立刻可用，允许为空
- 端到端：通过 UI 触发 init 与 incremental，观察任务监控与日志
- 边界：当日无数据、接口超限、网络失败重试

## 运行与回滚
- DB 迁移：python scripts/init_market_schema.py（幂等）
- 触发（直接脚本）示例：
  - python scripts/ingest_tushare_tdx_board.py --dataset tdx_board_index --mode init --start-date YYYY-MM-DD --end-date YYYY-MM-DD
- 触发（通过后端）：POST /api/ingestion/run {dataset, mode, options}
- 回滚：按需删除三张表或清空数据（谨慎）

## 后续扩展
- 根据 doc_id=378 扩展 tdx_daily 更多估值资金字段（确认字段清单后补列）
- 调整并发与限流策略，加入失败重试队列
- 将板块成员与行情与本地股票维表联动
