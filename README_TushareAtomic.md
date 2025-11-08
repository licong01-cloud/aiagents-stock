# Tushare Atomic API 模块

本模块以“原子化函数”封装 Tushare 文档（https://tushare.pro/document/2）中“沪深股票、ETF 专题、指数专题、⼤模型语料专题”的接口。

- 完全独立于现有统一数据获取模块，不修改任何既有代码。
- 通过环境变量 `TUSHARE_TOKEN` 或显式 `token` 初始化。
- 对所有接口提供统一的 `pro.query(api_name, **params)` 泛化调用。
- 为常用接口提供便捷函数封装；所有其余接口均可直接用 `call()` 访问。
- 附带接口元数据注册（名称、分类、文档链接、常见参数和返回字段）便于查阅。

---

## 安装与初始化

1) 安装依赖

```bash
pip install tushare pandas
```

2) 配置 Token（推荐环境变量）

- Windows PowerShell
```powershell
$env:TUSHARE_TOKEN = "你的TushareToken"
```
- 或在代码中显式传入：
```python
from tushare_atomic_api import TushareAtomicClient
cli = TushareAtomicClient(token="你的TushareToken")
```

> 未设置 `TUSHARE_TOKEN` 且未显式传入 `token` 将在初始化时报错。

---

## 快速开始

```python
from tushare_atomic_api import TushareAtomicClient

cli = TushareAtomicClient()  # 默认从环境变量读取 TUSHARE_TOKEN

# 1) 任意接口：泛化调用（覆盖全部文档接口）
df = cli.call("daily", ts_code="000001.SZ", start_date="20240101", end_date="20241231")

# 2) 便捷封装：等价于上面 call
df2 = cli.daily(ts_code="000001.SZ", start_date="20240101", end_date="20241231")

# 3) 组合调用（顺序执行，结果依次返回）
results = cli.compose(
    lambda c: c.stock_basic(fields="ts_code,name,market,list_date"),
    lambda c: c.index_daily(ts_code="000001.SH", start_date="20240101", end_date="20241231"),
)

# 4) 查看接口元数据（参数/字段/文档链接）
from tushare_atomic_api import get_endpoint_meta
meta = get_endpoint_meta("daily_basic")
print(meta)
```

---

## 分类与常用接口

> 下述列表为常用接口速览。文档左侧目录下更多子接口均可用 `cli.call("api_name", **params)` 直接访问。

### 1. 沪深股票（stock）
- `stock_basic`（股票基础）
  - 文档: https://tushare.pro/document/2?doc_id=25
  - 例：`cli.stock_basic(list_status="L", fields="ts_code,name,market,list_date")`
- `trade_cal`（交易日历）
  - 文档: https://tushare.pro/document/2?doc_id=26
  - 例：`cli.trade_cal(exchange="SSE", start_date="20240101", end_date="20241231")`
- `stock_st`（ST股票列表）
  - 文档: https://tushare.pro/document/2?doc_id=397
- `stock_hsgt`（沪深港通股票列表）
  - 文档: https://tushare.pro/document/2?doc_id=398
- `bse_mapping`（北交所新旧代码对照）
  - 文档: https://tushare.pro/document/2?doc_id=375
- `namechange`（曾用名）
  - 文档: https://tushare.pro/document/2?doc_id=100
- `new_share`（新股）
  - 文档: https://tushare.pro/document/2?doc_id=123
- `daily`（日线）
  - 文档: https://tushare.pro/document/2?doc_id=27
- `bak_daily`（备用口径-日线）
  - 文档: https://tushare.pro/document/2
- `weekly`（周线）
  - 文档: https://tushare.pro/document/2?doc_id=27
- `bak_weekly`（备用口径-周线）
  - 文档: https://tushare.pro/document/2
- `monthly`（月线）
  - 文档: https://tushare.pro/document/2?doc_id=27
- `bak_monthly`（备用口径-月线）
  - 文档: https://tushare.pro/document/2
- `adj_factor`（复权因子）
  - 文档: https://tushare.pro/document/2?doc_id=28
- `suspend_d`（停复牌）
  - 文档: https://tushare.pro/document/2?doc_id=31
- `stk_limit`（涨跌停价格）
  - 文档: https://tushare.pro/document/2
