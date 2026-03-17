"""
资金流水模型

CashFlowRecord：对应 Bitable 资金流水表的一条记录。
既用于"从 Bitable 读取"，也用于"计算结果写入 Bitable 前的暂存"。

纯 Pydantic，无外部依赖。
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, model_validator


class CashFlowType(str, Enum):
    """流水类型（对应 Bitable 单选字段选项）"""
    PREPAYMENT = "预付款"
    ELEMENT_PAYMENT = "元素货款"
    IMPURITY_DEDUCTION = "杂质扣款"
    GRADE_ADJUSTMENT = "品位调价"
    FREIGHT = "运费"
    ASSAY_FEE = "化验费"
    TRAVEL_FEE = "差旅费"
    TAX_ADJUSTMENT = "税费调整"
    FINAL_PAYMENT = "尾款"
    OTHER = "其他"


class CashFlowDirection(str, Enum):
    """流水方向（收入=对我方有利，支出=对我方不利）"""
    INCOME = "收入"    # 应收/已收款项
    EXPENSE = "支出"   # 应付/已付款项


class CashFlowRecord(BaseModel):
    """资金流水记录

    金额字段 amount 始终为正数，方向由 direction 字段表达。
    代数值 = INCOME → +amount，EXPENSE → -amount。
    同一合同所有流水代数值之和 = 0 → 结清。
    """
    record_id: Optional[str] = None       # Bitable record ID（写入后才有）
    contract_id: str                      # 关联合同 record ID
    flow_type: CashFlowType               # 流水类型
    direction: CashFlowDirection          # 收入 / 支出
    element: Optional[str] = None        # 计价元素（Cu/Au/Ag/无），仅元素货款时填
    # 元素货款明细（仅 flow_type = ELEMENT_PAYMENT 时填写）
    sample_id: Optional[str] = None      # 对应样号（便于追溯）
    dry_weight: Optional[Decimal] = None  # 干重(吨)
    metal_quantity: Optional[Decimal] = None  # 金属量(金属吨)
    unit_price: Optional[Decimal] = None      # 单价
    unit: Optional[str] = None               # 单价单位（元/金属吨等）
    # 核心字段
    amount: Decimal                       # 金额（正数）
    flow_date: Optional[date] = None      # 日期
    note: Optional[str] = None            # 备注

    @model_validator(mode="after")
    def check_element_payment_fields(self) -> "CashFlowRecord":
        """元素货款必须填写 element；按金属吨计价时还必须有 metal_quantity"""
        if self.flow_type == CashFlowType.ELEMENT_PAYMENT:
            if self.element is None:
                raise ValueError("元素货款必须指定计价元素 (element)")
            # 元/吨（按湿重）计价时不存在金属量，仅金属吨计价时要求
            if self.unit != "元/吨" and self.metal_quantity is None:
                raise ValueError("元素货款必须填写金属量 (metal_quantity)")
        return self

    @property
    def signed_amount(self) -> Decimal:
        """带符号金额：收入为正，支出为负"""
        if self.direction == CashFlowDirection.INCOME:
            return self.amount
        return -self.amount


class SettlementSummary(BaseModel):
    """结算摘要（按合同汇总流水，用于渲染结算单卡片）

    由 M3D-3 从 CashFlowRecord 列表生成，不存 Bitable。
    """
    contract_id: str
    contract_number: str
    total_income: Decimal               # 应收合计
    total_expense: Decimal              # 应付合计
    net_amount: Decimal                 # 净额（income - expense）
    is_settled: bool                    # 净额 == 0 视为结清
    records: list[CashFlowRecord]       # 明细列表

    @classmethod
    def from_records(
        cls,
        contract_id: str,
        contract_number: str,
        records: list[CashFlowRecord],
    ) -> "SettlementSummary":
        income = sum(
            (r.amount for r in records if r.direction == CashFlowDirection.INCOME),
            Decimal("0"),
        )
        expense = sum(
            (r.amount for r in records if r.direction == CashFlowDirection.EXPENSE),
            Decimal("0"),
        )
        net = income - expense
        return cls(
            contract_id=contract_id,
            contract_number=contract_number,
            total_income=income,
            total_expense=expense,
            net_amount=net,
            is_settled=(net == Decimal("0")),
            records=records,
        )
