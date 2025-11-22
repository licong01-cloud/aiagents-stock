"""indicator_stock_search

轻量封装东方财富智能选股接口的 Python 库，
用于根据自然语言选股条件获取股票及相关指标数据。

核心入口：
- SearchStockClient: 低层 HTTP 客户端
- search_to_dataframe: 一步获取 pandas.DataFrame
"""

from .client import SearchStockClient, search_to_dataframe
