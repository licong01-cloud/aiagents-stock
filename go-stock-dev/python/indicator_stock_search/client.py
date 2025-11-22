import time
from typing import Dict, Tuple, Any, Optional

import requests

try:
    import pandas as pd  # type: ignore
except ImportError:  # 允许在无 pandas 的环境下仅做原始 JSON 调用
    pd = None


DEFAULT_URL = "https://np-tjxg-g.eastmoney.com/api/smart-tag/stock/v3/pw/search-code"

DEFAULT_HEADERS: Dict[str, str] = {
    "Host": "np-tjxg-g.eastmoney.com",
    "Origin": "https://xuangu.eastmoney.com",
    "Referer": "https://xuangu.eastmoney.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:145.0) Gecko/20100101 Firefox/145.0",
    "Content-Type": "application/json",
}


class SearchStockClient:
    """封装东方财富智能选股接口的客户端。

    使用方式：

    ```python
    client = SearchStockClient()
    resp = client.search_raw("股价在20日线上，一月之内涨停次数>=1...", page_size=500)
    df, trace = client.to_dataframe(resp)
    ```
    """

    def __init__(
        self,
        url: str = DEFAULT_URL,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
    ) -> None:
        self.url = url
        self.headers = headers.copy() if headers is not None else DEFAULT_HEADERS.copy()
        self.timeout = timeout

    @staticmethod
    def build_payload(words: str, page_size: int = 5000) -> Dict[str, Any]:
        """构造与 go-stock 中 SearchStockApi 等价的请求体。"""
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

    def search_raw(self, words: str, page_size: int = 5000) -> Dict[str, Any]:
        """调用智能选股接口，返回原始 JSON 字典。

        与 go-stock 中 SearchStock 的行为等价，只是以 Python 实现。
        """
        payload = self.build_payload(words, page_size)
        resp = requests.post(self.url, headers=self.headers, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def to_dataframe(resp: Dict[str, Any]):
        """将响应结果转换为 pandas.DataFrame，并返回 traceInfo 文本。

        如果当前环境未安装 pandas，将抛出 RuntimeError，调用方可以选择
        仅使用 `search_raw` 返回的原始 JSON 自行处理。
        """
        if pd is None:
            raise RuntimeError("pandas is required to convert response to DataFrame. Please `pip install pandas`. ")

        if resp.get("code") != 100:
            raise ValueError(f"接口返回错误 code={resp.get('code')}, msg={resp.get('msg')}")

        data = resp.get("data", {})
        trace_info = data.get("traceInfo", {}).get("showText", "")

        result = data.get("result", {})
        columns = result.get("columns", [])
        data_list = result.get("dataList", [])

        # 构造列 key -> 展示名（根据 go-stock 前端逻辑）
        headers: Dict[str, str] = {}
        for col in columns:
            if col.get("hiddenNeed"):
                continue
            title = col.get("title", "")
            unit = col.get("unit") or ""
            if unit:
                title = f"{title}[{unit}]"

            children = col.get("children")
            if not children:
                headers[col["key"]] = title
            else:
                # 有子列时，对每个子列生成展示名
                for child in children:
                    if child.get("hiddenNeed"):
                        continue
                    child_title = child.get("dateMsg") or title
                    child_key = child.get("key")
                    headers[child_key] = child_title

        rows = []
        for item in data_list:
            row = {}
            for key, col_name in headers.items():
                row[col_name] = item.get(key)
            rows.append(row)

        df = pd.DataFrame(rows)
        return df, trace_info


def search_to_dataframe(words: str, page_size: int = 5000, timeout: int = 30):
    """便捷函数：一步完成搜索并返回 (DataFrame, traceInfo)。"""
    client = SearchStockClient(timeout=timeout)
    resp = client.search_raw(words, page_size=page_size)
    return client.to_dataframe(resp)
