"""
DataStore Protocol — 存储层接口定义

所有存储实现（JsonFileStore、BitableStore）必须实现此接口。
切换存储只改配置，不改上层业务代码。
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DataStore(Protocol):
    """通用 KV 存储接口，按表名 + 记录 ID 操作。

    每条记录为一个 dict，必须含 "id" 字段（字符串 UUID）。
    """

    def list(self, table: str, filters: dict[str, Any] | None = None) -> list[dict]:
        """返回表中所有记录（可选过滤条件）。

        filters 为 key=value 的精确匹配字典，例如：
            {"contract_id": "abc-123"}
        """
        ...

    def get(self, table: str, record_id: str) -> dict | None:
        """按 ID 查询单条记录，不存在返回 None。"""
        ...

    def create(self, table: str, data: dict) -> dict:
        """创建记录，自动生成 UUID 作为 id，返回含 id 的完整记录。

        如果 data 已含 "id" 字段，使用传入的值（方便测试）。
        """
        ...

    def update(self, table: str, record_id: str, data: dict) -> dict | None:
        """更新记录，返回更新后的完整记录，不存在返回 None。"""
        ...

    def delete(self, table: str, record_id: str) -> bool:
        """删除记录，成功返回 True，不存在返回 False。"""
        ...
