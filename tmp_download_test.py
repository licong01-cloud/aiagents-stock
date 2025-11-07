import requests
import re

detail_url = (
    "https://www.cninfo.com.cn/new/disclosure/detail"
    "?stockCode=688981"
    "&announcementId=1224788979"
    "&orgId=gshk0000981"
    "&announcementTime=2025-11-06"
)

session = requests.Session()
headers = {"User-Agent": "Mozilla/5.0"}

resp = session.get(detail_url, headers=headers, timeout=20)
print("detail status:", resp.status_code)
html = resp.text

download_url = None
match = re.search(r"downloadPdf\('([^']+)'\)", html)
if match:
    download_url = match.group(1)
print("download url:", download_url)

if not download_url:
    match = re.search(r"https?://static\.cninfo\.com\.cn/[^\"'<>]+\.PDF", html, re.I)
    if match:
        download_url = match.group(0)
    print("fallback url:", download_url)

if download_url:
    headers["Referer"] = detail_url
    resp = session.get(download_url, headers=headers, timeout=20)
    print("download status:", resp.status_code)
    print("content-type:", resp.headers.get("Content-Type"))
    print("content length:", len(resp.content))
    with open("test.pdf", "wb") as f:
        f.write(resp.content)
else:
    print("未找到下载链接")
