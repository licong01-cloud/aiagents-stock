# 📡 API功能完整集成指南

## 🎯 概述

已为您打包完成所有功能的API接口！包括：

### ✅ 已实现的基础接口（6个）
1. **GET /api/quote** - 五档行情
2. **GET /api/kline** - K线数据
3. **GET /api/minute** - 分时数据
4. **GET /api/trade** - 分时成交
5. **GET /api/search** - 搜索股票
6. **GET /api/stock-info** - 综合信息

### ✅ 扩展接口（6个）
7. **GET /api/codes** - 股票代码列表
8. **POST /api/batch-quote** - 批量获取行情
9. **GET /api/kline-history** - 历史K线范围查询
10. **GET /api/index** - 指数数据
11. **GET /api/market-stats** - 市场统计
12. **GET /api/health** - 健康检查

---

## 🚀 如何集成扩展接口

### 方法一：合并到现有server.go（推荐）

在 `web/server.go` 的 `main()` 函数中添加新路由：

```go
func main() {
	// 静态文件服务
	http.Handle("/", http.FileServer(http.Dir("./static")))

	// === 现有API路由 ===
	http.HandleFunc("/api/quote", handleGetQuote)
	http.HandleFunc("/api/kline", handleGetKline)
	http.HandleFunc("/api/minute", handleGetMinute)
	http.HandleFunc("/api/trade", handleGetTrade)
	http.HandleFunc("/api/search", handleSearchCode)
	http.HandleFunc("/api/stock-info", handleGetStockInfo)

	// === 新增扩展API路由 ===
	http.HandleFunc("/api/codes", handleGetCodes)
	http.HandleFunc("/api/batch-quote", handleBatchQuote)
	http.HandleFunc("/api/kline-history", handleGetKlineHistory)
	http.HandleFunc("/api/index", handleGetIndex)
	http.HandleFunc("/api/market-stats", handleGetMarketStats)
	http.HandleFunc("/api/status", handleGetServerStatus)
	http.HandleFunc("/api/health", handleHealthCheck)

	port := ":8080"
	log.Printf("服务启动成功，访问 http://localhost%s\n", port)
	log.Fatal(http.ListenAndServe(port, nil))
}
```

### 方法二：复制扩展函数到server.go

将 `server_api_extended.go` 中的所有函数复制到 `server.go` 文件末尾，然后添加路由。

---

## 📝 完整集成步骤

### 步骤1: 添加扩展接口代码

打开 `web/server.go`，在文件末尾添加以下代码：

```go
// ==================== 扩展API接口 ====================

// 获取股票代码列表
func handleGetCodes(w http.ResponseWriter, r *http.Request) {
	exchange := r.URL.Query().Get("exchange")

	type CodesResponse struct {
		Total     int                    `json:"total"`
		Exchanges map[string]int         `json:"exchanges"`
		Codes     []map[string]string    `json:"codes"`
	}

	resp := &CodesResponse{
		Exchanges: make(map[string]int),
		Codes:     []map[string]string{},
	}

	exchanges := []protocol.Exchange{}
	switch strings.ToLower(exchange) {
	case "sh":
		exchanges = []protocol.Exchange{protocol.ExchangeSH}
	case "sz":
		exchanges = []protocol.Exchange{protocol.ExchangeSZ}
	case "bj":
		exchanges = []protocol.Exchange{protocol.ExchangeBJ}
	default:
		exchanges = []protocol.Exchange{protocol.ExchangeSH, protocol.ExchangeSZ, protocol.ExchangeBJ}
	}

	for _, ex := range exchanges {
		codeResp, err := client.GetCodeAll(ex)
		if err != nil {
			continue
		}

		exName := ""
		switch ex {
		case protocol.ExchangeSH:
			exName = "sh"
		case protocol.ExchangeSZ:
			exName = "sz"
		case protocol.ExchangeBJ:
			exName = "bj"
		}

		count := 0
		for _, v := range codeResp.List {
			if protocol.IsStock(v.Code) {
				resp.Codes = append(resp.Codes, map[string]string{
					"code":     v.Code,
					"name":     v.Name,
					"exchange": exName,
				})
				count++
			}
		}
		resp.Exchanges[exName] = count
		resp.Total += count
	}

	successResponse(w, resp)
}

// 批量获取行情
func handleBatchQuote(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		errorResponse(w, "只支持POST请求")
		return
	}

	var req struct {
		Codes []string `json:"codes"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		errorResponse(w, "请求参数错误: "+err.Error())
		return
	}

	if len(req.Codes) == 0 {
		errorResponse(w, "股票代码列表不能为空")
		return
	}

	if len(req.Codes) > 50 {
		errorResponse(w, "一次最多查询50只股票")
		return
	}

	quotes, err := client.GetQuote(req.Codes...)
	if err != nil {
		errorResponse(w, fmt.Sprintf("获取行情失败: %v", err))
		return
	}

	successResponse(w, quotes)
}

