# go-stock-dev 数据获取API文档

## 概述

本文档详细说明 `go-stock-dev` 项目中所有数据获取接口的数据源、获取方式、频率和数据结构，供 Go 语言或 Python 开发者参考。

---

## 一、股票实时行情数据

### 1.1 A股实时行情

**数据源**: 新浪财经 (Sina Finance)  
**接口URL**: `http://hq.sinajs.cn/rn={timestamp}&list={codes}`  
**获取方式**: HTTP GET  
**频率**: 可配置（默认30秒，通过 `RefreshInterval` 配置）  
**代码位置**: `backend/data/stock_data_api.go:GetStockCodeRealTimeData()`

**数据格式**:
```
var hq_str_sz000001="平安银行,27.55,27.25,26.91,27.55,26.20,26.91,26.92,22114263,589824680,4695,26.91,57590,26.90,14700,26.89,14300,26.88,15100,26.87,3100,26.92,2008-01-11,15:05:32";
```

**字段说明**:
- 字段0: 股票名称
- 字段1: 今日开盘价
- 字段2: 昨日收盘价
- 字段3: 当前价格
- 字段4: 今日最高价
- 字段5: 今日最低价
- 字段6: 竞买价（买一报价）
- 字段7: 竞卖价（卖一报价）
- 字段8: 成交的股票数
- 字段9: 成交金额
- 字段10-19: 买一至买五申报和报价
- 字段20-29: 卖一至卖五申报和报价
- 字段30: 日期
- 字段31: 时间

**Go实现示例**:
```go
url := fmt.Sprintf("http://hq.sinajs.cn/rn=%d&list=%s", time.Now().Unix(), codes)
resp, err := client.R().
    SetHeader("Host", "hq.sinajs.cn").
    SetHeader("Referer", "https://finance.sina.com.cn/").
    SetHeader("User-Agent", "Mozilla/5.0...").
    Get(url)
```

**Python实现示例**:
```python
import requests
import time

def get_sina_stock_data(codes):
    url = f"http://hq.sinajs.cn/rn={int(time.time())}&list={codes}"
    headers = {
        "Host": "hq.sinajs.cn",
        "Referer": "https://finance.sina.com.cn/",
        "User-Agent": "Mozilla/5.0..."
    }
    response = requests.get(url, headers=headers)
    return response.text
```

---

### 1.2 港股实时行情

**数据源**: 腾讯财经 (Tencent Finance)  
**接口URL**: `http://qt.gtimg.cn/?_={timestamp}&q={codes}`  
**获取方式**: HTTP GET  
**频率**: 可配置（默认30秒）  
**代码位置**: `backend/data/stock_data_api.go:GetStockCodeRealTimeData()`

**数据格式**:
```
v_r_hk09660="100~地平线机器人-W~09660~6.240~5.690~5.800~192659034.0~...~2025/04/29 13:41:04~...";
```

**字段说明**:
- 字段0: 状态码
- 字段1: 股票名称
- 字段2: 股票代码
- 字段3: 当前价
- 字段4: 昨收价
- 字段5: 开盘价
- 字段33: 最高价
- 字段34: 最低价
- 字段30: 时间

**Go实现示例**:
```go
url := fmt.Sprintf("http://qt.gtimg.cn/?_=%d&q=%s", time.Now().Unix(), codes)
resp, err := client.R().
    SetHeader("Host", "qt.gtimg.cn").
    SetHeader("Referer", "https://gu.qq.com/").
    Get(url)
```

**Python实现示例**:
```python
def get_tencent_hk_stock_data(codes):
    url = f"http://qt.gtimg.cn/?_={int(time.time())}&q={codes}"
    headers = {
        "Host": "qt.gtimg.cn",
        "Referer": "https://gu.qq.com/",
        "User-Agent": "Mozilla/5.0..."
    }
    response = requests.get(url, headers=headers)
    return response.content.decode('gb18030')
```

---

### 1.3 美股实时行情

