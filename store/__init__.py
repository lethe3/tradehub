"""
存储层：DataStore 接口 + JsonFileStore 实现

开发期用 JsonFileStore（JSON 文件），生产期替换为 BitableStore。
"""
from .base import DataStore
from .json_store import JsonFileStore

__all__ = ["DataStore", "JsonFileStore"]