- `daily_basic`（每日指标）
  - 文档: https://tushare.pro/document/2?doc_id=32
- `daily_info`（市场每日统计，沪深合计成交量/额等）
  - 文档: https://tushare.pro/document/2?doc_id=258
- `moneyflow`（资金流）
  - 文档: https://tushare.pro/document/2?doc_id=170
- `moneyflow_ths`（同花顺口径）
  - 文档: https://tushare.pro/document/2?doc_id=348
- `moneyflow_dc`（大单成交/明细）
  - 文档: https://tushare.pro/document/2?doc_id=349
- `income`（利润表）
  - 文档: https://tushare.pro/document/2?doc_id=33
- `balancesheet`（资产负债表）
  - 文档: https://tushare.pro/document/2?doc_id=36
- `cashflow`（现金流量表）
  - 文档: https://tushare.pro/document/2?doc_id=44
- `fina_indicator`（财务指标）
  - 文档: https://tushare.pro/document/2?doc_id=79
- `fina_audit`（财务审计意见）
  - 文档: https://tushare.pro/document/2?doc_id=80
- `dividend`（分红送股）
  - 文档: https://tushare.pro/document/2?doc_id=103
- `forecast`（业绩预告）
  - 文档: https://tushare.pro/document/2?doc_id=45
- `express`（业绩快报）
  - 文档: https://tushare.pro/document/2?doc_id=46
- `announcement`（上市公司公告）
  - 文档: https://tushare.pro/document/2?doc_id=176
- `concept`（概念列表）
  - 文档: https://tushare.pro/document/2?doc_id=147
- `concept_detail`（概念成分明细）
  - 文档: https://tushare.pro/document/2?doc_id=148
- `share_float`（限售股解禁/流通股本变动）
  - 文档: https://tushare.pro/document/2?doc_id=108
- `float_share`（流通股本变动-另一口径）
  - 文档: https://tushare.pro/document/2
- `stk_premarket`（盘前股本情况）
  - 文档: https://tushare.pro/document/2?doc_id=329
- `hs_const`（沪深股通成份股）
  - 文档: https://tushare.pro/document/2?doc_id=104
- `margin`（融资融券汇总，市场级）
  - 文档: https://tushare.pro/document/2?doc_id=58
- `margin_detail`（融资融券明细，个股级）
  - 文档: https://tushare.pro/document/2?doc_id=59
- `moneyflow_hsgt`（沪深港通资金流向-日）
  - 文档: https://tushare.pro/document/2?doc_id=47
- `hsgt_top10`（沪深港通每日前十大成交股）
  - 文档: https://tushare.pro/document/2?doc_id=48
- `hk_hold`（港资持股明细）
  - 文档: https://tushare.pro/document/2?doc_id=188
- `block_trade`（大宗交易）
  - 文档: https://tushare.pro/document/2?doc_id=161
- `repurchase`（股份回购）
  - 文档: https://tushare.pro/document/2?doc_id=124
- `pledge_stat`（股权质押统计）
  - 文档: https://tushare.pro/document/2?doc_id=110
- `pledge_detail`（股权质押明细）
  - 文档: https://tushare.pro/document/2?doc_id=111
- `ggt_daily`（港股通每日统计）
  - 文档: https://tushare.pro/document/2?doc_id=196
- `ggt_top10`（港股通每日前十大）
  - 文档: https://tushare.pro/document/2?doc_id=49
- `hk_daily_adj`（港股复权行情）
  - 文档: https://tushare.pro/document/2?doc_id=339
- `pro_bar`（通用行情集成接口）
  - 文档: https://tushare.pro/document/2?doc_id=109
- `broker_recommend`（券商金股推荐）
  - 文档: https://tushare.pro/document/2?doc_id=267
- `broker_recommend_detail`（券商金股推荐明细）
  - 文档: https://tushare.pro/document/2?doc_id=267
- `report_rc`（券商盈利预测数据）
  - 文档: https://tushare.pro/document/2?doc_id=292
- `cyq_perf`（每日筹码平均成本及胜率）
  - 文档: https://tushare.pro/document/2?doc_id=293
- `cyq_chips`（每日筹码分布）
  - 文档: https://tushare.pro/document/2?doc_id=294
