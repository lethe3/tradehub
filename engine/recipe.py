"""
Python Recipe Evaluator — 管道公式版本（Phase 2）

核心理念：金额 = 数量 × 单价
- 数量管道：从 wet_weight 开始，经过零或多步变换
- 单价管道：从输入（固定价/基准价）开始，经过零或多步变换

核心函数：
  evaluate_recipe(recipe, batch_view, direction) -> list[SettlementItemRecord]

设计原则：
  - 通用管道执行器，支持任意变换组合
  - 金额全程 Decimal + ROUND_HALF_UP
  - direction 参数接受 "采购" 或 "销售"
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from core.models.batch import Batch, BatchView
from core.models.settlement_item import (
    PricingBasis,
    PriceFormula,
    PriceSource,
    SettlementDirection,
    SettlementItemRecord,
    SettlementRowType,
)

from .schema import PriceStep, QuantityStep, Recipe, TierEntry


# ══════════════════════════════════════════════════════════════
# 数量管道执行器
# ══════════════════════════════════════════════════════════════

def _execute_quantity_pipeline(
    pipeline: list[QuantityStep],
    batch: Batch,
) -> tuple[Decimal, dict]:
    """执行数量管道，返回最终数量和中间值

    Returns:
        (最终数量, 中间值字典) - 中间值包含 dry_weight, metal_quantity 等
    """
    wet_weight = batch.total_wet_weight
    assay = batch.assay_report
    h2o = assay.h2o_pct or Decimal("0")

    # 中间值记录
    intermediates: dict = {}

    # 当前累积值
    current: Decimal | None = None

    for i, step in enumerate(pipeline):
        if step.op == "start":
            if step.operand == "wet_weight":
                current = wet_weight
            elif step.operand == "dry_weight":
                # 单独计算干重并记录
                current = wet_weight * (Decimal("1") - h2o / Decimal("100"))
                intermediates["dry_weight"] = current
            else:
                raise ValueError(f"未知 operand: {step.operand}")

        elif step.op == "dry_weight":
            # 计算干重：wet × (1 - h2o/100)
            current = wet_weight * (Decimal("1") - h2o / Decimal("100"))
            intermediates["dry_weight"] = current

        elif step.op == "multiply_field":
            field = step.field
            if field is None:
                raise ValueError("multiply_field 需要指定 field")

            # 获取字段值
            field_value: Decimal | None = getattr(assay, field, None)
            if field_value is None:
                raise ValueError(f"化验单缺少字段: {field}")

            factor = step.factor if step.factor is not None else Decimal("1")

            if current is None:
                # 如果还没有累积值，直接用字段值
                current = field_value * factor
            else:
                # 乘法：current × field_value × factor
                current = current * field_value * factor

        elif step.op == "grade_adjust":
            """品位计算：计算金属量 = 干重 × 品位

            - unit="pct": 金属量 = 干重 × 品位 ÷ 100
            - unit="gpt": 金属量 = 干重 × 品位（不转换）
            """
            field = step.field
            if field is None:
                raise ValueError("grade_adjust 需要指定 field")

            field_value: Decimal | None = getattr(assay, field, None)
            if field_value is None:
                raise ValueError(f"化验单缺少字段: {field}")

            if current is None:
                raise ValueError("grade_adjust 前需要有累积值（干重）")

            # 根据单位决定是否转换
            if step.unit == "pct":
                # % 单位：除以 100
                current = current * field_value / Decimal("100")
            elif step.unit == "gpt" or step.unit is None:
                # g/t 单位：不转换
                current = current * field_value
            else:
                raise ValueError(f"grade_adjust 不支持的单位: {step.unit}")

            intermediates["metal_quantity"] = current

        elif step.op == "subtract":
            if step.value is None:
                raise ValueError("subtract 需要指定 value")
            if current is None:
                raise ValueError("subtract 前需要有累积值")
            current = current - step.value

        elif step.op == "add":
            if step.value is None:
                raise ValueError("add 需要指定 value")
            if current is None:
                raise ValueError("add 前需要有累积值")
            current = current + step.value

        elif step.op == "multiply":
            if step.value is None:
                raise ValueError("multiply 需要指定 value")
            if current is None:
                raise ValueError("multiply 前需要有累积值")
            current = current * step.value

        elif step.op == "divide":
            if step.value is None or step.value == Decimal("0"):
                raise ValueError("divide 需要指定非零 value")
            if current is None:
                raise ValueError("divide 前需要有累积值")
            current = current / step.value

        else:
            raise ValueError(f"未知数量操作: {step.op}")

    if current is None:
        raise ValueError("数量管道为空")

    return current.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP), intermediates


# ══════════════════════════════════════════════════════════════
# 单价管道执行器
# ══════════════════════════════════════════════════════════════

def _find_tier(grade: Decimal, tiers: list[TierEntry]) -> TierEntry | None:
    """查找品位对应的阶梯档位

    区间规则：lower 含（闭），upper 不含（开）。
    最高档 upper=None 表示无上限。
    """
    for tier in sorted(tiers, key=lambda t: t.lower):
        if grade < tier.lower:
            continue
        if tier.upper is None:
            return tier
        if grade < tier.upper:
            return tier
    return None


def _execute_price_pipeline(
    pipeline: list[PriceStep],
    batch: Batch,
) -> tuple[Decimal, str | None]:
    """执行单价管道，返回最终单价和字段名

    Returns:
        (最终单价, 品位字段名或None)
    """
    assay = batch.assay_report

    current: Decimal | None = None
    grade_field: str | None = None

    for step in pipeline:
        if step.op == "fixed":
            if step.value is None:
                raise ValueError("fixed 需要指定 value")
            current = step.value

        elif step.op == "multiply":
            if step.factor is None:
                raise ValueError("multiply 需要指定 factor")
            if current is None:
                raise ValueError("multiply 前需要有累积值")
            current = current * step.factor

        elif step.op == "subtract":
            if step.factor is None:
                raise ValueError("subtract 需要指定 factor")
            if current is None:
                raise ValueError("subtract 前需要有累积值")
            current = current - step.factor

        elif step.op == "tier_lookup":
            field = step.field
            if field is None:
                raise ValueError("tier_lookup 需要指定 field")
            if step.tiers is None:
                raise ValueError("tier_lookup 需要指定 tiers")

            grade_field = field

            # 获取字段值（品位）
            grade: Decimal | None = getattr(assay, field, None)
            if grade is None:
                raise ValueError(f"化验单缺少字段: {field}")

            tier = _find_tier(grade, step.tiers)
            if tier is None:
                # 品位未落入任何档位，单价为 0
                current = Decimal("0")
            else:
                current = tier.rate

        else:
            raise ValueError(f"未知单价操作: {step.op}")

    if current is None:
        raise ValueError("单价管道为空")

    return current.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), grade_field


# ══════════════════════════════════════════════════════════════
# 主函数
# ══════════════════════════════════════════════════════════════

def evaluate_recipe(
    recipe: Recipe,
    batch_view: BatchView,
    direction: str,
) -> list[SettlementItemRecord]:
    """
    用 Recipe（管道公式版本）对 BatchView 中的每个 Batch 计算结算明细。

    Args:
        recipe:      合同计价配方（管道版本）
        batch_view:  批次视图
        direction:   合同方向（"采购" 或 "销售"）

    Returns:
        SettlementItemRecord 列表：
          - 先按 batch 顺序输出各元素货款行
          - 再输出各杂质扣款行（按 recipe.elements 顺序）

    异常：
        ValueError  — 化验单缺少必要字段、步骤参数错误
    """
    settle_direction = (
        SettlementDirection.EXPENSE if direction == "采购"
        else SettlementDirection.INCOME
    )

    items: list[SettlementItemRecord] = []

    element_items = [e for e in recipe.elements if e.type == "element"]
    deduction_items = [e for e in recipe.elements if e.type == "deduction"]

    for batch in batch_view.batches:
        assay = batch.assay_report
        wet_weight = batch.total_wet_weight
        h2o_pct = assay.h2o_pct

        # 验证必要字段
        if h2o_pct is None:
            raise ValueError(
                f"批次 {batch.batch_id} 化验单缺少 h2o_pct，无法计算"
            )

        # ── 计价元素（type="element"）─────────────────────────────
        for elem in element_items:
            # 执行数量管道
            quantity, intermediates = _execute_quantity_pipeline(
                elem.quantity_pipeline, batch
            )

            # 执行单价管道
            unit_price, grade_field = _execute_price_pipeline(
                elem.price_pipeline, batch
            )

            # 计算金额
            amount = (quantity * unit_price).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            # 获取中间值
            dry_weight_val = intermediates.get("dry_weight")
            metal_quantity_val = intermediates.get("metal_quantity")

            # 金属量四舍五入到3位小数（结算标准）
            if metal_quantity_val is not None:
                metal_quantity_rounded = metal_quantity_val.quantize(
                    Decimal("0.001"), rounding=ROUND_HALF_UP
                )
                amount = (metal_quantity_rounded * unit_price).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            else:
                amount = (quantity * unit_price).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )

            # 获取品位值
            grade_value = None
            if grade_field:
                grade_value = getattr(assay, grade_field, None)

            # 构建 SettlementItemRecord
            item = SettlementItemRecord(
                contract_id=recipe.contract_id,
                sample_id=batch.sample_id,
                row_type=SettlementRowType.ELEMENT_PAYMENT,
                direction=settle_direction,
                element=elem.name,
                pricing_basis=PricingBasis.METAL_QUANTITY,
                price_source=PriceSource.FIXED,
                price_formula=PriceFormula.FIXED_PRICE,
                wet_weight=wet_weight,
                h2o_pct=h2o_pct,
                dry_weight=dry_weight_val,
                metal_quantity=metal_quantity_val.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP) if metal_quantity_val else None,
                assay_grade=grade_value,
                unit_price=unit_price,
                unit=elem.unit,
                amount=amount,
            )
            items.append(item)

        # ── 杂质扣款（type="deduction"）──────────────────────────
        for elem in deduction_items:
            # 执行数量管道（通常是干重）
            quantity, intermediates = _execute_quantity_pipeline(
                elem.quantity_pipeline, batch
            )

            # 执行单价管道（阶梯查表）
            unit_price, grade_field = _execute_price_pipeline(
                elem.price_pipeline, batch
            )

            # 如果单价为0（品位不在任何阶梯档位），跳过该扣款记录
            if unit_price == Decimal("0"):
                continue

            # 计算金额（扣款，方向为 EXPENSE）
            amount = (quantity * unit_price).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            # 获取品位值
            grade_value = None
            if grade_field:
                grade_value = getattr(assay, grade_field, None)

            # 档位说明
            tier_note = None
            for step in elem.price_pipeline:
                if step.op == "tier_lookup" and step.tiers:
                    tier = _find_tier(grade_value or Decimal("0"), step.tiers)
                    if tier:
                        if tier.upper is None:
                            tier_note = f"{elem.name} ≥{tier.lower}% → {tier.rate}元/吨"
                        else:
                            tier_note = f"{elem.name} [{tier.lower}%, {tier.upper}%) → {tier.rate}元/吨"
                    break

            items.append(SettlementItemRecord(
                contract_id=recipe.contract_id,
                sample_id=batch.sample_id,
                row_type=SettlementRowType.IMPURITY_DEDUCTION,
                direction=SettlementDirection.EXPENSE,
                element=elem.name,
                pricing_basis=PricingBasis.WET_WEIGHT,
                price_source=PriceSource.FIXED,
                wet_weight=wet_weight,
                assay_grade=grade_value,
                unit_price=unit_price,
                unit="元/吨",
                amount=amount,
                note=tier_note,
            ))

    return items
