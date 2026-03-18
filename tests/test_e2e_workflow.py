"""
端到端工作流测试 — 完整合同生命周期

覆盖：创建合同 → 录入磅单 → 录入化验单 → 保存配方 → 计算结算 → 验证金额

每个场景全程通过 API 操作，模拟真实的前端使用流程。
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


FIXTURES = Path(__file__).parent / "fixtures" / "mock_documents"


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture
def client(tmp_path):
    test_store = JsonFileStore(data_dir=tmp_path / "data")
    app = create_app()
    app.dependency_overrides[get_store] = lambda: test_store
    with TestClient(app) as c:
        yield c


# ══════════════════════════════════════════════════════════════
# 场景一：完整工作流
# ══════════════════════════════════════════════════════════════

class TestE2EScenario01:
    """铜精矿采购合同：手动录入数据 → 配方 → 结算验证。"""

    def test_full_workflow(self, client: TestClient) -> None:
        """
        完整工作流：
        1. 创建合同
        2. 录入 2 张磅单
        3. 录入 2 张化验单
        4. 保存计价配方
        5. 触发结算计算
        6. 断言金额与手算结果一致
        """
        # ── Step 1: 创建合同 ──────────────────────────────────
        resp = client.post("/api/contracts", json={
            "contract_number": "HT-2025-001",
            "direction": "采购",
            "counterparty": "某铜矿供应商",
            "commodity": "铜精矿",
            "assay_fee_bearer": "我方",
        })
        assert resp.status_code == 201
        contract_id = resp.json()["id"]

        # ── Step 2: 录入磅单 ───────────────────────────────────
        for wt in [
            {"ticket_number": "WT-001", "commodity": "铜精矿",
             "wet_weight": "50.225", "sample_id": "S2501"},
            {"ticket_number": "WT-002", "commodity": "铜精矿",
             "wet_weight": "48.780", "sample_id": "S2502"},
        ]:
            resp = client.post(f"/api/contracts/{contract_id}/weigh-tickets", json=wt)
            assert resp.status_code == 201

        # ── Step 3: 录入化验单 ─────────────────────────────────
        for ar in [
            {"sample_id": "S2501", "cu_pct": "18.50", "h2o_pct": "10.00"},
            {"sample_id": "S2502", "cu_pct": "19.20", "h2o_pct": "11.00"},
        ]:
            resp = client.post(f"/api/contracts/{contract_id}/assay-reports", json=ar)
            assert resp.status_code == 201

        # ── Step 4: 保存配方 ───────────────────────────────────
        recipe = {
            "version": "1.0",
            "elements": [{
                "name": "Cu",
                "type": "element",
                "quantity": {"basis": "metal_quantity", "grade_field": "cu_pct", "grade_deduction": "1.0"},
                "unit_price": {"source": "fixed", "value": "65000", "unit": "元/金属吨"},
                "operations": [],
                "tiers": [],
            }],
            "assay_fee": None,
        }
        resp = client.put(f"/api/contracts/{contract_id}/recipe", json=recipe)
        assert resp.status_code == 200

        # ── Step 5: 触发结算 ───────────────────────────────────
        resp = client.get(f"/api/contracts/{contract_id}/settlement")
        assert resp.status_code == 200, resp.text

        result = resp.json()
        items = result["items"]
        summary = result["summary"]

        # ── Step 6: 断言金额 ───────────────────────────────────
        # S2501: 干重=45.2025, 金属量=7.910, 货款=514150.00
        s2501 = next(i for i in items if i["sample_id"] == "S2501")
        assert s2501["dry_weight"] == "45.2025"
        assert s2501["metal_quantity"] == "7.910"
        assert s2501["amount"] == "514150.00"

        # S2502: 干重=43.4142, 金属量=7.901, 货款=513565.00
        s2502 = next(i for i in items if i["sample_id"] == "S2502")
        assert s2502["dry_weight"] == "43.4142"
        assert s2502["metal_quantity"] == "7.901"
        assert s2502["amount"] == "513565.00"

        # 货款合计 = 1027715.00
        assert summary["total_element_payment"] == "1027715.00"
        # 无杂质扣款
        assert summary["total_impurity_deduction"] == "0"
        # 净额（采购=支出）= -1027715.00
        assert summary["net_amount"] == "-1027715.00"


# ══════════════════════════════════════════════════════════════
# 场景二：完整工作流
# ══════════════════════════════════════════════════════════════

class TestE2EScenario02:
    """铜精矿采购：Cu + As 杂质扣款两档阶梯。"""

    def test_full_workflow(self, client: TestClient) -> None:
        """
        完整工作流：3 票磅单 + 3 张化验单 + 杂质扣款配方 → 结算验证
        """
        # 创建合同
        resp = client.post("/api/contracts", json={
            "contract_number": "HT-2026-002",
            "direction": "采购",
            "counterparty": "某铜矿供应商B",
            "commodity": "铜精矿",
        })
        contract_id = resp.json()["id"]

        # 录入 3 张磅单
        for wt in [
            {"ticket_number": "WT-201", "commodity": "铜精矿", "wet_weight": "50.000", "sample_id": "S2601"},
            {"ticket_number": "WT-202", "commodity": "铜精矿", "wet_weight": "45.000", "sample_id": "S2602"},
            {"ticket_number": "WT-203", "commodity": "铜精矿", "wet_weight": "30.000", "sample_id": "S2603"},
        ]:
            resp = client.post(f"/api/contracts/{contract_id}/weigh-tickets", json=wt)
            assert resp.status_code == 201

        # 录入 3 张化验单（S2601/S2602 有 As 超标，S2603 未超）
        for ar in [
            {"sample_id": "S2601", "cu_pct": "18.50", "h2o_pct": "10.00", "as_pct": "0.40"},
            {"sample_id": "S2602", "cu_pct": "19.20", "h2o_pct": "11.00", "as_pct": "0.55"},
            {"sample_id": "S2603", "cu_pct": "17.80", "h2o_pct": "9.00",  "as_pct": "0.20"},
        ]:
            resp = client.post(f"/api/contracts/{contract_id}/assay-reports", json=ar)
            assert resp.status_code == 201

        # 保存配方（含 As 杂质扣款）
        recipe = {
            "version": "1.0",
            "elements": [
                {
                    "name": "Cu",
                    "type": "element",
                    "quantity": {"basis": "metal_quantity", "grade_field": "cu_pct", "grade_deduction": "1.0"},
                    "unit_price": {"source": "fixed", "value": "65000", "unit": "元/金属吨"},
                    "operations": [],
                    "tiers": [],
                },
                {
                    "name": "As",
                    "type": "deduction",
                    "quantity": {"basis": "wet_weight", "grade_field": "as_pct", "grade_deduction": "0"},
                    "unit_price": {"source": "fixed", "value": None, "unit": "元/吨"},
                    "operations": [],
                    "tiers": [
                        {"lower": "0.30", "upper": "0.50", "rate": "20"},
                        {"lower": "0.50", "upper": None, "rate": "50"},
                    ],
                },
            ],
            "assay_fee": None,
        }
        resp = client.put(f"/api/contracts/{contract_id}/recipe", json=recipe)
        assert resp.status_code == 200

        # 触发结算
        resp = client.get(f"/api/contracts/{contract_id}/settlement")
        assert resp.status_code == 200, resp.text

        result = resp.json()
        items = result["items"]
        summary = result["summary"]

        # Cu 货款
        element_items = [i for i in items if i["row_type"] == "元素货款"]
        assert len(element_items) == 3

        s2601_cu = next(i for i in element_items if i["sample_id"] == "S2601")
        assert s2601_cu["amount"] == "511875.00"
        assert s2601_cu["metal_quantity"] == "7.875"

        s2602_cu = next(i for i in element_items if i["sample_id"] == "S2602")
        assert s2602_cu["amount"] == "473785.00"

        s2603_cu = next(i for i in element_items if i["sample_id"] == "S2603")
        assert s2603_cu["amount"] == "298090.00"

        # 杂质扣款
        deduction_items = [i for i in items if i["row_type"] == "杂质扣款"]
        assert len(deduction_items) == 2  # S2601 + S2602，S2603 无

        s2601_as = next(i for i in deduction_items if i["sample_id"] == "S2601")
        assert s2601_as["amount"] == "1000.00"   # 50×20

        s2602_as = next(i for i in deduction_items if i["sample_id"] == "S2602")
        assert s2602_as["amount"] == "2250.00"   # 45×50

        # 汇总
        assert summary["total_element_payment"] == "1283750.00"
        assert summary["total_impurity_deduction"] == "3250.00"
        assert summary["total_expense"] == "1287000.00"


# ══════════════════════════════════════════════════════════════
# 数据完整性测试
# ══════════════════════════════════════════════════════════════

class TestDataIntegrity:
    """数据录入的完整性与隔离性验证。"""

    def test_two_contracts_isolated(self, client: TestClient) -> None:
        """两份合同的数据互相隔离，结算不混淆。"""
        # 合同 A
        r1 = client.post("/api/contracts", json={
            "contract_number": "A-001", "direction": "采购", "counterparty": "供应商A"
        })
        id_a = r1.json()["id"]

        # 合同 B
        r2 = client.post("/api/contracts", json={
            "contract_number": "B-001", "direction": "销售", "counterparty": "买方B"
        })
        id_b = r2.json()["id"]

        # 为 A 录入磅单，为 B 不录入
        client.post(f"/api/contracts/{id_a}/weigh-tickets", json={
            "ticket_number": "WT-A", "commodity": "铜精矿", "wet_weight": "50.0", "sample_id": "S-A"
        })

        # B 的磅单列表为空
        resp = client.get(f"/api/contracts/{id_b}/weigh-tickets")
        assert len(resp.json()) == 0

        # A 的磅单列表有 1 条
        resp = client.get(f"/api/contracts/{id_a}/weigh-tickets")
        assert len(resp.json()) == 1

    def test_update_weigh_ticket(self, client: TestClient) -> None:
        """更新磅单湿重后，结算金额随之改变。"""
        # 创建合同
        r = client.post("/api/contracts", json={
            "contract_number": "UPD-001", "direction": "采购", "counterparty": "测试"
        })
        contract_id = r.json()["id"]

        # 录入磅单（初始湿重 50t）
        wt = client.post(f"/api/contracts/{contract_id}/weigh-tickets", json={
            "ticket_number": "WT-UPD", "commodity": "铜精矿",
            "wet_weight": "50.000", "sample_id": "S-UPD"
        })
        ticket_id = wt.json()["id"]

        # 录入化验单
        client.post(f"/api/contracts/{contract_id}/assay-reports", json={
            "sample_id": "S-UPD", "cu_pct": "18.50", "h2o_pct": "10.00"
        })

        # 保存配方
        recipe = {
            "version": "1.0",
            "elements": [{
                "name": "Cu", "type": "element",
                "quantity": {"basis": "metal_quantity", "grade_field": "cu_pct", "grade_deduction": "1.0"},
                "unit_price": {"source": "fixed", "value": "65000", "unit": "元/金属吨"},
                "operations": [], "tiers": [],
            }],
            "assay_fee": None,
        }
        client.put(f"/api/contracts/{contract_id}/recipe", json=recipe)

        # 计算初始结算
        r1 = client.get(f"/api/contracts/{contract_id}/settlement")
        amount_before = Decimal(r1.json()["items"][0]["amount"])

        # 更新磅单湿重（60t → 金额应增加）
        client.put(f"/api/contracts/{contract_id}/weigh-tickets/{ticket_id}", json={
            "wet_weight": "60.000"
        })

        # 重新计算结算
        r2 = client.get(f"/api/contracts/{contract_id}/settlement")
        amount_after = Decimal(r2.json()["items"][0]["amount"])

        assert amount_after > amount_before, "更新湿重后，结算金额应增加"

    def test_ready_check(self, client: TestClient) -> None:
        """就绪检查正确反映数据就绪状态。"""
        r = client.post("/api/contracts", json={
            "contract_number": "RDY-001", "direction": "采购", "counterparty": "测试"
        })
        contract_id = r.json()["id"]

        # 未录任何数据：422
        resp = client.get(f"/api/contracts/{contract_id}/settlement")
        assert resp.status_code == 422

        # 只录磅单：仍 422
        client.post(f"/api/contracts/{contract_id}/weigh-tickets", json={
            "ticket_number": "WT-R", "commodity": "铜精矿", "wet_weight": "50.0", "sample_id": "S-R"
        })
        resp = client.get(f"/api/contracts/{contract_id}/settlement")
        assert resp.status_code == 422
