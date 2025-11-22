# 📡 TDX股票数据API接口文档

## 🌐 基础信息

**Base URL**: `http://your-server:8080`  
**Content-Type**: `application/json; charset=utf-8`  
**编码**: UTF-8

---

## 📋 响应格式

所有接口统一返回格式：

```json
{
  "code": 0,           // 响应代码（整数，0=成功，-1=失败，用于判断请求是否成功）
  "message": "success", // 响应消息（字符串，success=成功，失败时包含错误描述信息）
  "data": {}           // 数据内容（对象或数组，成功时包含请求的数据，失败时为null或空）
}
```

---

## 📊 API接口列表

### 1. 获取五档行情

**接口**: `GET /api/quote`

**描述**: 获取股票实时五档买卖盘口数据

**请求参数**:
| 参数 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| code | string | 是 | 股票代码（如：000001）支持多个，逗号分隔 |

**请求示例**:
```
GET /api/quote?code=000001
GET /api/quote?code=000001,600519
```

**响应示例**:
```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "Exchange": 0,          // 交易所代码（0=深圳, 1=上海, 2=北京，无单位）
      "Code": "000001",       // 股票代码（6位数字，字符串类型）
      "Active1": 2843,        // 活跃度1（无单位，指标值）
      "K": {                  // K线数据对象，包含价格信息
        "Last": 12250,    // 昨收价（厘，1元=1000厘，前一交易日的收盘价）
        "Open": 12300,    // 开盘价（厘，1元=1000厘，当日开盘价格）
        "High": 12600,    // 最高价（厘，1元=1000厘，当日最高价格）
        "Low": 12280,     // 最低价（厘，1元=1000厘，当日最低价格）
        "Close": 12500    // 收盘价/最新价（厘，1元=1000厘，实时行情中为最新价，收盘后为收盘价）
      },
      "ServerTime": "1730617200",  // 服务器时间戳（秒，Unix时间戳）
      "TotalHand": 1235000,    // 总手数（手，1手=100股，当日累计成交量）
      "Intuition": 100,        // 现量（手，1手=100股，当前这一笔的成交量）
      "Amount": 156000000,     // 成交额（厘，1元=1000厘，当日累计成交金额）
      "InsideDish": 520000,    // 内盘（手，1手=100股，主动卖出成交量，通常视为资金流出）
      "OuterDisc": 715000,     // 外盘（手，1手=100股，主动买入成交量，通常视为资金流入）
      "BuyLevel": [            // 买五档
        {
          "Buy": true,         // 买入标识（布尔值，true=买盘，false=卖盘，无单位）
          "Price": 12500,      // 买一价（厘，1元=1000厘）
          "Number": 35000      // 挂单量（股，当前价位挂单的股票数量）
        },
        // ... 买二到买五
      ],
      "SellLevel": [           // 卖五档
        {
          "Buy": false,
          "Price": 12510,      // 卖一价（厘）
          "Number": 30000      // 挂单量（股）
        },
        // ... 卖二到卖五
      ],
      "Rate": 0.0,            // 涨速（百分比，小数形式，如0.0表示0%，0.0285表示2.85%，通常为0）
      "Active2": 2843         // 活跃度2（无单位，指标值，反映股票交易活跃程度）
    }
  ]
}
```

**数据说明**:
- 价格单位：厘（1元 = 1000厘）
- 成交量单位：手（1手 = 100股）
- 挂单量单位：股
- 成交额单位：厘（1元 = 1000厘）
- 内盘/外盘单位：手（1手 = 100股）
- 时间单位：秒（Unix时间戳）
- 活跃度：无单位（指标值）
- 涨速：百分比（小数形式，如0.0表示0%）

---

### 2. 获取K线数据

**接口**: `GET /api/kline`

**描述**: 获取股票K线数据（OHLC + 成交量成交额）。日/周/月K线默认返回同花顺前复权数据；若第三方源不可用将直接返回错误提示，不再自动切换通达信源。需要原始数据或自行设置兜底时，可调用文末的 `/api/kline-all/tdx` 等接口。

**请求参数**:
| 参数 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| code | string | 是 | 股票代码（如：000001） |
| type | string | 否 | K线类型，默认day |

**K线类型(type)**:
- `minute1` - 1分钟K线（最多24000条）
- `minute5` - 5分钟K线
- `minute15` - 15分钟K线
- `minute30` - 30分钟K线
- `hour` - 60分钟/小时K线
- `day` - 日K线（默认）
- `week` - 周K线
- `month` - 月K线

**请求示例**:
```
GET /api/kline?code=000001&type=day
GET /api/kline?code=600519&type=minute30
```

