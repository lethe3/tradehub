"""
Recipe Schema — 合同计价配方的声明式表示

Phase 1 支持：FIXED 计价 + 杂质扣款阶梯（operations 为空数组，结构预留）
Phase 2+ 扩展：均价×阶梯系数、分段累计等（通过 operations 字段）

纯 Pydantic，零外部依赖。
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal, Optional

from pydantic import BaseModel


class TierEntry(BaseModel):
    """杂质扣款阶梯档位"""
    lower: Decimal              # 下限（含）
    upper: Optional[Decimal] = None  # 上限（不含）；None 表示无上限
    rate: Decimal               # 扣款费率（元/吨湿重）


class QuantitySpec(BaseModel):
    """计量规格：决定「用什么基数计算金额」

    basis:
      - "wet_weight"      → 以湿重（吨）为计量基数
      - "dry_weight"      → 以干重（吨）为计量基数
      - "metal_quantity"  → 以金属量（金属吨）为计量基数

    grade_field: 对应 AssayReportRecord 上的属性名
      例如 "cu_pct"、"au_gt"、"as_pct"
      basis == "wet_weight" 或 "dry_weight" 时可为 None。

    grade_deduction: 品位扣减量（百分点），默认 0
      有效品位 = 化验品位 - grade_deduction
    """
    basis: Literal["wet_weight", "dry_weight", "metal_quantity"] = "metal_quantity"
    grade_field: Optional[str] = None       # AssayReportRecord 属性名
    grade_deduction: Decimal = Decimal("0")  # 品位扣减（百分点）


class UnitPriceSpec(BaseModel):
    """单价规格

    source:
      - "fixed"   → 合同固定价（Phase 1 支持）
      - "average" → 均价（Phase 2+ 扩展）
      - "spot"    → 点价（Phase 2+ 扩展）

    value: 固定价时的数值；均价/点价时为 None（由 operations 计算）
    unit:  单价单位，与 basis 对应
      - "元/吨"    → wet_weight
      - "元/干吨"  → dry_weight
      - "元/金属吨"→ metal_quantity
    """
    source: Literal["fixed", "average", "spot"] = "fixed"
    value: Optional[Decimal] = None         # 固定价数值
    unit: str = "元/金属吨"                  # 单价单位


class PriceOperation(BaseModel):
    """价格操作（Phase 2+ 扩展，Phase 1 留空）

    用于表达「均价×阶梯系数」「分段累计」等复杂定价逻辑。
    Phase 1 所有 RecipeElement.operations 均为 []。
    """
    type: str                               # 操作类型（"coefficient" | "segmented" 等）
    params: dict[str, Any] = {}            # 类型特定参数


class RecipeElement(BaseModel):
    """单个计价元素或杂质扣款项

    type:
      - "element"   → 计价元素（Cu/Au/Ag 等，产生货款行）
      - "deduction" → 杂质扣款（As/S 等，产生扣款行，使用 tiers 阶梯）

    对于 type="deduction"：
      - tiers 非空
      - unit_price.value 可为 None（由 tiers 决定费率）

    对于 type="element"：
      - tiers 为空
      - unit_price.value 非 None（Phase 1 固定价）
    """
    name: str                               # 元素名（Cu / Au / As 等）
    type: Literal["element", "deduction"] = "element"
    quantity: QuantitySpec = QuantitySpec()
    unit_price: UnitPriceSpec = UnitPriceSpec()
    operations: list[PriceOperation] = []   # Phase 2+ 扩展，Phase 1 为空
    tiers: list[TierEntry] = []             # 仅 type="deduction" 时使用


class Recipe(BaseModel):
    """合同计价配方（声明式）

    一个 Recipe 对应一份合同的完整计价规则。
    通过 evaluate_recipe(recipe, batch_view) → list[SettlementItemRecord] 求值。

    assay_fee: 化验费总额（我方承担时填写，None 表示不承担或由对方承担）
    """
    contract_id: str
    version: str = "1.0"
    elements: list[RecipeElement] = []
    assay_fee: Optional[Decimal] = None