- `ccass_hold`（中央结算系统持股汇总）
  - 文档: https://tushare.pro/document/2?doc_id=295
- `ccass_hold_detail`（中央结算系统持股明细）
  - 文档: https://tushare.pro/document/2?doc_id=274
- `stk_factor`（股票每日技术面因子）
  - 文档: https://tushare.pro/document/2?doc_id=296
- `stk_factor_pro`（股票每日技术面因子-专业版）
  - 文档: https://tushare.pro/document/2?doc_id=328
- `stk_auction_o`（股票开盘集合竞价数据）
  - 文档: https://tushare.pro/document/2?doc_id=353
- `stk_auction_c`（股票收盘集合竞价数据）
  - 文档: https://tushare.pro/document/2?doc_id=354
- `stk_mins`（A股历史分钟行情）
  - 文档: https://tushare.pro/document/2?doc_id=370
- `rt_min`（A股实时分钟行情）
  - 文档: https://tushare.pro/document/2?doc_id=374
- `rt_min_daily`（A股实时分钟—当日全量）
  - 文档: https://tushare.pro/document/2?doc_id=374
- `top_list`（龙虎榜每日明细）
  - 文档: https://tushare.pro/document/2?doc_id=106
- `top_inst`（龙虎榜机构成交明细）
  - 文档: https://tushare.pro/document/2?doc_id=107
- `ths_index`（同花顺概念/行业指数列表）
  - 文档: https://tushare.pro/document/2?doc_id=278
- `ths_member`（同花顺概念/行业成分）
  - 文档: https://tushare.pro/document/2?doc_id=279
- `shhk_daily`（沪深港通指数日度指标）
  - 文档: https://tushare.pro/document/2?doc_id=399
- `stk_nineturn`（神奇九转指标）
  - 文档: https://tushare.pro/document/2?doc_id=364
- `stk_ah_comparison`（AH股比价）
  - 文档: https://tushare.pro/document/2?doc_id=399
- `stk_surv`（机构调研数据）
  - 文档: https://tushare.pro/document/2?doc_id=275
- `stk_holdernumber`（股东户数）
  - 文档: https://tushare.pro/document/2
- `stk_holdertrade`（股东增减持）
  - 文档: https://tushare.pro/document/2
- `top10_holders`（前十大股东）
  - 文档: https://tushare.pro/document/2
- `top10_floatholders`（前十大流通股东）
  - 文档: https://tushare.pro/document/2

> 更多接口（如分钟、Tick、财务等）同样适用：`cli.call("api_name", **params)`

### 2. 指数专题（index）
- `index_basic`（指数基础）
  - 文档: https://tushare.pro/document/2?doc_id=94
- `index_daily`（指数日线）
  - 文档: https://tushare.pro/document/2?doc_id=95
- `index_dailybasic`（指数每日指标）
  - 文档: https://tushare.pro/document/2?doc_id=96
- `index_weight`（成分权重）
  - 文档: https://tushare.pro/document/2?doc_id=97
- `index_classify`（指数分类/列表）
  - 文档: https://tushare.pro/document/2
- `index_member`（指数成分明细）
  - 文档: https://tushare.pro/document/2
- `index_weekly`（周线）
  - 文档: https://tushare.pro/document/2
- `index_monthly`（月线）
  - 文档: https://tushare.pro/document/2

### 3. ETF 专题（etf）
- `fund_basic`（结合 `fund_type/market` 过滤 ETF）
  - 文档: https://tushare.pro/document/2?doc_id=43
- `fund_daily`（ETF/基金日线）
  - 文档: https://tushare.pro/document/2?doc_id=185
- `fund_nav`（净值；部分 ETF 提供）
  - 文档: https://tushare.pro/document/2?doc_id=44（如有 ETF 专用文档，以之为准）
- `fund_div`（基金分红）
  - 文档: https://tushare.pro/document/2
- `fund_portfolio`（持仓/成分，若 ETF 专题有专用表，以专用为准）
  - 文档: https://tushare.pro/document/2?doc_id=47（示意）
- `fund_adj`（基金复权因子）
  - 文档: https://tushare.pro/document/2
- `fund_share`（基金份额变动）
  - 文档: https://tushare.pro/document/2
- `fund_company`（基金公司）
  - 文档: https://tushare.pro/document/2