**响应示例**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "Count": 100,             // 数据条数（无单位，返回的K线数据总数量）
    "List": [                 // K线数据列表（数组类型，包含多条K线记录）
      {
        "Last": 12250,      // 昨收价（厘，1元=1000厘，前一交易日的收盘价，用于计算涨跌幅）
        "Open": 12300,      // 开盘价（厘，1元=1000厘，该K线周期的开盘价格）
        "High": 12600,      // 最高价（厘，1元=1000厘，该K线周期内的最高价格）
        "Low": 12280,       // 最低价（厘，1元=1000厘，该K线周期内的最低价格）
        "Close": 12500,     // 收盘价（厘，1元=1000厘，该K线周期的收盘价格）
        "Volume": 1235000,  // 成交量（手，1手=100股，该K线周期内的累计成交量）
        "Amount": 156000000,// 成交额（厘，1元=1000厘，该K线周期内的累计成交金额）
        "Time": "2024-11-03T00:00:00Z",  // 时间（ISO 8601格式，UTC时区，该K线的交易时间）
        "UpCount": 0,       // 上涨数（单位：只，仅指数有效，表示该指数中上涨的股票数量）
        "DownCount": 0      // 下跌数（单位：只，仅指数有效，表示该指数中下跌的股票数量）
      }
      // ... 更多K线数据
    ]
  }
}
```

**数据说明**:
- 数据按时间倒序排列（最新的在前）
- 价格单位：厘
- 成交量单位：手
- 成交额单位：厘

---

### 3. 获取分时数据

**接口**: `GET /api/minute`

**描述**: 获取股票分时走势数据。接口严格按照请求日期返回结果，不再自动回退其他交易日；若指定日期无数据，将返回空列表并保留原日期。

**请求参数**:
| 参数 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| code | string | 是 | 股票代码（如：000001） |
| date | string | 否 | 日期（YYYYMMDD格式），默认当天 |

**请求示例**:
```
GET /api/minute?code=000001
GET /api/minute?code=000001&date=20241103
```

**响应示例**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "date": "20251110",   // 实际数据日期（字符串格式YYYYMMDD，与请求日期一致）
    "Count": 240,         // 数据条数（无单位，分时数据的总数量，通常为240条）
    "List": [             // 分时数据列表（数组类型，按时间顺序排列）
      {
        "Time": "09:31",      // 时间（HH:mm格式，24小时制，该分钟的时间点）
        "Price": 12300,    // 价格（厘，1元=1000厘，该分钟的平均成交价格）
        "Number": 1500     // 成交量（手，1手=100股，该分钟的累计成交量）
      },
      {
        "Time": "09:32",      // 时间（HH:mm格式，24小时制）
        "Price": 12310,    // 价格（厘，1元=1000厘）
        "Number": 1200     // 成交量（手，1手=100股）
      }
      // ... 240个数据点（9:30-11:30, 13:00-15:00）
    ]
  }
}
```

**数据说明**:
- 交易时段：9:30-11:30（120分钟）, 13:00-15:00（120分钟）
- 共240个数据点
- 价格单位：厘
- 若 `List` 为空，表示该日期无分时数据，请由调用方自行选择备用日期或数据源

---

### 4. 获取分时成交

**接口**: `GET /api/trade`

**描述**: 获取股票逐笔成交明细

**请求参数**:
| 参数 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| code | string | 是 | 股票代码（如：000001） |
| date | string | 否 | 日期（YYYYMMDD格式），默认当天 |

**请求示例**:
```
GET /api/trade?code=000001
GET /api/trade?code=000001&date=20241103
```

**响应示例**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "Count": 1800,            // 数据条数（无单位，返回的成交记录总数量，当日最多1800条，历史最多2000条）
    "List": [                 // 成交明细列表（数组类型，按时间倒序排列，最新的在前）
      {
        "Time": "2024-11-03T14:59:58Z",  // 成交时间（ISO 8601格式，UTC时区，精确到秒的成交时间）
        "Price": 12500,    // 成交价（厘，1元=1000厘，该笔交易的成交价格）
        "Volume": 100,     // 成交量（手，1手=100股，该笔交易的成交量）
        "Status": 0,       // 买卖性质（枚举值，0=主动买入/外盘，1=主动卖出/内盘，2=中性/汇总，无单位）
        "Number": 5        // 成交单数（单位：笔，该笔交易包含的成交单数量，历史数据可能无效）
      },
      {
        "Time": "2024-11-03T14:59:55Z",  // 成交时间（ISO 8601格式，UTC时区）
        "Price": 12490,    // 成交价（厘，1元=1000厘）
        "Volume": 50,      // 成交量（手，1手=100股）
        "Status": 1,       // 买卖性质（0=买入，1=卖出，2=中性）
        "Number": 3        // 成交单数（单位：笔）
      }
      // ... 更多成交记录
    ]
  }
}
```

**数据说明**:
- Status: 0=主动买入(红色), 1=主动卖出(绿色), 2=中性
- 当日最多返回1800条
- 历史日期最多返回2000条
- 价格单位：厘（1元 = 1000厘）
- 成交量单位：手（1手 = 100股）
- 成交单数单位：笔
- 时间格式：ISO 8601（UTC时区）

---

### 5. 搜索股票代码

**接口**: `GET /api/search`

**描述**: 根据关键词搜索股票代码和名称

**请求参数**:
| 参数 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| keyword | string | 是 | 搜索关键词（代码或名称） |

**请求示例**:
```
GET /api/search?keyword=平安
GET /api/search?keyword=000001
```

**响应示例**:
```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "code": "000001",    // 股票代码（6位数字字符串，如000001表示平安银行）
      "name": "平安银行"   // 股票名称（中文字符串，股票的简称）
    },
    {
      "code": "601318",    // 股票代码（6位数字字符串）
      "name": "中国平安"   // 股票名称（中文字符串）
    }
    // ... 最多50条结果
  ]
}
```

**数据说明**:
- 支持代码和名称模糊搜索
- 最多返回50条结果
- 仅返回A股（过滤指数等）

---

### 6. 获取股票综合信息

**接口**: `GET /api/stock-info`

**描述**: 一次性获取股票的多种数据（五档行情+日K线+分时）

**请求参数**:
| 参数 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| code | string | 是 | 股票代码（如：000001） |

**请求示例**:
```
GET /api/stock-info?code=000001
```

**响应示例**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "quote": {
      // 五档行情数据（同/api/quote）
    },
    "kline_day": {
      // 最近30天日K线（同/api/kline?type=day）
    },
    "minute": {
      // 今日分时数据（同/api/minute）
    }
  }
}
```

**数据说明**:
- 整合了五档行情、最近30条日K线、最新分时数据
- 分时数据自带 `date`、`Count`、`List` 字段；若 `List` 为空表示该日期无分时数据
- 适合快速获取股票概览，减少API调用次数

