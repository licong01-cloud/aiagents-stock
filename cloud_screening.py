from __future__ import annotations

import time
from typing import Any, Dict, List

import requests


class EastmoneyCloudSelector:
    """简易封装东方财富智能选股/热门策略接口（实验性）。"""

    SEARCH_URL = "https://np-tjxg-g.eastmoney.com/api/smart-tag/stock/v3/pw/search-code"
    HOT_STRATEGY_URL = "https://np-ipick.eastmoney.com/recommend/stock/heat/ranking"

    COMMON_HEADERS = {
        "Origin": "https://xuangu.eastmoney.com",
        "Referer": "https://xuangu.eastmoney.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:145.0) Gecko/20100101 Firefox/145.0",
        "Content-Type": "application/json",
    }

    def search(self, keyword: str, page_size: int = 50) -> Dict[str, Any]:
        """调用东财智能选股搜索接口，返回原始 JSON。"""

        payload = {
            "keyWord": keyword,
            "pageSize": int(page_size),
            "pageNo": 1,
            "fingerprint": "02efa8944b1f90fbfe050e1e695a480d",
            "gids": [],
            "matchWord": "",
            "timestamp": str(int(time.time())),
            "shareToGuba": False,
            "requestId": f"gs_cloud_{int(time.time() * 1000)}",
            "needCorrect": True,
            "removedConditionIdList": [],
            "xcId": "xc0d61279aad33008260",
            "ownSelectAll": False,
            "dxInfo": [],
            "extraCondition": "",
        }

        headers = dict(self.COMMON_HEADERS)
        headers["Host"] = "np-tjxg-g.eastmoney.com"

        resp = requests.post(self.SEARCH_URL, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_hot_strategies(self, limit: int = 20) -> Dict[str, Any]:
        """获取东财云选股热门策略列表。"""

        ts = int(time.time())
        params = {
            "count": int(limit),
            "trace": ts,
            "client": "web",
            "biz": "web_smart_tag",
        }
        headers = dict(self.COMMON_HEADERS)
        headers["Host"] = "np-ipick.eastmoney.com"

        resp = requests.get(self.HOT_STRATEGY_URL, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()


_selector_singleton: EastmoneyCloudSelector | None = None


def get_cloud_selector() -> EastmoneyCloudSelector:
    global _selector_singleton
    if _selector_singleton is None:
        _selector_singleton = EastmoneyCloudSelector()
    return _selector_singleton