- `fund_manager`（基金经理）
  - 文档: https://tushare.pro/document/2

> ETF 专题与 `fund_*` 系接口在 Tushare 中存在重叠/映射，请以当前文档为准，均可用 `cli.call()` 访问。

### 4. 大模型语料专题（llm_corpus）
- 该专题下的具体子表名较新且可能随时间更新。
- 使用方式：
  - 直接调用：`cli.call("<api_name>", **params)`
  - 或统一入口：`cli.llm_corpus("<api_name>", **params)`
- 本模块在 `ENDPOINTS` 中保留专题链接与占位，便于后续补充。

---

## 设计说明

- 原子化：每个接口一个函数（或用 `call()` 直达），上层可自由组合。
- 兼容性：遇到文档名称差异时，以 `pro.query(api_name, **params)` 为准，文档链接保留以供比对。
- 隔离性：文件 `tushare_atomic_api.py` 独立存在，不改变既有统一数据访问层。
- 可扩展：
  - 新增接口：在 `ENDPOINTS` 注册并添加便捷函数（可选）。
  - 未内置的接口：始终可通过 `cli.call("api_name", **params)` 使用。

---

## 常见调用示例

```python
# 1) 获取上证综指、创业板指日线
cli.index_daily(ts_code="000001.SH", start_date="20240101", end_date="20241231")
cli.index_daily(ts_code="399006.SZ", start_date="20240101", end_date="20241231")

# 2) 获取指数每日指标
cli.index_dailybasic(ts_code="000905.SH", start_date="20240101", end_date="20241231")

# 3) 获取 ETF 列表（示意：按文档实际过滤字段）
cli.fund_basic(market="E", fields="ts_code,name,fund_type,market,list_date")

# 4) 获取 ETF 日线
cli.fund_daily(ts_code="510300.SH", start_date="20240101", end_date="20241231")

# 5) 股票资金流（近段时间）
cli.moneyflow(ts_code="000001.SZ", start_date="20240901", end_date="20241031")

# 6) 任意接口直达
cli.call("<api_name>", **{"param": "value"})

# 7) 市场成交统计（沪深合计，近10-30日）
cli.daily_info(start_date="20241001", end_date="20241031")

# 8) 融资融券
cli.margin_detail(ts_code="000001.SZ", start_date="20241001", end_date="20241031")
cli.margin(start_date="20241001", end_date="20241031")

# 9) 财务报表与指标
cli.income(ts_code="000001.SZ", period="20231231")
cli.balancesheet(ts_code="000001.SZ", period="20231231")
cli.cashflow(ts_code="000001.SZ", period="20231231")
cli.fina_indicator(ts_code="000001.SZ", period="20231231")

# 10) 沪深港通与大宗交易
cli.moneyflow_hsgt(start_date="20241001", end_date="20241031")
cli.hsgt_top10(trade_date="20241031", market="SSE")
cli.hk_hold(ts_code="000001.SZ", start_date="20241001", end_date="20241031")
cli.block_trade(ts_code="000001.SZ", start_date="20241001", end_date="20241031")

# 11) 股东结构
cli.stk_holdernumber(ts_code="000001.SZ", start_date="20240101", end_date="20241231")
cli.top10_holders(ts_code="000001.SZ", period="20231231")
cli.top10_floatholders(ts_code="000001.SZ", period="20231231")
```

---

## 接口元数据（ENDPOINTS）

模块内置 `ENDPOINTS` 字典登记了常用接口的：
- 名称、分类
- 文档链接
- 常见参数
- 返回字段（常见/示例）

可用 `get_endpoint_meta("api_name")` 查看。若某接口暂未登记，也不影响 `cli.call()` 使用。

### 导出接口总览（自动生成）

你可以在交互式环境中一键导出当前已登记的接口清单（按分类分组）：

```python
from tushare_atomic_api import export_endpoints_markdown
print(export_endpoints_markdown())
```

将打印出的 Markdown 片段复制到本文件的“接口总览”章节，保持索引与代码强一致。

---

## 注意事项

- 不考虑 Tushare 积分限制与频控，调用频率请自主管理。
- 字段与参数以官网文档为准；如发现差异，可直接通过 `cli.call()` 尝试，或在 `ENDPOINTS` 中补充更正。
- 本模块不进行数据清洗与兜底，仅提供原始访问与字段参考。

