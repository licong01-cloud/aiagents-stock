# TDX 数据入库与增量同步执行步骤（Runbook）

> 版本：v1.0（仅文档，未执行）
> 目标：按照“全 TDX 数据集”范围完成初始化与每日增量；支持进度条、失败重试与断点续传；分钟线以 1m 为事实层，5/15/60m 通过连续聚合生成。

## 0. 前置条件
- TimescaleDB 可访问（localhost:5432 / aistock / postgres / lc78080808 / schema=market）
- TDX 服务健康：`GET /api/health` 返回 200
- 应用已具备：页面配置项、后台作业 API、数据库迁移脚本能力

## 1. 配置与保存
1) 页面 → 环境配置 → 数据源配置 → 本地数据库
   - 填写：DB_HOST、DB_PORT、DB_NAME、DB_USER、DB_PASSWORD、DB_SCHEMA、DB_SSLMODE
   - 点击“测试连接”（期望：返回成功）
   - 点击“保存”（期望：持久化成功，密码不回显）

## 1.1 测试脚本集成与调度配置
1) 页面 → 本地数据管理 → 数据源测试
   - 点击“立即测试”按钮 → 调用 `/api/testing/run`，后台执行 `scripts/test_tdx_all_api.py`。
   - 结果展示：
     - UI 显示最新一次测试状态（成功/失败）、耗时、摘要。
     - 可下载 `tmp/tdx_api_test_results.json` 或跳转 `docs/tdx_api_failure_report.md` 查看详情。
2) 自动测试调度：
   - 在同页选择调度频率（关/5m/10m/15m/30m/1h/每日），点击“保存调度”。
   - 调度状态展示启用/停用切换；停用后立即取消队列中的下一次任务。
   - 失败告警：启用后将通知发送到预设渠道（邮件/IM），并附测试日志。
3) 后端：
   - 调度记录存储于 `testing_schedules`，执行记录写入 `testing_runs`、日志写入 `testing_logs`。
   - Worker 池使用 `testing` 队列，与数据入库分离但共享运行环境。

## 2. 数据库初始化（迁移）
1) 执行数据库初始化脚本（包含 schema/表/索引/策略/CAGG 定义）：
   - 创建 schema `market`
   - 创建表：symbol_dim、kline_daily_qfq/weekly_qfq/monthly_qfq、kline_minute_raw、tick_trade_raw、index_kline_*_qfq、stock_info、quote_snapshot、market_stats_snapshot、ingestion_jobs、ingestion_job_tasks、ingestion_state、ingestion_logs、trading_calendar
   - 设置 hypertable：`kline_daily_qfq` / `kline_minute_raw` / `tick_trade_raw` / `index_kline_daily_qfq` 等
   - 设置压缩/保留策略（分钟=7 天、CAGG=14 天、日/周/月=30 天）
   - 连续聚合：kline_5m/15m/60m
2) 校验：表/索引/策略存在；`create_hypertable`/CAGG 成功

## 3. 启动初始化任务（UI 或 API）
1) 页面 → 本地数据管理 → 数据更新
2) 选择数据集（默认勾选）：
   - codes、stock_info、kline_daily_qfq、minute_1m、index_kline、cagg_5m、cagg_15m、cagg_60m、quote_snapshot
   - 可选：weekly_qfq、monthly_qfq、tick_trade、market_stats_snapshot
   - 可选：接口聚合 K 线镜像（minute5/15/30/hour）默认关闭
3) 范围：
   - 代码：全部或按交易所；也可粘贴自定义列表
   - 日期：分钟/逐笔支持选择起止日期；默认分钟优先 VIPDOC 回填 + API 补齐；逐笔近 60 日
4) 接口策略：
   - 日线/指数：优先调用批量接口 `/api/kline-all`、`/api/index/all`（limit 默认 200，必要时自动分批）
   - 逐笔：启用 `/api/trade-history/full`，按 `cursor_payload` 拆分批次写入
   - 交易日历：使用 `/api/workday/range` 批量生成 `trading_calendar`
   - 若批量接口返回空或失败，自动回退至 `/api/kline`、`/api/trade` 等单日接口
5) 性能：并发=6，批量=2000，API 超时=10s，bulk timeout=30s；重试=3（指数退避）。任务按交易所/代码段拆分 worker queue；若与测试调度共享 worker，推荐设置速率限制。
6) 执行：点击“初始化更新”（或 POST `/api/ingestion/start`，mode=init）
7) 观察：
   - 顶部总进度、子进度（每数据集）、速率与 ETA
   - 实时日志（可下载）
   - 结果汇总（成功/跳过/失败）