---

## 🔧 扩展接口（高级功能）

### 7. 获取股票列表

**接口**: `GET /api/codes`

**描述**: 获取指定交易所的所有股票代码列表

**请求参数**:
| 参数 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| exchange | string | 否 | 交易所代码，默认all |

**交易所代码**:
- `sh` - 上海证券交易所
- `sz` - 深圳证券交易所
- `bj` - 北京证券交易所
- `all` - 全部（默认）

**请求示例**:
```
GET /api/codes
GET /api/codes?exchange=sh
```

**响应示例**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total": 5234,         // 总数量（无单位，所有交易所的股票总数）
    "exchanges": {         // 各交易所统计（对象类型，包含各交易所的股票数量）
      "sh": 2156,          // 上海证券交易所股票数量（无单位）
      "sz": 2845,          // 深圳证券交易所股票数量（无单位）
      "bj": 233            // 北京证券交易所股票数量（无单位）
    },
    "codes": [             // 股票列表（数组类型，包含股票代码、名称、交易所信息）
      {
        "code": "000001",  // 股票代码（6位数字字符串）
        "name": "平安银行", // 股票名称（中文字符串）
        "exchange": "sz"   // 交易所代码（字符串，sh=上海，sz=深圳，bj=北京）
      }
      // ... 更多股票
    ]
  }
}
```

---

### 8. 批量获取行情

**接口**: `POST /api/batch-quote`

**描述**: 批量获取多只股票的实时行情

**请求参数** (JSON Body):
```json
{
  "codes": ["000001", "600519", "601318"]
}
```

**请求示例**:
```bash
curl -X POST http://localhost:8080/api/batch-quote \
  -H "Content-Type: application/json" \
  -d '{"codes":["000001","600519","601318"]}'
```

**响应示例**:
```json
{
  "code": 0,
  "message": "success",
  "data": [
    // 数组，每个元素同/api/quote的单个股票数据
  ]
}
```

---

### 9. 获取历史K线

**接口**: `GET /api/kline-history`

**描述**: 获取指定时间范围的K线数据

**请求参数**:
| 参数 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| code | string | 是 | 股票代码 |
| type | string | 是 | K线类型 |
| start_date | string | 否 | 开始日期（YYYYMMDD） |
| end_date | string | 否 | 结束日期（YYYYMMDD） |
| limit | int | 否 | 返回条数，默认100，最大800 |

**请求示例**:
```
GET /api/kline-history?code=000001&type=day&limit=30
GET /api/kline-history?code=000001&type=day&start_date=20241001&end_date=20241101
```

---

### 10. 获取指数数据

**接口**: `GET /api/index`

**描述**: 获取指数K线数据（如上证指数、深证成指）

**请求参数**:
| 参数 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| code | string | 是 | 指数代码（如：sh000001） |
| type | string | 否 | K线类型，默认day |

**常用指数代码**:
- `sh000001` - 上证指数
- `sz399001` - 深证成指
- `sz399006` - 创业板指
- `sh000300` - 沪深300

**请求示例**:
```
GET /api/index?code=sh000001&type=day
```

---

### 11. 获取服务状态

**接口**: `GET /api/server-status`

**描述**: 返回API服务运行状态。

**响应示例**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "status": "running",     // 服务状态（字符串，running=运行中，stopped=已停止）
    "connected": true,       // 连接状态（布尔值，true=已连接到通达信服务器，false=未连接）
    "version": "1.0.0",      // 服务版本号（字符串，API服务的版本号）
    "uptime": "unknown"      // 运行时长（字符串，服务运行的总时长，可能为unknown表示未知）
  }
}
```

---

### 12. 创建批量K线入库任务

**接口**: `POST /api/tasks/pull-kline`

**描述**: 启动后台任务，批量拉取指定股票、指定周期的K线数据并存入本地数据库（默认目录：`data/database/kline`）。任务在后台异步执行，可通过任务管理接口查询状态。

**请求参数**（JSON Body）:
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| codes | array | 否 | 股票代码数组，默认遍历全部A股 |
| tables | array | 否 | K线类型列表，取值见下表，默认 `["day"]` |
| dir | string | 否 | 数据库存储目录，默认 `data/database/kline` |
| limit | int | 否 | 并发协程数量，默认1 |
| start_date | string | 否 | 起始日期阈值（`YYYY-MM-DD` 或 `YYYYMMDD`），早于此日期的数据不会重新拉取 |

**K线类型列表**:
`minute`, `5minute`, `15minute`, `30minute`, `hour`, `day`, `week`, `month`, `quarter`, `year`

**请求示例**:
```bash
curl -X POST http://localhost:8080/api/tasks/pull-kline \
  -H "Content-Type: application/json" \
  -d '{
    "codes": ["000001","600519"],
    "tables": ["day","week","month"],
    "limit": 4,
    "start_date": "2020-01-01"
  }'
```

**响应示例**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "task_id": "9b0d1b1b-7c3d-4ce6-9a0e-bd9f5e0dcf3b"
  }
}
```

---

### 13. 创建分时成交入库任务

**接口**: `POST /api/tasks/pull-trade`

**描述**: 拉取指定股票从 `start_year` 到 `end_year` 的历史分时成交数据，并自动导出CSV（默认目录：`data/database/trade`）。

**请求参数**（JSON Body）:
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 股票代码（如：000001） |
| dir | string | 否 | 输出目录，默认 `data/database/trade` |
| start_year | int | 否 | 起始年份，默认2000 |
| end_year | int | 否 | 结束年份，默认当年 |

**请求示例**:
```bash
curl -X POST http://localhost:8080/api/tasks/pull-trade \
  -H "Content-Type: application/json" \
  -d '{
    "code": "000001",
    "start_year": 2015,
    "end_year": 2023
  }'
