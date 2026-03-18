"""
Python Recipe Evaluator — 正式结算引擎（Decimal 精度）

核心函数：
  evaluate_recipe(recipe, batch_view, direction) -> list[SettlementItemRecord]

设计原则：
  - 复用 core/settlement.py 的底层计算函数，不重复实现
  - 不替换 core/settlement.py，两者并存，fixture 交叉验证一致性
  - 金额全程 Decimal + ROUND_HALF_UP
  - direction 参数接受 "采购" 或 "销售"（与 ContractRecord.direction 一致）
"""
from __future__ import annotations

from decimal import Decimal

from core.models.batch import BatchView
from core.models.settlement_item import (
    PricingBasis,
    PriceFormula,
    PriceSource,
    SettlementDirection,
    SettlementItemRecord,
    SettlementRowType,
)
from core.settlement import (
    calc_dry_weight,
    calc_element_payment,
    calc_impurity_amount,
    calc_metal_quantity,
    find_impurity_tier,
)

from .schema import Recipe, RecipeElement, TierEntry


# ── 计价基准映射 ────────────────────────────────────────────────
_BASIS_MAP = {
    "wet_weight": PricingBasis.WET_WEIGHT,
    "dry_weight": PricingBasis.DRY_WEIGHT,
    "metal_quantity": PricingBasis.METAL_QUANTITY,
}

# ── 杂质扣款阶梯适配（RecipeElement.tiers → ImpurityDeductionTier）────
# recipe.TierEntry 与 core.models.pricing.ImpurityDeductionTier 字段一致，
# 但为了不引入 core/models/pricing 依赖，直接用 recipe.TierEntry 做档位查找。