**数据源**: 新浪财经 (Sina Finance)  
**接口URL**: `http://hq.sinajs.cn/rn={timestamp}&list=gb_{code}`  
**获取方式**: HTTP GET  
**频率**: 可配置（默认30秒）  
**代码位置**: `backend/data/stock_data_api.go:GetStockCodeRealTimeData()`

**数据格式**:
```
var hq_str_gb_goog="谷歌,170.2100,-2.57,2025-02-28 09:38:50,-4.4900,175.9400,176.5900,169.7520,208.7000,130.9500,...";
```

**字段说明**:
- 字段0: 股票名称
- 字段1: 现价
- 字段2: 涨跌幅
- 字段3: 时间
- 字段4: 涨跌额
- 字段5: 今日开盘价
- 字段6-7: 区间价格
- 字段8-9: 52周区间
- 字段21: 盘前盘后价格
- 字段22: 盘前盘后涨跌幅
- 字段26: 前收盘价

---

## 二、股票基础信息数据

### 2.1 Tushare股票基础信息

**数据源**: Tushare Pro API  
**接口URL**: `http://api.tushare.pro`  
**获取方式**: HTTP POST (JSON)  
**频率**: 启动时更新（`UpdateBasicInfoOnStart=true`）或手动触发  
**代码位置**: `backend/data/stock_data_api.go:GetStockBaseInfo()`

**请求格式**:
```json
{
  "api_name": "stock_basic",
  "token": "{tushare_token}",
  "params": null,
  "fields": "ts_code,symbol,name,area,industry,cnspell,market,list_date,..."
}
```

**响应字段**:
- `ts_code`: TS代码
- `symbol`: 股票代码
- `name`: 股票名称
- `area`: 地域
- `industry`: 所属行业
- `market`: 市场类型
- `list_date`: 上市日期
- `list_status`: 上市状态

**Go实现示例**:
```go
resp, err := client.R().
    SetHeader("content-type", "application/json").
    SetBody(&TushareRequest{
        ApiName: "stock_basic",
        Token:   token,
        Params:  nil,
        Fields:  "ts_code,symbol,name,area,industry,...",
    }).
    Post("http://api.tushare.pro")
```

**Python实现示例**:
```python
import tushare as ts

def get_stock_basic_info():
    pro = ts.pro_api(token)
    df = pro.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name,area,industry')
    return df
```

---

### 2.2 东方财富股票列表

**数据源**: 东方财富 (Eastmoney)  
**接口URL**: `https://push2.eastmoney.com/api/qt/clist/get?np=1&fltt=1&invt=2&cb=data&fs={market}&fields=...&pn={page}&pz={pageSize}`  
**获取方式**: HTTP GET  
**频率**: 手动触发或定时更新  
**代码位置**: `backend/data/stock_data_api.go:getDCStockInfo()`

**市场参数**:
- A股: `m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048`
- 港股: `m:128+t:3,m:128+t:4,m:128+t:1,m:128+t:2`
- 美股: `m:105,m:106,m:107`

**Go实现示例**:
```go
url := fmt.Sprintf("https://push2.eastmoney.com/api/qt/clist/get?fs=%s&pn=%d&pz=%d&_=%d", 
    market, page, pageSize, time.Now().UnixMilli())
resp, err := client.R().
    SetHeader("Host", "push2.eastmoney.com").
    SetHeader("Referer", "https://quote.eastmoney.com/center/gridlist.html").
    Get(url)
```

---

## 三、K线数据

### 3.1 A股K线数据（新浪）

**数据源**: 新浪财经  
**接口URL**: `http://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData?symbol={code}&scale={type}&ma=yes&datalen={days}`  
**获取方式**: HTTP GET  
**频率**: 按需获取  
**代码位置**: `backend/data/stock_data_api.go:GetKLineData()`

**参数说明**:
- `symbol`: 股票代码（如 `sz000001`）
- `scale`: K线类型（`5`, `15`, `30`, `60`, `day`, `week`, `month`）
- `datalen`: 数据长度（天数）

