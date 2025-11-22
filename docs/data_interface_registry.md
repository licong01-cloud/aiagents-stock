# 数据接口注册表与浏览工具开发规范

本规范描述当前项目中 **数据接口元数据管理** 相关的约定，用于提升后续开发效率，避免每次新增功能时手动翻代码确定数据源和接口格式。

> 说明：本规范对应的实现仅用于开发辅助，不参与实际数据访问逻辑，不改变现有的数据获取路径。

---

## 1. 关键文件一览

- **数据接口配置（元数据）**
  - `config/data_endpoints.yaml`

- **注册表工具类**
  - `data_schema_registry.py`
  - 类：`DataSchemaRegistry`

- **命令行浏览工具**
  - `scripts/browse_data_endpoints.py`

---

## 2. 数据接口配置：`config/data_endpoints.yaml`

### 2.1 设计目标

- 用“**数据类型（kind）**”统一描述所有数据获取方式。
- 对每个 kind 记录：
  - 功能说明；
  - 优先数据源链路（DB / HTTP / 第三方库）；
  - 请求参数、响应结构的关键字段。
- 用于：
  - 开发阶段快速确认“我要的数据从哪里来、接口是什么样”；
  - 给 AI 助手提供统一的数据源信息，避免反复解释数据源细节。

### 2.2 基本结构

顶层是多个 `kind`，例如：

```yaml
realtime_quote:
  description: "单只或多只股票的实时盘口/最新价信息（不含名称解析）"
  preferred_sources:
    - name: tdx_quote
      type: http
      base_url_env: TDX_API_BASE
      path: "/api/quote"
      method: GET
      params:
        code: "6位股票代码，支持逗号分隔多个，如 '600519,000001'"
      response:
        root: "data[]"   # 数组，单票取 data[0]
        fields:
          symbol: "Code (string)"
          kline:
            last: "K.Last (int, 厘)"
            open: "K.Open (int, 厘)"
            high: "K.High (int, 厘)"
            low: "K.Low (int, 厘)"
            close: "K.Close (int, 厘)"
          volume: "TotalHand (int, 手)"
          amount: "Amount (int, 厘)"
      notes: |
        - 不提供名称字段，严禁用作名称解析。
        - Python 侧由 DataSourceManager._get_tdx_quote 做数值单位换算：价格 /1000，成交量 *100。
```

常用字段说明：

- **顶层**
  - `description`：kind 的用途说明。
  - `preferred_sources`：按优先级排序的数据源列表（从上到下兜底）。

- **source 通用字段**
  - `name`：数据源名（内部标识）。
  - `type`：`http` / `db` / `library`。
  - `notes`：额外说明。

- **HTTP 源**
  - `base_url_env`：Base URL 的环境变量名（如 `TDX_API_BASE`）。
  - `path`：HTTP 路径（如 `/api/quote`）。
  - `method`：`GET` / `POST`。
  - `params`：关键请求参数说明（字符串，不强制 JSON-schema 级别）。
  - `response.root`：返回 JSON 中数据的根路径（如 `data.List[]`）。
  - `response.fields`：重要字段含义和单位。

- **DB 源**
  - `table`：表名（如 `market.kline_daily_qfq`）。
  - `primary_keys`：主键字段列表。
  - `fields`：常用字段说明。

- **library 源**
  - `module`：Python 包名（如 `tushare`, `akshare`）。
  - `func`：函数名（如 `pro.stock_basic`）。
  - `params`：关键参数说明。

### 2.3 已定义的核心 kind（示例）

不完整列表，仅列出部分关键项：

- **实时行情**
  - `realtime_quote`

- **日线 / K 线**
  - `kline_daily_qfq`
  - `kline_daily_raw`

- **分时 / 逐笔成交**
  - `minute_intraday`
  - `trade_ticks`

- **基本信息 / 代码表**
  - `stock_basic_info`
  - `code_search`
  - `stock_codes_all`
  - `etf_list`

- **交易日 / 市场统计**
  - `trading_calendar`
  - `trading_calendar_range`
  - `market_count`

- **业务数据**
  - `portfolio_positions`
  - `watchlist_items`
  - `analysis_records`

新增数据源时，应优先 **在此文件中增加或更新对应 kind**，然后再在实际访问代码中实现具体调用逻辑。

---

## 3. 注册表工具类：`DataSchemaRegistry`

- 文件：`data_schema_registry.py`
- 主要类：`DataSchemaRegistry`

### 3.1 作用

- 从 `config/data_endpoints.yaml` 读取并缓存配置；
- 提供查询接口：
  - 列出所有 kind；
  - 查询某个 kind 的完整配置；
  - 查询某个 kind 的数据源列表。

> **重要：** 该类不负责真正访问 TDX/Tushare/DB，仅做元数据查询，不改变现有的数据访问逻辑。

### 3.2 主要接口