```

**响应示例**同上，返回 `task_id`。

---

### 14. 查询与控制任务

| 接口 | 方法 | 描述 |
|------|------|------|
| `/api/tasks` | GET | 列出所有已创建任务及状态 |
| `/api/tasks/{task_id}` | GET | 查询指定任务详情 |
| `/api/tasks/{task_id}/cancel` | POST | 取消正在执行的任务 |

**任务状态枚举**:
- `running`：执行中
- `success`：已完成
- `failed`：执行失败，`error` 字段包含原因
- `cancelled`：已取消

**响应示例** (`GET /api/tasks/{task_id}`):
```json
{
  "code": 0,
  "message": "success",
  "data": {
        "id": "9b0d1b1b-7c3d-4ce6-9a0e-bd9f5e0dcf3b",  // 任务ID（UUID格式字符串，唯一标识任务）
        "type": "pull_kline",                            // 任务类型（字符串，pull_kline=拉取K线，pull_trade=拉取成交）
        "status": "running",                             // 任务状态（字符串，running=执行中，success=已完成，failed=失败，cancelled=已取消）
        "started_at": "2025-11-10T13:05:26.123456+08:00" // 开始时间（ISO 8601格式，+08:00表示东八区，任务开始执行的时间）
  }
}
```

---

### 15. 获取ETF列表

**接口**: `GET /api/etf`

**描述**: 返回当前可用的 ETF 基金列表，可按交易所过滤并限制返回数量。

**请求参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| exchange | string | 否 | 交易所，`sh` / `sz` / `all`（默认） |
| limit | int | 否 | 返回条数限制 |

**响应示例**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total": 2,
    "list": [
      {
        "code": "510300",    // ETF代码（6位数字字符串）
        "name": "沪深300ETF", // ETF名称（中文字符串）
        "exchange": "sh",    // 交易所代码（字符串，sh=上海，sz=深圳）
        "last_price": 4.123  // 最新价格（元，注意：ETF接口的价格直接返回元，而非厘）
      },
      {
        "code": "159915",
        "name": "创业板ETF",
        "exchange": "sz",
        "last_price": 1.876
      }
    ]
  }
}
```

---

### 16. 获取历史分时成交（分页）

**接口**: `GET /api/trade-history`

**描述**: 分页获取历史交易日的分时成交明细，单次最多返回 2000 条。

**请求参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 股票代码 |
| date | string | 是 | 交易日期（YYYYMMDD） |
| start | int | 否 | 起始游标，默认0 |
| count | int | 否 | 返回条数，默认2000，最大2000 |

**响应示例**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "Count": 2000,
    "List": [
      {
        "Price": 12345,                    // 成交价（厘，1元=1000厘，该笔交易的成交价格）
        "Time": "2024-11-08T14:58:00+08:00",  // 成交时间（ISO 8601格式，+08:00表示东八区，精确到秒）
        "Status": 0,                       // 买卖性质（枚举值，0=主动买入/外盘，1=主动卖出/内盘，2=中性/汇总，无单位）
        "Volume": 50                       // 成交量（手，1手=100股，该笔交易的成交量）
      }
    ]
  }
}
```

---

### 17. 获取全天分时成交

**接口**: `GET /api/minute-trade-all`

**描述**: 一次性获取某交易日的全部分时成交明细；未指定日期时返回当日实时成交。

**请求参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 股票代码 |
| date | string | 否 | 交易日期（YYYYMMDD），默认当天 |

**响应示例**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "Count": 3150,         // 数据条数（无单位，返回的成交记录总数量，可能超过当日限制）
    "List": [              // 成交明细列表（数组类型，按时间顺序排列，包含全部分时成交记录）
      {
        "Price": 12500,                    // 成交价（厘，1元=1000厘，该笔交易的成交价格）
        "Time": "2024-11-08T09:30:01+08:00",  // 成交时间（ISO 8601格式，+08:00表示东八区，精确到秒）
        "Volume": 10,                      // 成交量（手，1手=100股，该笔交易的成交量）
        "Status": 0                       // 买卖性质（枚举值，0=主动买入/外盘，1=主动卖出/内盘，2=中性/汇总，无单位）
      }
    ]
  }
}
```

---

### 18. 查询交易日信息

**接口**: `GET /api/workday`

**描述**: 查询指定日期是否为交易日，并返回前后若干个最近的交易日。

**请求参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| date | string | 否 | 查询日期（YYYYMMDD 或 YYYY-MM-DD），默认当天 |
| count | int | 否 | 返回的前后交易日数量，范围 1-30，默认1 |

**响应示例**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "date": {               // 查询日期对象（包含ISO格式和数字格式）
      "iso": "2024-11-08",  // ISO格式日期（字符串，YYYY-MM-DD格式）
      "numeric": "20241108" // 数字格式日期（字符串，YYYYMMDD格式）
    },
    "is_workday": true,     // 是否交易日（布尔值，true=交易日，false=非交易日）
    "next": [               // 下一个交易日列表（数组类型，包含count个后续交易日）
      {
        "iso": "2024-11-11",  // ISO格式日期（字符串，YYYY-MM-DD格式）
        "numeric": "20241111" // 数字格式日期（字符串，YYYYMMDD格式）
      }
    ],
    "previous": [           // 上一个交易日列表（数组类型，包含count个历史交易日）
      {
        "iso": "2024-11-07",  // ISO格式日期（字符串，YYYY-MM-DD格式）
        "numeric": "20241107" // 数字格式日期（字符串，YYYYMMDD格式）
      }
    ]
  }
}
```

---

### 19. 获取市场证券数量

**接口**: `GET /api/market-count`

**描述**: 获取上交所、深交所、北交所当前可用证券数量统计。

**响应示例**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total": 7654,           // 总数量（无单位，所有交易所的证券总数）
    "exchanges": [           // 各交易所统计列表（数组类型，包含各交易所的证券数量）
      { 
        "exchange": "sh",    // 交易所代码（字符串，sh=上海，sz=深圳，bj=北京）
        "count": 2163        // 证券数量（无单位，该交易所的证券总数）
      },
      { 
        "exchange": "sz",    // 交易所代码（字符串）
        "count": 5337        // 证券数量（无单位）
      },
      { 
        "exchange": "bj",    // 交易所代码（字符串）
        "count": 154         // 证券数量（无单位）
      }
    ]
  }
}
```