**Go实现示例**:
```go
url := fmt.Sprintf("http://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData?symbol=%s&scale=%s&ma=yes&datalen=%d", 
    code, klineType, days)
resp, err := client.R().
    SetHeader("Host", "quotes.sina.cn").
    Get(url)
```

---

### 3.2 港股/美股K线数据（腾讯）

**数据源**: 腾讯财经  
**接口URL**: `https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},{type},,,{days},qfq`  
**获取方式**: HTTP GET  
**频率**: 按需获取  
**代码位置**: `backend/data/stock_data_api.go:GetHK_KLineData()`

**参数说明**:
- `code`: 股票代码（港股如 `00700.HK`，美股如 `AAPL.OQ`）
- `type`: K线类型（`day`, `week`, `month`）
- `days`: 数据天数

**Go实现示例**:
```go
url := fmt.Sprintf("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=%s,%s,,,%d,qfq", 
    code, klineType, days)
resp, err := client.R().
    SetHeader("Host", "web.ifzq.gtimg.cn").
    Get(url)
```

---

### 3.3 Tushare日线数据

**数据源**: Tushare Pro API  
**接口URL**: `http://api.tushare.pro`  
**获取方式**: HTTP POST  
**频率**: 按需获取  
**代码位置**: `backend/data/tushare_data_api.go:GetDaily()`

**请求格式**:
```json
{
  "api_name": "daily",
  "token": "{token}",
  "params": {
    "ts_code": "000001.SZ",
    "start_date": "20240101",
    "end_date": "20241231"
  },
  "fields": "ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount"
}
```

**支持的股票类型**:
- A股: `daily`
- 港股: `hk_daily`
- 美股: `us_daily`

---

## 四、分时数据

### 4.1 A股分时数据

**数据源**: 腾讯财经  
**接口URL**: `https://web.ifzq.gtimg.cn/appstock/app/minute/query?code={code}`  
**获取方式**: HTTP GET  
**频率**: 按需获取  
**代码位置**: `backend/data/stock_data_api.go:GetStockMinutePriceData()`

**数据格式**: JSON
```json
{
  "code": 0,
  "data": {
    "sz000001": {
      "data": {
        "date": "20250101",
        "data": ["0930 26.91 1000 26910", "0931 26.92 2000 53840", ...]
      }
    }
  }
}
```

**Go实现示例**:
```go
url := fmt.Sprintf("https://web.ifzq.gtimg.cn/appstock/app/minute/query?code=%s", code)
resp, err := client.R().
    SetHeader("Host", "web.ifzq.gtimg.cn").
    Get(url)
```

---

### 4.2 美股分时数据

**数据源**: 腾讯财经  
**接口URL**: `https://web.ifzq.gtimg.cn/appstock/app/UsMinute/query?code={code}`  
**获取方式**: HTTP GET  
**频率**: 按需获取  

**代码转换**: 美股代码需要转换为 `{code}.OQ` 格式（如 `AAPL.OQ`）

---

## 五、市场新闻数据

### 5.1 财联社电报

**数据源**: 财联社 (CLS)  
**接口URL**: `https://www.cls.cn/telegraph`  
**获取方式**: HTTP GET + HTML解析  
**频率**: 可配置（默认 `RefreshInterval+10` 秒）  
**代码位置**: `backend/data/market_news_api.go:GetNewTelegraph()`

**数据结构**:
- 时间
- 内容
- 主题标签
- 股票标签
- 是否标红

**Go实现示例**:
```go
resp, err := resty.New().R().
    SetHeader("Referer", "https://www.cls.cn/").
    SetHeader("User-Agent", "Mozilla/5.0...").
    Get("https://www.cls.cn/telegraph")
// 使用 goquery 解析 HTML
```

