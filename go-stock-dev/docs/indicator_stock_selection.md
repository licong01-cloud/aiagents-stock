# 指标选股业务逻辑与 Python 复现说明

> 适用版本：当前 go-stock 项目中“指标选股”功能实现（`ChoiceStockByIndicators` 工具 + `SearchStockApi` 数据层 + 前端 `SelectStock.vue`）。
>
> 目标：读者可以基于本文档，仅使用 Python 复现与客户端中“指标选股”等价的核心功能：根据自然语言描述的选股条件，从东方财富智能选股接口获取股票列表及相关指标数据，并以表格方式展示/后续处理。

---

## 一、整体业务流程概览

### 1.1 前后端调用链

- **前端入口**：
  - 组件：`frontend/src/components/market.vue`
  - 页签：`<n-tab-pane name="指标选股" tab="指标选股">`
  - 内嵌组件：`<SelectStock />`

- **前端核心组件**：`frontend/src/components/SelectStock.vue`
  - 使用 `SearchStock`（Wails 生成的 Go 绑定函数）向本地 Go 应用发起调用。
  - 主要逻辑：
    - 用户在输入框中输入选股的自然语言条件（或从“热门策略”点击填充）。
    - 调用 `SearchStock(search.value)` 获取选股结果。
    - 将返回的 `columns` 和 `dataList` 转为前端表格所需结构，并渲染。

- **Go 应用对外接口**：`go-stock-dev/go-stock-dev/app_common.go`

  ```go
  func (a App) SearchStock(words string) map[string]any {
      return data.NewSearchStockApi(words).SearchStock(5000)
  }
  ```

  - `words`：自然语言选股条件，由前端透传。
  - 内部调用：`data.NewSearchStockApi(words).SearchStock(5000)`。

- **数据访问层**：`backend/data/search_stock_api.go`

  ```go
  type SearchStockApi struct {
      words string
  }

  func NewSearchStockApi(words string) *SearchStockApi {
      return &SearchStockApi{words: words}
  }

  func (s SearchStockApi) SearchStock(pageSize int) map[string]any {
      url := "https://np-tjxg-g.eastmoney.com/api/smart-tag/stock/v3/pw/search-code"
      resp, err := resty.New().SetTimeout(time.Duration(30)*time.Second).R().
          SetHeader("Host", "np-tjxg-g.eastmoney.com").
          SetHeader("Origin", "https://xuangu.eastmoney.com").
          SetHeader("Referer", "https://xuangu.eastmoney.com/").
          SetHeader("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:145.0) Gecko/20100101 Firefox/145.0").
          SetHeader("Content-Type", "application/json").
          SetBody(fmt.Sprintf(`{
                  "keyWord": "%s",
                  "pageSize": %d,
                  "pageNo": 1,
                  "fingerprint": "02efa8944b1f90fbfe050e1e695a480d",
                  "gids": [],
                  "matchWord": "",
                  "timestamp": "%d",
                  "shareToGuba": false,
                  "requestId": "RMd3Y76AJI98axPvdhdbKvbBDVwLlUK61761559950168",
                  "needCorrect": true,
                  "removedConditionIdList": [],
                  "xcId": "xc0d61279aad33008260",
                  "ownSelectAll": false,
                  "dxInfo": [],
                  "extraCondition": ""
                  }`, s.words, pageSize, time.Now().Unix())).Post(url)
      // ... 解析 resp.Body() 为 map[string]any 并返回
  }
  ```

- **Agent 工具模式（可选路径）**：`backend/agent/tools/choice_stock_by_indicators_tool.go`
  - 提供一个名为 `ChoiceStockByIndicators` 的工具，用于在 AI Agent 中通过函数调用完成同样的选股操作。
  - 内部同样调用 `SearchStockApi.SearchStock`。
  - 在此路径下会将结果转换为 Markdown 表格，但核心数据来源与 `SearchStock` 接口一致。

### 1.2 核心结论

- **本系统并不在本地计算 K 线/技术指标**，而是将用户的自然语言选股条件透传给 **东方财富“智能选股”服务**，由对方服务完成：
  - 解析条件
  - 运行选股逻辑与指标筛选
  - 返回符合条件的股票及指标数据
- 本地侧主要负责：
  - 构造 HTTP 请求（带特定 Header 与 JSON Body）
  - 解析响应 JSON
  - 将 `columns` + `dataList` 映射为可读的表格（前端或 Markdown）。

---

## 二、请求接口与参数结构

### 2.1 目标接口

- **URL**：

  ```text
  https://np-tjxg-g.eastmoney.com/api/smart-tag/stock/v3/pw/search-code
  ```

- **方法**：`POST`

- **超时**：当前 Go 实现为 `30s`。