## 4. 断点续传与失败重试
- 若任务失败：
  1) 查看失败清单与错误信息
  2) 点击“重试”（或 POST `/api/ingestion/retry`）
  3) 断点续传：`ingestion_state` 持久化 `last_success_date/time` 及 `cursor_payload`（批量接口最后一批的 code/date/id），重试时从游标续跑
- 若中途取消：
  1) 点击“取消”（或 POST `/api/ingestion/cancel`）—— 实际调用 `/api/tasks/{id}/cancel`
  2) 之后可“重试”或“重新开始”（仍支持断点）

## 5. 初始化完成后的验证
- spot 检查：
  - symbol_dim 行数与 `/api/codes` 统计一致
  - 取 3 支股票：日/周/月、1m、指数 K 线均可查
  - CAGG：5/15/60m 聚合存在且有数据
  - 快照：quote_snapshot/market_stats_snapshot 有记录
- 性能：分钟表空间、CAGG 表空间与压缩生效

## 6. 每日增量与实时补齐
1) 收盘批处理：
   - 启动增量作业（mode=incremental）。数据集：codes、kline_daily_qfq、minute_1m、index_kline、tick_trade、trading_calendar（必要时）。
   - 接口：
     - `/api/kline-history`、`/api/trade-history/full` 搭配 `before` 参数补齐当日数据；若需要，调用 `/api/kline-all` (limit=50) 一次拉完当日缺口。
     - `/api/index/all`、`/api/workday/range` 更新指数和交易日信息。
   - 性能：沿用初始化参数，bulk timeout=30s。
2) 交易时段实时补齐：
   - 在“调度设置”页面为分钟/逐笔等数据集选择频率（关/5m/10m/15m/30m/1h）。
   - 调度器触发 `ingestion` 队列任务，先检查是否已有同类型作业运行；如有，根据配置选择排队或跳过。
   - 若发现缺口，后台自动发起补偿作业并记录日志。
3) 每日任务完成后：更新 `ingestion_state`，触发连续聚合刷新，记录 `ingestion_logs`；UI 显示执行历史列表，可手动重跑或停用调度。

## 7. 交易日历维护
- 初始化 `trading_calendar` 表（可从公开源或内部规则生成）
- 每周更新一次交易日历
- 所有按日任务以日历为准，非交易日自动跳过；必要时回退上一交易日

## 8. 常见故障与处理
- 连接失败：检查 DB 配置与网络；重试“测试连接”
- 接口超时/失败：检查 TDX `/api/health`；调整并发/超时；稍后重试
- 空数据：检查是否非交易日；使用交易日历或回退到上一交易日
- 写入冲突：确认 UPSERT 约束、分批大小；重试

## 9. 监控与维护
- 每日：观察增量任务状态与日志
- 每周：校验压缩/保留策略工作正常；检查空间使用
- 每月：抽样对账（接口聚合 K 线 vs CAGG）

## 10. 附：API 调用示例（快速验证）
```bash
# 健康检查
curl "http://localhost:8080/api/health"

# 代码表
curl "http://localhost:8080/api/codes?exchange=sh"

# 日 K（QFQ）
curl "http://localhost:8080/api/kline?code=000001&type=day"

# 分钟线（昨日）
py - << PY
import os,requests,datetime
b=os.environ.get('TDX_API_BASE','http://localhost:8080').rstrip('/')
wd=datetime.date.today().weekday();delta=(3 if wd==0 else (2 if wd==6 else 1))
prev=(datetime.date.today()-datetime.timedelta(days=delta)).strftime('%Y%m%d')
r=requests.get(f'{b}/api/minute',params={'code':'000001','date':prev},timeout=10)
print(prev, r.status_code, r.text[:200])
PY
```

## 11. 版本与变更
- v1.0：首版（按“全 TDX 数据集”方案）
- v1.1（2025-11-10）：补充批量接口、并行策略与每日增量说明；记录接口测试最新结果

## 12. 最新接口测试结论
- 测试脚本：`python scripts/test_tdx_all_api.py --verbose --bulk-timeout 30 --output tmp/tdx_api_test_results.json`
- 最新执行（2025-11-10）：31/31 接口通过，包括批量全量接口（`/api/kline-all`、`/api/index/all`、`/api/trade-history/full`、`/api/workday/range`）以及任务管理接口。
- 若未来测试失败：
  1) 查阅 `tmp/tdx_api_test_results.json` 与 `docs/tdx_api_failure_report.md`
  2) 在修复后重新运行脚本并更新本节摘要