**Python实现示例**:
```python
from bs4 import BeautifulSoup
import requests

def get_cls_telegraph():
    url = "https://www.cls.cn/telegraph"
    headers = {
        "Referer": "https://www.cls.cn/",
        "User-Agent": "Mozilla/5.0..."
    }
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    # 解析 .telegraph-content-box 元素
    return soup.select('.telegraph-content-box')
```

---

### 5.2 新浪财经新闻

**数据源**: 新浪财经  
**接口URL**: `https://zhibo.sina.com.cn/api/zhibo/feed?callback=callback&page=1&page_size=20&zhibo_id=152&...`  
**获取方式**: HTTP GET (JSONP)  
**频率**: 可配置（默认 `RefreshInterval+10` 秒）  
**代码位置**: `backend/data/market_news_api.go:GetSinaNews()`

**数据格式**: JSONP回调
```javascript
callback({
  "result": {
    "data": {
      "feed": {
        "list": [
          {
            "create_time": "2025-01-01 10:00:00",
            "rich_text": "新闻内容",
            "tag": [{"name": "标签"}]
          }
        ]
      }
    }
  }
});
```

---

### 5.3 TradingView新闻

**数据源**: TradingView  
**接口URL**: `https://news-mediator.tradingview.com/news-flow/v2/news?filter=lang:zh-Hans&filter=provider:panews,reuters&...`  
**获取方式**: HTTP GET  
**频率**: 按需获取  
**代码位置**: `backend/data/market_news_api.go:TradingViewNews()`

**注意**: 可能需要代理访问

---

## 六、市场数据

### 6.1 全球指数

**数据源**: 腾讯财经  
**接口URL**: `https://proxy.finance.qq.com/ifzqgtimg/appstock/app/rank/indexRankDetail2`  
**获取方式**: HTTP GET  
**频率**: 按需获取  
**代码位置**: `backend/data/market_news_api.go:GlobalStockIndexes()`

---

### 6.2 行业排名

**数据源**: 腾讯财经  
**接口URL**: `https://proxy.finance.qq.com/ifzqgtimg/appstock/app/mktHs/rank?l={count}&p=1&t=01/averatio&ordertype=&o={sort}`  
**获取方式**: HTTP GET  
**频率**: 按需获取  
**代码位置**: `backend/data/market_news_api.go:GetIndustryRank()`

**参数说明**:
- `l`: 返回数量
- `o`: 排序方式（`asc`/`desc`）

---

### 6.3 资金流向

**数据源**: 新浪财经  
**接口URL**: 
- 行业资金流向: `https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/MoneyFlow.ssl_bkzj_bk?page=1&num=20&sort={sort}&asc=0&fenlei={fenlei}`
- 个股资金流向: `https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/MoneyFlow.ssl_bkzj_ssggzj?page=1&num=20&sort={sort}&asc=0`
- 个股资金趋势: `http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/MoneyFlow.ssl_qsfx_zjlrqs?page=1&num={days}&sort=opendate&asc=0&daima={code}`

**获取方式**: HTTP GET  
**频率**: 按需获取  
**代码位置**: `backend/data/market_news_api.go:GetIndustryMoneyRankSina()`, `GetMoneyRankSina()`, `GetStockMoneyTrendByDay()`

---

### 6.4 龙虎榜

**数据源**: 东方财富  
**接口URL**: `https://datacenter-web.eastmoney.com/api/data/v1/get?callback=callback&sortColumns=...&pageSize=500&pageNumber=1&reportName=RPT_DAILYBILLBOARD_DETAILSNEW&...&filter=(TRADE_DATE<='{date}')(TRADE_DATE>='{date}')`  
**获取方式**: HTTP GET (JSONP)  
**频率**: 按需获取  
**代码位置**: `backend/data/market_news_api.go:LongTiger()`

---

## 七、研报数据

### 7.1 行业研报

**数据源**: 东方财富  
**接口URL**: `https://reportapi.eastmoney.com/report/list?industry=*&industryCode={code}&beginTime={begin}&endTime={end}&pageNo=1&pageSize=50&...`  
**获取方式**: HTTP GET  
**频率**: 按需获取  
**代码位置**: `backend/data/market_news_api.go:IndustryResearchReport()`

