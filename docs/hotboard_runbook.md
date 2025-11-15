# 热点板块跟踪（Hot Board Tracking）设计与落地手册

版本: v1.0  日期: 2025-11-14

## 1. 目标与范围
- 新增“热点板块跟踪”页面（新页面，不影响既有功能），包含：
  - 实时热点板块：基于新浪财经接口，3~60s（默认5s）刷新，红-白-绿色带，面积/颜色映射可选；开盘期间数据入库至 TimescaleDB 实时表，收盘后从新浪接口拉取当日最终数据入库日表，并按“10个交易日”策略清理实时表分区。
  - 历史热点板块：
    - 新浪历史热力图：来自“新浪板块日表”。
    - 通达信历史热力图：来自 TDX 板块表（tdx_board_index/member/daily），支持按板块类型（行业/风格/概念/地域）筛选。
  - 点击热力图板块 → Top20 股票：
    - 实时：使用 TDX 实时接口（data_source_manager.get_realtime_quotes）获取行情与排序。
    - 历史：使用本地 TDX 日线（kline_daily_qfq）计算涨幅/成交指标。
  - Top20 列表与“自选股票池”一致的展示风格，支持勾选后批量加入自选（新建或选择现有分类）。
- 交易日历（market.trading_calendar）本地化：
  - 在“本地数据管理”新增“交易日历”页；调用后端 /api/calendar/sync 从 Tushare trade_cal 手动同步；运行时如表缺口，后端自动兜底补齐近60天。

## 2. 数据库设计（TimescaleDB）
- 实时表（高频）：market.sina_board_intraday（超表）
  - ts TIMESTAMPTZ, cate_type SMALLINT(0=行业,1=概念,2=证监会), board_code TEXT, board_name TEXT
  - pct_chg NUMERIC(10,4), amount NUMERIC(28,2), net_inflow NUMERIC(28,2), turnover NUMERIC(18,4), ratioamount NUMERIC(18,6), meta JSONB
  - PK(ts, cate_type, board_code)
  - 索引：ts DESC；(cate_type, board_code, ts DESC)
  - 保留：EOD 任务按交易日历 drop_chunks，仅保留最近10个交易日

- 日表（历史）：market.sina_board_daily
  - trade_date DATE, cate_type SMALLINT, board_code TEXT, board_name TEXT
  - pct_chg, amount, net_inflow, turnover, ratioamount, meta JSONB
  - PK(trade_date, cate_type, board_code)

- 调度配置：market.hotboard_config
  - enabled, frequency_seconds(3~60), trading_windows(JSONB: ["09:25-11:35","12:55-15:05"]), last_run_at, updated_at

- 交易日历：market.trading_calendar（本地）
  - cal_date DATE PK, is_trading BOOLEAN
  - 来源：Tushare trade_cal；本地数据管理页面支持手动同步；后端运行时兜底补齐近60天

## 3. 后端实现（FastAPI, tdx_backend.py）
- 采集器（后台线程）
  - 每 3~60s 拉取一次 MoneyFlow.ssl_bkzj_bk（fenlei=0/1/2），批量 upsert 到 sina_board_intraday
  - 仅在交易时窗内工作（上海时区）
- EOD 汇总
  - 收盘后（15:05~16:00）再次调用新浪接口获取当日最终数据，落到 sina_board_daily
  - 基于 market.trading_calendar 保留最近10个交易日：drop_chunks(sina_board_intraday)
  - 若交易日历不足，后端自动从 Tushare 拉取近60天补全
- API 路由（/api/hotboard*）
  - POST /hotboard/collector/config, /collector/run
  - GET  /hotboard/realtime（支持 at 指定时刻、cate_type 过滤，返回 score/pct_chg/net_inflow/amount）
  - GET  /hotboard/realtime/timestamps（日内时间轴）
  - GET  /hotboard/daily（新浪历史日数据）
  - GET  /hotboard/tdx/types（板块类型）
  - GET  /hotboard/tdx/daily（按 idx_type 的 TDX 板块日数据）
  - GET  /hotboard/top-stocks/realtime（基于 TDX 实时行情的 Top20）
  - GET  /hotboard/top-stocks/tdx（基于本地 TDX 日线的 Top20）
- 交易日历：POST /api/calendar/sync（Tushare trade_cal）

## 4. 前端实现（Streamlit）
- 新页面：hotboard_ui.py
  - 顶部：映射方案（3种）、α 滑条、板块分类（行业/概念/证监会/全部）
  - Tab 实时：
    - 控件：刷新频率(3~60)、自动刷新、启用回放、固定时刻(ISO)
    - 时间轴：调用 /hotboard/realtime/timestamps，滑块定位后传 at 参数
    - 图：treemap（面积=净流入或涨幅；颜色=涨幅/净流入/复合），色带红-白-绿（0中心白）
    - 点击板块：调用 /hotboard/top-stocks/realtime，右侧渲染 Top20 表格（与自选风格一致），可加入自选（新建/已有分类）
  - Tab 历史：
    - 子页 A 新浪：按日期+分类绘制 treemap（颜色=涨幅，面积=成交额）
    - 子页 B TDX：按日期+类型绘制 treemap，点击板块后调用 /hotboard/top-stocks/tdx 并渲染 Top20（从本地日线）
- 本地数据管理（tdx_ui.py）：新增“交易日历”页，可手动同步 trade_cal

## 5. 部署与执行步骤
1. 运行数据库迁移（新增表/索引/超表）：
   - 脚本：scripts/init_market_schema.py（已加入 sina_board_intraday/sina_board_daily/hotboard_config）
2. 启动/重启后端：
   - 命令：uvicorn tdx_backend:app --host 0.0.0.0 --port 9000
   - 后端启动自动开启采集线程与 EOD 线程
3. 同步交易日历（推荐首次执行）：
   - 本地数据管理 → 交易日历 → 选择范围 → 同步
   - 或运行 scripts/sync_trading_calendar.py --start-date YYYY-MM-DD --end-date YYYY-MM-DD
4. 启动热点页面：
   - 命令：streamlit run hotboard_ui.py
5. 验证：
   - 实时页显示数据，回放滑块可用；点击板块可出 Top20；加入自选成功
   - 历史页新浪/TDX热力图正常；TDX Top20 表格数据来自本地日线
   - EOD 后检查 sina_board_daily 有当日数据，sina_board_intraday 仅保留近10个交易日分区

## 6. 测试要点
- 新浪接口超时/失败的容错；频率控制
- 交易日历缺失时的兜底拉取
- 回放时刻数据一致性
- Top20 实时使用 TDX 行情；历史使用本地日线
- watchlist 批量加入与分类创建
- 不影响既有页面/接口

## 7. 命名与映射方案
- 映射方案：
  1) 涨幅着色 · 流入定尺（颜色=涨幅，面积=净流入）
  2) 流入着色 · 涨幅定尺（颜色=净流入，面积=涨幅）
  3) 复合着色(α) · 流入定尺（颜色=α·z(涨幅)+(1-α)·z(净流入)，面积=净流入）
- 色带：红-白-绿（0中心白；跌=绿、涨=红）

## 8. 风险与回退
- 新浪接口变更/风控：UA/Referer、退避与重试，必要时引入备用源
- DB 膨胀：严格 EOD 保留10交易日，必要时增加自动压缩策略
- 可观测性：统一写入 ingestion_logs（可扩展）