### 2.2 请求头（Headers）

参考 Go 实现：

- `Host: np-tjxg-g.eastmoney.com`
- `Origin: https://xuangu.eastmoney.com`
- `Referer: https://xuangu.eastmoney.com/`
- `User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:145.0) Gecko/20100101 Firefox/145.0`
- `Content-Type: application/json`

> 在 Python 复现时，应尽量保持与上述 Header 一致，以避免风控或接口拒绝。

### 2.3 请求体（JSON Body）

Go 中使用 `fmt.Sprintf` 拼接，结构如下：

```jsonc
{
  "keyWord": "<自然语言选股条件>",
  "pageSize": <整数, 单页返回多少只股票>,
  "pageNo": 1,
  "fingerprint": "02efa8944b1f90fbfe050e1e695a480d",
  "gids": [],
  "matchWord": "",
  "timestamp": "<当前 Unix 时间戳（秒）>",
  "shareToGuba": false,
  "requestId": "RMd3Y76AJI98axPvdhdbKvbBDVwLlUK61761559950168",
  "needCorrect": true,
  "removedConditionIdList": [],
  "xcId": "xc0d61279aad33008260",
  "ownSelectAll": false,
  "dxInfo": [],
  "extraCondition": ""
}
```

其中：

- **`keyWord`**：核心字段，对应本系统的 `words`，支持自然语言 + 股票名称 + 指标/财务条件混合，例如：
  - `上海贝岭,macd,rsi,kdj,boll,5日均线,14日均线,30日均线,60日均线,成交量,OBV,EMA`
  - `创新药,半导体;PE<30;净利润增长率>50%。`
  - `股价在20日线上，一月之内涨停次数>=1，量比大于1，换手率大于3%，流通市值大于50亿小于200亿。`
- **`pageSize`**：返回记录条数，前端接口固定使用 `5000`；Agent 工具中使用 `random.RandInt(5, 20)` 随机返回少量结果。
- 其他字段（`fingerprint`, `xcId`, `requestId` 等）在当前实现中是固定值，用于模拟来自网页端的请求特征。

### 2.4 响应结构（关键字段）

典型响应结构（简化）：

```jsonc
{
  "code": 100,
  "msg": "成功",
  "data": {
    "traceInfo": {
      "showText": "经解析后的选股条件描述..."
    },
    "result": {
      "columns": [
        {
          "key": "SECURITY_CODE",
          "title": "股票代码",
          "unit": "",
          "hiddenNeed": false,
          "children": null
        },
        {
          "key": "...",
          "title": "...",
          "unit": "%",
          "hiddenNeed": false,
          "children": [
            {
              "key": "INDICATOR_20241031",
              "dateMsg": "2024-10-31",
              "hiddenNeed": false,
              "unit": "%"
            }
          ]
        }
      ],
      "dataList": [
        {
          "SECURITY_CODE": "600171",
          "SECURITY_SHORT_NAME": "上海贝岭",
          "MARKET_SHORT_NAME": "sh",
          "...": "..."
        }
      ]
    }
  }
}
```

当前代码对响应的关键使用方式：

- 判断 `code == 100` 表示成功。
- 从 `data.result.columns` 构造表头；
- 从 `data.result.dataList` 获取每只股票对应的字段值；
- 前端过滤掉 `hiddenNeed == true` 的列及 `市场码`、`市场简称` 等不需要展示的列。

---

## 三、Go 端业务逻辑要点

### 3.1 SearchStock 接口（给前端用）

- **位置**：`app_common.go`
- **签名**：`func (a App) SearchStock(words string) map[string]any`
- **职责**：
  - 接受前端输入的自然语言选股条件 `words`；
  - 固定 `pageSize = 5000`；
  - 调用 `SearchStockApi.SearchStock` 访问东方财富接口；
  - 直接返回原始响应 `map[string]any` 给前端。

前端 `SelectStock.vue` 负责：

- 从 `res.data.traceInfo.showText` 中读取“选股条件解析结果”，展示在界面上；
- 从 `res.data.result.columns` 构造 `columns`：
  - 过滤 `hiddenNeed` 为 `true` 的列；
  - 过滤掉标题为 `市场码`、`市场简称` 的列；
  - 对 `children` 列进行展开，形成多层表头；
- 从 `res.data.result.dataList` 填充 `dataList`，用于表格渲染。

### 3.2 ChoiceStockByIndicators 工具（给 AI Agent 用）

- **位置**：`backend/agent/tools/choice_stock_by_indicators_tool.go`
- **接口描述**：

  ```go
  Name: "ChoiceStockByIndicators",
  Desc: "根据自然语言筛选股票，返回自然语言选股条件要求的股票所有相关数据...",
  Params: { "words": string, required }
  ```