---

### 7.2 个股研报

**数据源**: 东方财富  
**接口URL**: `https://reportapi.eastmoney.com/report/list2`  
**获取方式**: HTTP POST (JSON)  
**频率**: 按需获取  
**代码位置**: `backend/data/market_news_api.go:StockResearchReport()`

**请求格式**:
```json
{
  "code": "000001",
  "industryCode": "*",
  "beginTime": "2024-01-01",
  "endTime": "2025-01-01",
  "PageNo": 1,
  "PageSize": 50
}
```

---

### 7.3 研报详情

**数据源**: 东方财富  
**接口URL**: `https://data.eastmoney.com/report/zw_industry.jshtml?infocode={infoCode}`  
**获取方式**: HTTP GET + HTML解析  
**频率**: 按需获取  
**代码位置**: `backend/data/market_news_api.go:GetIndustryReportInfo()`

---

## 八、公司公告

### 8.1 股票公告

**数据源**: 东方财富  
**接口URL**: `https://np-anotice-stock.eastmoney.com/api/security/ann?page_size=50&page_index=1&ann_type=SHA%2CCYB%2CSZA%2CBJA%2CINV&client_source=web&f_node=0&stock_list={codes}`  
**获取方式**: HTTP GET  
**频率**: 按需获取  
**代码位置**: `backend/data/market_news_api.go:StockNotice()`

**参数说明**:
- `stock_list`: 股票代码列表（逗号分隔，如 `000001,600000`）
- `ann_type`: 公告类型（`SHA`, `CYB`, `SZA`, `BJA`, `INV`）

---

## 九、热门数据

### 9.1 雪球热门股票

**数据源**: 雪球 (Xueqiu)  
**接口URL**: `https://stock.xueqiu.com/v5/stock/hot_stock/list.json?page=1&size={size}&_type={marketType}&type={marketType}`  
**获取方式**: HTTP GET  
**频率**: 按需获取（前端定时刷新）  
**代码位置**: `backend/data/market_news_api.go:XUEQIUHotStock()`

**注意**: 需要先访问 `https://xueqiu.com/hq#hot` 获取 Cookie

---

### 9.2 雪球热门事件

**数据源**: 雪球  
**接口URL**: `https://xueqiu.com/hot_event/list.json?count={size}`  
**获取方式**: HTTP GET  
**频率**: 按需获取  
**代码位置**: `backend/data/market_news_api.go:HotEvent()`

---

### 9.3 股吧热门话题

**数据源**: 东方财富股吧  
**接口URL**: `https://gubatopic.eastmoney.com/interface/GetData.aspx?path=newtopic/api/Topic/HomePageListRead`  
**获取方式**: HTTP POST  
**频率**: 按需获取  
**代码位置**: `backend/data/market_news_api.go:HotTopic()`

**请求参数**:
```
param: ps={size}&p=1&type=0
path: newtopic/api/Topic/HomePageListRead
env: 2
```

---

## 十、财经日历

### 10.1 九阳公社财经日历

**数据源**: 九阳公社  
**接口URL**: `https://app.jiuyangongshe.com/jystock-app/api/v1/timeline/list`  
**获取方式**: HTTP POST (JSON)  
**频率**: 按需获取  
**代码位置**: `backend/data/market_news_api.go:InvestCalendar()`

**请求格式**:
```json
{
  "date": "2025-01",
  "grade": "0"
}
```

---

### 10.2 财联社财经日历

**数据源**: 财联社  
**接口URL**: `https://www.cls.cn/api/calendar/web/list?app=CailianpressWeb&flag=0&os=web&sv=8.4.6&type=0&sign=...`  
**获取方式**: HTTP GET  
**频率**: 按需获取  
**代码位置**: `backend/data/market_news_api.go:ClsCalendar()`

---

