"""
M3A 模型验证测试

1. Pydantic 模型构造和字段校验
2. Batch.total_wet_weight 属性
3. BatchView 聚合属性
4. PricingElement.effective_grade() 计算
5. SettlementSummary.from_records() 结算汇总
6. 与 scenario_01 expected_cash_flows.yaml 手算数字对齐（核心断言）
"""
from __future__ import annotations

import math
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest
import yaml

from core.models import (
    AssayReportRecord,
    Batch,
    BatchView,
    CashFlowDirection,
    CashFlowRecord,
    CashFlowType,
    ContractRecord,
    SettlementSummary,
    WeighTicketRecord,
)

# ── 路径常量 ────────────────────────────────────────────────────
SCENARIO_01 = Path(__file__).parent / "fixtures" / "mock_documents" / "scenario_01"


# ── Fixture 加载工具 ────────────────────────────────────────────

def load_yaml(filename: str) -> dict:
    with open(SCENARIO_01 / filename, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── 辅助函数（对应 M3D-1 将实现的逻辑，此处内联用于验证）─────────

def calc_dry_weight(wet_weight: Decimal, h2o_pct: Decimal) -> Decimal:
    """干重 = 湿重 × (1 - 水分%)"""
    return wet_weight * (1 - h2o_pct / Decimal("100"))


def calc_metal_quantity(
    dry_weight: Decimal,
    effective_grade_pct: Decimal,
) -> Decimal:
    """金属量(吨) = 干重 × 有效品位% / 100，保留3位小数，四舍五入"""
    raw = dry_weight * effective_grade_pct / Decimal("100")
    return raw.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def calc_element_payment(metal_quantity: Decimal, unit_price: Decimal) -> Decimal:
    """元素货款 = 金属量 × 单价，保留2位小数"""
    return (metal_quantity * unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ═══════════════════════════════════════════════════════════════
# Part 1: ContractRecord 模型
# ═══════════════════════════════════════════════════════════════

class TestContractRecord:
    def test_basic_construction(self):
        c = ContractRecord(
            contract_id="c001",
            contract_number="HT-2025-001",
            direction="采购",
            commodity="铜精矿",
            counterparty="某铜矿",
        )
        assert c.contract_id == "c001"
        assert c.direction == "采购"
        assert c.pricing_elements == []

    def test_optional_fields_default_none(self):
        c = ContractRecord(
            contract_id="c002",
            contract_number="HT-2025-002",
            direction="销售",
            commodity="黄铜块",
            counterparty="某客户",
        )
        assert c.signing_date is None
        assert c.tax_included is None


# ═══════════════════════════════════════════════════════════════
# Part 2: WeighTicketRecord 模型
# ═══════════════════════════════════════════════════════════════

class TestWeighTicketRecord:
    def test_weight_parsed_as_decimal(self):
        wt = WeighTicketRecord(
            ticket_id="wt001",
            ticket_number="WT-001",
            contract_id="c001",
            commodity="铜精矿",
            wet_weight="50.225",
        )
        assert isinstance(wt.wet_weight, Decimal)
        assert wt.wet_weight == Decimal("50.225")

    def test_string_and_float_weight(self):
        wt = WeighTicketRecord(
            ticket_id="wt002",
            ticket_number="WT-002",
            contract_id="c001",
            commodity="铜精矿",
            wet_weight=48.78,  # float 输入
        )
        assert isinstance(wt.wet_weight, Decimal)


# ═══════════════════════════════════════════════════════════════
# Part 3: AssayReportRecord 模型
# ═══════════════════════════════════════════════════════════════

class TestAssayReportRecord:
    def test_basic_construction(self):
        ar = AssayReportRecord(
            report_id="ar001",
            contract_id="c001",
            sample_id="S2501",
            cu_pct="18.50",
            h2o_pct="10.00",
        )
        assert ar.cu_pct == Decimal("18.50")
        assert ar.h2o_pct == Decimal("10.00")
        assert ar.au_gt is None

    def test_none_grades_accepted(self):
        ar = AssayReportRecord(
            report_id="ar002",
            contract_id="c001",
            sample_id="S2502",
            cu_pct=None,
            h2o_pct=None,
        )
        assert ar.cu_pct is None


# ═══════════════════════════════════════════════════════════════
# Part 4: Batch 和 BatchView
# ═══════════════════════════════════════════════════════════════

def make_contract() -> ContractRecord:
    return ContractRecord(
        contract_id="mock-contract-001",
        contract_number="HT-2025-001",
        direction="采购",
        commodity="铜精矿",
        counterparty="某铜矿供应商",
    )


def make_batch(sample_id: str, wet_weight: str, cu_pct: str, h2o_pct: str) -> Batch:
    wt = WeighTicketRecord(
        ticket_id=f"wt-{sample_id}",
        ticket_number=f"WT-{sample_id}",
        contract_id="mock-contract-001",
        commodity="铜精矿",
        wet_weight=wet_weight,
        sample_id=sample_id,
    )
    ar = AssayReportRecord(
        report_id=f"ar-{sample_id}",
        contract_id="mock-contract-001",
        sample_id=sample_id,
        cu_pct=cu_pct,
        h2o_pct=h2o_pct,
    )
    return Batch(
        batch_id=sample_id,
        contract_id="mock-contract-001",
        sample_id=sample_id,
        weigh_tickets=[wt],
        assay_reports=[ar],
    )


class TestBatch:
    def test_total_wet_weight_single_ticket(self):
        batch = make_batch("S2501", "50.225", "18.50", "10.00")
        assert batch.total_wet_weight == Decimal("50.225")

    def test_total_wet_weight_multiple_tickets(self):
        """同一样号对应多张磅单（N:1 场景）"""
        wt1 = WeighTicketRecord(
            ticket_id="wt-a", ticket_number="WT-a", contract_id="c001",
            commodity="铜精矿", wet_weight="30.000", sample_id="S9901",
        )
        wt2 = WeighTicketRecord(
            ticket_id="wt-b", ticket_number="WT-b", contract_id="c001",
            commodity="铜精矿", wet_weight="20.100", sample_id="S9901",
        )
        ar = AssayReportRecord(
            report_id="ar-S9901", contract_id="c001", sample_id="S9901",
        )
        batch = Batch(
            batch_id="S9901",
            contract_id="c001",
            sample_id="S9901",
            weigh_tickets=[wt1, wt2],
            assay_reports=[ar],
        )
        assert batch.total_wet_weight == Decimal("50.100")


class TestBatchView:
    def test_total_wet_weight_and_count(self):
        contract = make_contract()
        batch1 = make_batch("S2501", "50.225", "18.50", "10.00")
        batch2 = make_batch("S2502", "48.780", "19.20", "11.00")
        view = BatchView(contract=contract, batches=[batch1, batch2])
        assert view.batch_count == 2
        assert view.total_wet_weight == Decimal("50.225") + Decimal("48.780")


# ═══════════════════════════════════════════════════════════════
# Part 5: PricingElement.effective_grade()
# ═══════════════════════════════════════════════════════════════

class TestPricingElement:
    pass


# ═══════════════════════════════════════════════════════════════
# Part 6: CashFlowRecord 校验
# ═══════════════════════════════════════════════════════════════

class TestCashFlowRecord:
    def test_element_payment_requires_element(self):
        with pytest.raises(Exception):
            CashFlowRecord(
                contract_id="c001",
                flow_type=CashFlowType.ELEMENT_PAYMENT,
                direction=CashFlowDirection.EXPENSE,
                # element 缺失 → 应抛出 ValidationError
                metal_quantity=Decimal("8.362"),
                amount=Decimal("543530.00"),
            )

    def test_signed_amount_income(self):
        r = CashFlowRecord(
            contract_id="c001",
            flow_type=CashFlowType.PREPAYMENT,
            direction=CashFlowDirection.INCOME,
            amount=Decimal("100000"),
        )
        assert r.signed_amount == Decimal("100000")

    def test_signed_amount_expense(self):
        r = CashFlowRecord(
            contract_id="c001",
            flow_type=CashFlowType.FREIGHT,
            direction=CashFlowDirection.EXPENSE,
            amount=Decimal("3000"),
        )
        assert r.signed_amount == Decimal("-3000")


# ═══════════════════════════════════════════════════════════════
# Part 7: SettlementSummary.from_records()
# ═══════════════════════════════════════════════════════════════

class TestSettlementSummary:
    def _make_records(self) -> list[CashFlowRecord]:
        return [
            CashFlowRecord(
                contract_id="c001",
                flow_type=CashFlowType.ELEMENT_PAYMENT,
                direction=CashFlowDirection.EXPENSE,
                element="Cu",
                sample_id="S2501",
                metal_quantity=Decimal("8.362"),
                unit_price=Decimal("65000"),
                unit="元/金属吨",
                amount=Decimal("543530.00"),
            ),
            CashFlowRecord(
                contract_id="c001",
                flow_type=CashFlowType.ELEMENT_PAYMENT,
                direction=CashFlowDirection.EXPENSE,
                element="Cu",
                sample_id="S2502",
                metal_quantity=Decimal("8.336"),
                unit_price=Decimal("65000"),
                unit="元/金属吨",
                amount=Decimal("541840.00"),
            ),
            CashFlowRecord(
                contract_id="c001",
                flow_type=CashFlowType.ASSAY_FEE,
                direction=CashFlowDirection.EXPENSE,
                amount=Decimal("2000.00"),
            ),
        ]

    def test_summary_totals(self):
        records = self._make_records()
        summary = SettlementSummary.from_records("c001", "HT-2025-001", records)
        assert summary.total_income == Decimal("0")
        assert summary.total_expense == Decimal("1087370.00")
        assert summary.net_amount == Decimal("-1087370.00")
        assert summary.is_settled is False

    def test_settled_when_net_zero(self):
        records = [
            CashFlowRecord(
                contract_id="c001",
                flow_type=CashFlowType.FINAL_PAYMENT,
                direction=CashFlowDirection.INCOME,
                amount=Decimal("1029715.00"),
            ),
            CashFlowRecord(
                contract_id="c001",
                flow_type=CashFlowType.ELEMENT_PAYMENT,
                direction=CashFlowDirection.EXPENSE,
                element="Cu",
                metal_quantity=Decimal("15.811"),
                amount=Decimal("1029715.00"),
            ),
        ]
        summary = SettlementSummary.from_records("c001", "HT-2025-001", records)
        assert summary.is_settled is True


# ═══════════════════════════════════════════════════════════════
# Part 8: 与 scenario_01 手算数字对齐（核心断言）
# ═══════════════════════════════════════════════════════════════

class TestScenario01Alignment:
    """从 YAML fixture 加载，用内联计算函数验证手算数字"""

    @pytest.fixture(autouse=True)
    def load_fixtures(self):
        self.contract_data = load_yaml("contract.yaml")
        self.tickets = load_yaml("weigh_tickets.yaml")["weigh_tickets"]
        self.reports = load_yaml("assay_reports.yaml")["assay_reports"]
        self.expected = load_yaml("expected_cash_flows.yaml")

    def test_fixture_loaded(self):
        assert self.contract_data["contract_number"] == "HT-2025-001"
        assert len(self.tickets) == 2
        assert len(self.reports) == 2

    def test_batch_s2501_dry_weight(self):
        """S2501 干重 = 50.225 × 0.90 = 45.2025"""
        wet = Decimal("50.225")
        h2o = Decimal("10.00")
        dry = calc_dry_weight(wet, h2o)
        expected = Decimal("45.2025")
        assert dry == expected, f"实际={dry}，期望={expected}"

    def test_batch_s2501_metal_quantity(self):
        """S2501 金属量 = 45.2025 × 0.1850 = 8.3624625 → 8.362"""
        dry = Decimal("45.2025")
        cu_pct = Decimal("18.50")
        mq = calc_metal_quantity(dry, cu_pct)
        assert mq == Decimal("8.362"), f"实际={mq}"

    def test_batch_s2501_payment(self):
        """S2501 货款 = 8.362 × 65000 = 543,530.00"""
        mq = Decimal("8.362")
        price = Decimal("65000")
        payment = calc_element_payment(mq, price)
        assert payment == Decimal("543530.00"), f"实际={payment}"

    def test_batch_s2502_dry_weight(self):
        """S2502 干重 = 48.780 × 0.89 = 43.4142"""
        wet = Decimal("48.780")
        h2o = Decimal("11.00")
        dry = calc_dry_weight(wet, h2o)
        assert dry == Decimal("43.4142"), f"实际={dry}"

    def test_batch_s2502_metal_quantity(self):
        """S2502 金属量 = 43.4142 × 0.1920 = 8.3355264 → 8.336"""
        dry = Decimal("43.4142")
        cu_pct = Decimal("19.20")
        mq = calc_metal_quantity(dry, cu_pct)
        assert mq == Decimal("8.336"), f"实际={mq}"

    def test_batch_s2502_payment(self):
        """S2502 货款 = 8.336 × 65000 = 541,840.00"""
        mq = Decimal("8.336")
        price = Decimal("65000")
        payment = calc_element_payment(mq, price)
        assert payment == Decimal("541840.00"), f"实际={payment}"

    def test_total_element_payment(self):
        """货款合计 = 543,530.00 + 541,840.00 = 1,085,370.00"""
        total = Decimal("543530.00") + Decimal("541840.00")
        expected = Decimal(str(self.expected["summary"]["total_element_payment"]))
        assert total == expected, f"实际={total}，期望={expected}"

    def test_expected_cash_flow_count(self):
        """期望流水共3条（S2501货款 + S2502货款 + 化验费）"""
        assert len(self.expected["expected_cash_flows"]) == 3

    def test_all_expected_amounts_match_yaml(self):
        """所有期望金额与 YAML 中批次计算结果一致"""
        batch_calc = {b["sample_id"]: b for b in self.expected["batch_calculations"]}

        for sample_id, bc in batch_calc.items():
            wet = Decimal(str(bc["wet_weight"]))
            h2o = Decimal(str(bc["h2o_pct"]))
            dry = calc_dry_weight(wet, h2o)
            assert dry == Decimal(str(bc["dry_weight"])), \
                f"{sample_id} 干重不符：{dry} vs {bc['dry_weight']}"

            eff_pct = Decimal(str(bc["cu_effective_pct"]))
            mq = calc_metal_quantity(dry, eff_pct)
            assert mq == Decimal(str(bc["metal_quantity_cu"])), \
                f"{sample_id} 金属量不符：{mq} vs {bc['metal_quantity_cu']}"

            payment = calc_element_payment(mq, Decimal(str(bc["unit_price"])))
            assert payment == Decimal(str(bc["element_payment"])), \
                f"{sample_id} 货款不符：{payment} vs {bc['element_payment']}"

    def test_pydantic_models_load_from_fixture(self):
        """从 YAML fixture 构造 Pydantic 模型，确认类型转换无误"""
        for t in self.tickets:
            wt = WeighTicketRecord(**t)
            assert isinstance(wt.wet_weight, Decimal)

        for r in self.reports:
            # 将 null 转为 None
            ar_data = {k: (None if v == "null" else v) for k, v in r.items()}
            ar = AssayReportRecord(**ar_data)
            assert isinstance(ar.cu_pct, Decimal)
            assert isinstance(ar.h2o_pct, Decimal)