- **调用链**：
  - AI Agent 通过工具调用传入 `words`；
  - 内部同样调用 `data.NewSearchStockApi(words).SearchStock(random.RandInt(5, 20))`；
  - 将返回 `columns + dataList` 转换为 Markdown 表格文本，作为工具的输出，供大模型继续生成答案。

> **注意**：无论是前端 `SearchStock` 还是 Agent 工具 `ChoiceStockByIndicators`，**核心选股逻辑完全在东方财富接口中**，本地仅作请求转发与结果展示。

### 3.3 基于 SearchStockApi 返回值的本地处理说明

- **当前版本中，本地不对 SearchStockApi 返回的股票集合做“二次选股”逻辑**：
  - 不会在 Go 端根据市值、涨跌幅、技术指标阈值等字段再过滤一次；
  - 不会改变东方财富接口返回的股票集合，只会在展示层做列过滤与排序；
  - 前端仅做：
    - 列的隐藏（`hiddenNeed == true`、"市场码"、"市场简称" 等）；
    - 表格层面的排序、颜色高亮（根据数值大小改变文字颜色）。
- **二次筛选如果需要，应在调用方自行完成**：
  - Go 客户端当前没有内置这一步；
  - 本文提供的 Python 示例中同样只完成“拉取 + 表格化”的步骤；
  - 如需要“在 SearchStockApi 基础上再叠加本地策略”，建议在 Python 的 `DataFrame` 上操作，例如：
    - `df = df[df['涨幅%'] > 5]` 进一步过滤涨幅；
    - `df = df[(df['流通市值(亿)'] > 50) & (df['流通市值(亿)'] < 200)]` 按市值范围筛选；
    - `df.sort_values('量比', ascending=False).head(50)` 取前 50 只量比最高的股票。

通过以上约束，可以明确：**SearchStockApi 返回值的“选股结果”完全由东方财富服务决定，本地不对结果做再加工的选股判断，只对展示方式和简单列过滤负责**。

---

## 四、使用 Python 复现指标选股功能

本节提供一份纯 Python 示例代码，让读者在不依赖 go-stock 的情况下，从本地直接调用东方财富智能选股接口，达到与“指标选股”页面相同的效果。

### 4.1 环境准备

- Python 版本：建议 3.8+
- 依赖库：
  - `requests`：HTTP 请求
  - `pandas`（可选）：表格展示与进一步处理

示例安装命令：

```bash
pip install requests pandas
```

### 4.2 Python 示例代码：基础请求与表格构建

```python
import time
import requests
import pandas as pd

URL = "https://np-tjxg-g.eastmoney.com/api/smart-tag/stock/v3/pw/search-code"

HEADERS = {
    "Host": "np-tjxg-g.eastmoney.com",
    "Origin": "https://xuangu.eastmoney.com",
    "Referer": "https://xuangu.eastmoney.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:145.0) Gecko/20100101 Firefox/145.0",
    "Content-Type": "application/json",
}


def build_payload(words: str, page_size: int = 5000) -> dict:
    """构造与 Go 端等价的请求体。"""
    return {
        "keyWord": words,
        "pageSize": page_size,
        "pageNo": 1,
        "fingerprint": "02efa8944b1f90fbfe050e1e695a480d",
        "gids": [],
        "matchWord": "",
        "timestamp": str(int(time.time())),
        "shareToGuba": False,
        "requestId": "RMd3Y76AJI98axPvdhdbKvbBDVwLlUK61761559950168",
        "needCorrect": True,
        "removedConditionIdList": [],
        "xcId": "xc0d61279aad33008260",
        "ownSelectAll": False,
        "dxInfo": [],
        "extraCondition": "",
    }


def search_stock(words: str, page_size: int = 5000) -> dict:
    """
    调用东方财富智能选股接口，返回原始 JSON 字典。
    与 Go 的 SearchStock 行为等价。
    """
    payload = build_payload(words, page_size)
    resp = requests.post(URL, headers=HEADERS, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data


def to_dataframe(resp: dict) -> tuple[pd.DataFrame, str]:
    """将响应结果转换为 pandas.DataFrame，并返回 traceInfo 文本。"""
    if resp.get("code") != 100:
        raise ValueError(f"接口返回错误 code={resp.get('code')}, msg={resp.get('msg')}")

    data = resp.get("data", {})
    trace_info = data.get("traceInfo", {}).get("showText", "")

    result = data.get("result", {})
    columns = result.get("columns", [])
    data_list = result.get("dataList", [])

    # 构造列 key -> 展示名（参考 Go/前端逻辑）
    headers = {}
    for col in columns:
        if col.get("hiddenNeed"):
            continue
        title = col.get("title", "")
        unit = col.get("unit") or ""
        if unit:
            title = f"{title}[{unit}]"

        # 无子列
        if not col.get("children"):
            headers[col["key"]] = title
        else:
            # 有子列时，对每个子列生成 "标题[dateMsg][unit]" 风格的列名
            for child in col["children"]:
                if child.get("hiddenNeed"):
                    continue
                child_title = child.get("dateMsg") or title
                child_key = child.get("key")
                headers[child_key] = child_title

    # 组装 DataFrame
    rows = []
    for item in data_list:
        row = {}
        for key, col_name in headers.items():
            row[col_name] = item.get(key)
        rows.append(row)

    df = pd.DataFrame(rows)
    return df, trace_info


if __name__ == "__main__":
    # 示例：使用自然语言进行选股
    words = "股价在20日线上，一月之内涨停次数>=1，量比大于1，换手率大于3%，流通市值大于50亿小于200亿"

    resp = search_stock(words, page_size=500)
    df, trace = to_dataframe(resp)

    print("解析后的选股条件:")
    print(trace)
    print()

    print("前 10 条结果：")
    print(df.head(10).to_string(index=False))
```

