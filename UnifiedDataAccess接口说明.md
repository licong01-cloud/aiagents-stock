# UnifiedDataAccess 统一数据访问接口说明

## 📋 概述

`UnifiedDataAccess` 是股票分析系统的统一数据访问入口，封装了所有数据获取功能，提供一致的接口调用方式。

---

## 🔧 初始化

```python
from unified_data_access import UnifiedDataAccess

unified_data = UnifiedDataAccess()
```

---

## 📊 核心方法列表

### 1. 基础股票数据

#### `get_stock_info(symbol: str) -> Dict[str, Any]`
获取股票基本信息

**参数**:
- `symbol`: 股票代码（如 "000001", "600519"）

**返回**: 包含股票名称、行业、市值等基本信息的字典

**示例**:
```python
stock_info = unified_data.get_stock_info("000001")
print(stock_info['name'])  # 平安银行
```

---

#### `get_stock_data(symbol: str, period: str = '1y')`
获取股票历史行情数据

**参数**:
- `symbol`: 股票代码
- `period`: 时间周期
  - `'1mo'`: 1个月
  - `'3mo'`: 3个月
  - `'6mo'`: 6个月
  - `'1y'`: 1年（默认）
  - `'2y'`: 2年
  - `'5y'`: 5年
  - `'max'`: 最大范围

**返回**: pandas DataFrame，包含日期、开高低收、成交量等

**示例**:
```python
stock_data = unified_data.get_stock_data("000001", period="1y")
print(stock_data.head())
```

---

#### `get_stock_hist_data(symbol: str, start_date: str, end_date: str, adjust: str = 'qfq')`
获取指定日期范围的股票历史数据

**参数**:
- `symbol`: 股票代码
- `start_date`: 开始日期（格式：'YYYYMMDD'）
- `end_date`: 结束日期（格式：'YYYYMMDD'）
- `adjust`: 复权类型（'qfq'前复权, 'hfq'后复权, ''不复权）

**返回**: pandas DataFrame

---

#### `get_stock_basic_info(symbol: str) -> Dict[str, Any]`
获取股票基础信息（与get_stock_info相同，底层方法）

---

#### `get_realtime_quotes(symbol: str) -> Dict[str, Any]`
获取实时行情

**返回**: 包含当前价、涨跌幅等实时数据

---

### 2. 财务数据

#### `get_financial_data(symbol: str, report_type: str = 'income')`
获取财务报表数据

**参数**:
- `symbol`: 股票代码
- `report_type`: 报表类型
  - `'income'`: 利润表（默认）
  - `'balance'`: 资产负债表
  - `'cashflow'`: 现金流量表

**返回**: pandas DataFrame 或 Dict

**示例**:
```python
income = unified_data.get_financial_data("000001", "income")
```

---

#### `get_quarterly_reports(symbol: str) -> Dict[str, Any]`
获取季度财务报告（仅A股）

**返回**: 包含多个季度的财务数据字典

---

### 3. 资金数据

#### `get_fund_flow_data(symbol: str) -> Dict[str, Any]`
获取资金流向数据（仅A股）

**返回**: 包含主力、大单、中单、小单资金流向

**示例**:
```python
fund_flow = unified_data.get_fund_flow_data("000001")
if fund_flow['data_success']:
    print(f"主力净流入: {fund_flow['main_net_inflow']}")
```

---

### 4. 市场情绪

#### `get_market_sentiment_data(symbol: str, stock_data) -> Dict[str, Any]`
获取市场情绪数据（仅A股）

**参数**:
- `symbol`: 股票代码
- `stock_data`: 股票历史数据（用于计算情绪指标）

**返回**: 包含ARBR、换手率等情绪指标

---

### 5. 新闻数据

#### `get_stock_news(symbol: str) -> Dict[str, Any]`
获取股票新闻（仅A股）

**返回**: 包含最近的新闻列表

