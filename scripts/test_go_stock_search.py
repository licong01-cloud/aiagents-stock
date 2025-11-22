import os
import sys

# 将 go-stock-dev/python 加入 sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY_CLIENT_DIR = os.path.join(BASE_DIR, "go-stock-dev", "python")
if PY_CLIENT_DIR not in sys.path:
    sys.path.append(PY_CLIENT_DIR)

try:
    from indicator_stock_search.client import search_to_dataframe
except ImportError as e:
    print("IMPORT_ERROR", e)
    print("sys.path=", sys.path)
    sys.exit(1)


def main() -> None:
    words = "银行"
    try:
        df, trace = search_to_dataframe(words, page_size=50, timeout=30)
    except Exception as e:
        print("CALL_ERROR", e)
        return

    print("traceInfo:", trace)
    try:
        print("DataFrame shape:", df.shape)
        print(df.head())
    except Exception as e:
        print("DF_ERROR", e)


if __name__ == "__main__":
    main()