此代码实现了：

- 与 Go 端完全等价的 HTTP 请求逻辑（URL、Headers、Body 主体字段）；
- 对响应中的 `columns + dataList` 进行解析并生成 `pandas.DataFrame`；
- 输出东方财富解析后的“选股条件文本”。

### 4.3 与 Go 端行为的一致性注意点

- **pageSize**：
  - 前端界面使用 `5000`，Agent 工具使用 `[5, 20]` 的随机值；
  - Python 代码中可以根据需要设定为较小值以降低请求数据量。
- **字段过滤**：
  - 前端会隐藏 `hiddenNeed == true` 的列，并去掉 `市场码`、`市场简称` 等；
  - Python 示例中仅按 `hiddenNeed` 过滤，读者可根据需要在 `headers` 构造逻辑中手动排除某些列名。
- **类型转换与排序**：
  - 前端在表格中会根据列内容是否为数字来决定排序逻辑；
  - Python 中可使用 `pd.to_numeric` 将特定列转为数值类型并排序、筛选、可视化等。

---

## 五、扩展使用示例

以下是一些从文档和代码中提取的自然语言选股示例，可直接用于 Python 的 `words` 参数：

- **示例 1：指定个股 + 技术指标**

  ```text
  上海贝岭,macd,rsi,kdj,boll,5日均线,14日均线,30日均线,60日均线,成交量,OBV,EMA
  ```

- **示例 2：行业 + 估值 + 成长性**

  ```text
  创新药,半导体;PE<30;净利润增长率>50%。
  ```

- **示例 3：指数 / 板块**

  ```text
  上证指数,科创50。
  ```

- **示例 4：量价行为 + 财务约束**

  ```text
  换手率大于3%小于25%.量比1以上. 10日内有过涨停.股价处于峰值的二分之一以下.流通股本<100亿.当日和连续四日净流入;股价在20日均线以上.分时图股价在均线之上.热门板块下涨幅领先的A股. 当日量能20000手以上.沪深个股.近一年市盈率波动小于150%.MACD金叉;不要ST股及不要退市股，非北交所，每股收益>0。
  ```

- **示例 5：多周期、多均线条件**

  ```text
  今日涨幅大于等于2%小于等于9%;量比大于等于1.1小于等于5;换手率大于等于5%小于等于20%;市值大于等于30小于等于300亿;5日、10日、30日、60日均线、5周、10周、30周、60周均线多头排列
  ```

这些“自然语言条件”无需本地解析，直接写入 `keyWord` 即可由东方财富服务完成解析与选股。

---

## 六、风险提示与注意事项

- **接口稳定性与限制**：
  - 东方财富接口属于网页内部接口，可能存在访问频率限制、参数变更或封禁风险；
  - 建议在个人研究/学习场景下合理控制调用频率，不用于高频批量爬取。

- **字段含义**：
  - 返回字段较多（技术指标、财务指标、量价数据等），具体含义可结合东方财富网站“智能选股”页面与实际业务经验理解。

- **投资风险**：
  - 无论是 go-stock 客户端还是本 Python 复现代码，仅提供数据和筛选辅助，不构成任何投资建议。
  - 投资需谨慎，风险自担。

---

通过本文档，你可以：

- 清晰理解 go-stock 中“指标选股”功能的完整调用链与核心逻辑；
- 使用 Python 在本地直接调用相同的东方财富智能选股接口；
- 在此基础上进行二次开发，例如：将结果写入数据库、做回测、加入自己的因子模型等。