def _find_tier(grade: Decimal, tiers: list[TierEntry]) -> TierEntry | None:
    """与 core.settlement.find_impurity_tier 等效的 TierEntry 版本。

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


# ══════════════════════════════════════════════════════════════
# 主函数
# ══════════════════════════════════════════════════════════════

def evaluate_recipe(
    recipe: Recipe,
    batch_view: BatchView,
    direction: str,
) -> list[SettlementItemRecord]:
    """
    用 Recipe 对 BatchView 中的每个批次单元计算结算明细。

    Args:
        recipe:      合同计价配方
        batch_view:  M3C 串联输出的批次视图
        direction:   合同方向（"采购" 或 "销售"）

    Returns:
        SettlementItemRecord 列表：
          - 先按 batch_unit 顺序输出各元素货款行
          - 再输出各杂质扣款行（按 recipe.elements 顺序）

    异常：
        ValueError  — 化验单缺少必要字段、元素名未识别
        NotImplementedError — unit_price.source 不为 "fixed" 或未实现的 operations
    """
    settle_direction = (
        SettlementDirection.EXPENSE if direction == "采购"
        else SettlementDirection.INCOME
    )

    items: list[SettlementItemRecord] = []

    # ── 元素货款（type="element"）─────────────────────────────
    element_items = [e for e in recipe.elements if e.type == "element"]
    deduction_items = [e for e in recipe.elements if e.type == "deduction"]

    for unit in batch_view.batch_units:
        assay = unit.assay_report
        wet_weight = unit.total_wet_weight

        if assay.h2o_pct is None:
            raise ValueError(
                f"样号 {unit.sample_id} 化验单缺少 h2o_pct，无法计算干重"
            )

        dry_weight = calc_dry_weight(wet_weight, assay.h2o_pct)

        for elem in element_items:
            if elem.unit_price.source != "fixed":
                raise NotImplementedError(
                    f"仅支持 source=fixed，元素 {elem.name} 使用了 {elem.unit_price.source}"
                )
            if elem.operations:
                raise NotImplementedError(
                    f"元素 {elem.name} 含 operations，Phase 1 暂不支持"
                )
            if elem.unit_price.value is None:
                raise ValueError(
                    f"元素 {elem.name} 的 unit_price.value 不能为 None（fixed 模式）"
                )

            unit_price = elem.unit_price.value
            basis = elem.quantity.basis

            pricing_basis = _BASIS_MAP[basis]

            if basis == "wet_weight":
                # 按湿重计价
                from decimal import ROUND_HALF_UP
                payment = (wet_weight * unit_price).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                items.append(SettlementItemRecord(
                    contract_id=recipe.contract_id,
                    sample_id=unit.sample_id,
                    row_type=SettlementRowType.ELEMENT_PAYMENT,
                    direction=settle_direction,
                    element=elem.name,
                    pricing_basis=pricing_basis,
                    price_source=PriceSource.FIXED,
                    price_formula=PriceFormula.FIXED_PRICE,
                    wet_weight=wet_weight,
                    h2o_pct=assay.h2o_pct,
                    unit_price=unit_price,
                    unit=elem.unit_price.unit,
                    amount=payment,
                ))

            elif basis == "dry_weight":
                # 按干重计价
                from decimal import ROUND_HALF_UP
                payment = (dry_weight * unit_price).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                items.append(SettlementItemRecord(
                    contract_id=recipe.contract_id,
                    sample_id=unit.sample_id,
                    row_type=SettlementRowType.ELEMENT_PAYMENT,
                    direction=settle_direction,
                    element=elem.name,
                    pricing_basis=pricing_basis,
                    price_source=PriceSource.FIXED,
                    price_formula=PriceFormula.FIXED_PRICE,
                    wet_weight=wet_weight,
                    h2o_pct=assay.h2o_pct,
                    dry_weight=dry_weight,
                    unit_price=unit_price,
                    unit=elem.unit_price.unit,
                    amount=payment,
                ))

            elif basis == "metal_quantity":
                # 按金属量计价
                grade_field = elem.quantity.grade_field
                if grade_field is None:
                    raise ValueError(
                        f"元素 {elem.name} basis=metal_quantity 必须指定 grade_field"
                    )
                assay_grade: Decimal | None = getattr(assay, grade_field, None)
                if assay_grade is None:
                    raise ValueError(
                        f"样号 {unit.sample_id} 化验单缺少字段 {grade_field}"
                    )
                grade_deduction = elem.quantity.grade_deduction
                eff_grade = assay_grade - grade_deduction
                metal_qty = calc_metal_quantity(dry_weight, assay_grade, grade_deduction)
                payment = calc_element_payment(metal_qty, unit_price)

                # 判断公式类型
                formula = (
                    PriceFormula.GRADE_DEDUCTION
                    if grade_deduction != Decimal("0")
                    else PriceFormula.FIXED_PRICE
                )

                items.append(SettlementItemRecord(
                    contract_id=recipe.contract_id,
                    sample_id=unit.sample_id,
                    row_type=SettlementRowType.ELEMENT_PAYMENT,
                    direction=settle_direction,
                    element=elem.name,
                    pricing_basis=pricing_basis,
                    price_source=PriceSource.FIXED,
                    price_formula=formula,
                    wet_weight=wet_weight,
                    h2o_pct=assay.h2o_pct,
                    dry_weight=dry_weight,
                    assay_grade=assay_grade,
                    grade_deduction_val=grade_deduction,
                    effective_grade=eff_grade,
                    metal_quantity=metal_qty,
                    unit_price=unit_price,
                    unit=elem.unit_price.unit,
                    amount=payment,
                ))

            else:
                raise NotImplementedError(f"未知 basis: {basis}")

    # ── 杂质扣款（type="deduction"）──────────────────────────
    for elem in deduction_items:
        grade_field = elem.quantity.grade_field
        if grade_field is None:
            raise ValueError(
                f"杂质 {elem.name} 必须指定 grade_field 以读取化验品位"
            )

        for unit in batch_view.batch_units:
            assay = unit.assay_report
            grade: Decimal | None = getattr(assay, grade_field, None)
            if grade is None:
                continue  # 该样号无此杂质数据，跳过

            tier = _find_tier(grade, elem.tiers)
            if tier is None:
                continue  # 品位未落入任何档位，不扣款

            amount = calc_impurity_amount(unit.total_wet_weight, tier.rate)

            # 档位说明
            if tier.upper is None:
                tier_note = f"{elem.name} ≥{tier.lower}% → {tier.rate}元/吨"
            else:
                tier_note = f"{elem.name} [{tier.lower}%, {tier.upper}%) → {tier.rate}元/吨"

            items.append(SettlementItemRecord(
                contract_id=recipe.contract_id,
                sample_id=unit.sample_id,
                row_type=SettlementRowType.IMPURITY_DEDUCTION,
                direction=SettlementDirection.EXPENSE,
                element=elem.name,
                pricing_basis=PricingBasis.WET_WEIGHT,
                price_source=PriceSource.FIXED,
                wet_weight=unit.total_wet_weight,
                assay_grade=grade,
                unit_price=tier.rate,
                unit="元/吨",
                amount=amount,
                note=tier_note,
            ))

    return items