## 十一、经济数据

### 11.1 GDP数据

**数据源**: 东方财富数据中心  
**接口URL**: `https://datacenter-web.eastmoney.com/api/data/v1/get?callback=data&columns=REPORT_DATE%2CTIME%2CDOMESTICL_PRODUCT_BASE%2C...&reportName=RPT_ECONOMY_GDP&...`  
**获取方式**: HTTP GET (JSONP)  
**频率**: 按需获取  
**代码位置**: `backend/data/market_news_api.go:GetGDP()`

---

### 11.2 CPI数据

**数据源**: 东方财富数据中心  
**接口URL**: `https://datacenter-web.eastmoney.com/api/data/v1/get?callback=data&columns=REPORT_DATE%2CTIME%2CNATIONAL_SAME%2C...&reportName=RPT_ECONOMY_CPI&...`  
**获取方式**: HTTP GET (JSONP)  
**频率**: 按需获取  
**代码位置**: `backend/data/market_news_api.go:GetCPI()`

---

### 11.3 PPI数据

**数据源**: 东方财富数据中心  
**接口URL**: `https://datacenter-web.eastmoney.com/api/data/v1/get?callback=data&columns=REPORT_DATE,TIME,BASE,BASE_SAME,BASE_ACCUMULATE&reportName=RPT_ECONOMY_PPI&...`  
**获取方式**: HTTP GET (JSONP)  
**频率**: 按需获取  
**代码位置**: `backend/data/market_news_api.go:GetPPI()`

---

### 11.4 PMI数据

**数据源**: 东方财富数据中心  
**接口URL**: `https://datacenter-web.eastmoney.com/api/data/v1/get?callback=data&columns=REPORT_DATE%2CTIME%2CMAKE_INDEX%2C...&reportName=RPT_ECONOMY_PMI&...`  
**获取方式**: HTTP GET (JSONP)  
**频率**: 按需获取  
**代码位置**: `backend/data/market_news_api.go:GetPMI()`

---

## 十二、基金数据

### 12.1 基金基本信息

**数据源**: 天天基金网（爬虫）  
**接口URL**: `http://fund.eastmoney.com/{fundCode}.html`  
**获取方式**: HTTP GET + HTML解析（使用 Chromedp）  
**频率**: 按需获取  
**代码位置**: `backend/data/fund_data_api.go:CrawlFundBasic()`

**解析字段**:
- 基金名称
- 基金类型
- 成立日期
- 基金规模
- 基金管理人
- 基金经理
- 基金评级
- 跟踪标的
- 净值涨跌幅（近1月、近3月、近6月、近1年、近3年、近5年、今年来、成立来）

---

### 12.2 基金净值估算

**数据源**: 天天基金网  
**接口URL**: `https://fundgz.1234567.com.cn/js/{fundCode}.js?rt={timestamp}`  
**获取方式**: HTTP GET (JSONP)  
**频率**: 可配置（默认60秒）  
**代码位置**: `backend/data/fund_data_api.go:CrawlFundNetEstimatedUnit()`

**数据格式**:
```javascript
jsonpgz({
  "fundcode": "000001",
  "name": "华夏成长混合",
  "jzrq": "2025-01-01",
  "dwjz": "1.2345",
  "gsz": "1.2356",
  "gszzl": "0.09",
  "gztime": "2025-01-01 15:00"
});
```

---

### 12.3 基金净值

**数据源**: 新浪财经  
**接口URL**: `http://hq.sinajs.cn/rn={timestamp}&list=f_{fundCode}`  
**获取方式**: HTTP GET  
**频率**: 可配置（默认60秒）  
**代码位置**: `backend/data/fund_data_api.go:CrawlFundNetUnitValue()`

**数据格式**:
```
var hq_str_f_000001="华夏成长混合,1.2345,1.2345,1.2345,2025-01-01";
```

---

### 12.4 基金列表