// 健康检查
func handleHealthCheck(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status": "healthy",
		"time":   time.Now().Unix(),
	})
}

// ... 其他扩展函数（见server_api_extended.go）
```

### 步骤2: 添加import依赖

在 `server.go` 顶部的import中确保有：

```go
import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strconv"      // 新增
	"strings"      // 新增
	"time"

	"github.com/injoyai/tdx"
	"github.com/injoyai/tdx/protocol"
)
```

### 步骤3: 注册新路由

在 `main()` 函数中添加：

```go
func main() {
	// ... 现有代码 ...
	
	// 扩展API路由
	http.HandleFunc("/api/codes", handleGetCodes)
	http.HandleFunc("/api/batch-quote", handleBatchQuote)
	http.HandleFunc("/api/health", handleHealthCheck)
	
	// ... 启动服务器代码 ...
}
```

### 步骤4: 重新构建部署

```bash
# 停止服务
docker-compose down

# 重新构建
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

---

## 🧪 测试新接口

### 测试1: 获取股票代码列表

```bash
# 获取所有股票
curl "http://localhost:8080/api/codes"

# 只获取上海股票
curl "http://localhost:8080/api/codes?exchange=sh"

# 只获取深圳股票
curl "http://localhost:8080/api/codes?exchange=sz"
```

预期响应：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total": 5234,
    "exchanges": {
      "sh": 2156,
      "sz": 2845,
      "bj": 233
    },
    "codes": [
      {
        "code": "000001",
        "name": "平安银行",
        "exchange": "sz"
      }
    ]
  }
}
```

### 测试2: 批量获取行情

```bash
curl -X POST http://localhost:8080/api/batch-quote \
  -H "Content-Type: application/json" \
  -d '{"codes":["000001","600519","601318"]}'
```

预期响应：
```json
{
  "code": 0,
  "message": "success",
  "data": [
    { /* 000001的行情数据 */ },
    { /* 600519的行情数据 */ },
    { /* 601318的行情数据 */ }
  ]
}
```

### 测试3: 健康检查

```bash
curl "http://localhost:8080/api/health"
```

预期响应：
```json
{
  "status": "healthy",
  "time": 1730617200
}
```

---

## 📚 完整API列表

### 基础数据接口

| 接口 | 方法 | 说明 | 状态 |
|-----|------|------|------|
| /api/quote | GET | 五档行情 | ✅ 已实现 |
| /api/kline | GET | K线数据 | ✅ 已实现 |
| /api/minute | GET | 分时数据 | ✅ 已实现 |
| /api/trade | GET | 分时成交 | ✅ 已实现 |
| /api/search | GET | 搜索股票 | ✅ 已实现 |
| /api/stock-info | GET | 综合信息 | ✅ 已实现 |

### 扩展功能接口

| 接口 | 方法 | 说明 | 状态 |
|-----|------|------|------|
| /api/codes | GET | 股票列表 | ✅ 已实现 |
| /api/batch-quote | POST | 批量行情 | ✅ 已实现 |
| /api/kline-history | GET | 历史K线 | ✅ 已实现 |
| /api/index | GET | 指数数据 | ✅ 已实现 |
| /api/market-stats | GET | 市场统计 | ✅ 已实现 |
| /api/status | GET | 服务状态 | ✅ 已实现 |
| /api/health | GET | 健康检查 | ✅ 已实现 |

### 静态文件

| 路径 | 说明 | 状态 |
|-----|------|------|
| / | Web界面 | ✅ 已实现 |
| /static/* | 静态资源 | ✅ 已实现 |

---

## 🎯 使用场景

### 场景1: 量化交易系统

```python
import requests