**示例**:
```python
news = unified_data.get_stock_news("000001")
if news['data_success']:
    for item in news['news_items']:
        print(f"{item['date']}: {item['title']}")
```

---

#### `get_news_data(symbol: str) -> Dict[str, Any]`
获取新闻数据（与get_stock_news相同，底层方法）

---

### 6. 风险数据

#### `get_risk_data(symbol: str) -> Dict[str, Any]`
获取风险数据（仅A股）

**返回**: 包含限售解禁、大股东减持、重要事件等风险信息

---

### 7. 机构研报

#### `get_research_reports_data(symbol: str, days: int = 30) -> Dict[str, Any]`
获取机构研报数据（仅A股）

**参数**:
- `symbol`: 股票代码
- `days`: 获取最近N天的研报（默认30天）

**返回**: 包含研报列表，每条研报包含日期、标题、机构、评级、目标价等

**示例**:
```python
reports = unified_data.get_research_reports_data("600519", days=30)
if reports['data_success']:
    for report in reports['research_reports']:
        print(f"{report['日期']}: {report['研报标题']} - {report['评级']}")
```

---

### 8. 公告数据

#### `get_announcement_data(symbol: str, days: int = 30) -> Dict[str, Any]`
获取上市公司公告（仅A股）

**参数**:
- `symbol`: 股票代码
- `days`: 获取最近N天的公告（默认30天）

**返回**: 包含公告列表，每条公告包含日期、标题、类型、摘要

**示例**:
```python
announcements = unified_data.get_announcement_data("600519", days=30)
if announcements['data_success']:
    print(f"获取到 {announcements['count']} 条公告")
    for ann in announcements['announcements']:
        print(f"{ann['日期']}: {ann['公告标题']}")
```

---

### 9. 筹码数据

#### `get_chip_distribution_data(symbol: str) -> Dict[str, Any]`
获取筹码分布数据（仅A股，占位实现）

**注意**: 当前为占位接口，返回错误提示

---

### 10. 辅助方法

#### `_is_chinese_stock(symbol: str) -> bool`
判断是否为中国A股

**参数**:
- `symbol`: 股票代码

**返回**: 
- `True`: A股（6位数字代码）
- `False`: 非A股

**示例**:
```python
is_a_stock = unified_data._is_chinese_stock("000001")  # True
is_a_stock = unified_data._is_chinese_stock("00700")   # False (港股)
```

---

### 11. 技术指标计算

通过 `stock_data_fetcher` 属性访问：

#### `stock_data_fetcher.calculate_technical_indicators(stock_data)`
计算技术指标

**参数**:
- `stock_data`: pandas DataFrame，股票历史数据

**返回**: 添加了技术指标列的DataFrame（MA、EMA、MACD、RSI、KDJ等）

---

#### `stock_data_fetcher.get_latest_indicators(stock_data_with_indicators)`
获取最新的技术指标值

**参数**:
- `stock_data_with_indicators`: 已包含技术指标的DataFrame

**返回**: 字典，包含最新的各项技术指标

**示例**:
```python
# 计算技术指标
stock_data_with_indicators = unified_data.stock_data_fetcher.calculate_technical_indicators(stock_data)

# 获取最新指标
indicators = unified_data.stock_data_fetcher.get_latest_indicators(stock_data_with_indicators)
print(f"RSI: {indicators['rsi']}")
print(f"MACD: {indicators['macd']}")
```

---

## 📝 数据返回格式

### 成功响应
```python
{
    "symbol": "000001",
    "data_success": True,
    "source": "akshare",  # 数据源
    "count": 10,          # 数据条数（可选）
    # ... 其他数据字段
}
```

### 失败响应
```python
{
    "symbol": "000001",
    "data_success": False,
    "error": "错误信息"
}
```

---

## 🎯 使用场景