---

## 变更与扩展建议

- 若你需要我继续把四大专题下的“所有接口”逐一登记到 `ENDPOINTS` 并补充字段注释，我可以基于官网目录批量补全（本模块已保证功能上全量可用，登记仅影响文档化与导航）。
- 若你希望为特定接口增加高级封装（如自动回补日期、聚合统计、口径统一），建议在上层新建组合器，保持本模块的原子性。

---

## 接口总览（自动导出）

- **stock**
  - adj_factor (https://tushare.pro/document/2?doc_id=28)
  - announcement (https://tushare.pro/document/2?doc_id=176)
  - bak_basic (https://tushare.pro/document/2?doc_id=262)
  - bak_daily (https://tushare.pro/document/2?doc_id=255)
  - bak_monthly (https://tushare.pro/document/2?doc_id=171)
  - bak_weekly (https://tushare.pro/document/2?doc_id=171)
  - balancesheet (https://tushare.pro/document/2?doc_id=36)
  - block_trade (https://tushare.pro/document/2?doc_id=161)
  - broker_recommend (https://tushare.pro/document/2?doc_id=267)
  - broker_recommend_detail (https://tushare.pro/document/2?doc_id=267)
  - bse_mapping (https://tushare.pro/document/2?doc_id=375)
  - cashflow (https://tushare.pro/document/2?doc_id=44)
  - ccass_hold (https://tushare.pro/document/2?doc_id=295)
  - ccass_hold_detail (https://tushare.pro/document/2?doc_id=274)
  - concept (https://tushare.pro/document/2?doc_id=147)
  - concept_detail (https://tushare.pro/document/2?doc_id=148)
  - cyq_chips (https://tushare.pro/document/2?doc_id=294)
  - cyq_perf (https://tushare.pro/document/2?doc_id=293)
  - daily (https://tushare.pro/document/2?doc_id=27)
  - daily_basic (https://tushare.pro/document/2?doc_id=32)
  - daily_info (https://tushare.pro/document/2?doc_id=258)
  - dividend (https://tushare.pro/document/2?doc_id=103)
  - express (https://tushare.pro/document/2?doc_id=46)
  - fina_audit (https://tushare.pro/document/2?doc_id=80)
  - fina_indicator (https://tushare.pro/document/2?doc_id=79)
  - fina_mainbz (https://tushare.pro/document/2?doc_id=81)
  - float_share (https://tushare.pro/document/2)
  - forecast (https://tushare.pro/document/2?doc_id=45)
  - ggt_daily (https://tushare.pro/document/2?doc_id=196)
  - ggt_monthly (https://tushare.pro/document/2?doc_id=197)
  - ggt_top10 (https://tushare.pro/document/2?doc_id=49)
  - hk_daily_adj (https://tushare.pro/document/2?doc_id=339)
  - hk_hold (https://tushare.pro/document/2?doc_id=188)
  - hk_mins (https://tushare.pro/document/2?doc_id=304)
  - hk_tradecal (https://tushare.pro/document/2?doc_id=250)
  - hs_const (https://tushare.pro/document/2?doc_id=104)
  - hsgt_top10 (https://tushare.pro/document/2?doc_id=48)
  - income (https://tushare.pro/document/2?doc_id=33)
  - limit_list_d (https://tushare.pro/document/2?doc_id=298)
  - margin (https://tushare.pro/document/2?doc_id=58)
  - margin_detail (https://tushare.pro/document/2?doc_id=59)
  - margin_secs (https://tushare.pro/document/2?doc_id=326)
  - moneyflow (https://tushare.pro/document/2?doc_id=170)
  - moneyflow_dc (https://tushare.pro/document/2?doc_id=349)
  - moneyflow_hsgt (https://tushare.pro/document/2?doc_id=47)
  - moneyflow_ths (https://tushare.pro/document/2?doc_id=348)
  - monthly (https://tushare.pro/document/2?doc_id=27)
  - namechange (https://tushare.pro/document/2?doc_id=100)
  - new_share (https://tushare.pro/document/2?doc_id=123)
  - pledge_detail (https://tushare.pro/document/2?doc_id=111)
  - pledge_stat (https://tushare.pro/document/2?doc_id=110)
  - pro_bar (https://tushare.pro/document/2?doc_id=109)
  - report_rc (https://tushare.pro/document/2?doc_id=292)
  - repurchase (https://tushare.pro/document/2?doc_id=124)
  - rt_k (https://tushare.pro/document/2?doc_id=372)
  - rt_min (https://tushare.pro/document/2?doc_id=374)
  - rt_min_daily (https://tushare.pro/document/2?doc_id=374)
  - share_float (https://tushare.pro/document/2?doc_id=108)
  - shhk_daily (https://tushare.pro/document/2?doc_id=399)
  - stk_ah_comparison (https://tushare.pro/document/2?doc_id=399)
  - stk_auction_c (https://tushare.pro/document/2?doc_id=354)
  - stk_auction_o (https://tushare.pro/document/2?doc_id=353)
  - stk_factor (https://tushare.pro/document/2?doc_id=296)
  - stk_factor_pro (https://tushare.pro/document/2?doc_id=328)
  - stk_holdernumber (https://tushare.pro/document/2?doc_id=166)
  - stk_holdertrade (https://tushare.pro/document/2?doc_id=175)
  - stk_limit (https://tushare.pro/document/2?doc_id=183)
  - stk_managers (https://tushare.pro/document/2?doc_id=193)
  - stk_mins (https://tushare.pro/document/2?doc_id=370)
  - stk_nineturn (https://tushare.pro/document/2?doc_id=364)
  - stk_premarket (https://tushare.pro/document/2?doc_id=329)
  - stk_restrict (https://tushare.pro/document/2)
  - stk_rewards (https://tushare.pro/document/2?doc_id=194)
  - stk_surv (https://tushare.pro/document/2?doc_id=275)
  - stk_week_month_adj (https://tushare.pro/document/2?doc_id=365)
  - stk_weekly_monthly (https://tushare.pro/document/2?doc_id=336)
  - stock_basic (https://tushare.pro/document/2?doc_id=25)
  - stock_company (https://tushare.pro/document/2?doc_id=112)
  - stock_hsgt (https://tushare.pro/document/2?doc_id=398)
  - stock_mx (https://tushare.pro/document/2?doc_id=300)
  - stock_st (https://tushare.pro/document/2?doc_id=397)
  - suspend_d (https://tushare.pro/document/2?doc_id=31)
  - ths_index (https://tushare.pro/document/2?doc_id=278)
  - ths_member (https://tushare.pro/document/2?doc_id=279)
  - top10_floatholders (https://tushare.pro/document/2?doc_id=62)
  - top10_holders (https://tushare.pro/document/2?doc_id=61)
  - top_inst (https://tushare.pro/document/2?doc_id=107)
  - top_list (https://tushare.pro/document/2?doc_id=106)
  - trade_cal (https://tushare.pro/document/2?doc_id=26)
  - weekly (https://tushare.pro/document/2?doc_id=27)

- **index**
  - index_basic (https://tushare.pro/document/2?doc_id=94)
  - index_classify (https://tushare.pro/document/2)
  - index_daily (https://tushare.pro/document/2?doc_id=95)
  - index_dailybasic (https://tushare.pro/document/2?doc_id=96)
  - index_member (https://tushare.pro/document/2)
  - index_monthly (https://tushare.pro/document/2)
  - index_weekly (https://tushare.pro/document/2)
  - index_weight (https://tushare.pro/document/2?doc_id=97)

- **etf**
  - fund_adj (https://tushare.pro/document/2)
  - fund_basic (https://tushare.pro/document/2?doc_id=43)
  - fund_company (https://tushare.pro/document/2)
  - fund_daily (https://tushare.pro/document/2?doc_id=185)
  - fund_div (https://tushare.pro/document/2)
  - fund_manager (https://tushare.pro/document/2)
  - fund_nav (https://tushare.pro/document/2?doc_id=44)
  - fund_portfolio (https://tushare.pro/document/2?doc_id=47)
  - fund_share (https://tushare.pro/document/2)
  - rt_etf_k (https://tushare.pro/document/2?doc_id=400)

- **llm_corpus**
  - llm_example (https://tushare.pro/document/2)
