"""
M3D-1 结算计算测试（固定计价 + 品位扣减）

覆盖：
1. 单函数单元测试：calc_dry_weight / calc_metal_quantity / calc_element_payment
2. scenario_01 端到端断言：干重 / 金属量 / 货款 / 化验费
3. 汇总断言：total_expense
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
from core.models.pricing import ContractPricing, FormulaType, PricingElement, PriceSourceType
from core.settlement import (
    calc_dry_weight,
    calc_element_payment,
    calc_metal_quantity,
    generate_cash_flows,
)

SCENARIO_01 = Path(__file__).parent / "fixtures" / "mock_documents" / "scenario_01"


# ── Fixture 加载 ─────────────────────────────────────────────

def load_yaml(filename: str) -> dict:
    with open(SCENARIO_01 / filename, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_scenario_01():
    """返回 (BatchView, ContractPricing, expected_data)"""
    raw_contract = load_yaml("contract.yaml")
    raw_tickets = load_yaml("weigh_tickets.yaml")["weigh_tickets"]
    raw_reports = load_yaml("assay_reports.yaml")["assay_reports"]
    expected = load_yaml("expected_cash_flows.yaml")

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

    contract_pricing = ContractPricing(
        contract_id=raw_contract["contract_id"],
        dry_weight_formula=p.get("dry_weight_formula", "wet * (1 - h2o)"),
        pricing_elements=pricing_elements,
        assay_fee_total=Decimal(str(p["assay_fee_total"])) if p.get("assay_fee_total") is not None else None,
    )

    return batch_view, contract_pricing, expected


# ══════════════════════════════════════════════════════════════
# 单元测试：核心计算函数
# ══════════════════════════════════════════════════════════════

class TestCalcDryWeight:
    def test_scenario_01_s2501(self):
        # 50.225 × (1 - 0.10) = 45.2025
        result = calc_dry_weight(Decimal("50.225"), Decimal("10.00"))
        assert result == Decimal("45.2025")

    def test_scenario_01_s2502(self):
        # 48.780 × (1 - 0.11) = 43.4142
        result = calc_dry_weight(Decimal("48.780"), Decimal("11.00"))
        assert result == Decimal("43.4142")

    def test_zero_moisture(self):
        result = calc_dry_weight(Decimal("100.000"), Decimal("0.00"))
        assert result == Decimal("100.0000")

    def test_rounding_4dp(self):
        # 10.000 × (1 - 0.333) = 6.67000 → 6.6700
        result = calc_dry_weight(Decimal("10.000"), Decimal("33.3"))
        assert result == Decimal("6.6700")


class TestCalcMetalQuantity:
    def test_scenario_01_s2501(self):
        # 45.2025 × 0.1850 = 8.3624625 → 8.362（无扣减）
        result = calc_metal_quantity(
            Decimal("45.2025"), Decimal("18.50")
        )
        assert result == Decimal("8.362")

    def test_scenario_01_s2502(self):
        # 43.4142 × 0.1920 = 8.3355264 → 8.336（无扣减）
        result = calc_metal_quantity(
            Decimal("43.4142"), Decimal("19.20")
        )
        assert result == Decimal("8.336")

    def test_rounding_3dp(self):
        # 10.000 × 0.1955 = 1.9550 → 1.955（无扣减）
        result = calc_metal_quantity(
            Decimal("10.000"), Decimal("19.55")
        )
        assert result == Decimal("1.955")


class TestCalcElementPayment:
    def test_scenario_01_s2501(self):
        # 8.362 × 65000 = 543530.00（无扣减）
        result = calc_element_payment(Decimal("8.362"), Decimal("65000"))
        assert result == Decimal("543530.00")

    def test_scenario_01_s2502(self):
        # 8.336 × 65000 = 541840.00（无扣减）
        result = calc_element_payment(Decimal("8.336"), Decimal("65000"))
        assert result == Decimal("541840.00")

    def test_rounding_2dp(self):
        # 1.001 × 3 = 3.003 → 3.00
        result = calc_element_payment(Decimal("1.001"), Decimal("3"))
        assert result == Decimal("3.00")


# ══════════════════════════════════════════════════════════════
# 端到端测试：scenario_01
# ══════════════════════════════════════════════════════════════

class TestGenerateCashFlowsScenario01:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.batch_view, self.contract_pricing, self.expected = load_scenario_01()
        self.records = generate_cash_flows(self.batch_view, self.contract_pricing)

    def test_record_count(self):
        # 2 元素货款 + 1 化验费 = 3 条
        assert len(self.records) == 3

    def test_element_payment_s2501(self):
        r = next(x for x in self.records if x.flow_type == CashFlowType.ELEMENT_PAYMENT and x.sample_id == "S2501")
        assert r.direction == CashFlowDirection.EXPENSE
        assert r.element == "Cu"
        assert r.dry_weight == Decimal("45.2025")
        assert r.metal_quantity == Decimal("8.362")
        assert r.unit_price == Decimal("65000")
        assert r.amount == Decimal("543530.00")

    def test_element_payment_s2502(self):
        r = next(x for x in self.records if x.flow_type == CashFlowType.ELEMENT_PAYMENT and x.sample_id == "S2502")
        assert r.direction == CashFlowDirection.EXPENSE
        assert r.element == "Cu"
        assert r.dry_weight == Decimal("43.4142")
        assert r.metal_quantity == Decimal("8.336")
        assert r.unit_price == Decimal("65000")
        assert r.amount == Decimal("541840.00")

    def test_assay_fee(self):
        r = next(x for x in self.records if x.flow_type == CashFlowType.ASSAY_FEE)
        assert r.direction == CashFlowDirection.EXPENSE
        assert r.amount == Decimal("2000.00")
        assert r.element is None

    def test_summary_total_expense(self):
        summary = SettlementSummary.from_records(
            contract_id=self.batch_view.contract.contract_id,
            contract_number=self.batch_view.contract.contract_number,
            records=self.records,
        )
        expected_total = Decimal(self.expected["summary"]["total_expense"])
        assert summary.total_expense == expected_total

    def test_summary_total_income(self):
        summary = SettlementSummary.from_records(
            contract_id=self.batch_view.contract.contract_id,
            contract_number=self.batch_view.contract.contract_number,
            records=self.records,
        )
        assert summary.total_income == Decimal("0.00")

    def test_contract_id_propagated(self):
        for r in self.records:
            assert r.contract_id == "mock-contract-001"


# ══════════════════════════════════════════════════════════════
# 边界 / 错误场景
# ══════════════════════════════════════════════════════════════

class TestGenerateCashFlowsEdgeCases:
    def _make_contract(self, direction: str = "采购") -> ContractRecord:
        return ContractRecord(
            contract_id="c-test",
            contract_number="HT-TEST",
            direction=direction,
            commodity="铜精矿",
            counterparty="测试方",
        )

    def _make_pricing(self, assay_fee: float | None = None) -> ContractPricing:
        return ContractPricing(
            contract_id="c-test",
            pricing_elements=[
                PricingElement(
                    element="Cu",
                    price_source_type=PriceSourceType.FIXED,
                    base_price=Decimal("65000"),
                    formula_type=FormulaType.FIXED_PRICE,
                )
            ],
            assay_fee_total=Decimal(str(assay_fee)) if assay_fee is not None else None,
        )

    def _make_batch_view(self, contract: ContractRecord, cu_pct: str = "18.50", h2o_pct: str = "10.00") -> BatchView:
        ticket = WeighTicketRecord(
            ticket_id="t1", ticket_number="WT-01",
            contract_id=contract.contract_id,
            commodity="铜精矿", wet_weight=Decimal("50.000"),
            sample_id="S001", is_settlement=True,
        )
        report = AssayReportRecord(
            report_id="r1", contract_id=contract.contract_id,
            sample_id="S001", cu_pct=Decimal(cu_pct), h2o_pct=Decimal(h2o_pct),
        )
        unit = BatchUnit(sample_id="S001", weigh_tickets=[ticket], assay_report=report)
        return BatchView(contract=contract, batch_units=[unit])

    def test_sales_direction_is_income(self):
        contract = self._make_contract(direction="销售")
        pricing = self._make_pricing()
        bv = self._make_batch_view(contract)
        records = generate_cash_flows(bv, pricing)
        payments = [r for r in records if r.flow_type == CashFlowType.ELEMENT_PAYMENT]
        assert all(r.direction == CashFlowDirection.INCOME for r in payments)

    def test_no_assay_fee_when_none(self):
        contract = self._make_contract()
        pricing = self._make_pricing(assay_fee=None)
        bv = self._make_batch_view(contract)
        records = generate_cash_flows(bv, pricing)
        assert not any(r.flow_type == CashFlowType.ASSAY_FEE for r in records)

    def test_assay_fee_always_expense(self):
        contract = self._make_contract(direction="销售")
        pricing = self._make_pricing(assay_fee=1500.0)
        bv = self._make_batch_view(contract)
        records = generate_cash_flows(bv, pricing)
        fee = next(r for r in records if r.flow_type == CashFlowType.ASSAY_FEE)
        assert fee.direction == CashFlowDirection.EXPENSE
        assert fee.amount == Decimal("1500")

    def test_missing_h2o_raises(self):
        contract = self._make_contract()
        ticket = WeighTicketRecord(
            ticket_id="t1", ticket_number="WT-01",
            contract_id=contract.contract_id,
            commodity="铜精矿", wet_weight=Decimal("50.000"),
            sample_id="S001", is_settlement=True,
        )
        report = AssayReportRecord(
            report_id="r1", contract_id=contract.contract_id,
            sample_id="S001", cu_pct=Decimal("18.50"), h2o_pct=None,
        )
        unit = BatchUnit(sample_id="S001", weigh_tickets=[ticket], assay_report=report)
        bv = BatchView(contract=contract, batch_units=[unit])
        pricing = self._make_pricing()
        with pytest.raises(ValueError, match="h2o_pct"):
            generate_cash_flows(bv, pricing)
