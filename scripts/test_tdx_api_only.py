"""简单测试本地 TDX API 是否可用。

仅发起 HTTP 请求到 TDX_API_BASE，不访问数据库。
"""
from __future__ import annotations

import os
from typing import Any, Dict

import requests
from dotenv import load_dotenv


def test_tdx_api() -> None:
    load_dotenv()
    base = os.getenv("TDX_API_BASE", "http://localhost:8080").rstrip("/")
    print(f"TDX_API_BASE = {base}")

    def _test(path: str, params: Dict[str, Any] | None = None) -> None:
        url = base + path
        print("\n=== GET", url, "params=", params, "===")
        try:
            resp = requests.get(url, params=params, timeout=5)
            print("status_code:", resp.status_code)
            text = resp.text
            print("body_head:", text[:400].replace("\n", " "))
        except Exception as exc:  # noqa: BLE001
            print("ERROR:", exc)

    # 测试股票列表
    _test("/api/codes", {"exchange": "sh"})
    # 测试日线全量接口
    _test("/api/kline-all/tdx", {"code": "600000"})
    # 可选：再测一次分钟线接口
    _test("/api/minute", {"code": "600000", "type": "minute1", "date": "20251101"})


if __name__ == "__main__":
    test_tdx_api()