**数据源**: 天天基金网  
**接口URL**: `https://fund.eastmoney.com/allfund.html`  
**获取方式**: HTTP GET + HTML解析  
**频率**: 手动触发  
**代码位置**: `backend/data/fund_data_api.go:AllFund()`

---

## 十三、股票搜索

### 13.1 东方财富股票搜索

**数据源**: 东方财富  
**接口URL**: `https://np-tjxg-g.eastmoney.com/api/smart-tag/stock/v3/pw/search-code`  
**获取方式**: HTTP POST (JSON)  
**频率**: 按需获取  
**代码位置**: `backend/data/search_stock_api.go:SearchStock()`

**请求格式**:
```json
{
  "keyWord": "平安银行",
  "pageSize": 10,
  "pageNo": 1,
  "fingerprint": "...",
  "timestamp": 1234567890
}
```

---

### 13.2 热门策略

**数据源**: 东方财富  
**接口URL**: `https://np-ipick.eastmoney.com/recommend/stock/heat/ranking?count=20&trace={timestamp}&client=web&biz=web_smart_tag`  
**获取方式**: HTTP GET  
**频率**: 按需获取  
**代码位置**: `backend/data/search_stock_api.go:HotStrategy()`

---

## 十四、互动问答

### 14.1 深交所互动易

**数据源**: 深交所互动易  
**接口URL**: `https://irm.cninfo.com.cn/newircs/index/search?_t={timestamp}`  
**获取方式**: HTTP POST (Form Data)  
**频率**: 按需获取  
**代码位置**: `backend/data/market_news_api.go:InteractiveAnswer()`

**请求参数**:
```
pageNo: 1
pageSize: 20
searchTypes: 11
highLight: true
keyWord: {keyword}
```

---

## 十五、数据更新频率总结

| 数据类型 | 默认频率 | 配置项 | 说明 |
|---------|---------|--------|------|
| 股票实时行情 | 30秒 | `RefreshInterval` | 可配置，最小1秒 |
| 财联社电报 | `RefreshInterval+10`秒 | - | 相对股票行情延迟10秒 |
| 新浪财经新闻 | `RefreshInterval+10`秒 | - | 相对股票行情延迟10秒 |
| 基金净值估算 | 60秒 | - | 固定 |
| 基金净值 | 60秒 | - | 固定 |
| 股票基础信息 | 启动时 | `UpdateBasicInfoOnStart` | 布尔值 |
| Tushare数据 | 按需 | - | 手动调用 |
| K线数据 | 按需 | - | 手动调用 |
| 分时数据 | 按需 | - | 手动调用 |
| 市场新闻 | 按需 | - | 手动调用 |
| 研报数据 | 按需 | - | 手动调用 |
| 公告数据 | 按需 | - | 手动调用 |

---

## 十六、技术实现要点

### 16.1 HTTP客户端

**Go实现**: 使用 `github.com/go-resty/resty/v2`
```go
client := resty.New()
client.SetTimeout(time.Duration(timeout) * time.Second)
resp, err := client.R().
    SetHeader("User-Agent", "Mozilla/5.0...").
    Get(url)
```

**Python实现**: 使用 `requests`
```python
import requests

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0..."
})
response = session.get(url, timeout=30)
```

---

### 16.2 HTML解析

**Go实现**: 使用 `github.com/PuerkitoBio/goquery`
```go
doc, err := goquery.NewDocumentFromReader(strings.NewReader(html))
doc.Find(".class-name").Each(func(i int, s *goquery.Selection) {
    text := s.Text()
})
```

**Python实现**: 使用 `BeautifulSoup`
```python
from bs4 import BeautifulSoup

soup = BeautifulSoup(html, 'html.parser')
elements = soup.select('.class-name')
for elem in elements:
    text = elem.get_text()
```

---

### 16.3 浏览器自动化（爬虫）

**Go实现**: 使用 `github.com/chromedp/chromedp`
```go
ctx, cancel := chromedp.NewContext(context.Background())
defer cancel()
err := chromedp.Run(ctx,
    chromedp.Navigate(url),
    chromedp.WaitVisible("selector", chromedp.ByQuery),
    chromedp.InnerHTML("body", &htmlContent),
)
```