### 场景1: 完整股票分析
```python
from unified_data_access import UnifiedDataAccess

unified = UnifiedDataAccess()
symbol = "000001"

# 1. 基础信息
stock_info = unified.get_stock_info(symbol)

# 2. 历史数据
stock_data = unified.get_stock_data(symbol, period="1y")

# 3. 技术指标
stock_data_with_indicators = unified.stock_data_fetcher.calculate_technical_indicators(stock_data)
indicators = unified.stock_data_fetcher.get_latest_indicators(stock_data_with_indicators)

# 4. 财务数据
financial_data = unified.get_financial_data(symbol)

# 5. 季报数据（A股）
if unified._is_chinese_stock(symbol):
    quarterly_data = unified.get_quarterly_reports(symbol)
    fund_flow = unified.get_fund_flow_data(symbol)
    sentiment = unified.get_market_sentiment_data(symbol, stock_data)
    news = unified.get_stock_news(symbol)
    risk = unified.get_risk_data(symbol)
    reports = unified.get_research_reports_data(symbol, days=30)
    announcements = unified.get_announcement_data(symbol, days=30)
```

### 场景2: 只获取基础数据
```python
unified = UnifiedDataAccess()

# 快速获取股票信息和历史数据
info = unified.get_stock_info("600519")
data = unified.get_stock_data("600519", "6mo")

print(f"{info['name']}: {data['close'].iloc[-1]}")
```

### 场景3: 研报和公告分析
```python
unified = UnifiedDataAccess()
symbol = "600519"

# 获取最近30天的研报
reports = unified.get_research_reports_data(symbol, days=30)
if reports['data_success']:
    print(f"研报数量: {reports['count']}")
    for report in reports['research_reports']:
        print(f"  {report['机构名称']}: {report['评级']}")

# 获取最近30天的公告
announcements = unified.get_announcement_data(symbol, days=30)
if announcements['data_success']:
    print(f"公告数量: {announcements['count']}")
    for ann in announcements['announcements']:
        print(f"  {ann['日期']}: {ann['公告标题']}")
```

---

## ⚠️ 注意事项

### 1. 股票类型限制
- **仅A股支持**: 季报、资金流向、市场情绪、新闻、风险、研报、公告、筹码
- **A股和港股**: 基础信息、历史数据、财务数据

### 2. 网络优化
所有数据获取都自动使用代理优化（通过`network_optimizer`）

### 3. 异常处理
所有方法都内置异常处理，失败时返回包含错误信息的字典

### 4. 时间格式
- `get_stock_hist_data`: 需要 'YYYYMMDD' 格式（如 '20250101'）
- `get_stock_data`: 使用预定义的period字符串（如 '1y'）

### 5. 数据源
- 优先使用 Tushare（需要token）
- 自动降级到 Akshare
- 使用代理优化网络访问

---

## 🔍 方法检查工具

使用提供的测试脚本验证所有方法是否可用：

```bash
python test_unified_access_methods.py
```

输出示例：
```
✅ get_stock_info                 存在
✅ get_stock_data                 存在
✅ stock_data_fetcher             存在
✅ get_financial_data             存在
✅ _is_chinese_stock              存在
✅ get_quarterly_reports          存在
✅ get_fund_flow_data             存在
✅ get_market_sentiment_data      存在
✅ get_stock_news                 存在
✅ get_risk_data                  存在
```

---

## 📦 依赖模块

- `data_source_manager`: 基础数据源管理
- `stock_data`: 股票数据获取和技术指标计算
- `quarterly_report_data`: 季报数据
- `fund_flow_akshare`: 资金流向
- `market_sentiment_data`: 市场情绪
- `qstock_news_data`: 新闻数据
- `risk_data_fetcher`: 风险数据
- `network_optimizer`: 网络优化

---

## 📞 技术支持

如遇问题，请检查：
1. 相应模块是否已安装
2. 网络连接是否正常
3. 代理设置是否正确
4. 股票代码是否正确（A股6位数字）

---

**版本**: v2.0  
**更新日期**: 2025-11-01  
**状态**: ✅ 已完成并测试