BASE_URL = "http://your-server:8080"

# 1. 获取所有股票代码
codes_resp = requests.get(f"{BASE_URL}/api/codes")
all_codes = [c['code'] for c in codes_resp.json()['data']['codes']]

# 2. 批量获取行情（每次50只）
for i in range(0, len(all_codes), 50):
    batch = all_codes[i:i+50]
    quotes = requests.post(
        f"{BASE_URL}/api/batch-quote",
        json={"codes": batch}
    ).json()['data']
    
    # 分析行情数据
    for quote in quotes:
        analyze_quote(quote)

# 3. 获取K线进行技术分析
kline = requests.get(
    f"{BASE_URL}/api/kline?code=000001&type=day"
).json()['data']['List']

calculate_ma(kline)  # 计算均线
calculate_macd(kline)  # 计算MACD
```

### 场景2: 实时监控面板

```javascript
// 定时刷新行情
setInterval(async () => {
    // 批量获取自选股行情
    const watchlist = ['000001', '600519', '601318'];
    const response = await fetch('/api/batch-quote', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({codes: watchlist})
    });
    const quotes = await response.json();
    
    // 更新界面
    updateDashboard(quotes.data);
}, 3000);
```

### 场景3: 数据分析

```python
# 获取全市场数据进行分析
import pandas as pd

# 1. 获取所有股票
codes = get_all_codes()

# 2. 获取每只股票的日K线
data = []
for code in codes:
    kline = get_kline(code, 'day')
    df = pd.DataFrame(kline)
    df['code'] = code
    data.append(df)

# 3. 合并分析
all_data = pd.concat(data)

# 4. 筛选涨停股
limit_up = all_data[all_data['涨跌幅'] >= 9.9]
```

---

## 🔐 安全建议

### 1. 添加认证

```go
func authMiddleware(next http.HandlerFunc) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        token := r.Header.Get("Authorization")
        if token != "your-secret-token" {
            errorResponse(w, "未授权")
            return
        }
        next(w, r)
    }
}

// 使用
http.HandleFunc("/api/quote", authMiddleware(handleGetQuote))
```

### 2. 限流控制

```go
import "golang.org/x/time/rate"

var limiter = rate.NewLimiter(10, 20) // 每秒10次，突发20次

func rateLimitMiddleware(next http.HandlerFunc) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        if !limiter.Allow() {
            errorResponse(w, "请求过于频繁")
            return
        }
        next(w, r)
    }
}
```

### 3. CORS配置

```go
func corsMiddleware(next http.HandlerFunc) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        w.Header().Set("Access-Control-Allow-Origin", "*")
        w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
        
        if r.Method == "OPTIONS" {
            w.WriteHeader(http.StatusOK)
            return
        }
        next(w, r)
    }
}
```

---

## 📊 性能优化

### 1. 启用gzip压缩

```go
import "github.com/NYTimes/gziphandler"

http.Handle("/api/", gziphandler.GzipHandler(apiRouter))
```

### 2. 添加缓存

```go
var cache = make(map[string]interface{})
var cacheMux sync.RWMutex

func getCached(key string) (interface{}, bool) {
    cacheMux.RLock()
    defer cacheMux.RUnlock()
    val, ok := cache[key]
    return val, ok
}

func setCache(key string, val interface{}) {
    cacheMux.Lock()
    defer cacheMux.Unlock()
    cache[key] = val
}
```

---

## 📖 完整文档

- **API接口文档**: `API_接口文档.md`
- **本集成指南**: `API_集成指南.md`
- **扩展代码**: `web/server_api_extended.go`

---

## ✅ 总结

### 已完成
✅ 12个完整API接口  
✅ 详细的接口文档  
✅ 使用示例（Python/JavaScript/cURL）  
✅ 集成指南  
✅ 安全和性能建议  

### 使用流程
1. 阅读 `API_接口文档.md` 了解所有接口
2. 按照本文档集成扩展接口
3. 重新构建Docker镜像
4. 测试接口功能
5. 开始使用API开发应用

---

**现在所有功能都已打包为API接口，可以直接使用！** 🎉

