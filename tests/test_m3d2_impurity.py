"""
M3D-2 杂质扣款测试

覆盖：
1. find_impurity_tier()：落第一档 / 落第二档 / 低于下限 / 恰好等于上限（开/闭区间）
2. calc_impurity_amount()：精确值 + 舍入
3. scenario_02 端到端：S2601/S2602 有扣款，S2603 无扣款
4. 无杂质规则时不生成记录（scenario_01 回归）
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from core.linking import build_batch_view
from core.models.batch import (
    AssayReportRecord,
    BatchUnit,
    BatchView,
    ContractRecord,
    WeighTicketRecord,
)
from core.models.cash_flow import CashFlowDirection, CashFlowType, SettlementSummary
from core.models.pricing import (
    ContractPricing,
    FormulaType,
    ImpurityDeduction,
    ImpurityDeductionTier,
    PricingElement,
    PriceSourceType,
)
from core.settlement import (
    calc_impurity_amount,
    find_impurity_tier,
    generate_cash_flows,
)

SCENARIO_01 = Path(__file__).parent / "fixtures" / "mock_documents" / "scenario_01"
SCENARIO_02 = Path(__file__).parent / "fixtures" / "mock_documents" / "scenario_02"


# ── Fixture 加载工具 ──────────────────────────────────────────

def load_yaml(path: Path, filename: str) -> dict:
    with open(path / filename, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_scenario_02():
    """返回 (BatchView, ContractPricing, expected_data)"""
    raw_contract = load_yaml(SCENARIO_02, "contract.yaml")
    raw_tickets = load_yaml(SCENARIO_02, "weigh_tickets.yaml")["weigh_tickets"]
    raw_reports = load_yaml(SCENARIO_02, "assay_reports.yaml")["assay_reports"]
    expected = load_yaml(SCENARIO_02, "expected_cash_flows.yaml")

    contract = ContractRecord(
        contract_id=raw_contract["contract_id"],
        contract_number=raw_contract["contract_number"],
        direction=raw_contract["direction"],
        commodity=raw_contract["commodity"],
        counterparty=raw_contract["counterparty"],
        signing_date=date.fromisoformat(raw_contract["signing_date"]),
        tax_included=raw_contract.get("tax_included"),
        freight_bearer=raw_contract.get("freight_bearer"),
        assay_fee_bearer=raw_contract.get("assay_fee_bearer"),
        pricing_elements=raw_contract.get("pricing_elements", []),
    )

    tickets = [WeighTicketRecord(**t) for t in raw_tickets]
    reports = [AssayReportRecord(**r) for r in raw_reports]
    batch_view, _ = build_batch_view(contract, tickets, reports)

    # 解析 ContractPricing
    p = raw_contract["pricing"]

    pricing_elements = []
    for pe in p["pricing_elements"]:
        pricing_elements.append(PricingElement(
            element=pe["element"],
            price_source_type=PriceSourceType(pe["price_source_type"]),
            base_price=Decimal(str(pe["base_price"])),
            unit=pe["unit"],
            formula_type=FormulaType(pe["formula_type"]),
        ))

    impurity_deductions = []
    for imp in p.get("impurity_deductions", []):
        tiers = []
        for t in imp["tiers"]:
            tiers.append(ImpurityDeductionTier(
                lower=Decimal(str(t["lower"])),
                upper=Decimal(str(t["upper"])) if t.get("upper") is not None else None,
                rate=Decimal(str(t["rate"])),
                upper_open=t.get("upper_open", True),
            ))
        impurity_deductions.append(ImpurityDeduction(
            element=imp["element"],
            tiers=tiers,
        ))

    contract_pricing = ContractPricing(
        contract_id=raw_contract["contract_id"],
        dry_weight_formula=p.get("dry_weight_formula", "wet * (1 - h2o)"),
        pricing_elements=pricing_elements,
        impurity_deductions=impurity_deductions,
        assay_fee_total=Decimal(str(p["assay_fee_total"])) if p.get("assay_fee_total") is not None else None,
    )

    return batch_view, contract_pricing, expected


# ── 辅助：构造阶梯（As，两档）────────────────────────────────

def _as_tiers() -> list[ImpurityDeductionTier]:
    """[0.3%, 0.5%) → 20; [0.5%, ∞) → 50"""
    return [
        ImpurityDeductionTier(lower=Decimal("0.30"), upper=Decimal("0.50"), rate=Decimal("20"), upper_open=True),
        ImpurityDeductionTier(lower=Decimal("0.50"), upper=None, rate=Decimal("50"), upper_open=True),
    ]


# ══════════════════════════════════════════════════════════════
# 单元测试：find_impurity_tier
# ══════════════════════════════════════════════════════════════

class TestFindImpurityTier:
    def test_falls_in_first_tier(self):
        tier = find_impurity_tier(Decimal("0.40"), _as_tiers())
        assert tier is not None
        assert tier.rate == Decimal("20")

    def test_falls_in_second_tier(self):
        tier = find_impurity_tier(Decimal("0.55"), _as_tiers())
        assert tier is not None
        assert tier.rate == Decimal("50")

    def test_below_lower_bound_returns_none(self):
        tier = find_impurity_tier(Decimal("0.20"), _as_tiers())
        assert tier is None

    def test_exactly_at_lower_bound_matches(self):
        # 0.30 == lower → 含，应落第一档
        tier = find_impurity_tier(Decimal("0.30"), _as_tiers())
        assert tier is not None
        assert tier.rate == Decimal("20")

    def test_exactly_at_upper_open_does_not_match_tier(self):
        # 0.50 == upper of tier1，上限开区间 → 不落第一档，应落第二档
        tier = find_impurity_tier(Decimal("0.50"), _as_tiers())
        assert tier is not None
        assert tier.rate == Decimal("50")

    def test_upper_closed_interval_matches_at_upper(self):
        # upper_open=False → 上限闭区间，恰好等于 upper 应匹配
        tiers = [
            ImpurityDeductionTier(lower=Decimal("0.30"), upper=Decimal("0.50"), rate=Decimal("20"), upper_open=False),
        ]
        tier = find_impurity_tier(Decimal("0.50"), tiers)
        assert tier is not None
        assert tier.rate == Decimal("20")

    def test_empty_tiers_returns_none(self):
        assert find_impurity_tier(Decimal("0.40"), []) is None


# ══════════════════════════════════════════════════════════════
# 单元测试：calc_impurity_amount
# ══════════════════════════════════════════════════════════════

class TestCalcImpurityAmount:
    def test_exact_value(self):
        # 50.000 × 20 = 1000.00
        result = calc_impurity_amount(Decimal("50.000"), Decimal("20"))
        assert result == Decimal("1000.00")

    def test_exact_value_second_tier(self):
        # 45.000 × 50 = 2250.00
        result = calc_impurity_amount(Decimal("45.000"), Decimal("50"))
        assert result == Decimal("2250.00")

    def test_rounding_half_up(self):
        # 10.001 × 3 = 30.003 → 30.00
        result = calc_impurity_amount(Decimal("10.001"), Decimal("3"))
        assert result == Decimal("30.00")

    def test_rounding_rounds_up(self):
        # 1.005 × 1 = 1.005 → 1.01 (ROUND_HALF_UP)
        result = calc_impurity_amount(Decimal("1.005"), Decimal("1"))
        assert result == Decimal("1.01")


# ══════════════════════════════════════════════════════════════
# 端到端测试：scenario_02
# ══════════════════════════════════════════════════════════════

class TestGenerateCashFlowsScenario02:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.batch_view, self.contract_pricing, self.expected = load_scenario_02()
        self.records = generate_cash_flows(self.batch_view, self.contract_pricing)

    def test_record_count(self):
        # 3 元素货款 + 2 杂质扣款（S2601, S2602）= 5 条；S2603 无杂质扣款
        assert len(self.records) == 5

    def test_s2601_element_payment(self):
        r = next(x for x in self.records
                 if x.flow_type == CashFlowType.ELEMENT_PAYMENT and x.sample_id == "S2601")
        assert r.direction == CashFlowDirection.EXPENSE
        assert r.element == "Cu"
        assert r.dry_weight == Decimal("45.0000")
        assert r.metal_quantity == Decimal("8.325")
        assert r.amount == Decimal("541125.00")

    def test_s2602_element_payment(self):
        r = next(x for x in self.records
                 if x.flow_type == CashFlowType.ELEMENT_PAYMENT and x.sample_id == "S2602")
        assert r.dry_weight == Decimal("40.0500")
        assert r.metal_quantity == Decimal("7.690")
        assert r.amount == Decimal("499850.00")

    def test_s2603_element_payment(self):
        r = next(x for x in self.records
                 if x.flow_type == CashFlowType.ELEMENT_PAYMENT and x.sample_id == "S2603")
        assert r.dry_weight == Decimal("27.3000")
        assert r.metal_quantity == Decimal("4.859")
        assert r.amount == Decimal("315835.00")

    def test_s2601_impurity_deduction(self):
        # As=0.40% → 第一档 → 50.000 × 20 = 1000.00
        r = next(x for x in self.records
                 if x.flow_type == CashFlowType.IMPURITY_DEDUCTION and x.sample_id == "S2601")
        assert r.direction == CashFlowDirection.EXPENSE
        assert r.element == "As"
        assert r.amount == Decimal("1000.00")

    def test_s2602_impurity_deduction(self):
        # As=0.55% → 第二档 → 45.000 × 50 = 2250.00
        r = next(x for x in self.records
                 if x.flow_type == CashFlowType.IMPURITY_DEDUCTION and x.sample_id == "S2602")
        assert r.direction == CashFlowDirection.EXPENSE
        assert r.element == "As"
        assert r.amount == Decimal("2250.00")

    def test_s2603_no_impurity_deduction(self):
        # As=0.20% → 低于下限 → 无扣款
        imp_records = [x for x in self.records
                       if x.flow_type == CashFlowType.IMPURITY_DEDUCTION and x.sample_id == "S2603"]
        assert len(imp_records) == 0

    def test_summary_total_expense(self):
        summary = SettlementSummary.from_records(
            contract_id=self.batch_view.contract.contract_id,
            contract_number=self.batch_view.contract.contract_number,
            records=self.records,
        )
        assert summary.total_expense == Decimal("1360060.00")

    def test_summary_total_income(self):
        summary = SettlementSummary.from_records(
            contract_id=self.batch_view.contract.contract_id,
            contract_number=self.batch_view.contract.contract_number,
            records=self.records,
        )
        assert summary.total_income == Decimal("0.00")

    def test_all_records_have_contract_id(self):
        for r in self.records:
            assert r.contract_id == "mock-contract-002"


# ══════════════════════════════════════════════════════════════
# 回归测试：scenario_01 无杂质规则，不生成杂质扣款记录
# ══════════════════════════════════════════════════════════════

class TestNoImpurityWhenRulesAbsent:
    def test_scenario_01_has_no_impurity_records(self):
        raw_contract = load_yaml(SCENARIO_01, "contract.yaml")
        raw_tickets = load_yaml(SCENARIO_01, "weigh_tickets.yaml")["weigh_tickets"]
        raw_reports = load_yaml(SCENARIO_01, "assay_reports.yaml")["assay_reports"]

        contract = ContractRecord(
            contract_id=raw_contract["contract_id"],
            contract_number=raw_contract["contract_number"],
            direction=raw_contract["direction"],
            commodity=raw_contract["commodity"],
            counterparty=raw_contract["counterparty"],
            signing_date=date.fromisoformat(raw_contract["signing_date"]),
        )
        tickets = [WeighTicketRecord(**t) for t in raw_tickets]
        reports = [AssayReportRecord(**r) for r in raw_reports]
        batch_view, _ = build_batch_view(contract, tickets, reports)

        p = raw_contract["pricing"]
        pricing_elements = [PricingElement(
            element=pe["element"],
            price_source_type=PriceSourceType(pe["price_source_type"]),
            base_price=Decimal(str(pe["base_price"])),
            unit=pe["unit"],
            formula_type=FormulaType(pe["formula_type"]),
        ) for pe in p["pricing_elements"]]

        contract_pricing = ContractPricing(
            contract_id=raw_contract["contract_id"],
            pricing_elements=pricing_elements,
            impurity_deductions=[],  # 无杂质规则
        )

        records = generate_cash_flows(batch_view, contract_pricing)
        imp_records = [r for r in records if r.flow_type == CashFlowType.IMPURITY_DEDUCTION]
        assert len(imp_records) == 0
