"""
API 依赖注入

get_store() 返回全局 DataStore 实例。
切换存储时只改此处，路由层无需修改。
"""
from __future__ import annotations

from functools import lru_cache

from store.json_store import JsonFileStore

# 全局单例（通过 lru_cache 保证）
@lru_cache(maxsize=1)
def get_store() -> JsonFileStore:
    """返回全局 JsonFileStore 实例（data/ 目录）。"""
    return JsonFileStore(data_dir="data")