---

### 20. 获取股票代码列表

**接口**: `GET /api/stock-codes`

**描述**: 返回全市场股票代码列表，可控制是否携带交易所前缀。

**请求参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| limit | int | 否 | 返回条数限制 |
| prefix | bool | 否 | 是否包含交易所前缀（默认 true，即 `sh600000`） |

**响应示例**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "count": 5600,           // 数量（无单位，返回的股票代码总数）
    "list": [                // 股票代码列表（字符串数组，包含所有股票代码）
      "sh600000",            // 股票代码（字符串，前缀格式：sh/sz/bj+6位数字，如sh600000表示上海交易所股票）
      "sz000001"             // 股票代码（字符串，sz000001表示深圳交易所股票）
      // ...
    ]
  }
}
```

---

### 21. 获取ETF代码列表

**接口**: `GET /api/etf-codes`

**描述**: 返回所有 ETF 基金代码，参数与 `/api/stock-codes` 相同。

**响应示例**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "count": 200,            // 数量（无单位，返回的ETF代码总数）
    "list": [                // ETF代码列表（字符串数组，包含所有ETF代码）
      "sh510050",            // ETF代码（字符串，前缀格式：sh/sz+6位数字，如sh510050表示上海交易所ETF）
      "sz159915"             // ETF代码（字符串，sz159915表示深圳交易所ETF）
    ]
  }
}
```

---

### 22. 获取股票全部历史K线

**接口**: `GET /api/kline-all`

**描述**: 返回指定股票在某个周期的全部历史 K 线数据（天、周、月自动使用前复权）。

**请求参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 股票代码 |
| type | string | 否 | K 线类型，默认 day，可选 minute1/5/15/30/hour/day/week/month/quarter/year |
| limit | int | 否 | 返回条数限制（从最近开始截取） |

**注意**: 全量数据较大，建议配合 `limit` 控制响应大小。

---

### 23. 获取指数全部历史K线

**接口**: `GET /api/index/all`

**描述**: 返回指数在各周期的全部历史 K 线数据。

**请求参数**与 `/api/kline-all` 相同。

---

### 24. 获取上市以来分时成交

**接口**: `GET /api/trade-history/full`

**描述**: 返回指定股票上市以来的全部历史分时成交明细，可选截断截止日期与限制数量。

**请求参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 股票代码 |
| before | string | 否 | 截止日期（YYYYMMDD 或 YYYY-MM-DD），默认今日 |
| limit | int | 否 | 返回条数限制（从最近开始截取） |

---

### 25. 获取交易日范围

**接口**: `GET /api/workday/range`

**描述**: 返回指定起止日期之间的所有交易日。

**请求参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| start | string | 是 | 起始日期（YYYYMMDD 或 YYYY-MM-DD） |
| end | string | 是 | 结束日期（YYYYMMDD 或 YYYY-MM-DD） |

---

### 26. 计算收益区间指标

**接口**: `GET /api/income`

**描述**: 以某日收盘价格为基准，计算若干交易日后的收益情况。

**请求参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 股票代码 |
| start_date | string | 是 | 基准日期（YYYYMMDD 或 YYYY-MM-DD） |
| days | string | 否 | 多个天数偏移（逗号分隔），默认 5,10,20,60,120 |

**响应示例**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "count": 3,
    "list": [
      {
        "offset": 5,        // 交易日偏移量（整数，单位：天，表示基准日期后第几个交易日）
        "time": "2024-11-15T15:00:00+08:00",  // 目标交易日期时间（ISO 8601格式，+08:00表示东八区）
        "rise": 350.0,                     // 涨幅（厘，1元=1000厘，目标日期收盘价相对于基准日期收盘价的涨跌金额）
        "rise_rate": 0.0285,               // 涨幅率（小数形式，如0.0285表示2.85%，涨幅除以基准价格的百分比）
        "source": { "close": 12250.0, "open": 12300.0, "...": 0 },  // 基准日期K线数据（对象，包含基准日的开盘价、收盘价等，价格单位：厘）
        "current": { "close": 12580.0, "open": 12600.0, "...": 0 }  // 目标日期K线数据（对象，包含目标日的开盘价、收盘价等，价格单位：厘）
      }
    ]
  }
}
```

---

## 💡 使用示例

### Python示例

```python
import requests

BASE_URL = "http://your-server:8080"

# 1. 获取五档行情
def get_quote(code):
    url = f"{BASE_URL}/api/quote?code={code}"
    response = requests.get(url)
    data = response.json()
    if data['code'] == 0:
        return data['data']
    return None

# 2. 获取日K线
def get_kline(code, type='day'):
    url = f"{BASE_URL}/api/kline?code={code}&type={type}"
    response = requests.get(url)
    data = response.json()
    if data['code'] == 0:
        return data['data']['List']
    return None

# 3. 搜索股票
def search_stock(keyword):
    url = f"{BASE_URL}/api/search?keyword={keyword}"
    response = requests.get(url)
    data = response.json()
    if data['code'] == 0:
        return data['data']
    return None

