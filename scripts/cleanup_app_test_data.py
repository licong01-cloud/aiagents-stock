#!/usr/bin/env python
"""清理 app 侧测试数据（持仓、自选、分析记录）。

会执行：
- TRUNCATE app.portfolio_stocks
- TRUNCATE app.watchlist_item_categories
- TRUNCATE app.watchlist_items
- TRUNCATE app.analysis_records
"""
from __future__ import annotations

import os
import sys

import psycopg2
from dotenv import load_dotenv


def get_db_cfg():
    load_dotenv(override=True)
    return dict(
        host=os.getenv("TDX_DB_HOST", "localhost"),
        port=int(os.getenv("TDX_DB_PORT", "5432")),
        user=os.getenv("TDX_DB_USER", "postgres"),
        password=os.getenv("TDX_DB_PASSWORD", ""),
        dbname=os.getenv("TDX_DB_NAME", "aistock"),
    )


SQLS = [
    "TRUNCATE TABLE app.portfolio_stocks RESTART IDENTITY CASCADE;",
    "TRUNCATE TABLE app.watchlist_item_categories RESTART IDENTITY;",
    "TRUNCATE TABLE app.watchlist_items RESTART IDENTITY CASCADE;",
    "TRUNCATE TABLE app.analysis_records RESTART IDENTITY;",
]


def main() -> None:
    cfg = get_db_cfg()
    print("将连接数据库：", cfg)
    confirm = input(
        "\n警告：即将清空 app.portfolio_stocks / app.watchlist_* / app.analysis_records 测试数据。\n"
        "请输入 YES 确认执行，其他任意键取消："
    ).strip()
    if confirm != "YES":
        print("已取消，不执行任何操作。")
        return

    conn = psycopg2.connect(**cfg)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            for sql in SQLS:
                print(f"\n执行: {sql.strip()}")
                cur.execute(sql)
        print("\n✅ 清理完成。")
    except Exception as exc:  # noqa: BLE001
        print(f"\n❌ 清理失败: {exc}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n中断退出")
        sys.exit(1)
