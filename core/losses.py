"""
Batch 损耗计算。

纯函数，不接存储，不依赖 API。
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from .models.batch import AssayReportRecord, AssayReportType, Batch, GRADE_FIELDS, WeighTicketType


class WeightLossResult(BaseModel):
    shipped_weight: Decimal
    received_weight: Decimal
    transfer_weight: Decimal
    loss_weight: Decimal
    loss_rate: Optional[Decimal] = None


class MetalLossMetric(BaseModel):
    field: str
    baseline_type: AssayReportType
    final_type: AssayReportType
    shipped_wet_weight: Decimal
    received_wet_weight: Decimal
    baseline_h2o_pct: Decimal
    final_h2o_pct: Decimal
    baseline_grade: Decimal
    final_grade: Decimal
    shipped_dry_weight: Decimal
    received_dry_weight: Decimal
    shipped_metal_quantity: Decimal
    received_metal_quantity: Decimal
    loss_quantity: Decimal
    loss_rate: Optional[Decimal] = None


class MetalLossResult(BaseModel):
    metrics: dict[str, MetalLossMetric] = Field(default_factory=dict)


def calc_weight_loss(batch: Batch) -> WeightLossResult:
    shipped = _sum_weight(batch, WeighTicketType.SHIPMENT)
    received = _sum_weight(batch, WeighTicketType.RECEIPT)
    transfer = _sum_weight(batch, WeighTicketType.TRANSFER)
    loss_weight = shipped - received
    loss_rate = None if shipped == 0 else loss_weight / shipped
    return WeightLossResult(
        shipped_weight=shipped,
        received_weight=received,
        transfer_weight=transfer,
        loss_weight=loss_weight,
        loss_rate=loss_rate,
    )


def calc_metal_loss(batch: Batch) -> MetalLossResult:
    baseline = _pick_assay(batch, AssayReportType.SURVEY)
    final = _pick_assay(batch, AssayReportType.SETTLEMENT)
    shipped_weight = _sum_weight(batch, WeighTicketType.SHIPMENT)
    received_weight = _sum_weight(batch, WeighTicketType.RECEIPT)
    metrics: dict[str, MetalLossMetric] = {}

    if baseline is None or final is None:
        return MetalLossResult(metrics=metrics)
    if baseline.h2o_pct is None or final.h2o_pct is None:
        return MetalLossResult(metrics=metrics)

    shipped_dry_weight = shipped_weight * (Decimal("1") - baseline.h2o_pct / Decimal("100"))
    received_dry_weight = received_weight * (Decimal("1") - final.h2o_pct / Decimal("100"))

    for field in GRADE_FIELDS:
        if field == "h2o_pct":
            continue

        baseline_grade = getattr(baseline, field, None)
        final_grade = getattr(final, field, None)
        if baseline_grade is None or final_grade is None:
            continue

        shipped_metal = _calc_metal_quantity(shipped_dry_weight, baseline_grade, field)
        received_metal = _calc_metal_quantity(received_dry_weight, final_grade, field)
        loss_quantity = shipped_metal - received_metal
        loss_rate = None if shipped_metal == 0 else loss_quantity / shipped_metal

        metrics[field] = MetalLossMetric(
            field=field,
            baseline_type=baseline.type,
            final_type=final.type,
            shipped_wet_weight=shipped_weight,
            received_wet_weight=received_weight,
            baseline_h2o_pct=baseline.h2o_pct,
            final_h2o_pct=final.h2o_pct,
            baseline_grade=baseline_grade,
            final_grade=final_grade,
            shipped_dry_weight=shipped_dry_weight,
            received_dry_weight=received_dry_weight,
            shipped_metal_quantity=shipped_metal,
            received_metal_quantity=received_metal,
            loss_quantity=loss_quantity,
            loss_rate=loss_rate,
        )

    return MetalLossResult(metrics=metrics)


def calc_grade_loss(batch: Batch) -> MetalLossResult:
    """
    兼容旧接口名。

    语义已更新为“金属量损耗”：
    发货金属量 - 收货结算金属量
    """
    return calc_metal_loss(batch)


def _sum_weight(batch: Batch, ticket_type: WeighTicketType) -> Decimal:
    return sum(
        (ticket.wet_weight for ticket in batch.weigh_tickets if ticket.type == ticket_type),
        Decimal("0"),
    )


def _calc_metal_quantity(dry_weight: Decimal, grade: Decimal, field: str) -> Decimal:
    if field.endswith("_pct"):
        return dry_weight * grade / Decimal("100")
    return dry_weight * grade


def _pick_assay(batch: Batch, report_type: AssayReportType) -> AssayReportRecord | None:
    candidates = [report for report in batch.assay_reports if report.type == report_type]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda report: (report.assay_date is None, report.assay_date, report.report_id),
    )[-1]
