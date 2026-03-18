"""
store/ 单元测试 — JsonFileStore CRUD 验证

覆盖：create / list / get / update / delete + 过滤查询
"""
import tempfile
from pathlib import Path

import pytest

from store.json_store import JsonFileStore


@pytest.fixture
def store(tmp_path: Path) -> JsonFileStore:
    """每个测试用独立临时目录，测试间互不影响。"""
    return JsonFileStore(data_dir=tmp_path / "data")


# ── create ──────────────────────────────────────────────────

def test_create_auto_id(store: JsonFileStore) -> None:
    """create 未传 id 时自动生成 UUID。"""
    record = store.create("contracts", {"name": "合同A"})
    assert "id" in record
    assert record["name"] == "合同A"
    assert len(record["id"]) == 36  # UUID 格式


def test_create_custom_id(store: JsonFileStore) -> None:
    """create 传入自定义 id 时使用该 id。"""
    record = store.create("contracts", {"id": "custom-001", "name": "合同B"})
    assert record["id"] == "custom-001"


def test_create_persists(store: JsonFileStore) -> None:
    """create 后数据持久化到文件，重新实例化仍能读取。"""
    store.create("contracts", {"id": "persist-001", "name": "持久化测试"})

    # 用相同目录新建实例，验证文件持久化
    store2 = JsonFileStore(data_dir=store._data_dir)
    record = store2.get("contracts", "persist-001")
    assert record is not None
    assert record["name"] == "持久化测试"


# ── list ────────────────────────────────────────────────────

def test_list_empty(store: JsonFileStore) -> None:
    """空表返回空列表。"""
    result = store.list("contracts")
    assert result == []


def test_list_all(store: JsonFileStore) -> None:
    """list 返回全部记录。"""
    store.create("contracts", {"id": "c1", "direction": "采购"})
    store.create("contracts", {"id": "c2", "direction": "销售"})
    result = store.list("contracts")
    assert len(result) == 2


def test_list_with_filter(store: JsonFileStore) -> None:
    """list 使用 filters 精确匹配。"""
    store.create("weigh_tickets", {"id": "wt1", "contract_id": "c1"})
    store.create("weigh_tickets", {"id": "wt2", "contract_id": "c2"})
    store.create("weigh_tickets", {"id": "wt3", "contract_id": "c1"})

    result = store.list("weigh_tickets", filters={"contract_id": "c1"})
    assert len(result) == 2
    assert all(r["contract_id"] == "c1" for r in result)


# ── get ─────────────────────────────────────────────────────

def test_get_existing(store: JsonFileStore) -> None:
    """get 返回对应记录。"""
    store.create("contracts", {"id": "get-001", "name": "铜精矿合同"})
    record = store.get("contracts", "get-001")
    assert record is not None
    assert record["name"] == "铜精矿合同"


def test_get_nonexistent(store: JsonFileStore) -> None:
    """get 不存在的 ID 返回 None。"""
    result = store.get("contracts", "nonexistent")
    assert result is None


# ── update ──────────────────────────────────────────────────

def test_update_existing(store: JsonFileStore) -> None:
    """update 修改指定字段，其余字段保留。"""
    store.create("contracts", {"id": "upd-001", "name": "原名", "direction": "采购"})
    updated = store.update("contracts", "upd-001", {"name": "新名"})
    assert updated is not None
    assert updated["name"] == "新名"
    assert updated["direction"] == "采购"  # 未改字段保留
    assert updated["id"] == "upd-001"     # id 不变


def test_update_nonexistent(store: JsonFileStore) -> None:
    """update 不存在的 ID 返回 None。"""
    result = store.update("contracts", "nonexistent", {"name": "x"})
    assert result is None


def test_update_persists(store: JsonFileStore) -> None:
    """update 后重新读取数据一致。"""
    store.create("contracts", {"id": "upd-002", "status": "草稿"})
    store.update("contracts", "upd-002", {"status": "已签"})
    record = store.get("contracts", "upd-002")
    assert record["status"] == "已签"


# ── delete ──────────────────────────────────────────────────

def test_delete_existing(store: JsonFileStore) -> None:
    """delete 返回 True，记录被移除。"""
    store.create("contracts", {"id": "del-001", "name": "待删除"})
    result = store.delete("contracts", "del-001")
    assert result is True
    assert store.get("contracts", "del-001") is None


def test_delete_nonexistent(store: JsonFileStore) -> None:
    """delete 不存在的 ID 返回 False。"""
    result = store.delete("contracts", "nonexistent")
    assert result is False


def test_delete_only_removes_target(store: JsonFileStore) -> None:
    """delete 只删目标记录，其余记录不受影响。"""
    store.create("contracts", {"id": "keep-001", "name": "保留"})
    store.create("contracts", {"id": "drop-001", "name": "删除"})
    store.delete("contracts", "drop-001")
    assert store.get("contracts", "keep-001") is not None
    assert len(store.list("contracts")) == 1


# ── 多表隔离 ────────────────────────────────────────────────

def test_tables_isolated(store: JsonFileStore) -> None:
    """不同表之间数据互相隔离。"""
    store.create("contracts", {"id": "c1", "name": "合同"})
    store.create("weigh_tickets", {"id": "c1", "name": "磅单"})  # 同 id，不同表

    contract = store.get("contracts", "c1")
    ticket = store.get("weigh_tickets", "c1")
    assert contract["name"] == "合同"
    assert ticket["name"] == "磅单"
