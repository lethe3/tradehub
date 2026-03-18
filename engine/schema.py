"""
Recipe Schema — 管道公式框架（Phase 2 重新设计）

核心理念：金额 = 数量 × 单价
- 数量管道：从 wet_weight 开始，经过零或多步变换
- 单价管道：从输入（固定价/基准价）开始，经过零或多步变换

纯 Pydantic，零外部依赖。
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal, Optional

from pydantic import BaseModel


# ══════════════════════════════════════════════════════════════
# 数量管道步骤
# ══════════════════════════════════════════════════════════════

class QuantityStep(BaseModel):
    """数量管道中的一个步骤

    op（操作类型）：
      - "start"         → 起点，operand 指定起始值（wet_weight / dry_weight）
      - "multiply_field"→ 乘以某字段（如品位 cu_pct → 金属量）
      - "grade_adjust"  → 品位调整：× (field - deduction) / 单位换算
      - "subtract"      → 减去常数
      - "add"           → 加上常数
      - "multiply"      → 乘以常数
      - "divide"        → 除以常数

    单位换算（grade_adjust 专用）：
      - unit="pct"  → 除以 100（% 转为小数，如 18.5% → 0.185）
      - unit="gpt"  → 不转换（g/t 直接乘）
    """
    op: Literal["start", "dry_weight", "multiply_field", "multiply_add_field", "grade_adjust", "subtract", "add", "multiply", "divide"]

    # op="start" 时使用
    operand: Optional[Literal["wet_weight", "dry_weight"]] = None

    # op="multiply_field" 时使用
    field: Optional[str] = None           # 字段名，如 "cu_pct", "pb_pct", "h2o_pct"
    factor: Optional[Decimal] = None      # 乘数因子，默认 None 表示直接乘字段值

    # op="grade_adjust" 时使用
    unit: Optional[Literal["pct", "gpt"]] = None  # 品位单位：pct → ÷100，gpt → 不转换

    # op="subtract" / "add" / "multiply" / "divide" 时使用
    value: Optional[Decimal] = None        # 常数值


# ══════════════════════════════════════════════════════════════
# 单价管道步骤
# ══════════════════════════════════════════════════════════════

class PriceStep(BaseModel):
    """单价管道中的一个步骤

    op（操作类型）：
      - "fixed"      → 固定值（直接给数值）
      - "multiply"   → 乘以常数（如系数）
      - "subtract"   → 减去常数（如减价）
      - "tier_lookup"→ 阶梯查表（品位查费率）

    示例（固定价 65000）：
      - step 1: op="fixed", value=Decimal("65000")

    示例（阶梯扣款）：
      - step 1: op="tier_lookup", field="as_pct", tiers=[...]
    """
    op: Literal["fixed", "multiply", "subtract", "tier_lookup"]

    # op="fixed" 时使用
    value: Optional[Decimal] = None

    # op="multiply" / "subtract" 时使用
    factor: Optional[Decimal] = None      # 乘数或减数

    # op="tier_lookup" 时使用
    field: Optional[str] = None           # 查表字段，如 "as_pct"
    tiers: Optional[list[TierEntry]] = None  # 阶梯定义


class TierEntry(BaseModel):
    """阶梯档位（用于单价管道 tier_lookup）"""
    lower: Decimal              # 下限（含）
    upper: Optional[Decimal] = None  # 上限（不含）；None 表示无上限
    rate: Decimal               # 费率（元/吨湿重）


# ══════════════════════════════════════════════════════════════
# 计价元素
# ══════════════════════════════════════════════════════════════

class RecipeElement(BaseModel):
    """单个计价元素或杂质扣款项

    type:
      - "element"   → 计价元素（Cu/Pb/Au/Ag 等）
      - "deduction" → 杂质扣款（As/S 等），金额为负

    数量管道示例（Cu 元素，金属量计价）：
      quantity_pipeline:
        - op: "start", operand: "wet_weight"
        - op: "multiply_field", field: "h2o_pct", factor: Decimal("-1")  # 干重
        - op: "multiply_field", field: "cu_pct"  # × 品位
        - op: "divide", value: Decimal("100")    # 转为吨

    单价管道示例（固定价 65000）：
      price_pipeline:
        - op: "fixed", value: Decimal("65000")
    """
    name: str                               # 元素名（Cu / Pb / Au / As 等）
    type: Literal["element", "deduction"] = "element"

    quantity_pipeline: list[QuantityStep] = []   # 数量管道
    price_pipeline: list[PriceStep] = []        # 单价管道

    unit: str = "元/金属吨"                  # 单位

    # 基准价引用（Phase 2+ 扩展）
    base_price_ref: Optional[str] = None


# ══════════════════════════════════════════════════════════════
# Recipe 根结构
# ══════════════════════════════════════════════════════════════

class Recipe(BaseModel):
    """合同计价配方（管道公式版本）

    一个 Recipe 对应一份合同的完整计价规则。
    通过 evaluate_recipe(recipe, batch_view, direction) 求值。

    assay_fee: 化验费总额（我方承担时填写，None 表示不承担或由对方承担）
    """
    contract_id: str
    version: str = "2.0"  # 管道版本
    elements: list[RecipeElement] = []
    assay_fee: Optional[Decimal] = None
