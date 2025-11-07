# coding: utf-8
"""Fetch announcements and attachment download URLs from cninfo WebAPI."""
import os
import sys
import requests
from datetime import datetime

BASE_URL = "https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1127"


def require_api_key() -> str:
    api_key = os.environ.get("CNINFO_API_KEY")
    if not api_key:
        print("CNINFO_API_KEY 未设置，无法调用接口")
        sys.exit(1)
    return api_key


def fetch_announcements(api_key: str, scode: str, start_date: str, end_date: str,
                        column: str = "szse", announcement_type: str = "EQA",
                        page_size: int = 100):
    params = {
        "scode": scode,
        "sdate": start_date,
        "edate": end_date,
        "column": column,
        "type": announcement_type,
        "sortName": "declDate",
        "sortType": "desc",
        "pageSize": page_size,
        "pageNum": 1,
        "api_key": api_key,
    }

    records = []
    while True:
        response = requests.get(BASE_URL, params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0:
            raise RuntimeError(f"接口返回错误: {payload.get('msg')}")
        page_records = payload.get("records") or []
        if not page_records:
            break
        records.extend(page_records)
        if len(page_records) < page_size:
            break
        params["pageNum"] += 1
    return records


def main():
    api_key = require_api_key()
    scode = sys.argv[1] if len(sys.argv) > 1 else "300073"
    start_date = sys.argv[2] if len(sys.argv) > 2 else datetime.now().replace(day=1).strftime("%Y-%m-%d")
    end_date = sys.argv[3] if len(sys.argv) > 3 else datetime.now().strftime("%Y-%m-%d")

    print(f"查询股票 {scode} 公告，区间 {start_date} ~ {end_date}")
    records = fetch_announcements(api_key, scode, start_date, end_date)
    print(f"共获取 {len(records)} 条公告")

    for idx, record in enumerate(records, 1):
        title = record.get("TITLE", "N/A")
        decl_date = record.get("DECL_DATE", "N/A")
        url = record.get("URL")
        attachments = record.get("FJXX") or []
        print(f"{idx}. [{decl_date}] {title}")
        print(f"   详情URL: {url}")
        if attachments:
            for attachment in attachments:
                file_name = attachment.get("FILE_NAME")
                download_url = attachment.get("DOWNLOAD_URL")
                print(f"   附件: {file_name} -> {download_url}")
        else:
            print("   无附件")


if __name__ == "__main__":
    main()
