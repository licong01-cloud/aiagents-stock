# indicator_stock_search

基于 go-stock 项目中 `SearchStockApi` 封装的 Python 选股客户端库，
方便在其它程序中直接使用东方财富智能选股接口。

## 安装依赖

```bash
pip install requests pandas
```

> 如果只需要原始 JSON 结果，可以只安装 `requests`，不安装 `pandas`，
> 此时调用 `SearchStockClient.search_raw` 即可。

## 快速上手

```python
from indicator_stock_search import search_to_dataframe

words = "股价在20日线上，一月之内涨停次数>=1，量比大于1，换手率大于3%，流通市值大于50亿小于200亿"

df, trace = search_to_dataframe(words, page_size=500)

print("解析后的选股条件:")
print(trace)
print("前 10 条结果:")
print(df.head(10).to_string(index=False))
```

## 使用客户端类以获得更多控制

```python
from indicator_stock_search import SearchStockClient

client = SearchStockClient()

# 1. 获取原始 JSON
resp = client.search_raw("创新药,半导体;PE<30;净利润增长率>50%。", page_size=1000)

# 2. 转为 DataFrame（需安装 pandas）
df, trace = client.to_dataframe(resp)

# 在此基础上可以做本地二次筛选，例如：
# 过滤涨幅大于 5% 的股票
# df = df[df["涨幅%"] > 5]
```

## 设计原则

- 与 go-stock 中 `SearchStockApi` 请求逻辑保持等价：
  - 使用相同的 URL、Headers、Body 结构；
  - 根据当前时间生成 `timestamp`；
- 不在本地做“二次选股”逻辑：
  - 东方财富接口返回的股票集合视为最终选股结果；
  - 本库仅负责：
    - 构造请求；
    - 解析响应；
    - 以 DataFrame 形式输出，方便调用方做进一步策略处理。