# 使用示例
if __name__ == "__main__":
    # 搜索股票
    stocks = search_stock("平安")
    print(f"搜索结果: {stocks}")
    
    # 获取行情
    quote = get_quote("000001")
    print(f"最新价: {quote[0]['K']['Close'] / 1000}元")
    
    # 获取K线
    klines = get_kline("000001", "day")
    print(f"获取到{len(klines)}条K线数据")
```

### JavaScript示例

```javascript
const BASE_URL = 'http://your-server:8080';

// 1. 获取五档行情
async function getQuote(code) {
    const response = await fetch(`${BASE_URL}/api/quote?code=${code}`);
    const data = await response.json();
    if (data.code === 0) {
        return data.data;
    }
    return null;
}

// 2. 获取K线
async function getKline(code, type = 'day') {
    const response = await fetch(`${BASE_URL}/api/kline?code=${code}&type=${type}`);
    const data = await response.json();
    if (data.code === 0) {
        return data.data.List;
    }
    return null;
}

// 3. 批量获取行情
async function batchGetQuote(codes) {
    const response = await fetch(`${BASE_URL}/api/batch-quote`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ codes })
    });
    const data = await response.json();
    return data.data;
}

// 使用示例
(async () => {
    // 获取行情
    const quote = await getQuote('000001');
    console.log('最新价:', quote[0].K.Close / 1000);
    
    // 获取K线
    const klines = await getKline('000001', 'day');
    console.log('K线数据量:', klines.length);
    
    // 批量获取
    const quotes = await batchGetQuote(['000001', '600519', '601318']);
    console.log('批量行情:', quotes.length);
})();
```

### cURL示例

```bash
# 1. 获取五档行情
curl "http://localhost:8080/api/quote?code=000001"

# 2. 获取日K线
curl "http://localhost:8080/api/kline?code=000001&type=day"

# 3. 获取分时数据
curl "http://localhost:8080/api/minute?code=000001"

# 4. 搜索股票
curl "http://localhost:8080/api/search?keyword=平安"

# 5. 批量获取行情
curl -X POST http://localhost:8080/api/batch-quote \
  -H "Content-Type: application/json" \
  -d '{"codes":["000001","600519"]}'
```

---

## 📚 全量历史K线接口

为了区分不同数据源，并方便调用方自行决定兜底策略，历史K线提供以下两个独立接口，返回格式完全一致：

### 1. 通达信原始历史K线

**接口**: `GET /api/kline-all/tdx`

**说明**: 返回通达信原始（不复权）K线，内部按800条一批拼接完成。支持所有 `type` 取值（分钟、小时、日、周、月、季、年）。

**请求参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 股票代码（6位数字） |
| type | string | 否 | 默认 `day`，取值同 `/api/kline` |
| limit | int | 否 | 结果截断条数（从末尾取最近N条），默认返回全量 |

**响应示例**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "count": 4100,                        // 数据条数（无单位）
    "list": [
      {
        "Time": "1991-04-03T00:00:00Z",  // 时间（ISO 8601格式，UTC时区）
        "Open": 1260,                     // 开盘价（厘）
        "High": 1320,                     // 最高价（厘）
        "Low": 1240,                      // 最低价（厘）
        "Close": 1280,                    // 收盘价（厘）
        "Volume": 3500,                   // 成交量（手）
        "Amount": 4280000,                // 成交额（厘）
        "Last": 0                         // 昨收价（厘，历史数据可能为0）
      }
      // ... 时间正序排列的全部K线
    ],
    "meta": {                // 元数据对象（包含数据源、类型、限制和说明信息）
      "source": "tdx",       // 数据源（字符串，tdx=通达信，ths=同花顺）
      "type": "day",         // K线类型（字符串，day=日K，week=周K，month=月K等）
      "batch_limit": 800,    // 批次限制（整数，无单位，通达信单次请求最多返回的条数）
      "notes": [             // 说明信息列表（字符串数组，包含数据获取的注意事项）
        "通达信单次底层请求最多返回 800 条数据，服务端已顺序拼接全量结果",
        "对于上市时间较长的标的，请预估调用耗时（通常 1-5 秒），客户端需自行设置超时与兜底策略",
        "若实测请求在超时阈值内成功返回数据，即视为成功调用，无需按预设超时上限计入统计"
      ]
    }
  }
}
```

### 2. 同花顺前复权历史K线

**接口**: `GET /api/kline-all/ths`

**说明**: 返回同花顺前复权日K线，并提供基于日K转换的周、月K线。仅支持 `type=day/week/month`。

**请求参数**: 同上，`type` 限于 `day`、`week`、`month`。

