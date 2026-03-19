"""
批次数据模型

Phase 0 起，Batch 成为真实业务上的“一次流转”父节点：
- 同一 Batch 下可以有多张不同类型的磅单
- 同一 Batch 下可以有多张不同类型的化验单
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field, AliasChoices, field_validator, model_validator


class WeighTicketType(StrEnum):
    SHIPMENT = "发货"
    RECEIPT = "收货"
    TRANSFER = "中转"


class AssayReportType(StrEnum):
    ESTIMATE = "预估"
    SURVEY = "摸底"
    SETTLEMENT = "结算"
    NEGOTIATION = "协商"
    ARBITRATION = "仲裁"


GRADE_FIELDS = (
    "cu_pct",
    "au_gt",
    "ag_gt",
    "pb_pct",
    "zn_pct",
    "s_pct",
    "as_pct",
    "h2o_pct",
)


class ContractRecord(BaseModel):
    """合同表原始记录"""

    contract_id: str
    contract_number: str
    direction: str
    commodity: Optional[str] = None
    counterparty: str
    signing_date: Optional[date] = None
    tax_included: Optional[bool] = None
    freight_bearer: Optional[str] = None
    assay_fee_bearer: Optional[str] = None
    pricing_elements: list[str] = Field(default_factory=list)
    settlement_ticket_rule: Optional[str] = None
    settlement_assay_rule: Optional[str] = None


class WeighTicketRecord(BaseModel):
    """磅单表原始记录。"""

    ticket_id: str
    ticket_number: str
    contract_id: str
    commodity: str
    wet_weight: Decimal
    type: WeighTicketType = WeighTicketType.RECEIPT
    batch_id: Optional[str] = None
    weighing_date: Optional[date] = None
    sample_id: Optional[str] = None
    vehicle_number: Optional[str] = None
    gross_weight: Optional[Decimal] = None
    tare_weight: Optional[Decimal] = None
    deduction_weight: Optional[Decimal] = None
    is_settlement: bool = True
    price_group: Optional[int] = None

    @field_validator("wet_weight", "gross_weight", "tare_weight", "deduction_weight", mode="before")
    @classmethod
    def parse_weight(cls, v: object) -> Optional[Decimal]:
        if v is None:
            return None
        return Decimal(str(v))

    @model_validator(mode="after")
    def infer_batch_id(self) -> "WeighTicketRecord":
        if not self.batch_id and self.sample_id:
            self.batch_id = self.sample_id.strip() or None
        return self


class AssayReportRecord(BaseModel):
    """化验单表原始记录。"""

    report_id: str
    contract_id: str
    sample_id: str
    type: AssayReportType = Field(
        default=AssayReportType.SETTLEMENT,
        validation_alias=AliasChoices("type", "assay_type"),
    )
    batch_id: Optional[str] = None
    is_settlement: bool = True
    assay_date: Optional[date] = None
    assay_lab: Optional[str] = None
    cu_pct: Optional[Decimal] = None
    au_gt: Optional[Decimal] = None
    ag_gt: Optional[Decimal] = None
    pb_pct: Optional[Decimal] = None
    zn_pct: Optional[Decimal] = None
    s_pct: Optional[Decimal] = None
    as_pct: Optional[Decimal] = None
    h2o_pct: Optional[Decimal] = None

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v: object) -> object:
        mapping = {
            "结算化验": AssayReportType.SETTLEMENT,
            "快速摸底": AssayReportType.SURVEY,
            "摸底化验": AssayReportType.SURVEY,
            "预估化验": AssayReportType.ESTIMATE,
        }
        return mapping.get(v, v)

    @field_validator(*GRADE_FIELDS, mode="before")
    @classmethod
    def parse_grade(cls, v: object) -> Optional[Decimal]:
        if v is None:
            return None
        return Decimal(str(v))

    @model_validator(mode="after")
    def infer_compat_fields(self) -> "AssayReportRecord":
        if not self.batch_id and self.sample_id:
            self.batch_id = self.sample_id.strip() or None
        return self

    @property
    def assay_type(self) -> str:
        """兼容旧字段名。"""
        return self.type.value


class Batch(BaseModel):
    """一批货物的一次流转。"""

    batch_id: str
    contract_id: str
    sample_id: Optional[str] = None
    weigh_tickets: list[WeighTicketRecord] = Field(default_factory=list)
    assay_reports: list[AssayReportRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def infer_sample_id(self) -> "Batch":
        if self.sample_id:
            return self
        for ticket in self.weigh_tickets:
            if ticket.sample_id:
                self.sample_id = ticket.sample_id.strip()
                return self
        for report in self.assay_reports:
            if report.sample_id:
                self.sample_id = report.sample_id.strip()
                return self
        return self

    @property
    def settlement_weigh_tickets(self) -> list[WeighTicketRecord]:
        settlement = [t for t in self.weigh_tickets if t.is_settlement]
        return settlement or list(self.weigh_tickets)

    @property
    def settlement_assay_reports(self) -> list[AssayReportRecord]:
        settlement = [
            r for r in self.assay_reports
            if r.is_settlement or r.type == AssayReportType.SETTLEMENT
        ]
        return settlement or list(self.assay_reports)

    @property
    def assay_report(self) -> AssayReportRecord:
        reports = self.settlement_assay_reports
        if not reports:
            raise ValueError(f"Batch {self.batch_id} 缺少化验单")
        return sorted(
            reports,
            key=lambda r: (r.assay_date or date.min, r.report_id),
        )[-1]

    @property
    def total_wet_weight(self) -> Decimal:
        return sum((t.wet_weight for t in self.settlement_weigh_tickets), Decimal("0"))


class BatchView(BaseModel):
    """某合同的完整批次视图。"""

    contract: ContractRecord
    batches: list[Batch] = Field(default_factory=list)

    @property
    def total_wet_weight(self) -> Decimal:
        return sum((batch.total_wet_weight for batch in self.batches), Decimal("0"))

    @property
    def batch_count(self) -> int:
        return len(self.batches)
