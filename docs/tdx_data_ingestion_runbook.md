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
4) 性能：并发=6，批量=2000，超时=10s，重试=3
5) 执行：点击“初始化更新”（或 POST `/api/ingestion/start`，mode=init）
6) 观察：
   - 顶部总进度、子进度（每数据集）、速率与 ETA
   - 实时日志（可下载）
   - 结果汇总（成功/跳过/失败）

## 4. 断点续传与失败重试
- 若任务失败：
  1) 查看失败清单与错误信息
  2) 点击“重试”（或 POST `/api/ingestion/retry`）
  3) 断点续传：`ingestion_state` 将驱动从上次成功位置继续
- 若中途取消：
  1) 点击“取消”（或 POST `/api/ingestion/cancel`）
  2) 之后可“重试”或“重新开始”（仍支持断点）

## 5. 初始化完成后的验证
- spot 检查：
  - symbol_dim 行数与 `/api/codes` 统计一致
  - 取 3 支股票：日/周/月、1m、指数 K 线均可查
  - CAGG：5/15/60m 聚合存在且有数据
  - 快照：quote_snapshot/market_stats_snapshot 有记录
- 性能：分钟表空间、CAGG 表空间与压缩生效

## 6. 每日增量（收盘后）
1) 页面 → 本地数据管理 → 数据更新
2) 选择数据集：codes、kline_daily_qfq、minute_1m（当天）、index_kline、cagg_5m/15m/60m、（可选）quote_snapshot
3) （可选）tick_trade：收盘后对齐补齐
4) 性能参数沿用默认；执行“增量补充”（或 POST `/api/ingestion/start`，mode=incremental）
5) 观察进度与日志；若失败，使用“重试”继续

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
