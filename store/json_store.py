"""
JsonFileStore — JSON 文件存储实现

每张表对应 data/{table}.json 文件。
记录以 dict 列表存储，每条记录必须含 "id" 字段（UUID）。

开发期使用，生产期替换为 BitableStore 时只需修改配置。
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any


class JsonFileStore:
    """基于 JSON 文件的本地存储。

    Args:
        data_dir: 数据目录路径（默认为 ./data）
    """

    def __init__(self, data_dir: str | Path = "data") -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)

    # ── 私有工具方法 ────────────────────────────────────────────

    def _path(self, table: str) -> Path:
        return self._data_dir / f"{table}.json"

    def _load(self, table: str) -> list[dict]:
        p = self._path(table)
        if not p.exists():
            return []
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, table: str, records: list[dict]) -> None:
        p = self._path(table)
        with p.open("w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

    # ── 公开接口 ────────────────────────────────────────────────

    def list(self, table: str, filters: dict[str, Any] | None = None) -> list[dict]:
        """返回表中所有记录，可用 filters 做精确匹配过滤。"""
        records = self._load(table)
        if not filters:
            return records
        return [
            r for r in records
            if all(r.get(k) == v for k, v in filters.items())
        ]

    def get(self, table: str, record_id: str) -> dict | None:
        """按 ID 查单条记录。"""
        for r in self._load(table):
            if r.get("id") == record_id:
                return r
        return None

    def create(self, table: str, data: dict) -> dict:
        """新建记录，自动填充 id（若未提供）。"""
        records = self._load(table)
        record = {**data}
        if "id" not in record or not record["id"]:
            record["id"] = str(uuid.uuid4())
        records.append(record)
        self._save(table, records)
        return record

    def update(self, table: str, record_id: str, data: dict) -> dict | None:
        """更新记录，返回更新后的完整记录。"""
        records = self._load(table)
        for i, r in enumerate(records):
            if r.get("id") == record_id:
                updated = {**r, **data, "id": record_id}
                records[i] = updated
                self._save(table, records)
                return updated
        return None

    def delete(self, table: str, record_id: str) -> bool:
        """删除记录，成功返回 True。"""
        records = self._load(table)
        new_records = [r for r in records if r.get("id") != record_id]
        if len(new_records) == len(records):
            return False
        self._save(table, new_records)
        return True
