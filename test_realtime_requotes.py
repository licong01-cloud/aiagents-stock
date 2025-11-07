"""测试多种实时行情数据获取方式（以688981为例）

1. 调用现有的数据源管理器 `get_realtime_quotes`
2. 直接调用 Tushare `realtime_quote` 接口
3. 使用 Akshare `stock_zh_a_spot_em` 接口

运行前准备：
- 确保已在环境变量中设置 `TUSHARE_TOKEN`
- 安装所需依赖： `pip install tushare akshare`
"""

import os
import json
import traceback

import pandas as pd

from data_source_manager import data_source_manager


def print_json(title: str, data):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)
    if data is None:
        print("None")
        return

    if isinstance(data, (dict, list)):
        try:
            print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
            return
        except TypeError:
            pass

    print(data)


def test_existing_method(symbol: str):
    try:
        result = data_source_manager.get_realtime_quotes(symbol)
        print_json("现有数据源管理器 get_realtime_quotes", result)
    except Exception as exc:
        print("现有方法调用失败:", exc)
        traceback.print_exc()


def test_tushare_realtime(symbol: str):
    token = os.getenv("TUSHARE_TOKEN")
    if not token:
        print("未检测到 TUSHARE_TOKEN 环境变量，跳过 Tushare 实时行情测试")
        return

    try:
        import tushare as ts

        ts.set_token(token)
        pro = ts.pro_api()

        ts_code = data_source_manager._convert_to_ts_code(symbol)
        df = pro.realtime_quote(ts_code=ts_code)

        if df is None or df.empty:
            print("Tushare realtime_quote 返回空数据")
            return

        print_json("Tushare realtime_quote 返回数据", df.to_dict(orient="records"))
    except Exception as exc:
        print("Tushare realtime_quote 调用失败:", exc)
        traceback.print_exc()


def test_akshare_spot(symbol: str):
    try:
        import akshare as ak

        df = ak.stock_zh_a_spot_em()
        if df is None or df.empty:
            print("Akshare stock_zh_a_spot_em 返回空数据")
            return

        stock_df = df[df["代码"] == symbol]
        if stock_df.empty:
            print(f"Akshare 数据中未找到股票 {symbol}")
            return

        print_json("Akshare stock_zh_a_spot_em 返回数据", stock_df.to_dict(orient="records"))
    except Exception as exc:
        print("Akshare stock_zh_a_spot_em 调用失败:", exc)
        traceback.print_exc()


def main():
    symbol = "688981"  # 中芯国际

    print("开始测试多数据源实时行情获取...\n")

    test_existing_method(symbol)
    test_tushare_realtime(symbol)
    test_akshare_spot(symbol)


if __name__ == "__main__":
    main()

