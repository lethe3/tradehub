"""
API 请求/响应 Pydantic 模型

与 core/models/ 的区别：
  - 这里是面向 HTTP API 的 DTO（Data Transfer Object）
  - 使用 JSON 友好的类型（str 而非 Decimal，前端直接使用）
  - Decimal 字段序列化为字符串，避免浮点精度损失
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


# ── 通用响应封装 ─────────────────────────────────────────────

class APIResponse(BaseModel):
    """统一响应包装"""
    success: bool
    data: Any = None
    error: Optional[str] = None


# ── 合同 ────────────────────────────────────────────────────

class ContractCreate(BaseModel):
    """新建合同请求体"""
    contract_number: str
    direction: str                          # 采购 / 销售
    counterparty: str
    commodity: Optional[str] = None
    signing_date: Optional[date] = None
    tax_included: Optional[bool] = None
    freight_bearer: Optional[str] = None
    assay_fee_bearer: Optional[str] = None
    settlement_ticket_rule: Optional[str] = None
    settlement_assay_rule: Optional[str] = None


class ContractUpdate(BaseModel):
    """更新合同请求体（所有字段可选）"""
    contract_number: Optional[str] = None
    direction: Optional[str] = None
    counterparty: Optional[str] = None
    commodity: Optional[str] = None
    signing_date: Optional[date] = None
    tax_included: Optional[bool] = None
    freight_bearer: Optional[str] = None
    assay_fee_bearer: Optional[str] = None
    settlement_ticket_rule: Optional[str] = None
    settlement_assay_rule: Optional[str] = None


# ── 磅单 ────────────────────────────────────────────────────

class WeighTicketCreate(BaseModel):
    """新建磅单请求体"""
    ticket_number: str
    commodity: str
    wet_weight: Decimal
    sample_id: Optional[str] = None
    weighing_date: Optional[date] = None
    vehicle_number: Optional[str] = None
    gross_weight: Optional[Decimal] = None
    tare_weight: Optional[Decimal] = None
    deduction_weight: Optional[Decimal] = None
    is_settlement: bool = True
    price_group: Optional[int] = None

    model_config = ConfigDict(json_encoders={Decimal: str})


class WeighTicketUpdate(BaseModel):
    """更新磅单请求体"""
    ticket_number: Optional[str] = None
    commodity: Optional[str] = None
    wet_weight: Optional[Decimal] = None
    sample_id: Optional[str] = None
    weighing_date: Optional[date] = None
    vehicle_number: Optional[str] = None
    gross_weight: Optional[Decimal] = None
    tare_weight: Optional[Decimal] = None
    deduction_weight: Optional[Decimal] = None
    is_settlement: Optional[bool] = None
    price_group: Optional[int] = None

    model_config = ConfigDict(json_encoders={Decimal: str})


# ── 化验单 ──────────────────────────────────────────────────

class AssayReportCreate(BaseModel):
    """新建化验单请求体"""
    sample_id: str
    assay_type: str = "结算化验"
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

    model_config = ConfigDict(json_encoders={Decimal: str})


class AssayReportUpdate(BaseModel):
    """更新化验单请求体"""
    sample_id: Optional[str] = None
    assay_type: Optional[str] = None
    is_settlement: Optional[bool] = None
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

    model_config = ConfigDict(json_encoders={Decimal: str})


# ── 结算响应 ─────────────────────────────────────────────────

class SettlementItemOut(BaseModel):
    """结算明细行（响应用）"""
    sample_id: Optional[str] = None
    row_type: str
    direction: str
    element: Optional[str] = None
    pricing_basis: Optional[str] = None
    wet_weight: Optional[str] = None
    h2o_pct: Optional[str] = None
    dry_weight: Optional[str] = None
    assay_grade: Optional[str] = None
    grade_deduction_val: Optional[str] = None
    effective_grade: Optional[str] = None
    metal_quantity: Optional[str] = None
    unit_price: Optional[str] = None
    unit: Optional[str] = None
    amount: str
    note: Optional[str] = None


class SettlementSummaryOut(BaseModel):
    """结算汇总（响应用）"""
    total_element_payment: str       # 元素货款合计
    total_impurity_deduction: str    # 杂质扣款合计
    total_income: str                # 收入合计
    total_expense: str               # 支出合计
    net_amount: str                  # 净额（正=收，负=付）


class SettlementResponse(BaseModel):
    """结算端点完整响应"""
    contract_id: str
    direction: str
    items: list[SettlementItemOut]
    summary: SettlementSummaryOut
    ready_check: dict[str, bool]     # weigh_tickets / assay_reports / recipe


# ── 就绪检查 ─────────────────────────────────────────────────

class ReadyCheck(BaseModel):
    """合同就绪状态"""
    weigh_tickets: bool
    assay_reports: bool
    recipe: bool
    is_ready: bool
