from qstock_news_data import QStockNewsDataFetcher


def main():
    fetcher = QStockNewsDataFetcher()
    result = fetcher.get_stock_news("688981")
    print("=== 原始结果键 ===")
    print(result.keys())
    print("data_success:", result.get("data_success"))
    if "error" in result:
        print("error:", result["error"])

    news_data = result.get("news_data")
    if not news_data:
        print("news_data 为空或未获取到任何新闻")
        return

    print("\n=== 汇总信息 ===")
    print("symbol:", result.get("symbol"))
    print("count:", news_data.get("count"))
    print("query_time:", news_data.get("query_time"))
    print("date_range:", news_data.get("date_range"))

    items = news_data.get("items", [])
    print("\n=== 前几条新闻预览 ===")
    for idx, item in enumerate(items[:5], 1):
        print(f"\n--- 新闻 {idx} ---")
        # 尝试取一些常见字段
        title = item.get("标题") or item.get("title") or "<无标题>"
        time = item.get("发布时间") or item.get("time") or item.get("日期") or "<无时间>"
        src = item.get("source") or item.get("来源") or "<未知来源>"
        print("来源:", src)
        print("时间:", time)
        print("标题:", title)
        # 内容字段可能不统一，打印前 100 字
        content = item.get("内容") or item.get("content") or ""
        if content:
            print("内容:", str(content)[:100].replace("\n", " ") + ("..." if len(str(content)) > 100 else ""))


if __name__ == "__main__":
    main()
