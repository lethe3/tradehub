"""
M3D-3 结算单卡片渲染测试

覆盖：
1. 返回值可被 json.loads 解析
2. header 包含合同号
3. 元素货款 section 存在
4. 关键金额出现在卡片内容中
5. 杂质扣款 section（scenario_02）
6. 无杂质扣款时不渲染相关 section
7. 空 records 不崩溃
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from core.linking import build_batch_view
from core.models.batch import (
    AssayReportRecord,
    ContractRecord,
    WeighTicketRecord,
)
from core.models.cash_flow import SettlementSummary
from core.models.pricing import (
    ContractPricing,
    FormulaType,
    ImpurityDeduction,
    ImpurityDeductionTier,
    PricingElement,
    PriceSourceType,
)
from core.settlement import generate_cash_flows
from feishu.settlement_card import build_settlement_card

SCENARIO_01 = Path(__file__).parent / "fixtures" / "mock_documents" / "scenario_01"
SCENARIO_02 = Path(__file__).parent / "fixtures" / "mock_documents" / "scenario_02"


# ── Fixture 加载工具 ──────────────────────────────────────────

def _load_yaml(path: Path, filename: str) -> dict:
    with open(path / filename, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_scenario_01() -> SettlementSummary:
    raw_contract = _load_yaml(SCENARIO_01, "contract.yaml")
    raw_tickets = _load_yaml(SCENARIO_01, "weigh_tickets.yaml")["weigh_tickets"]
    raw_reports = _load_yaml(SCENARIO_01, "assay_reports.yaml")["assay_reports"]

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

    p = raw_contract["pricing"]
    pricing_elements = [
        PricingElement(
            element=pe["element"],
            price_source_type=PriceSourceType(pe["price_source_type"]),
            base_price=Decimal(str(pe["base_price"])),
            unit=pe["unit"],
            formula_type=FormulaType(pe["formula_type"]),
            grade_deduction=Decimal(str(pe["grade_deduction"])),
        )
        for pe in p["pricing_elements"]
    ]

    contract_pricing = ContractPricing(
        contract_id=raw_contract["contract_id"],
        dry_weight_formula=p.get("dry_weight_formula", "wet * (1 - h2o)"),
        pricing_elements=pricing_elements,
        assay_fee_total=Decimal(str(p["assay_fee_total"])) if p.get("assay_fee_total") is not None else None,
    )

    records = generate_cash_flows(batch_view, contract_pricing)
    return SettlementSummary.from_records(
        contract_id=contract.contract_id,
        contract_number=contract.contract_number,
        records=records,
    )


def load_scenario_02() -> SettlementSummary:
    raw_contract = _load_yaml(SCENARIO_02, "contract.yaml")
    raw_tickets = _load_yaml(SCENARIO_02, "weigh_tickets.yaml")["weigh_tickets"]
    raw_reports = _load_yaml(SCENARIO_02, "assay_reports.yaml")["assay_reports"]

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

    p = raw_contract["pricing"]

    pricing_elements = [
        PricingElement(
            element=pe["element"],
            price_source_type=PriceSourceType(pe["price_source_type"]),
            base_price=Decimal(str(pe["base_price"])),
            unit=pe["unit"],
            formula_type=FormulaType(pe["formula_type"]),
            grade_deduction=Decimal(str(pe["grade_deduction"])),
        )
        for pe in p["pricing_elements"]
    ]

    impurity_deductions = []
    for imp in p.get("impurity_deductions", []):
        tiers = [
            ImpurityDeductionTier(
                lower=Decimal(str(t["lower"])),
                upper=Decimal(str(t["upper"])) if t.get("upper") is not None else None,
                rate=Decimal(str(t["rate"])),
                upper_open=t.get("upper_open", True),
            )
            for t in imp["tiers"]
        ]
        impurity_deductions.append(ImpurityDeduction(element=imp["element"], tiers=tiers))

    contract_pricing = ContractPricing(
        contract_id=raw_contract["contract_id"],
        dry_weight_formula=p.get("dry_weight_formula", "wet * (1 - h2o)"),
        pricing_elements=pricing_elements,
        impurity_deductions=impurity_deductions,
        assay_fee_total=Decimal(str(p["assay_fee_total"])) if p.get("assay_fee_total") is not None else None,
    )

    records = generate_cash_flows(batch_view, contract_pricing)
    return SettlementSummary.from_records(
        contract_id=contract.contract_id,
        contract_number=contract.contract_number,
        records=records,
    )


# ══════════════════════════════════════════════════════════════
# 测试
# ══════════════════════════════════════════════════════════════

class TestSettlementCard:

    def test_card_is_valid_json(self):
        summary = load_scenario_01()
        card_json = build_settlement_card(summary)
        parsed = json.loads(card_json)
        assert isinstance(parsed, dict)

    def test_card_header_scenario01(self):
        summary = load_scenario_01()
        card_json = build_settlement_card(summary)
        parsed = json.loads(card_json)
        header_content = parsed["header"]["title"]["content"]
        assert "HT-2025-001" in header_content

    def test_card_has_element_section_scenario01(self):
        summary = load_scenario_01()
        card_json = build_settlement_card(summary)
        assert "元素货款" in card_json

    def test_card_amounts_scenario01(self):
        summary = load_scenario_01()
        card_json = build_settlement_card(summary)
        assert "514,150.00" in card_json
        assert "513,565.00" in card_json

    def test_card_assay_fee_scenario01(self):
        summary = load_scenario_01()
        card_json = build_settlement_card(summary)
        assert "2,000.00" in card_json

    def test_card_summary_scenario01(self):
        summary = load_scenario_01()
        card_json = build_settlement_card(summary)
        # total_expense = 514,150 + 513,565 + 2,000 = 1,029,715
        assert "1,029,715.00" in card_json

    def test_card_has_impurity_section_scenario02(self):
        summary = load_scenario_02()
        card_json = build_settlement_card(summary)
        assert "杂质扣款" in card_json

    def test_card_impurity_amounts_scenario02(self):
        summary = load_scenario_02()
        card_json = build_settlement_card(summary)
        assert "1,000.00" in card_json
        assert "2,250.00" in card_json

    def test_no_impurity_section_when_none(self):
        summary = load_scenario_01()
        card_json = build_settlement_card(summary)
        assert "杂质扣款" not in card_json

    def test_empty_records_renders_without_crash(self):
        summary = SettlementSummary(
            contract_id="test-empty",
            contract_number="HT-EMPTY",
            total_income=Decimal("0"),
            total_expense=Decimal("0"),
            net_amount=Decimal("0"),
            is_settled=True,
            records=[],
        )
        card_json = build_settlement_card(summary)
        parsed = json.loads(card_json)
        assert isinstance(parsed, dict)
        assert "HT-EMPTY" in card_json
