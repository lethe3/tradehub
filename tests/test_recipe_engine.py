"""
Recipe Engine 测试

1. evaluate_recipe 场景1验证（固定计价，Cu，品位扣减）
2. evaluate_recipe 场景2验证（Cu + As 杂质扣款）
3. 交叉验证：evaluate_recipe vs generate_settlement_items 结果一致性
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from core.linking import build_batch_view
from core.models.batch import AssayReportRecord, ContractRecord, WeighTicketRecord
from core.models.pricing import (
    ContractPricing,
    FormulaType,
    ImpurityDeduction,
    ImpurityDeductionTier,
    PricingElement,
    PriceSourceType,
    UnitType,
)
from core.settlement import generate_settlement_items
from engine.recipe import evaluate_recipe
from engine.schema import (
    PriceStep,
    QuantityStep,
    Recipe,
    RecipeElement,
    TierEntry,
)

# ── Fixture 路径 ────────────────────────────────────────────
FIXTURES = Path(__file__).parent / "fixtures" / "mock_documents"


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── 场景数据加载工具 ────────────────────────────────────────

def _load_scenario(name: str):
    """加载场景目录下的 4 个 YAML 文件，返回 (contract, weigh_tickets, assay_reports, expected, recipe)。"""
    d = FIXTURES / name
    contract_data = _load_yaml(d / "contract.yaml")
    wt_data = _load_yaml(d / "weigh_tickets.yaml")
    ar_data = _load_yaml(d / "assay_reports.yaml")
    recipe_data = _load_yaml(d / "recipe.yaml")

    contract = ContractRecord(
        contract_id=contract_data["contract_id"],
        contract_number=contract_data["contract_number"],
        direction=contract_data["direction"],
        counterparty=contract_data["counterparty"],
    )
    weigh_tickets = [WeighTicketRecord(**wt) for wt in wt_data["weigh_tickets"]]
    assay_reports = [AssayReportRecord(**ar) for ar in ar_data["assay_reports"]]
    recipe = Recipe(**recipe_data)

    return contract, weigh_tickets, assay_reports, recipe


def _build_batch_view(contract, weigh_tickets, assay_reports):
    batch_view, _ = build_batch_view(contract, weigh_tickets, assay_reports)
    return batch_view


# ══════════════════════════════════════════════════════════════
# 场景 1：固定计价，Cu，品位扣减
# ══════════════════════════════════════════════════════════════

class TestScenario01:
    """场景一：铜精矿采购，固定价，Cu 品位扣减 1%，化验费 2000 元。"""

    def setup_method(self):
        self.contract, self.tickets, self.reports, self.recipe = _load_scenario("scenario_01")
        self.batch_view = _build_batch_view(self.contract, self.tickets, self.reports)
        self.items = evaluate_recipe(self.recipe, self.batch_view, "采购")
        # 载入预期结果
        expected_data = _load_yaml(FIXTURES / "scenario_01" / "expected_cash_flows.yaml")
        self.expected = expected_data["batch_calculations"]
        self.expected_flows = expected_data["expected_cash_flows"]

    def test_item_count(self):
        """场景1：2 个批次 × 1 个计价元素 = 2 条元素货款记录。"""
        assert len(self.items) == 2

    def test_s2501_dry_weight(self):
        """S2501 干重 = 45.2025。"""
        item = next(i for i in self.items if i.sample_id == "S2501")
        assert item.dry_weight == Decimal("45.2025")

    def test_s2501_metal_quantity(self):
        """S2501 金属量 = 8.362（无扣减）。"""
        item = next(i for i in self.items if i.sample_id == "S2501")
        assert item.metal_quantity == Decimal("8.362")

    def test_s2501_payment(self):
        """S2501 货款 = 543530.00。"""
        item = next(i for i in self.items if i.sample_id == "S2501")
        assert item.amount == Decimal("543530.00")

    def test_s2502_dry_weight(self):
        """S2502 干重 = 43.4142。"""
        item = next(i for i in self.items if i.sample_id == "S2502")
        assert item.dry_weight == Decimal("43.4142")

    def test_s2502_metal_quantity(self):
        """S2502 金属量 = 8.336（无扣减）。"""
        item = next(i for i in self.items if i.sample_id == "S2502")
        assert item.metal_quantity == Decimal("8.336")

    def test_s2502_payment(self):
        """S2502 货款 = 541840.00。"""
        item = next(i for i in self.items if i.sample_id == "S2502")
        assert item.amount == Decimal("541840.00")

    def test_all_expense_direction(self):
        """采购合同所有元素货款方向为 EXPENSE。"""
        from core.models.settlement_item import SettlementDirection
        assert all(i.direction == SettlementDirection.EXPENSE for i in self.items)

    def test_total_element_payment(self):
        """元素货款合计 = 1085370.00（无扣减）。"""
        total = sum(i.amount for i in self.items)
        assert total == Decimal("1085370.00")


# ══════════════════════════════════════════════════════════════
# 场景 2：Cu + As 杂质扣款
# ══════════════════════════════════════════════════════════════

class TestScenario02:
    """场景二：铜精矿采购，固定价，Cu + As 杂质扣款两档阶梯。"""

    def setup_method(self):
        self.contract, self.tickets, self.reports, self.recipe = _load_scenario("scenario_02")
        self.batch_view = _build_batch_view(self.contract, self.tickets, self.reports)
        self.items = evaluate_recipe(self.recipe, self.batch_view, "采购")

        self.expected_data = _load_yaml(FIXTURES / "scenario_02" / "expected_cash_flows.yaml")

    def test_item_count(self):
        """3 批次 × 1 元素 + 2 条扣款（S2603 未落入档位）= 5 条记录。"""
        assert len(self.items) == 5

    def test_s2601_cu_payment(self):
        """S2601 Cu 货款 = 541125.00（无扣减）。"""
        from core.models.settlement_item import SettlementRowType
        item = next(
            i for i in self.items
            if i.sample_id == "S2601" and i.row_type == SettlementRowType.ELEMENT_PAYMENT
        )
        assert item.amount == Decimal("541125.00")

    def test_s2602_cu_payment(self):
        """S2602 Cu 货款 = 499850.00（无扣减）。"""
        from core.models.settlement_item import SettlementRowType
        item = next(
            i for i in self.items
            if i.sample_id == "S2602" and i.row_type == SettlementRowType.ELEMENT_PAYMENT
        )
        assert item.amount == Decimal("499850.00")

    def test_s2603_cu_payment(self):
        """S2603 Cu 货款 = 315835.00（无扣减）。"""
        from core.models.settlement_item import SettlementRowType
        item = next(
            i for i in self.items
            if i.sample_id == "S2603" and i.row_type == SettlementRowType.ELEMENT_PAYMENT
        )
        assert item.amount == Decimal("315835.00")

    def test_s2601_as_deduction(self):
        """S2601 As=0.40%，落第一档，扣款 = 50.000×20 = 1000.00。"""
        from core.models.settlement_item import SettlementRowType
        item = next(
            i for i in self.items
            if i.sample_id == "S2601" and i.row_type == SettlementRowType.IMPURITY_DEDUCTION
        )
        assert item.amount == Decimal("1000.00")

    def test_s2602_as_deduction(self):
        """S2602 As=0.55%，落第二档，扣款 = 45.000×50 = 2250.00。"""
        from core.models.settlement_item import SettlementRowType
        item = next(
            i for i in self.items
            if i.sample_id == "S2602" and i.row_type == SettlementRowType.IMPURITY_DEDUCTION
        )
        assert item.amount == Decimal("2250.00")

    def test_s2603_no_deduction(self):
        """S2603 As=0.20%，低于下限 0.30%，无杂质扣款行。"""
        from core.models.settlement_item import SettlementRowType
        deduction_items = [
            i for i in self.items
            if i.sample_id == "S2603" and i.row_type == SettlementRowType.IMPURITY_DEDUCTION
        ]
        assert len(deduction_items) == 0

    def test_total_cu_payment(self):
        """Cu 货款合计 = 1356810.00（无扣减）。"""
        from core.models.settlement_item import SettlementRowType
        total = sum(i.amount for i in self.items if i.row_type == SettlementRowType.ELEMENT_PAYMENT)
        assert total == Decimal("1356810.00")

    def test_total_deduction(self):
        """As 扣款合计 = 3250.00。"""
        from core.models.settlement_item import SettlementRowType
        total = sum(i.amount for i in self.items if i.row_type == SettlementRowType.IMPURITY_DEDUCTION)
        assert total == Decimal("3250.00")


# ══════════════════════════════════════════════════════════════
# 交叉验证：evaluate_recipe vs generate_settlement_items
# ══════════════════════════════════════════════════════════════

def _build_contract_pricing_01() -> ContractPricing:
    return ContractPricing(
        contract_id="mock-contract-001",
        pricing_elements=[
            PricingElement(
                element="Cu",
                price_source_type=PriceSourceType.FIXED,
                base_price=Decimal("65000"),
                unit=UnitType.CNY_PER_METAL_TON,
                formula_type=FormulaType.FIXED_PRICE,
            )
        ],
        impurity_deductions=[],
        assay_fee_total=None,  # generate_settlement_items 不输出化验费行
    )


def _build_contract_pricing_02() -> ContractPricing:
    return ContractPricing(
        contract_id="mock-contract-002",
        pricing_elements=[
            PricingElement(
                element="Cu",
                price_source_type=PriceSourceType.FIXED,
                base_price=Decimal("65000"),
                unit=UnitType.CNY_PER_METAL_TON,
                formula_type=FormulaType.FIXED_PRICE,
            )
        ],
        impurity_deductions=[
            ImpurityDeduction(
                element="As",
                tiers=[
                    ImpurityDeductionTier(lower=Decimal("0.30"), upper=Decimal("0.50"), rate=Decimal("20"), upper_open=True),
                    ImpurityDeductionTier(lower=Decimal("0.50"), upper=None, rate=Decimal("50"), upper_open=True),
                ],
            )
        ],
        assay_fee_total=None,
    )


class TestCrossValidation:
    """交叉验证：evaluate_recipe 与 generate_settlement_items 的数值结果一致。"""

    def test_scenario_01_amounts_match(self):
        """场景1：两引擎各批次金额完全一致。"""
        contract, tickets, reports, recipe = _load_scenario("scenario_01")
        batch_view = _build_batch_view(contract, tickets, reports)

        recipe_items = evaluate_recipe(recipe, batch_view, "采购")
        legacy_items = generate_settlement_items(batch_view, _build_contract_pricing_01())

        assert len(recipe_items) == len(legacy_items)
        for r, l in zip(recipe_items, legacy_items):
            assert r.sample_id == l.sample_id, f"sample_id 不匹配: {r.sample_id} vs {l.sample_id}"
            assert r.amount == l.amount, f"金额不匹配 [{r.sample_id}]: {r.amount} vs {l.amount}"
            if r.dry_weight is not None:
                assert r.dry_weight == l.dry_weight, f"干重不匹配 [{r.sample_id}]"
            if r.metal_quantity is not None:
                assert r.metal_quantity == l.metal_quantity, f"金属量不匹配 [{r.sample_id}]"

    def test_scenario_02_amounts_match(self):
        """场景2：两引擎各批次金额（含杂质扣款）完全一致。"""
        contract, tickets, reports, recipe = _load_scenario("scenario_02")
        batch_view = _build_batch_view(contract, tickets, reports)

        recipe_items = evaluate_recipe(recipe, batch_view, "采购")
        legacy_items = generate_settlement_items(batch_view, _build_contract_pricing_02())

        assert len(recipe_items) == len(legacy_items)
        # 按 (sample_id, row_type) 建立索引比对
        from core.models.settlement_item import SettlementRowType

        def key(item):
            return (item.sample_id or "", item.row_type.value)

        recipe_map = {key(i): i for i in recipe_items}
        legacy_map = {key(i): i for i in legacy_items}

        assert set(recipe_map.keys()) == set(legacy_map.keys()), \
            f"记录集合不一致: recipe={set(recipe_map.keys())} legacy={set(legacy_map.keys())}"

        for k in recipe_map:
            r = recipe_map[k]
            l = legacy_map[k]
            assert r.amount == l.amount, f"金额不匹配 [{k}]: {r.amount} vs {l.amount}"