```python
from data_schema_registry import DataSchemaRegistry

registry = DataSchemaRegistry()

# 1. 列出所有 kind
kinds = registry.list_kinds()  # -> List[str]

# 2. 获取某个 kind 的完整配置
info = registry.get_kind("kline_daily_qfq")  # -> Dict[str, Any]

# 3. 获取某个 kind 的数据源列表
sources = registry.get_sources("realtime_quote")  # -> List[Dict[str, Any]]
```

行为约定：

- 配置文件不存在 / 解析失败时：
  - 内部 `_data` 置为空；
  - `list_kinds()` 返回空列表；
  - `get_kind()` 返回 `{}`；
  - 不抛异常，避免影响其他功能。

---

## 4. 数据接口浏览脚本：`browse_data_endpoints.py`

- 文件：`scripts/browse_data_endpoints.py`
- 用途：命令行浏览数据接口配置，便于开发调试和规范查阅。

### 4.1 使用示例

在项目根目录下运行：

#### 1）列出所有 kind

```bash
python -m scripts.browse_data_endpoints list
```

输出示例：

```text
已配置的数据 kind：
 - realtime_quote
 - kline_daily_qfq
 - stock_basic_info
 - ...
```

#### 2）查看某个 kind 的详细配置

```bash
python -m scripts.browse_data_endpoints show realtime_quote
```

输出示例（JSON 格式）：

```json
{
  "description": "单只或多只股票的实时盘口/最新价信息（不含名称解析）",
  "preferred_sources": [
    {
      "base_url_env": "TDX_API_BASE",
      "method": "GET",
      "name": "tdx_quote",
      "params": {
        "code": "6位股票代码，支持逗号分隔多个，如 '600519,000001'"
      },
      "path": "/api/quote",
      "response": {
        "fields": {
          "amount": "Amount (int, 厘)",
          "kline": {
            "close": "K.Close (int, 厘)",
            "high": "K.High (int, 厘)",
            "last": "K.Last (int, 厘)",
            "low": "K.Low (int, 厘)",
            "open": "K.Open (int, 厘)"
          },
          "symbol": "Code (string)",
          "volume": "TotalHand (int, 手)"
        },
        "root": "data[]"
      },
      "type": "http"
    }
  ]
}
```

### 4.2 适用场景

- 新开发一个功能，需要知道：
  - “实时行情”用哪个接口？字段含义是什么？
  - “前复权日线”优先用哪张表 / 哪个 HTTP 接口兜底？
- 修改某个 ingest 脚本时，想确认已有数据源规划。

---

## 5. 使用规范与约定

### 5.1 开发新功能时的推荐流程

1. **先查 kind**  
   使用命令行浏览脚本或 `DataSchemaRegistry` 查询已有 kind：

   - 如果没有合适的 kind：在 `config/data_endpoints.yaml` 中新增一个；
   - 如果有合适的 kind：直接复用。

2. **业务代码中继续使用现有数据访问层**  
   实际取数仍使用：

   - `data_source_manager`（封装 TDX/Tushare/Akshare）；
   - 各 `pg_*` 仓库类（PostgreSQL / TimescaleDB）；
   - 已存在的 helper 函数（如 portfolio_manager 等）。

   > 本规范不要求把所有调用替换为某个通用 DataAgent，仅保证数据源定义集中在 YAML 中，方便查阅与扩展。

3. **新增数据源 / 调整优先级时**  
   - 先在 `config/data_endpoints.yaml` 更新对应 kind 的 `preferred_sources`；
   - 再在具体的数据访问层（如 `data_source_manager`、某个 repo）实现或调整调用逻辑；
   - 以后如果你在对话中提示“某个数据源新增/变化”，AI 助手可以根据 YAML 自动识别并使用正确接口。

### 5.2 当前阶段不做的事情

- 不强制引入统一的 `DataAgent.fetch(kind, **params)` 运行时层，避免多一层访问影响性能和调试难度。
- 不改变现有 ingest 脚本、API、UI 的数据访问路径；所有新工具仅为**开发阶段辅助**。

---

## 6. 面向未来的可选扩展

当系统复杂度进一步提高、数据源更多时，可以在本规范基础上扩展：

- 在少数复杂业务模块上，引入轻量级的 `DataAgent`：
  - 根据 kind + `preferred_sources` 选择实际调用的函数 / HTTP / DB；
  - 对高频路径（批量 ingest、实时行情）仍保持直接调用现有函数。

- 在前端/文档系统中生成一份“数据接口说明页面”：
  - 基于 YAML + `DataSchemaRegistry` 的输出渲染成 HTML/Markdown，供团队查阅；
  - 作为“数据访问规范”的一部分随代码一起版本管理。

---

## 7. 总结

- `config/data_endpoints.yaml`：统一描述“有哪些数据类型，每种数据从哪里取，接口/表/字段是什么”；
- `DataSchemaRegistry`：程序内查询这些定义的工具类；
- `scripts/browse_data_endpoints.py`：命令行浏览当前所有数据接口配置；
- 以上组件 **不改变现有数据获取逻辑**，仅作为开发规范和效率工具，为后续功能开发和数据源扩展提供统一参考。