**响应示例**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "count": 4100,                        // 数据条数（无单位）
    "list": [
      {
        "Time": "1991-04-03T00:00:00Z",  // 时间（ISO 8601格式，UTC时区）
        "Open": 1260,                     // 开盘价（厘）
        "High": 1320,                     // 最高价（厘）
        "Low": 1240,                      // 最低价（厘）
        "Close": 1280,                    // 收盘价（厘）
        "Volume": 3500,                   // 成交量（手）
        "Amount": 4280000,                // 成交额（厘）
        "Last": 0                         // 昨收价（厘，历史数据可能为0）
      }
      // ... 全量前复权数据
    ],
    "meta": {                // 元数据对象（包含数据源、类型、限制和说明信息）
      "source": "ths",       // 数据源（字符串，ths=同花顺，tdx=通达信）
      "type": "day",         // K线类型（字符串，day=日K，week=周K，month=月K等）
      "batch_limit": 4100,   // 批次限制（整数，无单位，同花顺单次请求最多返回的条数）
      "notes": [             // 说明信息列表（字符串数组，包含数据获取的注意事项）
        "同花顺接口一次性返回前复权数据，响应时长依赖网络与标的数据量（通常 2-8 秒）",
        "建议调用方在 Python 等客户端中设置 ≥10 秒超时时间，并按需准备自定义兜底逻辑",
        "若实测请求在超时阈值内成功返回数据，即视为成功调用，无需按预设超时上限计入统计"
      ]
    }
  }
}
```

> ⚠️ **提示**：上述接口不会对接第三方兜底逻辑；若返回空或失败，请由调用方自行决定重试或切换数据源。

---

## 🔒 错误码说明

| code | message | 说明 |
|------|---------|------|
| 0 | success | 请求成功 |
| -1 | 股票代码不能为空 | 缺少必填参数code |
| -1 | 获取行情失败: xxx | 数据获取失败，xxx为具体错误 |
| -1 | 获取K线失败: xxx | K线数据获取失败 |
| -1 | 未找到相关股票 | 搜索无结果 |
| -1 | 搜索关键词不能为空 | 缺少keyword参数 |

---

## 📊 数据单位换算

### 价格单位
- **返回值**：厘（1元 = 1000厘）
- **换算公式**：元 = 厘 / 1000
- **示例**：12500厘 = 12.50元
- **特殊说明**：ETF接口的 `last_price` 字段直接返回元（如4.123元），而非厘

### 成交量单位
- **返回值**：手（1手 = 100股）
- **换算公式**：股 = 手 × 100
- **示例**：1235手 = 123500股
- **适用范围**：`Volume`、`TotalHand`、`Intuition`、`InsideDish`、`OuterDisc`、`Number`（分时数据中的成交量）

### 成交额单位
- **返回值**：厘
- **换算公式**：元 = 厘 / 1000
- **示例**：156000000厘 = 156000元 = 15.6万元
- **适用范围**：`Amount` 字段

### 挂单量单位
- **返回值**：股
- **换算公式**：手 = 股 / 100
- **示例**：35000股 = 350手
- **适用范围**：`BuyLevel`、`SellLevel` 中的 `Number` 字段

### 时间单位
- **Unix时间戳**：秒（如 `ServerTime: "1730617200"`）
- **ISO 8601格式**：字符串格式（如 `"2024-11-03T14:59:58Z"` 或 `"2024-11-08T14:58:00+08:00"`）
- **分时时间格式**：HH:mm（24小时制，如 `"09:31"`）

### 其他字段单位
- **Count**：数量（无单位，表示条数、笔数等）
- **Number**（成交单数）：笔（无单位，表示成交笔数）
- **Status**：枚举值（0=买入, 1=卖出, 2=中性，无单位）
- **Rate**：百分比（小数形式，如0.0表示0%，0.0285表示2.85%）
- **Active1/Active2**：活跃度（无单位，指标值）
- **UpCount/DownCount**：只（指数中上涨/下跌股票数量）
- **total/count**：数量（无单位，表示总数、条数等）

---

## 🚀 性能建议

1. **批量请求**：使用批量接口代替多次单个请求
2. **缓存**：对不常变化的数据（如股票列表）做本地缓存
3. **限流**：避免频繁请求，建议间隔>=3秒
4. **压缩**：使用gzip压缩减少传输量

---

## 📋 股票代码与名称相关接口汇总

TDX接口提供了多个用于获取股票代码、名称和基本信息的接口：

### 1. 搜索股票代码和名称

**接口**: `GET /api/search`

**功能**: 根据关键词（代码或名称）搜索股票

**返回字段**:
- `code`: 股票代码（6位数字）
- `name`: 股票名称

**示例**:
```bash
GET /api/search?keyword=平安
# 返回: [{"code": "000001", "name": "平安银行"}, ...]
```

---

### 2. 获取股票代码列表（详细信息）

**接口**: `GET /api/codes`

**功能**: 获取指定交易所的所有股票代码列表，包含代码、名称、交易所信息

**返回字段**:
- `total`: 总数量
- `exchanges`: 各交易所统计（sh/sz/bj）
- `codes`: 股票列表，每个元素包含：
  - `code`: 股票代码（6位数字）
  - `name`: 股票名称
  - `exchange`: 交易所代码（sh/sz/bj）

**示例**:
```bash
GET /api/codes?exchange=sh
# 返回: {"total": 2156, "exchanges": {...}, "codes": [{"code": "600000", "name": "浦发银行", "exchange": "sh"}, ...]}
```

---

### 3. 获取股票代码列表（简化版）

**接口**: `GET /api/stock-codes`

**功能**: 返回全市场股票代码列表，可控制是否携带交易所前缀

**返回字段**:
- `count`: 数量
- `list`: 代码列表（字符串数组）

**参数**:
- `limit`: 返回条数限制
- `prefix`: 是否包含交易所前缀（默认true，即 `sh600000`）

**示例**:
```bash
GET /api/stock-codes?prefix=true&limit=100
# 返回: {"count": 5600, "list": ["sh600000", "sz000001", ...]}
```

---

### 4. 获取股票综合信息

**接口**: `GET /api/stock-info`

**功能**: 一次性获取股票的多种数据（五档行情+日K线+分时）

**返回字段**:
- `quote`: 五档行情数据（包含代码、名称、价格等）
- `kline_day`: 最近30天日K线
- `minute`: 今日分时数据

**注意**: 此接口返回的是实时行情和K线数据，不是股票的基本信息（如上市日期、所属板块等）

---

### 5. 获取ETF代码列表

**接口**: `GET /api/etf-codes`

**功能**: 返回所有ETF基金代码列表

**参数**: 同 `/api/stock-codes`

---

### 6. 获取ETF列表（详细信息）

**接口**: `GET /api/etf`

**功能**: 返回ETF基金列表，包含代码、名称、交易所、最新价

**返回字段**:
- `total`: 总数量
- `list`: ETF列表，每个元素包含：
  - `code`: ETF代码
  - `name`: ETF名称
  - `exchange`: 交易所（sh/sz）
  - `last_price`: 最新价格

**示例**:
```bash
GET /api/etf?exchange=sh&limit=10
# 返回: {"total": 200, "list": [{"code": "510300", "name": "沪深300ETF", "exchange": "sh", "last_price": 4.123}, ...]}
```

---

## 📊 实时行情与资金流向数据说明

### ✅ 实时行情数据

TDX接口**完全支持**个股实时行情数据，通过 `GET /api/quote` 接口获取：

**可获取的实时行情字段**:
- ✅ **价格数据**：
  - `K.Last`: 昨收价
  - `K.Open`: 开盘价
  - `K.High`: 最高价
  - `K.Low`: 最低价
  - `K.Close`: 最新价/收盘价
- ✅ **成交量数据**：
  - `TotalHand`: 总手数（累计成交量）
  - `Intuition`: 现量（当前成交量）
  - `Amount`: 成交额（累计成交金额）
- ✅ **盘口数据**：
  - `BuyLevel`: 买五档（买1-买5的价格和挂单量）
  - `SellLevel`: 卖五档（卖1-卖5的价格和挂单量）
- ✅ **资金流向相关数据**：
  - `InsideDish`: 内盘（主动卖出成交量，单位：手）
  - `OuterDisc`: 外盘（主动买入成交量，单位：手）
  - `Active1` / `Active2`: 活跃度指标

**数据更新频率**: 实时（通过通达信服务器获取，通常延迟<1秒）

**使用示例**:
```bash
# 获取单只股票实时行情
GET /api/quote?code=000001

