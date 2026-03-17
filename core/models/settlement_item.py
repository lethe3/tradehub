"""
结算明细记录模型

SettlementItemRecord：对应 Bitable 结算明细表的一条记录。
每行 = 一条磅单 × 一个计价元素（或一条杂质扣款记录）。

纯 Pydantic，无外部依赖。
"""
from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class SettlementRowType(str, Enum):
    """行类型"""
    ELEMENT_PAYMENT = "元素货款"
    IMPURITY_DEDUCTION = "杂质扣款"


class SettlementDirection(str, Enum):
    """方向（对我方）"""
    INCOME = "收"
    EXPENSE = "付"


class PricingBasis(str, Enum):
    """计价基准"""
    WET_WEIGHT = "湿重"
    DRY_WEIGHT = "干重"
    METAL_QUANTITY = "金属量"


class PriceSource(str, Enum):
    """基准价来源"""
    FIXED = "固定"
    AVERAGE = "均价"
    SPOT = "点价"


class PriceFormula(str, Enum):
    """单价公式"""
    FIXED_PRICE = "固定单价"
    GRADE_DEDUCTION = "品位扣减"
    COEFFICIENT = "系数法"


class SettlementItemRecord(BaseModel):
    """结算明细记录

    每行对应一条磅单 × 一个计价元素，或一条杂质扣款。
    金额字段 amount 始终为正数，方向由 direction 字段表达。
    """
    record_id: Optional[str] = None        # Bitable record ID（写入后才有）
    contract_id: str                        # 关联合同 record ID
    weigh_ticket_id: Optional[str] = None  # 关联磅单 record ID
    sample_id: Optional[str] = None        # 样号
    # 分类字段
    row_type: SettlementRowType             # 元素货款 / 杂质扣款
    direction: SettlementDirection          # 收 / 付
    element: Optional[str] = None          # 计价元素（Cu/Au/Ag/As/S 等）
    # 计价三轴
    pricing_basis: Optional[PricingBasis] = None    # 计价基准
    price_source: PriceSource = PriceSource.FIXED   # 基准价来源
    price_formula: Optional[PriceFormula] = None    # 单价公式
    # 原始计算参数
    wet_weight: Optional[Decimal] = None           # 湿重(吨)
    h2o_pct: Optional[Decimal] = None              # H2O(%)
    dry_weight: Optional[Decimal] = None           # 干重(吨)，计算得
    assay_grade: Optional[Decimal] = None          # 化验品位
    grade_deduction_val: Optional[Decimal] = None  # 品位扣减（合同约定）
    effective_grade: Optional[Decimal] = None      # 有效品位 = 化验 - 扣减
    metal_quantity: Optional[Decimal] = None       # 金属量(吨)，计算得
    unit_price: Optional[Decimal] = None           # 单价
    unit: Optional[str] = None                     # 单价单位
    # 结果
    amount: Decimal                                 # 金额（正数）
    note: Optional[str] = None                     # 备注（杂质扣款时记录档位说明）
