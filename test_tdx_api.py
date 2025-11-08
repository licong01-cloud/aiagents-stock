import os
import json
from datetime import datetime
from typing import Dict, Any, Iterable

import requests

BASE_URL = os.environ.get("TDX_API_BASE", "http://localhost:8080")


def call_api(path: str, params: Dict[str, Any] | None = None, method: str = "GET", json_body: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """GET 请求指定接口并打印状态"""
    url = f"{BASE_URL.rstrip('/')}{path}"
    try:
        if method.upper() == "POST":
            resp = requests.post(url, params=params, json=json_body, timeout=10)
        else:
            resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        code = data.get("code") if isinstance(data, dict) else None
        message = data.get("message") if isinstance(data, dict) else None
        if code == 0:
            print(f"✅ {path} -> code=0 message={message}")
        else:
            print(f"⚠️ {path} -> code={code} message={message}")
        return data
    except requests.exceptions.HTTPError as exc:
        response = exc.response
        raw_message = None
        if response is not None:
            try:
                error_data = response.json()
                if isinstance(error_data, dict):
                    raw_message = error_data.get("message") or error_data.get("msg")
            except Exception:
                raw_message = response.text[:200]
        if raw_message:
            print(f"❌ {path} 请求失败: {raw_message}")
        else:
            print(f"❌ {path} 请求失败: {exc}")
    except requests.exceptions.RequestException as exc:
        print(f"❌ {path} 请求失败: {exc}")
    except json.JSONDecodeError:
        print(f"❌ {path} 返回非JSON数据: {resp.text[:200]}")
    return {}


def to_yuan(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return value / 1000
    return None


def to_shares(value: Any) -> int | None:
    if isinstance(value, (int, float)):
        return int(value * 100)
    return None


def show_quote_details(resp: Dict[str, Any], label: str = "000001") -> None:
    data = resp.get("data") if isinstance(resp, dict) else None
    if not data:
        print(f"⚠️ {label} 行情数据为空")
        return
    first = data[0] if isinstance(data, Iterable) else None
    if not isinstance(first, dict):
        print(f"⚠️ {label} 行情格式异常: {first}")
        return
    kline = first.get("K") or {}
    last_price = to_yuan(kline.get("Close"))
    high_price = to_yuan(kline.get("High"))
    low_price = to_yuan(kline.get("Low"))
    volume = to_shares(kline.get("Volume"))
    amount = to_yuan(kline.get("Amount"))
    print(f"行情({label}) 最新价={last_price or '未知'} 元, 最高={high_price or '未知'} 元, 最低={low_price or '未知'} 元, 成交量={volume or '未知'} 股, 成交额={amount or '未知'} 元")


def show_kline_summary(resp: Dict[str, Any], label: str) -> None:
    data = resp.get("data") if isinstance(resp, dict) else None
    series = None
    if isinstance(data, dict):
        series = data.get("List") or data.get("list")
    if not isinstance(series, Iterable):
        print(f"⚠️ {label} 无有效K线数据")
        return
    series = list(series)
    if not series:
        print(f"⚠️ {label} K线列表为空")
        return
    head = series[0]
    tail = series[-1]
    def extract(entry: Dict[str, Any]) -> str:
        if not isinstance(entry, dict):
            return str(entry)
        date = entry.get("Date") or entry.get("date")
        close = to_yuan(entry.get("Close") or entry.get("close"))
        volume = to_shares(entry.get("Volume") or entry.get("volume"))
        return f"{date}: 收盘 {close or '未知'} 元, 成交量 {volume or '未知'} 股"

    print(f"{label} 共 {len(series)} 条, 首条 {extract(head)}, 末条 {extract(tail)}")


def show_intraday_summary(resp: Dict[str, Any], label: str) -> None:
    data = resp.get("data") if isinstance(resp, dict) else None
    if not data:
        print(f"⚠️ {label} 数据为空")
        return
    items = data.get("List") or data.get("list") or data
    if isinstance(items, dict):
        items = items.get("List") or items.get("list")
    if not isinstance(items, Iterable):
        print(f"⚠️ {label} 返回格式未知: {items}")
        return
    items = list(items)
    print(f"{label} 数据条数: {len(items)}")
    if items:
        first = items[0]
        if isinstance(first, dict):
            price = to_yuan(first.get("Price") or first.get("price"))
            volume = to_shares(first.get("Volume") or first.get("volume"))
            print(f"{label} 首条 -> 时间: {first.get('Time') or first.get('time')}, 价格: {price or '未知'} 元, 成交量: {volume or '未知'} 股")


def show_search_results(resp: Dict[str, Any]) -> None:
    data = resp.get("data") if isinstance(resp, dict) else None
    if not data:
        print("⚠️ 搜索结果为空")
        return
    first = data[0] if isinstance(data, Iterable) else None
    if isinstance(first, dict):
        print(f"搜索首条: 代码 {first.get('Code') or first.get('code')} 名称 {first.get('Name') or first.get('name')}")
    else:
        print(f"搜索结果示例: {first}")


def show_stock_info(resp: Dict[str, Any]) -> None:
    data = resp.get("data") if isinstance(resp, dict) else None
    if not isinstance(data, dict):
        print("⚠️ 股票基础信息为空")
        return
    print(f"股票信息: 代码 {data.get('code')} 名称 {data.get('name')} 行业 {data.get('industry')}")


def show_code_list(resp: Dict[str, Any]) -> None:
    data = resp.get("data") if isinstance(resp, dict) else None
    if isinstance(data, Iterable):
        sample = list(data)[:5]
        print(f"股票列表样例({len(sample)}条): {sample}")
    else:
        print("⚠️ 股票列表接口数据为空或格式未知")


def show_batch_quote(resp: Dict[str, Any]) -> None:
    data = resp.get("data") if isinstance(resp, dict) else None
    if not isinstance(data, Iterable):
        print("⚠️ 批量行情数据为空")
        return
    data = list(data)
    print(f"批量行情数量: {len(data)}")
    if data:
        first = data[0]
        if isinstance(first, dict):
            kline = first.get("K") or {}
            last_price = to_yuan(kline.get("Close"))
            print(f"批量首条 -> 代码: {first.get('Code') or first.get('code')}, 最新价: {last_price or '未知'} 元")


def main() -> None:
    print(f"测试 TDX API，基础地址: {BASE_URL}")

    # 单只股票行情
    quote_resp = call_api("/api/quote", {"code": "000001"})
    show_quote_details(quote_resp)

    # 额外测试另一只股票行情
    show_quote_details(call_api("/api/quote", {"code": "600519"}), label="600519")

    kline_resp = call_api("/api/kline", {"code": "000001", "type": "day"})
    show_kline_summary(kline_resp, label="实时K线")

    today = datetime.now().strftime("%Y%m%d")
    show_intraday_summary(call_api("/api/minute", {"code": "000001", "date": today}), "分时数据")
    show_intraday_summary(call_api("/api/trade", {"code": "000001", "date": today}), "逐笔成交")

    show_search_results(call_api("/api/search", {"keyword": "平安"}))
    show_stock_info(call_api("/api/stock-info", {"code": "000001"}))
    try:
        show_code_list(call_api("/api/codes", {"exchange": "sh"}))
    except Exception as exc:
        print(f"⚠️ /api/codes 处理失败: {exc}")
    try:
        show_batch_quote(call_api("/api/batch-quote", method="POST", json_body={"codes": ["000001", "600519", "601318"]}))
    except Exception as exc:
        print(f"⚠️ /api/batch-quote 处理失败: {exc}")
    show_kline_summary(call_api("/api/kline-history", {"code": "000001", "type": "day", "limit": 30}), label="历史K线")
    show_kline_summary(call_api("/api/index", {"code": "sh000001", "type": "day"}), label="指数K线")


if __name__ == "__main__":
    main()