# 批量获取多只股票实时行情
GET /api/quote?code=000001,600519,601318
```

---

### ⚠️ 资金流向数据说明

**TDX接口提供的资金流向相关数据**:

1. **内盘/外盘数据**（通过 `/api/quote` 接口）:
   - `InsideDish`: 内盘（主动卖出，通常视为资金流出）
   - `OuterDisc`: 外盘（主动买入，通常视为资金流入）
   - 可用于计算：净流入 = 外盘 - 内盘

2. **分时成交数据**（通过 `/api/trade` 或 `/api/minute-trade-all` 接口）:
   - 每笔成交的价格、成交量、买卖性质（0=买入，1=卖出，2=中性）
   - 成交时间（精确到秒）
   - **可用于分析大单行为**：通过成交量大小判断大单、中单、小单

**TDX接口不直接提供的数据**:
- ❌ 主力资金净流入/净流出（需要自行计算）
- ❌ 大单、中单、小单的分类统计（需要根据分时成交数据自行分类）
- ❌ 资金流向排名
- ❌ 行业/板块资金流向

**如何分析资金流向**:

1. **使用内盘/外盘数据**:
   ```python
   # 净流入 = 外盘 - 内盘
   net_inflow = quote['OuterDisc'] - quote['InsideDish']
   # 净流入率 = (外盘 - 内盘) / 总成交量
   net_inflow_rate = net_inflow / quote['TotalHand'] if quote['TotalHand'] > 0 else 0
   ```

2. **使用分时成交数据分析大单**:
   ```python
   # 获取分时成交数据
   trades = get_minute_trade_all(code)
   # 定义大单阈值（如：单笔成交量 > 1000手）
   large_trade_threshold = 1000
   # 统计大单买入和卖出
   large_buy = sum(t['Volume'] for t in trades if t['Status'] == 0 and t['Volume'] > large_trade_threshold)
   large_sell = sum(t['Volume'] for t in trades if t['Status'] == 1 and t['Volume'] > large_trade_threshold)
   ```

3. **结合五档盘口分析**:
   - 大单挂单（买五档或卖五档中出现大额挂单）可能预示主力操作
   - 连续大单买入 = 资金流入
   - 大单卖出频繁 = 可能见顶

**建议**:
- 如需更详细的资金流向数据（如主力资金、大单统计），建议：
  1. 使用第三方数据源（如东方财富、同花顺等）
  2. 基于TDX的分时成交数据自行计算和分类
  3. 结合内盘/外盘数据进行综合分析

---

## ⚠️ 关于股票详细信息

**当前TDX接口的限制**:

TDX接口目前**不提供**以下详细信息：
- ❌ 上市日期
- ❌ 所属板块（行业板块、概念板块）
- ❌ 行业分类
- ❌ 公司简介
- ❌ 财务数据
- ❌ 股本结构

**可获取的基本信息**:
- ✅ 股票代码（6位数字）
- ✅ 股票名称
- ✅ 所属交易所（sh/sz/bj）
- ✅ 实时行情数据（价格、成交量等）
- ✅ 历史K线数据
- ✅ 分时数据

**如需获取详细信息，建议**:
1. 使用第三方数据源（如东方财富、同花顺、新浪财经等）
2. 结合TDX接口获取实时行情数据
3. 自行维护股票基本信息数据库

---

## 📝 更新日志

### v1.0.0 (2024-11-03)
- ✅ 实现基础6个API接口
- ✅ 统一响应格式
- ✅ 完整文档和示例

### v1.1.0 (计划中)
- 🔄 批量查询接口
- 🔄 历史K线范围查询
- 🔄 指数数据接口
- 🔄 WebSocket实时推送

---

## 📞 技术支持

- 文档地址：本文件
- API测试：使用Postman或cURL
- 问题反馈：GitHub Issues

---

**Happy Coding!** 🎉

