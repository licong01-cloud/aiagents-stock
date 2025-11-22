import os
import requests

# 从 .env 读取 TDX_API_BASE，默认 http://localhost:8080
BASE_URL = os.getenv("TDX_API_BASE", "http://localhost:8080").rstrip("/")

# 随机挑选的一些股票和 ETF 代码（你可以根据需要自行增减）
TEST_CODES = [
    "600103",
    "600460",
    "300073",
    "688981",
    "512930",
    "588000",
    "000001",
    "600519",
]


def call_search(keyword: str):
    """调用 /api/search 接口并返回 JSON。"""
    url = f"{BASE_URL}/api/search"
    resp = requests.get(url, params={"keyword": keyword}, timeout=5)
    resp.raise_for_status()
    return resp.json()


def main():
    print(f"Using TDX_API_BASE = {BASE_URL}")
    for code in TEST_CODES:
        print("=" * 60)
        print(f"测试 /api/search?keyword={code}")
        try:
            payload = call_search(code)
        except Exception as e:
            print(f"  请求失败: {e}")
            continue

        print(f"  原始返回: code={payload.get('code')}, message={payload.get('message')}")
        data = payload.get("data") or []
        if not isinstance(data, list) or not data:
            print("  ⚠️ data 为空或不是列表")
            continue

        # 精确匹配 code 的结果，并打印 name
        hits = []
        for item in data:
            try:
                c = str(item.get("code") or "").strip()
                nm = str(item.get("name") or "").strip()
                exch = str(item.get("exchange") or "")
            except Exception:
                continue
            if c == code:
                hits.append((c, nm, exch))

        if not hits:
            print("  ⚠️ 未找到 code 精确匹配项，只打印前几个原始项：")
            for item in data[:5]:
                print(
                    f"    - code={item.get('code')}, name={item.get('name')}, "
                    f"exchange={item.get('exchange')}"
                )
        else:
            print("  ✅ 精确匹配结果：")
            for c, nm, exch in hits:
                is_code_like = nm.isdigit() and len(nm) == 6
                flag = " ⚠️(像代码)" if is_code_like else ""
                print(f"    - code={c}, name={nm}, exchange={exch}{flag}")


if __name__ == "__main__":
    main()
