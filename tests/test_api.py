"""
API 集成测试 — FastAPI TestClient

覆盖：
  - 合同 CRUD
  - 磅单 / 化验单子资源
  - Recipe upsert
  - 结算计算端点（场景1和场景2）
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from api.app import create_app
from api.deps import get_store
from store.json_store import JsonFileStore


# ── Fixtures ────────────────────────────────────────────────

FIXTURES = Path(__file__).parent / "fixtures" / "mock_documents"


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture
def client(tmp_path):
    """每个测试用独立临时存储，避免数据污染。"""
    test_store = JsonFileStore(data_dir=tmp_path / "data")
    app = create_app()
    # 覆盖依赖注入，使用测试用 store
    app.dependency_overrides[get_store] = lambda: test_store
    with TestClient(app) as c:
        yield c


# ── 健康检查 ────────────────────────────────────────────────

def test_health(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── 合同 CRUD ────────────────────────────────────────────────

def test_create_and_list_contracts(client: TestClient) -> None:
    """创建合同后能在列表中查到。"""
    resp = client.post("/api/contracts", json={
        "contract_number": "HT-2026-001",
        "direction": "采购",
        "counterparty": "某矿业公司",
        "commodity": "铜精矿",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["contract_number"] == "HT-2026-001"
    assert "id" in data

    resp2 = client.get("/api/contracts")
    assert resp2.status_code == 200
    assert len(resp2.json()) == 1


def test_get_contract(client: TestClient) -> None:
    """按 ID 查询合同。"""
    create_resp = client.post("/api/contracts", json={
        "contract_number": "HT-TEST-001",
        "direction": "销售",
        "counterparty": "买方公司",
    })
    contract_id = create_resp.json()["id"]

    resp = client.get(f"/api/contracts/{contract_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == contract_id


def test_get_contract_not_found(client: TestClient) -> None:
    resp = client.get("/api/contracts/nonexistent-id")
    assert resp.status_code == 404


def test_update_contract(client: TestClient) -> None:
    """更新合同字段。"""
    create_resp = client.post("/api/contracts", json={
        "contract_number": "HT-UPD-001",
        "direction": "采购",
        "counterparty": "原对手方",
    })
    contract_id = create_resp.json()["id"]

    resp = client.put(f"/api/contracts/{contract_id}", json={"counterparty": "新对手方"})
    assert resp.status_code == 200
    assert resp.json()["counterparty"] == "新对手方"
    assert resp.json()["contract_number"] == "HT-UPD-001"  # 未更改字段保留


# ── 磅单子资源 ───────────────────────────────────────────────

def test_create_and_list_weigh_tickets(client: TestClient) -> None:
    """创建磅单并按合同查询。"""
    contract_id = _create_test_contract(client)

    resp = client.post(f"/api/contracts/{contract_id}/weigh-tickets", json={
        "ticket_number": "WT-001",
        "commodity": "铜精矿",
        "wet_weight": "50.225",
        "sample_id": "S001",
    })
    assert resp.status_code == 201
    assert resp.json()["contract_id"] == contract_id

    resp2 = client.get(f"/api/contracts/{contract_id}/weigh-tickets")
    assert resp2.status_code == 200
    assert len(resp2.json()) == 1


def test_delete_weigh_ticket(client: TestClient) -> None:
    contract_id = _create_test_contract(client)
    create_resp = client.post(f"/api/contracts/{contract_id}/weigh-tickets", json={
        "ticket_number": "WT-DEL",
        "commodity": "铜精矿",
        "wet_weight": "10.0",
    })
    ticket_id = create_resp.json()["id"]

    resp = client.delete(f"/api/contracts/{contract_id}/weigh-tickets/{ticket_id}")
    assert resp.status_code == 204

    resp2 = client.get(f"/api/contracts/{contract_id}/weigh-tickets")
    assert len(resp2.json()) == 0


# ── 化验单子资源 ─────────────────────────────────────────────

def test_create_and_list_assay_reports(client: TestClient) -> None:
    contract_id = _create_test_contract(client)

    resp = client.post(f"/api/contracts/{contract_id}/assay-reports", json={
        "sample_id": "S001",
        "cu_pct": "18.50",
        "h2o_pct": "10.00",
    })
    assert resp.status_code == 201
    assert resp.json()["contract_id"] == contract_id

    resp2 = client.get(f"/api/contracts/{contract_id}/assay-reports")
    assert len(resp2.json()) == 1


# ── Recipe ───────────────────────────────────────────────────

def test_upsert_and_get_recipe(client: TestClient) -> None:
    contract_id = _create_test_contract(client)
    recipe_data = {
        "version": "1.0",
        "elements": [
            {
                "name": "Cu",
                "type": "element",
                "quantity": {"basis": "metal_quantity", "grade_field": "cu_pct", "grade_deduction": "1.0"},
                "unit_price": {"source": "fixed", "value": "65000", "unit": "元/金属吨"},
                "operations": [],
                "tiers": [],
            }
        ],
        "assay_fee": "2000.00",
    }
    resp = client.put(f"/api/contracts/{contract_id}/recipe", json=recipe_data)
    assert resp.status_code == 200

    resp2 = client.get(f"/api/contracts/{contract_id}/recipe")
    assert resp2.status_code == 200
    assert resp2.json()["contract_id"] == contract_id


def test_recipe_not_found(client: TestClient) -> None:
    contract_id = _create_test_contract(client)
    resp = client.get(f"/api/contracts/{contract_id}/recipe")
    assert resp.status_code == 404


# ── 结算端点 ─────────────────────────────────────────────────

def test_settlement_missing_data(client: TestClient) -> None:
    """未录磅单时，结算端点返回 422。"""
    contract_id = _create_test_contract(client)
    resp = client.get(f"/api/contracts/{contract_id}/settlement")
    assert resp.status_code == 422


def test_settlement_scenario_01(client: TestClient) -> None:
    """端到端：场景1 通过 API 计算结算，验证货款金额。"""
    scenario = "scenario_01"
    d = FIXTURES / scenario

    # 创建合同
    contract_data = _load_yaml(d / "contract.yaml")
    contract_id = _seed_scenario(client, contract_data, d)

    # 调用结算端点
    resp = client.get(f"/api/contracts/{contract_id}/settlement")
    assert resp.status_code == 200, resp.text

    result = resp.json()
    items = result["items"]
    summary = result["summary"]

    # 验证元素货款合计 = 1027715.00
    assert summary["total_element_payment"] == "1027715.00"

    # 验证 S2501 货款
    s2501 = next(i for i in items if i["sample_id"] == "S2501")
    assert s2501["amount"] == "514150.00"
    assert s2501["metal_quantity"] == "7.910"

    # 验证 S2502 货款
    s2502 = next(i for i in items if i["sample_id"] == "S2502")
    assert s2502["amount"] == "513565.00"


def test_settlement_scenario_02(client: TestClient) -> None:
    """端到端：场景2 通过 API 计算结算，验证货款 + 杂质扣款。"""
    scenario = "scenario_02"
    d = FIXTURES / scenario

    contract_data = _load_yaml(d / "contract.yaml")
    contract_id = _seed_scenario(client, contract_data, d)

    resp = client.get(f"/api/contracts/{contract_id}/settlement")
    assert resp.status_code == 200, resp.text

    result = resp.json()
    items = result["items"]
    summary = result["summary"]

    # Cu 货款合计 = 1283750.00
    assert summary["total_element_payment"] == "1283750.00"
    # 杂质扣款合计 = 3250.00
    assert summary["total_impurity_deduction"] == "3250.00"

    # S2601 杂质扣款 = 1000.00
    deduction_items = [i for i in items if i["row_type"] == "杂质扣款"]
    s2601_ded = next(i for i in deduction_items if i["sample_id"] == "S2601")
    assert s2601_ded["amount"] == "1000.00"


# ── 工具函数 ─────────────────────────────────────────────────

def _create_test_contract(client: TestClient) -> str:
    """创建一个简单测试合同，返回 contract_id。"""
    resp = client.post("/api/contracts", json={
        "contract_number": "TEST-001",
        "direction": "采购",
        "counterparty": "测试对手方",
    })
    return resp.json()["id"]


def _seed_scenario(client: TestClient, contract_data: dict, scenario_dir: Path) -> str:
    """将场景数据写入 API，返回 contract_id。"""
    # 创建合同
    resp = client.post("/api/contracts", json={
        "contract_number": contract_data["contract_number"],
        "direction": contract_data["direction"],
        "counterparty": contract_data["counterparty"],
        "commodity": contract_data.get("commodity"),
    })
    assert resp.status_code == 201, resp.text
    contract_id = resp.json()["id"]

    # 写入磅单
    wt_data = _load_yaml(scenario_dir / "weigh_tickets.yaml")
    for wt in wt_data["weigh_tickets"]:
        resp = client.post(f"/api/contracts/{contract_id}/weigh-tickets", json={
            "ticket_number": wt["ticket_number"],
            "commodity": wt["commodity"],
            "wet_weight": str(wt["wet_weight"]),
            "sample_id": wt.get("sample_id"),
            "is_settlement": wt.get("is_settlement", True),
        })
        assert resp.status_code == 201, resp.text

    # 写入化验单
    ar_data = _load_yaml(scenario_dir / "assay_reports.yaml")
    for ar in ar_data["assay_reports"]:
        body = {
            "sample_id": ar["sample_id"],
            "is_settlement": ar.get("is_settlement", True),
        }
        for field in ["cu_pct", "h2o_pct", "as_pct", "au_gt", "ag_gt", "pb_pct", "zn_pct", "s_pct"]:
            if ar.get(field) is not None:
                body[field] = str(ar[field])
        resp = client.post(f"/api/contracts/{contract_id}/assay-reports", json=body)
        assert resp.status_code == 201, resp.text

    # 写入 Recipe
    recipe_data = _load_yaml(scenario_dir / "recipe.yaml")
    recipe_body = {k: v for k, v in recipe_data.items() if k != "contract_id"}
    # Decimal 序列化
    _serialize_recipe(recipe_body)
    resp = client.put(f"/api/contracts/{contract_id}/recipe", json=recipe_body)
    assert resp.status_code == 200, resp.text

    return contract_id


def _serialize_recipe(data: dict | list) -> None:
    """递归将 recipe 数据中的 Decimal 字段转为字符串（YAML 可能解析为 float）。"""
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                _serialize_recipe(v)
            elif isinstance(v, float):
                data[k] = str(v)
    elif isinstance(data, list):
        for item in data:
            _serialize_recipe(item)