**Python实现**: 使用 `selenium` 或 `playwright`
```python
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

driver = webdriver.Chrome()
driver.get(url)
element = WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.CSS_SELECTOR, "selector"))
)
html = driver.page_source
driver.quit()
```

---

### 16.4 JSONP解析

**Go实现**: 使用 `github.com/robertkrimen/otto` (JavaScript引擎)
```go
vm := otto.New()
vm.Run("function callback(res){return res};")
val, err := vm.Run(jsString)
data, _ := val.Object().Value().Export()
```

**Python实现**: 使用正则表达式或 `json` 模块
```python
import re
import json

# 提取JSONP中的JSON数据
match = re.search(r'callback\((.*)\);', js_string)
if match:
    json_data = json.loads(match.group(1))
```

---

### 16.5 字符编码转换

**Go实现**: 使用 `golang.org/x/text/encoding/simplifiedchinese`
```go
import "golang.org/x/text/encoding/simplifiedchinese"
import "golang.org/x/text/transform"

reader := transform.NewReader(bytes.NewReader(data), simplifiedchinese.GB18030.NewDecoder())
utf8Data, _ := io.ReadAll(reader)
```

**Python实现**: 使用 `decode`
```python
data = response.content.decode('gb18030')
# 或
data = response.text  # requests会自动处理编码
```

---

## 十七、注意事项

1. **请求频率限制**: 各数据源可能有请求频率限制，建议：
   - 股票实时行情：不低于3秒
   - 新闻数据：不低于10秒
   - 其他数据：按需获取

2. **User-Agent**: 建议设置真实的浏览器 User-Agent，避免被反爬虫机制拦截

3. **Referer**: 某些接口需要设置正确的 Referer 头

4. **Cookie**: 部分接口（如雪球）需要先访问主页获取 Cookie

5. **代理**: TradingView、Reuters 等国外数据源可能需要代理访问

6. **超时设置**: 建议设置合理的超时时间（30-60秒）

7. **错误处理**: 所有接口调用都应包含错误处理和重试机制

8. **数据缓存**: 对于不经常变化的数据（如股票基础信息），建议缓存以减少请求

---

## 十八、配置说明

### 18.1 主要配置项

**配置文件**: `config.json` 或数据库 `settings` 表

```json
{
  "refresh_interval": 30,           // 数据刷新间隔（秒）
  "crawl_time_out": 60,             // 爬虫超时时间（秒）
  "tushare_token": "...",           // Tushare Token
  "update_basic_info_on_start": true, // 启动时更新基础信息
  "browser_path": "...",            // 浏览器路径（用于爬虫）
  "browser_pool_size": 1,           // 浏览器池大小
  "http_proxy": "...",              // HTTP代理
  "http_proxy_enabled": false        // 是否启用代理
}
```

---

## 十九、数据库存储

程序使用 SQLite 数据库存储以下数据：
- `stock_info`: 股票实时信息
- `followed_stock`: 关注股票列表
- `tushare_stock_basic`: Tushare股票基础信息
- `tushare_index_basic`: Tushare指数基础信息
- `telegraph`: 财联社电报
- `tags`: 标签
- `telegraph_tags`: 电报标签关联
- `fund_basic`: 基金基本信息
- `followed_fund`: 关注基金列表
- `settings`: 系统设置
- `ai_config`: AI配置

---

## 二十、参考资源

- [Tushare Pro API文档](https://tushare.pro/document/2)
- [新浪财经API](https://finance.sina.com.cn/)
- [腾讯财经API](https://finance.qq.com/)
- [东方财富API](https://www.eastmoney.com/)
- [财联社API](https://www.cls.cn/)

---

**文档版本**: 1.0  
**最后更新**: 2025-01-XX  
**维护者**: go-stock-dev 项目组

