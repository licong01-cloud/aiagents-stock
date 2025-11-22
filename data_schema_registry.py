import os
from typing import Any, Dict, List

import yaml


class DataSchemaRegistry:
    """数据接口注册表：从 config/data_endpoints.yaml 读取配置并提供查询能力。

    本类仅用于提升开发效率，不参与实际数据访问逻辑，不影响现有功能。

    用法示例：
    >>> registry = DataSchemaRegistry()
    >>> kinds = registry.list_kinds()
    >>> info = registry.get_kind("realtime_quote")
    """

    def __init__(self, config_path: str | None = None) -> None:
        # 默认在当前项目根目录下查找 config/data_endpoints.yaml
        if config_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(base_dir, "config", "data_endpoints.yaml")
        self._config_path = config_path
        self._data: Dict[str, Any] = {}
        self.reload()

    @property
    def config_path(self) -> str:
        """返回当前使用的配置文件路径。"""
        return self._config_path

    def reload(self) -> None:
        """重新加载配置文件。

        若文件不存在或解析失败，将载入空配置，避免影响调用方逻辑。
        """
        try:
            if not os.path.exists(self._config_path):
                self._data = {}
                return
            with open(self._config_path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
            if not isinstance(loaded, dict):
                # 配置文件格式异常时，不抛异常，只置空，避免影响现有逻辑
                self._data = {}
            else:
                self._data = loaded
        except Exception:
            # 避免因为开发期配置错误影响其他功能
            self._data = {}

    def list_kinds(self) -> List[str]:
        """返回所有已配置的数据 kind 名称（排序后）。"""
        return sorted(self._data.keys())

    def get_kind(self, kind: str) -> Dict[str, Any]:
        """获取指定 kind 的配置字典，不存在则返回空 dict。"""
        try:
            value = self._data.get(kind) or {}
            if isinstance(value, dict):
                return value
            return {}
        except Exception:
            return {}

    def get_sources(self, kind: str) -> List[Dict[str, Any]]:
        """获取指定 kind 的 preferred_sources 列表。"""
        info = self.get_kind(kind)
        sources = info.get("preferred_sources") or []
        if isinstance(sources, list):
            return [s for s in sources if isinstance(s, dict)]
        return []
