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
from decimal import Decimal

from core.models.cash_flow import (
    CashFlowDirection,
    CashFlowRecord,
    CashFlowType,
    SettlementSummary,
)
from feishu.settlement_card import build_settlement_card


# ── Fixture 构造工具 ──────────────────────────────────────────

def _make_scenario_01_summary() -> SettlementSummary:
    """场景一：2 条货款 + 1 条化验费（采购，无杂质扣款）。

    S2501: 干重 45.2025t，金属量 8.362t，货款 543530.00 元
    S2502: 干重 43.4142t，金属量 8.336t，货款 541840.00 元
    化验费: 2000.00 元（我方承担）
    """
    records = [
        CashFlowRecord(
            contract_id="mock-contract-001",
            flow_type=CashFlowType.ELEMENT_PAYMENT,
            direction=CashFlowDirection.EXPENSE,
            element="Cu",
            sample_id="S2501",
            dry_weight=Decimal("45.2025"),
            metal_quantity=Decimal("8.362"),
            unit_price=Decimal("65000"),
            unit="元/金属吨",
            amount=Decimal("543530.00"),
        ),
        CashFlowRecord(
            contract_id="mock-contract-001",
            flow_type=CashFlowType.ELEMENT_PAYMENT,
            direction=CashFlowDirection.EXPENSE,
            element="Cu",
            sample_id="S2502",
            dry_weight=Decimal("43.4142"),
            metal_quantity=Decimal("8.336"),
            unit_price=Decimal("65000"),
            unit="元/金属吨",
            amount=Decimal("541840.00"),
        ),
        CashFlowRecord(
            contract_id="mock-contract-001",
            flow_type=CashFlowType.ASSAY_FEE,
            direction=CashFlowDirection.EXPENSE,
            element=None,
            amount=Decimal("2000.00"),
        ),
    ]
    return SettlementSummary.from_records(
        contract_id="mock-contract-001",
        contract_number="HT-2025-001",
        records=records,
    )


def _make_scenario_02_summary() -> SettlementSummary:
    """场景二：3 条货款 + 2 条杂质扣款（采购，As 两档阶梯）。"""
    records = [
        CashFlowRecord(
            contract_id="mock-contract-002",
            flow_type=CashFlowType.ELEMENT_PAYMENT,
            direction=CashFlowDirection.EXPENSE,
            element="Cu",
            sample_id="S2601",
            dry_weight=Decimal("45.0000"),
            metal_quantity=Decimal("8.325"),
            unit_price=Decimal("65000"),
            unit="元/金属吨",
            amount=Decimal("541125.00"),
        ),
        CashFlowRecord(
            contract_id="mock-contract-002",
            flow_type=CashFlowType.ELEMENT_PAYMENT,
            direction=CashFlowDirection.EXPENSE,
            element="Cu",
            sample_id="S2602",
            dry_weight=Decimal("40.0500"),
            metal_quantity=Decimal("7.690"),
            unit_price=Decimal("65000"),
            unit="元/金属吨",
            amount=Decimal("499850.00"),
        ),
        CashFlowRecord(
            contract_id="mock-contract-002",
            flow_type=CashFlowType.ELEMENT_PAYMENT,
            direction=CashFlowDirection.EXPENSE,
            element="Cu",
            sample_id="S2603",
            dry_weight=Decimal("27.3000"),
            metal_quantity=Decimal("4.859"),
            unit_price=Decimal("65000"),
            unit="元/金属吨",
            amount=Decimal("315835.00"),
        ),
        CashFlowRecord(
            contract_id="mock-contract-002",
            flow_type=CashFlowType.IMPURITY_DEDUCTION,
            direction=CashFlowDirection.EXPENSE,
            element="As",
            sample_id="S2601",
            amount=Decimal("1000.00"),
        ),
        CashFlowRecord(
            contract_id="mock-contract-002",
            flow_type=CashFlowType.IMPURITY_DEDUCTION,
            direction=CashFlowDirection.EXPENSE,
            element="As",
            sample_id="S2602",
            amount=Decimal("2250.00"),
        ),
    ]
    return SettlementSummary.from_records(
        contract_id="mock-contract-002",
        contract_number="HT-2025-002",
        records=records,
    )


# ══════════════════════════════════════════════════════════════
# 测试
# ══════════════════════════════════════════════════════════════

class TestSettlementCard:

    def test_card_is_valid_json(self):
        summary = _make_scenario_01_summary()
        card_json = build_settlement_card(summary)
        parsed = json.loads(card_json)
        assert isinstance(parsed, dict)

    def test_card_header_scenario01(self):
        summary = _make_scenario_01_summary()
        card_json = build_settlement_card(summary)
        parsed = json.loads(card_json)
        header_content = parsed["header"]["title"]["content"]
        assert "HT-2025-001" in header_content

    def test_card_has_element_section_scenario01(self):
        summary = _make_scenario_01_summary()
        card_json = build_settlement_card(summary)
        assert "元素货款" in card_json

    def test_card_amounts_scenario01(self):
        summary = _make_scenario_01_summary()
        card_json = build_settlement_card(summary)
        assert "543,530.00" in card_json
        assert "541,840.00" in card_json

    def test_card_assay_fee_scenario01(self):
        summary = _make_scenario_01_summary()
        card_json = build_settlement_card(summary)
        assert "2,000.00" in card_json

    def test_card_summary_scenario01(self):
        summary = _make_scenario_01_summary()
        card_json = build_settlement_card(summary)
        # total_expense = 543530 + 541840 + 2000 = 1,087,370
        assert "1,087,370.00" in card_json

    def test_card_has_impurity_section_scenario02(self):
        summary = _make_scenario_02_summary()
        card_json = build_settlement_card(summary)
        assert "杂质扣款" in card_json

    def test_card_impurity_amounts_scenario02(self):
        summary = _make_scenario_02_summary()
        card_json = build_settlement_card(summary)
        assert "1,000.00" in card_json
        assert "2,250.00" in card_json

    def test_no_impurity_section_when_none(self):
        summary = _make_scenario_01_summary()
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
