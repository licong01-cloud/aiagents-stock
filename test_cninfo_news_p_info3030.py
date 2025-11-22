# coding: utf-8
"""Simple tester for cninfo news API p_info3030.

Usage (from project root):

    set CNINFO_API_KEY=你的token
    python test_cninfo_news_p_info3030.py 600584 2025-10-01 2025-10-31

It will:
- call http://webapi.cninfo.com.cn/api/info/p_info3030
- print basic fields of returned news
- try to access F006V / F008V links and report HTTP status & size
"""

import os
import sys
import json
from typing import Any, Dict, List, Optional

import requests


BASE_URL = "http://webapi.cninfo.com.cn/api/info/p_info3030"


def get_api_key() -> Optional[str]:
    """Get CNINFO_API_KEY from env or prompt user.

    优先从环境变量 CNINFO_API_KEY 读取；
    如果环境变量不存在，则在命令行提示用户输入 token。
    用户直接回车则仍然以无 token 方式调用，便于做对比测试。
    """
    api_key = os.environ.get("CNINFO_API_KEY")
    if api_key:
        return api_key

    print("[INFO] 未检测到环境变量 CNINFO_API_KEY。")
    entered = input("请输入巨潮 CNINFO_API_KEY（留空则不使用 token）: ").strip()
    if not entered:
        print("[WARN] 本次将不携带 api_key 参数调用 p_info3030，用于测试是否无需 token 也可访问。")
        return None
    return entered


def fetch_news(
    api_key: str,
    scode: Optional[str] = None,
    sdate: Optional[str] = None,
    edate: Optional[str] = None,
    stype: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Call p_info3030 and return records list.

    根据你提供的文档，支持参数：scode, sdate, edate, stype, @limit, @orderby 等。
    这里默认按 DECLAREDATE 降序排序，只取前 limit 条。
    """

    params: Dict[str, Any] = {
        "format": "json",
        "@limit": limit,
        "@orderby": "DECLAREDATE:desc",
    }

    # 仅在提供 api_key 时才携带该参数，便于对比“有 / 无 token”的行为
    if api_key:
        params["api_key"] = api_key

    if scode:
        params["scode"] = scode
    if sdate:
        params["sdate"] = sdate
    if edate:
        params["edate"] = edate
    if stype:
        params["stype"] = stype

    resp = requests.get(BASE_URL, params=params, timeout=20)
    print("[HTTP]", resp.status_code, resp.url)
    resp.raise_for_status()

    # p_info3030 返回格式可能是 {records:[...]} 或直接列表，这里做一下兼容
    try:
        data = resp.json()
    except Exception:
        print("响应不是 JSON，原始内容前 500 字符:\n", resp.text[:500])
        raise

    if isinstance(data, dict):
        records = data.get("records") or data.get("data") or []
    elif isinstance(data, list):
        records = data
    else:
        print("未知响应结构:", type(data))
        print(json.dumps(data, ensure_ascii=False)[:500])
        records = []

    return records


def test_links(records: List[Dict[str, Any]], max_test: int = 5) -> None:
    """Try to access F006V / F008V links of first N records."""
    count = 0
    for rec in records:
        if count >= max_test:
            break
        url1 = (rec.get("F006V") or "").strip()
        url2 = (rec.get("F008V") or "").strip()
        for label, url in (("F006V", url1), ("F008V", url2)):
            if not url:
                continue
            count += 1
            print(f"\n[TEST] {label} link for TEXTID={rec.get('TEXTID')} -> {url}")
            try:
                r = requests.get(url, timeout=20)
                size = len(r.content or b"")
                print(f"  status={r.status_code}, size={size} bytes, content-type={r.headers.get('Content-Type')}")
            except Exception as e:
                print("  请求失败:", repr(e))
            if count >= max_test:
                break


def main() -> None:
    api_key = get_api_key()

    # 命令行参数：scode sdate edate stype
    scode = sys.argv[1] if len(sys.argv) > 1 else None
    sdate = sys.argv[2] if len(sys.argv) > 2 else None
    edate = sys.argv[3] if len(sys.argv) > 3 else None
    stype = sys.argv[4] if len(sys.argv) > 4 else None

    print("调用 p_info3030 参数:")
    print("  scode =", scode)
    print("  sdate =", sdate)
    print("  edate =", edate)
    print("  stype =", stype)
    print("  使用 api_key =", "<SET>" if api_key else "<NOT SET>")

    records = fetch_news(api_key, scode=scode, sdate=sdate, edate=edate, stype=stype, limit=20)
    print(f"\n共返回 {len(records)} 条记录，前几条示例：")
    for i, rec in enumerate(records[:10]):
        print("-" * 60)
        print(f"[{i+1}] DECLAREDATE = {rec.get('DECLAREDATE')}")
        print(f"     TEXTID      = {rec.get('TEXTID')}")
        print(f"     SECCODE     = {rec.get('SECCODE')}")
        print(f"     F003V(分类) = {rec.get('F003V')}")
        print(f"     F004V(标题) = {rec.get('F004V')}")
        print(f"     F006V(link) = {rec.get('F006V')}")
        print(f"     F008V(link) = {rec.get('F008V')}")

    if records:
        print("\n开始测试部分链接是否可访问...")
        test_links(records, max_test=6)
    else:
        print("没有返回记录，无法测试链接。")


if __name__ == "__main__":
    main()
