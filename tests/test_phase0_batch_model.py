from __future__ import annotations

from decimal import Decimal

from core.losses import calc_grade_loss, calc_metal_loss, calc_weight_loss
from core.models import (
    AssayReportRecord,
    Batch,
    BatchView,
    ContractRecord,
    WeighTicketRecord,
)


def test_batch_supports_multiple_typed_tickets_and_reports() -> None:
    batch = Batch(
        batch_id="B001",
        contract_id="c001",
        sample_id="S001",
        weigh_tickets=[
            WeighTicketRecord(
                ticket_id="wt-out",
                ticket_number="WT-OUT",
                contract_id="c001",
                commodity="铜精矿",
                sample_id="S001",
                type="发货",
                wet_weight="100.000",
                is_settlement=False,
            ),
            WeighTicketRecord(
                ticket_id="wt-in",
                ticket_number="WT-IN",
                contract_id="c001",
                commodity="铜精矿",
                sample_id="S001",
                type="收货",
                wet_weight="98.500",
                is_settlement=True,
            ),
        ],
        assay_reports=[
            AssayReportRecord(
                report_id="ar-survey",
                contract_id="c001",
                sample_id="S001",
                type="摸底",
                cu_pct="19.20",
                h2o_pct="9.80",
                is_settlement=False,
            ),
            AssayReportRecord(
                report_id="ar-settle",
                contract_id="c001",
                sample_id="S001",
                type="结算",
                cu_pct="18.70",
                h2o_pct="10.10",
                is_settlement=True,
            ),
        ],
    )

    view = BatchView(
        contract=ContractRecord(
            contract_id="c001",
            contract_number="HT-001",
            direction="采购",
            counterparty="某供应商",
        ),
        batches=[batch],
    )

    assert view.batch_count == 1
    assert batch.total_wet_weight == Decimal("98.500")
    assert batch.assay_report.type.value == "结算"
    assert len(batch.weigh_tickets) == 2
    assert len(batch.assay_reports) == 2


def test_loss_calculation_fixture_matches_manual_numbers() -> None:
    batch = Batch(
        batch_id="B-L1",
        contract_id="c001",
        sample_id="S-L1",
        weigh_tickets=[
            WeighTicketRecord(
                ticket_id="wt-ship",
                ticket_number="WT-SHIP",
                contract_id="c001",
                commodity="铜精矿",
                sample_id="S-L1",
                type="发货",
                wet_weight="100.000",
                is_settlement=False,
            ),
            WeighTicketRecord(
                ticket_id="wt-receive",
                ticket_number="WT-RECV",
                contract_id="c001",
                commodity="铜精矿",
                sample_id="S-L1",
                type="收货",
                wet_weight="98.500",
                is_settlement=True,
            ),
        ],
        assay_reports=[
            AssayReportRecord(
                report_id="ar-survey",
                contract_id="c001",
                sample_id="S-L1",
                type="摸底",
                cu_pct="19.20",
                h2o_pct="9.80",
                is_settlement=False,
            ),
            AssayReportRecord(
                report_id="ar-settlement",
                contract_id="c001",
                sample_id="S-L1",
                type="结算",
                cu_pct="18.70",
                h2o_pct="10.10",
                is_settlement=True,
            ),
        ],
    )

    weight_loss = calc_weight_loss(batch)
    assert weight_loss.shipped_weight == Decimal("100.000")
    assert weight_loss.received_weight == Decimal("98.500")
    assert weight_loss.loss_weight == Decimal("1.500")
    assert weight_loss.loss_rate == Decimal("0.015")

    metal_loss = calc_metal_loss(batch)
    cu_loss = metal_loss.metrics["cu_pct"]
    assert cu_loss.baseline_grade == Decimal("19.20")
    assert cu_loss.final_grade == Decimal("18.70")
    assert cu_loss.shipped_dry_weight == Decimal("90.20000")
    assert cu_loss.received_dry_weight == Decimal("88.55150")
    assert cu_loss.shipped_metal_quantity == Decimal("17.3184000")
    assert cu_loss.received_metal_quantity == Decimal("16.5591305")
    assert cu_loss.loss_quantity == Decimal("0.7592695")
    assert cu_loss.loss_rate == Decimal("0.04384178099593495934959349593")

    legacy_loss = calc_grade_loss(batch)
    assert legacy_loss.metrics["cu_pct"].loss_quantity == Decimal("0.7592695")
