"""
M3C 数据串联引擎测试

覆盖：
1. 正常 1:1 匹配（scenario_01 标准场景）
2. N:1 匹配（多张磅单共用同一样号）
3. 无样号磅单 → 进入 unmatched
4. 找不到化验单的磅单 → 进入 unmatched
5. settlement_only 过滤
6. 化验单重复样号处理（保留 is_settlement=True 的）
7. build_batch_view() 端到端验证（含 scenario_01 数字对齐）
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from core.linking import build_batch_view, match_by_sample_id
from core.models import (
    AssayReportRecord,
    BatchView,
    ContractRecord,
    WeighTicketRecord,
)

SCENARIO_01 = Path(__file__).parent / "fixtures" / "mock_documents" / "scenario_01"


# ── Fixture 加载 ─────────────────────────────────────────────

def load_yaml(filename: str) -> dict:
    with open(SCENARIO_01 / filename, encoding="utf-8") as f:
        return yaml.safe_load(f)


def make_contract(**kw) -> ContractRecord:
    defaults = dict(
        contract_id="c001",
        contract_number="HT-2025-001",
        direction="采购",
        commodity="铜精矿",
        counterparty="某铜矿",
    )
    defaults.update(kw)
    return ContractRecord(**defaults)


def make_ticket(
    ticket_id: str,
    sample_id: str | None,
    wet_weight: str = "50.000",
    is_settlement: bool = True,
) -> WeighTicketRecord:
    return WeighTicketRecord(
        ticket_id=ticket_id,
        ticket_number=f"WT-{ticket_id}",
        contract_id="c001",
        commodity="铜精矿",
        wet_weight=wet_weight,
        sample_id=sample_id,
        is_settlement=is_settlement,
    )


def make_report(
    report_id: str,
    sample_id: str,
    cu_pct: str = "18.00",
    h2o_pct: str = "10.00",
    is_settlement: bool = True,
) -> AssayReportRecord:
    return AssayReportRecord(
        report_id=report_id,
        contract_id="c001",
        sample_id=sample_id,
        cu_pct=cu_pct,
        h2o_pct=h2o_pct,
        is_settlement=is_settlement,
    )


# ═══════════════════════════════════════════════════════════════
# Part 1: match_by_sample_id — 正常 1:1 匹配
# ═══════════════════════════════════════════════════════════════

class TestMatchByIdBasic:
    def test_one_to_one_match(self):
        tickets = [
            make_ticket("t1", "S001", "50.000"),
            make_ticket("t2", "S002", "48.000"),
        ]
        reports = [
            make_report("r1", "S001"),
            make_report("r2", "S002"),
        ]
        matched, unmatched = match_by_sample_id(tickets, reports)
        assert len(matched) == 2
        assert len(unmatched) == 0
        sample_ids = {u.sample_id for u in matched}
        assert sample_ids == {"S001", "S002"}

    def test_matched_batch_unit_fields(self):
        tickets = [make_ticket("t1", "S001", "50.225")]
        reports = [make_report("r1", "S001", cu_pct="18.50", h2o_pct="10.00")]
        matched, _ = match_by_sample_id(tickets, reports)
        unit = matched[0]
        assert unit.sample_id == "S001"
        assert len(unit.weigh_tickets) == 1
        assert unit.weigh_tickets[0].wet_weight == Decimal("50.225")
        assert unit.assay_report.cu_pct == Decimal("18.50")
        assert unit.total_wet_weight == Decimal("50.225")

    def test_result_sorted_by_sample_id(self):
        """匹配结果按样号升序排列，保证稳定性"""
        tickets = [make_ticket("t2", "S002"), make_ticket("t1", "S001")]
        reports = [make_report("r2", "S002"), make_report("r1", "S001")]
        matched, _ = match_by_sample_id(tickets, reports)
        assert [u.sample_id for u in matched] == ["S001", "S002"]


# ═══════════════════════════════════════════════════════════════
# Part 2: N:1 匹配（多磅单共用同一样号）
# ═══════════════════════════════════════════════════════════════

class TestNToOneMatch:
    def test_two_tickets_one_assay(self):
        tickets = [
            make_ticket("t1", "S001", "30.000"),
            make_ticket("t2", "S001", "20.100"),
        ]
        reports = [make_report("r1", "S001")]
        matched, unmatched = match_by_sample_id(tickets, reports)
        assert len(matched) == 1
        assert len(unmatched) == 0
        unit = matched[0]
        assert unit.sample_id == "S001"
        assert len(unit.weigh_tickets) == 2
        assert unit.total_wet_weight == Decimal("50.100")

    def test_three_tickets_one_assay(self):
        tickets = [
            make_ticket("t1", "S001", "20.000"),
            make_ticket("t2", "S001", "18.500"),
            make_ticket("t3", "S001", "15.300"),
        ]
        reports = [make_report("r1", "S001")]
        matched, _ = match_by_sample_id(tickets, reports)
        assert matched[0].total_wet_weight == Decimal("53.800")


# ═══════════════════════════════════════════════════════════════
# Part 3: 无样号磅单 → unmatched
# ═══════════════════════════════════════════════════════════════

class TestNoSampleId:
    def test_ticket_without_sample_id_goes_unmatched(self):
        tickets = [
            make_ticket("t1", None, "50.000"),
            make_ticket("t2", "S002", "48.000"),
        ]
        reports = [make_report("r2", "S002")]
        matched, unmatched = match_by_sample_id(tickets, reports)
        assert len(matched) == 1
        assert len(unmatched) == 1
        assert unmatched[0].ticket_id == "t1"

    def test_ticket_with_empty_string_sample_id(self):
        tickets = [make_ticket("t1", "", "50.000")]
        reports = []
        matched, unmatched = match_by_sample_id(tickets, reports)
        assert len(matched) == 0
        assert len(unmatched) == 1


# ═══════════════════════════════════════════════════════════════
# Part 4: 找不到化验单 → unmatched
# ═══════════════════════════════════════════════════════════════

class TestMissingAssay:
    def test_ticket_with_no_matching_assay_goes_unmatched(self):
        tickets = [
            make_ticket("t1", "S001"),
            make_ticket("t2", "S999"),  # 无对应化验单
        ]
        reports = [make_report("r1", "S001")]
        matched, unmatched = match_by_sample_id(tickets, reports)
        assert len(matched) == 1
        assert len(unmatched) == 1
        assert unmatched[0].ticket_id == "t2"

    def test_all_unmatched_when_no_reports(self):
        tickets = [make_ticket("t1", "S001"), make_ticket("t2", "S002")]
        matched, unmatched = match_by_sample_id(tickets, [])
        assert len(matched) == 0
        assert len(unmatched) == 2

    def test_empty_input(self):
        matched, unmatched = match_by_sample_id([], [])
        assert matched == []
        assert unmatched == []


# ═══════════════════════════════════════════════════════════════
# Part 5: settlement_only 过滤
# ═══════════════════════════════════════════════════════════════

class TestSettlementOnlyFilter:
    def test_non_settlement_tickets_excluded(self):
        tickets = [
            make_ticket("t1", "S001", is_settlement=True),
            make_ticket("t2", "S002", is_settlement=False),  # 非结算，排除
        ]
        reports = [
            make_report("r1", "S001"),
            make_report("r2", "S002"),
        ]
        matched, unmatched = match_by_sample_id(tickets, reports, settlement_only=True)
        assert len(matched) == 1
        assert matched[0].sample_id == "S001"

    def test_non_settlement_assay_excluded(self):
        tickets = [
            make_ticket("t1", "S001"),
            make_ticket("t2", "S002"),
        ]
        reports = [
            make_report("r1", "S001", is_settlement=True),
            make_report("r2", "S002", is_settlement=False),  # 非结算化验单，排除
        ]
        matched, unmatched = match_by_sample_id(tickets, reports, settlement_only=True)
        assert len(matched) == 1
        assert len(unmatched) == 1  # t2 找不到结算化验单 → unmatched

    def test_settlement_only_false_includes_all(self):
        tickets = [
            make_ticket("t1", "S001", is_settlement=False),
        ]
        reports = [
            make_report("r1", "S001", is_settlement=False),
        ]
        matched, unmatched = match_by_sample_id(tickets, reports, settlement_only=False)
        assert len(matched) == 1
        assert len(unmatched) == 0


# ═══════════════════════════════════════════════════════════════
# Part 6: 化验单重复样号处理
# ═══════════════════════════════════════════════════════════════

class TestDuplicateAssay:
    def test_prefers_settlement_assay_over_non_settlement(self):
        tickets = [make_ticket("t1", "S001")]
        reports = [
            make_report("r1", "S001", cu_pct="18.00", is_settlement=False),
            make_report("r2", "S001", cu_pct="19.00", is_settlement=True),
        ]
        matched, _ = match_by_sample_id(tickets, reports)
        # 应使用 r2（is_settlement=True）
        assert matched[0].assay_report.cu_pct == Decimal("19.00")


# ═══════════════════════════════════════════════════════════════
# Part 7: build_batch_view() 端到端（scenario_01）
# ═══════════════════════════════════════════════════════════════

class TestBuildBatchViewScenario01:
    @pytest.fixture(autouse=True)
    def load_scenario(self):
        raw_contract = load_yaml("contract.yaml")
        raw_tickets = load_yaml("weigh_tickets.yaml")["weigh_tickets"]
        raw_reports = load_yaml("assay_reports.yaml")["assay_reports"]
        self.expected = load_yaml("expected_cash_flows.yaml")

        self.contract = ContractRecord(
            contract_id=raw_contract["contract_id"],
            contract_number=raw_contract["contract_number"],
            direction=raw_contract["direction"],
            commodity=raw_contract["commodity"],
            counterparty=raw_contract["counterparty"],
        )
        self.tickets = [WeighTicketRecord(**t) for t in raw_tickets]
        self.reports = [AssayReportRecord(**r) for r in raw_reports]

    def test_batch_view_has_two_units(self):
        view, unmatched = build_batch_view(self.contract, self.tickets, self.reports)
        assert isinstance(view, BatchView)
        assert view.batch_count == 2
        assert len(unmatched) == 0

    def test_contract_preserved_in_view(self):
        view, _ = build_batch_view(self.contract, self.tickets, self.reports)
        assert view.contract.contract_number == "HT-2025-001"

    def test_total_wet_weight(self):
        """总湿重 = 50.225 + 48.780 = 99.005 t"""
        view, _ = build_batch_view(self.contract, self.tickets, self.reports)
        assert view.total_wet_weight == Decimal("50.225") + Decimal("48.780")

    def test_s2501_unit(self):
        view, _ = build_batch_view(self.contract, self.tickets, self.reports)
        units = {u.sample_id: u for u in view.batch_units}
        u = units["S2501"]
        assert u.total_wet_weight == Decimal("50.225")
        assert u.assay_report.cu_pct == Decimal("18.50")
        assert u.assay_report.h2o_pct == Decimal("10.00")

    def test_s2502_unit(self):
        view, _ = build_batch_view(self.contract, self.tickets, self.reports)
        units = {u.sample_id: u for u in view.batch_units}
        u = units["S2502"]
        assert u.total_wet_weight == Decimal("48.780")
        assert u.assay_report.cu_pct == Decimal("19.20")
        assert u.assay_report.h2o_pct == Decimal("11.00")

    def test_each_unit_has_exactly_one_ticket(self):
        view, _ = build_batch_view(self.contract, self.tickets, self.reports)
        for unit in view.batch_units:
            assert len(unit.weigh_tickets) == 1, f"{unit.sample_id} 应该只有 1 张磅单"

    def test_batch_units_sorted_by_sample_id(self):
        view, _ = build_batch_view(self.contract, self.tickets, self.reports)
        ids = [u.sample_id for u in view.batch_units]
        assert ids == sorted(ids)

    def test_expected_yaml_amounts_consistent_with_view(self):
        """验证 YAML 手算数字与 BatchView 中的重量字段一致"""
        view, _ = build_batch_view(self.contract, self.tickets, self.reports)
        units = {u.sample_id: u for u in view.batch_units}
        for bc in self.expected["batch_calculations"]:
            sample_id = bc["sample_id"]
            assert sample_id in units, f"缺少批次 {sample_id}"
            unit = units[sample_id]
            assert unit.total_wet_weight == Decimal(str(bc["wet_weight"])), \
                f"{sample_id} 湿重不符"
            assert unit.assay_report.h2o_pct == Decimal(str(bc["h2o_pct"])), \
                f"{sample_id} 水分不符"
            assert unit.assay_report.cu_pct == Decimal(str(bc["cu_assay_pct"])), \
                f"{sample_id} Cu% 不符"
