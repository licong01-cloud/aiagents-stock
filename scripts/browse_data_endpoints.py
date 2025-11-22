"""简单的数据接口浏览脚本。

用途：
- 列出 config/data_endpoints.yaml 中定义的所有数据 kind
- 查看某个 kind 对应的数据源配置（preferred_sources 等）

仅作为开发辅助工具，不参与业务逻辑。

用法示例：

  # 列出所有 kind
  python -m scripts.browse_data_endpoints list

  # 查看某个 kind 的详细配置
  python -m scripts.browse_data_endpoints show realtime_quote

"""

import argparse
import json
from typing import Any

from data_schema_registry import DataSchemaRegistry


def _print_json(obj: Any) -> None:
    try:
        print(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True))
    except Exception:
        print(obj)


def cmd_list(args: argparse.Namespace) -> None:
    registry = DataSchemaRegistry()
    kinds = registry.list_kinds()
    if not kinds:
        print("[INFO] 未在配置中发现任何数据 kind，请检查 config/data_endpoints.yaml")
        return
    print("已配置的数据 kind：")
    for k in kinds:
        print(" -", k)


def cmd_show(args: argparse.Namespace) -> None:
    kind = args.kind
    registry = DataSchemaRegistry()
    info = registry.get_kind(kind)
    if not info:
        print(f"[WARN] 未找到 kind='{kind}' 的配置")
        return
    print(f"kind = {kind}")
    _print_json(info)


def main() -> None:
    parser = argparse.ArgumentParser(description="浏览数据接口配置 (config/data_endpoints.yaml)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_list = subparsers.add_parser("list", help="列出所有数据 kind")
    p_list.set_defaults(func=cmd_list)

    p_show = subparsers.add_parser("show", help="查看指定 kind 的配置")
    p_show.add_argument("kind", help="数据 kind 名称，例如 realtime_quote 或 kline_daily_qfq")
    p_show.set_defaults(func=cmd_show)

    args = parser.parse_args()
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return
    func(args)


if __name__ == "__main__":
    main()
