import os
import json
from typing import Dict, Any

import requests


BASE_URL = os.environ.get("TDX_API_BASE", "http://localhost:8080")


def call_api(path: str, *, params: Dict[str, Any] | None = None, method: str = "GET", json_body: Dict[str, Any] | None = None) -> Dict[str, Any] | None:
    url = f"{BASE_URL.rstrip('/')}{path}"
    try:
        if method.upper() == "POST":
            resp = requests.post(url, params=params, json=json_body, timeout=10)
        else:
            resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        print(f"✅ {path} -> code={data.get('code')} message={data.get('message')}")
        return data
    except requests.exceptions.HTTPError as exc:
        response = exc.response
        status = response.status_code if response is not None else "unknown"
        raw_text = None
        if response is not None:
            try:
                payload = response.json()
                print(f"❌ {path} HTTPError status={status} payload={payload}")
            except Exception:
                raw_text = response.text
                print(f"❌ {path} HTTPError status={status} raw={raw_text}")
        else:
            print(f"❌ {path} HTTPError: {exc}")
    except requests.exceptions.RequestException as exc:
        print(f"❌ {path} 请求异常: {exc}")
    return None


def test_optional_endpoints() -> None:
    print(f"测试可选接口 | Base URL: {BASE_URL}")

    call_api("/api/codes", params={"exchange": "sh"})

    call_api(
        "/api/batch-quote",
        method="POST",
        json_body={"codes": ["000001", "600519", "601318"]},
    )

    call_api("/api/kline-history", params={"code": "000001", "type": "day", "limit": 30})

    call_api("/api/index", params={"code": "sh000001", "type": "day"})


if __name__ == "__main__":
    test_optional_endpoints()
