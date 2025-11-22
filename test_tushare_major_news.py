import pathlib
import re

import tushare as ts


def load_token_from_env_file() -> str | None:
    env_path = pathlib.Path(".env")
    if not env_path.exists():
        print(".env file not found in project root")
        return None
    text = env_path.read_text(encoding="utf-8")
    m = re.search(r"^TUSHARE_TOKEN=(.+)$", text, re.M)
    if not m:
        print("TUSHARE_TOKEN not found in .env")
        return None
    token = m.group(1).strip().strip('"').strip("'")
    return token or None


def main():
    token = load_token_from_env_file()
    print("TOKEN_FROM_ENV_FILE:", bool(token))
    if not token:
        raise SystemExit("No valid TUSHARE_TOKEN found in .env")

    ts.set_token(token)
    pro = ts.pro_api()

    try:
        # 按照官方文档示例：仅通过日期区间获取重要新闻
        df = pro.major_news(
            start_date="20240101",
            end_date="20241231",
            limit=5,
        )
        print("ROWS:", len(df))
        if not df.empty:
            print(df.head().to_string())
        else:
            print("major_news 返回空 DataFrame")
    except Exception as e:
        print("调用 major_news 出错:", repr(e))


if __name__ == "__main__":
    main()
