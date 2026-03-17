"""
M3D-1：结算计算引擎（固定计价）

核心函数：
  calc_dry_weight()          — 干重 = 湿重 × (1 - H2O%)，保留 4dp
  calc_metal_quantity()      — 金属量 = 干重 × 有效品位，保留 3dp
  calc_element_payment()     — 货款 = 金属量 × 单价，保留 2dp
  generate_cash_flows()      — BatchView + ContractPricing → list[CashFlowRecord]（旧版，仅测试使用）
  generate_settlement_items()— BatchView + ContractPricing → list[SettlementItemRecord]（新版，含完整计价元数据）

【注意】generate_cash_flows 与 generate_settlement_items 计算逻辑重复。
  generate_settlement_items 是当前生产路径；generate_cash_flows 仅存量测试使用，
  不支持 CNY_PER_DRY_TON 且不输出化验费行（与 generate_settlement_items 的差异）。
  TODO：待 SettlementItemRecord 稳定后，迁移测试并删除 generate_cash_flows。

设计原则：
  - 纯函数，不 import feishu/ 或 ai/
  - 金额全程 Decimal + ROUND_HALF_UP
  - M3D-1 仅实现 FIXED + GRADE_DEDUCTION；其余 formula_type 抛 NotImplementedError
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from .models.batch import BatchView
from .models.cash_flow import CashFlowDirection, CashFlowRecord, CashFlowType
from .models.pricing import ContractPricing, FormulaType, ImpurityDeductionTier, PriceSourceType, UnitType
from .models.settlement_item import (
    PricingBasis,
    PriceFormula,
    PriceSource,
    SettlementDirection,
    SettlementItemRecord,
    SettlementRowType,
)


# ── 品位字段映射：元素名 → AssayReportRecord 对应属性名 ────────────
_ELEMENT_ATTR: dict[str, str] = {
    "Cu": "cu_pct",
    "Au": "au_gt",
    "Ag": "ag_gt",
    "Pb": "pb_pct",
    "Zn": "zn_pct",
    "S": "s_pct",
    "As": "as_pct",
}


# ══════════════════════════════════════════════════════════════
# 核心计算函数
# ══════════════════════════════════════════════════════════════

def calc_dry_weight(wet_weight: Decimal, h2o_pct: Decimal) -> Decimal:
    """干重 = 湿重 × (1 - H2O% / 100)，保留 4 位小数，ROUND_HALF_UP。

    Args:
        wet_weight: 湿重（吨）
        h2o_pct:    水分百分比（如 10.00 表示 10%）
    """
    factor = Decimal("1") - h2o_pct / Decimal("100")
    result = wet_weight * factor
    return result.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def calc_metal_quantity(
    dry_weight: Decimal,
    assay_pct: Decimal,
    grade_deduction: Decimal,
) -> Decimal:
    """金属量 = 干重 × (有效品位 / 100)，保留 3 位小数，ROUND_HALF_UP。

    Args:
        dry_weight:      干重（吨）
        assay_pct:       化验品位（如 18.50 表示 18.50%）
        grade_deduction: 品位扣减量（百分点，如 1.0 表示扣 1%）
    """
    effective_grade = assay_pct - grade_deduction
    result = dry_weight * (effective_grade / Decimal("100"))
    return result.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def calc_element_payment(
    metal_quantity: Decimal,
    unit_price: Decimal,
) -> Decimal:
    """货款 = 金属量 × 单价，保留 2 位小数，ROUND_HALF_UP。"""
    result = metal_quantity * unit_price
    return result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def find_impurity_tier(
    grade: Decimal,
    tiers: list[ImpurityDeductionTier],
) -> ImpurityDeductionTier | None:
    """返回 grade 匹配的档位，无匹配返回 None。按 lower 升序查找。

    区间规则：lower 含（闭），upper 不含（开，upper_open=True）。
    最高档 upper=None 表示无上限。
    """
    for tier in sorted(tiers, key=lambda t: t.lower):
        if grade < tier.lower:
            continue
        if tier.upper is None:
            return tier
        if tier.upper_open and grade < tier.upper:
            return tier
        if not tier.upper_open and grade <= tier.upper:
            return tier
    return None


def calc_impurity_amount(wet_weight: Decimal, rate: Decimal) -> Decimal:
    """扣款金额 = 湿重 × rate，保留 2dp ROUND_HALF_UP。"""
    result = wet_weight * rate
    return result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ══════════════════════════════════════════════════════════════
# 主函数
# ══════════════════════════════════════════════════════════════

def generate_cash_flows(
    batch_view: BatchView,
    contract_pricing: ContractPricing,
) -> list[CashFlowRecord]:
    """
    遍历 batch_units × pricing_elements，生成 CashFlowRecord 列表。

    规则：
    - 合同 direction=="采购" → 货款方向为支出；"销售" → 收入
    - 若 contract_pricing.assay_fee_total 不为 None，追加化验费（支出）
    - 支持 FIXED + GRADE_DEDUCTION 和 FIXED + FIXED_PRICE（元/吨、元/金属吨）

    Args:
        batch_view:        M3C 串联输出的批次视图
        contract_pricing:  合同计价规则（从合同 YAML 加载）

    Returns:
        CashFlowRecord 列表，先元素货款（按 batch_unit 顺序），后化验费
    """
    contract = batch_view.contract
    direction = (
        CashFlowDirection.EXPENSE
        if contract.direction == "采购"
        else CashFlowDirection.INCOME
    )

    records: list[CashFlowRecord] = []

    for unit in batch_view.batch_units:
        assay = unit.assay_report
        wet_weight = unit.total_wet_weight

        if assay.h2o_pct is None:
            raise ValueError(
                f"样号 {unit.sample_id} 化验单缺少 h2o_pct，无法计算干重"
            )

        dry_weight = calc_dry_weight(wet_weight, assay.h2o_pct)

        for pe in contract_pricing.pricing_elements:
            if pe.price_source_type != PriceSourceType.FIXED:
                raise NotImplementedError(
                    f"仅支持 fixed 基准价，元素 {pe.element} 使用了 {pe.price_source_type}"
                )

            if pe.formula_type == FormulaType.FIXED_PRICE:
                # 固定计价：元/吨（湿重）或 元/金属吨
                if pe.unit == UnitType.CNY_PER_TON:
                    payment = (wet_weight * pe.base_price).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                    records.append(CashFlowRecord(
                        contract_id=contract.contract_id,
                        flow_type=CashFlowType.ELEMENT_PAYMENT,
                        direction=direction,
                        element=pe.element,
                        sample_id=unit.sample_id,
                        unit_price=pe.base_price,
                        unit=pe.unit.value,
                        amount=payment,
                    ))
                elif pe.unit == UnitType.CNY_PER_METAL_TON:
                    attr = _ELEMENT_ATTR.get(pe.element)
                    if attr is None:
                        raise ValueError(f"未知计价元素：{pe.element}")
                    assay_grade: Decimal | None = getattr(assay, attr, None)
                    if assay_grade is None:
                        raise ValueError(
                            f"样号 {unit.sample_id} 化验单缺少元素 {pe.element} 的品位数据"
                        )
                    metal_qty = calc_metal_quantity(dry_weight, assay_grade, Decimal("0"))
                    payment = calc_element_payment(metal_qty, pe.base_price)
                    records.append(CashFlowRecord(
                        contract_id=contract.contract_id,
                        flow_type=CashFlowType.ELEMENT_PAYMENT,
                        direction=direction,
                        element=pe.element,
                        sample_id=unit.sample_id,
                        dry_weight=dry_weight,
                        metal_quantity=metal_qty,
                        unit_price=pe.base_price,
                        unit=pe.unit.value,
                        amount=payment,
                    ))
                else:
                    raise NotImplementedError(
                        f"FIXED_PRICE 不支持单位 {pe.unit}，仅支持元/吨 和 元/金属吨"
                    )

            elif pe.formula_type == FormulaType.GRADE_DEDUCTION:
                # 品位扣减公式
                attr = _ELEMENT_ATTR.get(pe.element)
                if attr is None:
                    raise ValueError(f"未知计价元素：{pe.element}")
                assay_grade = getattr(assay, attr, None)
                if assay_grade is None:
                    raise ValueError(
                        f"样号 {unit.sample_id} 化验单缺少元素 {pe.element} 的品位数据"
                    )

                metal_qty = calc_metal_quantity(dry_weight, assay_grade, pe.grade_deduction)
                payment = calc_element_payment(metal_qty, pe.base_price)

                records.append(CashFlowRecord(
                    contract_id=contract.contract_id,
                    flow_type=CashFlowType.ELEMENT_PAYMENT,
                    direction=direction,
                    element=pe.element,
                    sample_id=unit.sample_id,
                    dry_weight=dry_weight,
                    metal_quantity=metal_qty,
                    unit_price=pe.base_price,
                    unit=pe.unit.value,
                    amount=payment,
                ))

            else:
                raise NotImplementedError(
                    f"不支持公式类型 {pe.formula_type}，元素 {pe.element}"
                )

    # 杂质扣款
    for imp in contract_pricing.impurity_deductions:
        attr = _ELEMENT_ATTR.get(imp.element)
        if attr is None:
            raise ValueError(f"未知杂质元素：{imp.element}")
        for unit in batch_view.batch_units:
            grade: Decimal | None = getattr(unit.assay_report, attr, None)
            if grade is None:
                continue
            tier = find_impurity_tier(grade, imp.tiers)
            if tier is None:
                continue
            amount = calc_impurity_amount(unit.total_wet_weight, tier.rate)
            records.append(CashFlowRecord(
                contract_id=contract.contract_id,
                flow_type=CashFlowType.IMPURITY_DEDUCTION,
                direction=CashFlowDirection.EXPENSE,
                element=imp.element,
                sample_id=unit.sample_id,
                amount=amount,
            ))

    # 化验费（若合同约定我方承担）
    if contract_pricing.assay_fee_total is not None:
        records.append(CashFlowRecord(
            contract_id=contract.contract_id,
            flow_type=CashFlowType.ASSAY_FEE,
            direction=CashFlowDirection.EXPENSE,
            amount=contract_pricing.assay_fee_total,
        ))

    return records


# ══════════════════════════════════════════════════════════════
# 新结算明细函数（输出 SettlementItemRecord，含完整计价元数据）
# ══════════════════════════════════════════════════════════════

def generate_settlement_items(
    batch_view: BatchView,
    contract_pricing: ContractPricing,
) -> list[SettlementItemRecord]:
    """
    遍历 batch_units × pricing_elements，生成 SettlementItemRecord 列表。

    每条记录内嵌完整计价参数（计价基准、基准价来源、单价公式）。
    杂质扣款行：备注字段记录档位说明。

    Args:
        batch_view:        M3C 串联输出的批次视图
        contract_pricing:  合同计价规则

    Returns:
        SettlementItemRecord 列表，先元素货款（按 batch_unit 顺序），后杂质扣款
    """
    contract = batch_view.contract
    direction = (
        SettlementDirection.EXPENSE
        if contract.direction == "采购"
        else SettlementDirection.INCOME
    )

    items: list[SettlementItemRecord] = []

    for unit in batch_view.batch_units:
        assay = unit.assay_report
        wet_weight = unit.total_wet_weight

        if assay.h2o_pct is None:
            raise ValueError(
                f"样号 {unit.sample_id} 化验单缺少 h2o_pct，无法计算干重"
            )

        dry_weight = calc_dry_weight(wet_weight, assay.h2o_pct)

        for pe in contract_pricing.pricing_elements:
            if pe.price_source_type != PriceSourceType.FIXED:
                raise NotImplementedError(
                    f"仅支持 fixed 基准价，元素 {pe.element} 使用了 {pe.price_source_type}"
                )

            if pe.formula_type == FormulaType.FIXED_PRICE:
                if pe.unit == UnitType.CNY_PER_TON:
                    payment = (wet_weight * pe.base_price).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                    items.append(SettlementItemRecord(
                        contract_id=contract.contract_id,
                        sample_id=unit.sample_id,
                        row_type=SettlementRowType.ELEMENT_PAYMENT,
                        direction=direction,
                        element=pe.element,
                        pricing_basis=PricingBasis.WET_WEIGHT,
                        price_source=PriceSource.FIXED,
                        price_formula=PriceFormula.FIXED_PRICE,
                        wet_weight=wet_weight,
                        h2o_pct=assay.h2o_pct,
                        unit_price=pe.base_price,
                        unit=pe.unit.value,
                        amount=payment,
                    ))

                elif pe.unit == UnitType.CNY_PER_DRY_TON:
                    payment = (dry_weight * pe.base_price).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                    items.append(SettlementItemRecord(
                        contract_id=contract.contract_id,
                        sample_id=unit.sample_id,
                        row_type=SettlementRowType.ELEMENT_PAYMENT,
                        direction=direction,
                        element=pe.element,
                        pricing_basis=PricingBasis.DRY_WEIGHT,
                        price_source=PriceSource.FIXED,
                        price_formula=PriceFormula.FIXED_PRICE,
                        wet_weight=wet_weight,
                        h2o_pct=assay.h2o_pct,
                        dry_weight=dry_weight,
                        unit_price=pe.base_price,
                        unit=pe.unit.value,
                        amount=payment,
                    ))

                elif pe.unit == UnitType.CNY_PER_METAL_TON:
                    attr = _ELEMENT_ATTR.get(pe.element)
                    if attr is None:
                        raise ValueError(f"未知计价元素：{pe.element}")
                    assay_grade: Decimal | None = getattr(assay, attr, None)
                    if assay_grade is None:
                        raise ValueError(
                            f"样号 {unit.sample_id} 化验单缺少元素 {pe.element} 的品位数据"
                        )
                    metal_qty = calc_metal_quantity(dry_weight, assay_grade, Decimal("0"))
                    payment = calc_element_payment(metal_qty, pe.base_price)
                    items.append(SettlementItemRecord(
                        contract_id=contract.contract_id,
                        sample_id=unit.sample_id,
                        row_type=SettlementRowType.ELEMENT_PAYMENT,
                        direction=direction,
                        element=pe.element,
                        pricing_basis=PricingBasis.METAL_QUANTITY,
                        price_source=PriceSource.FIXED,
                        price_formula=PriceFormula.FIXED_PRICE,
                        wet_weight=wet_weight,
                        h2o_pct=assay.h2o_pct,
                        dry_weight=dry_weight,
                        assay_grade=assay_grade,
                        grade_deduction_val=Decimal("0"),
                        effective_grade=assay_grade,
                        metal_quantity=metal_qty,
                        unit_price=pe.base_price,
                        unit=pe.unit.value,
                        amount=payment,
                    ))
                else:
                    raise NotImplementedError(
                        f"FIXED_PRICE 不支持单位 {pe.unit}"
                    )

            elif pe.formula_type == FormulaType.GRADE_DEDUCTION:
                attr = _ELEMENT_ATTR.get(pe.element)
                if attr is None:
                    raise ValueError(f"未知计价元素：{pe.element}")
                assay_grade = getattr(assay, attr, None)
                if assay_grade is None:
                    raise ValueError(
                        f"样号 {unit.sample_id} 化验单缺少元素 {pe.element} 的品位数据"
                    )
                eff_grade = assay_grade - pe.grade_deduction
                metal_qty = calc_metal_quantity(dry_weight, assay_grade, pe.grade_deduction)
                payment = calc_element_payment(metal_qty, pe.base_price)
                items.append(SettlementItemRecord(
                    contract_id=contract.contract_id,
                    sample_id=unit.sample_id,
                    row_type=SettlementRowType.ELEMENT_PAYMENT,
                    direction=direction,
                    element=pe.element,
                    pricing_basis=PricingBasis.METAL_QUANTITY,
                    price_source=PriceSource.FIXED,
                    price_formula=PriceFormula.GRADE_DEDUCTION,
                    wet_weight=wet_weight,
                    h2o_pct=assay.h2o_pct,
                    dry_weight=dry_weight,
                    assay_grade=assay_grade,
                    grade_deduction_val=pe.grade_deduction,
                    effective_grade=eff_grade,
                    metal_quantity=metal_qty,
                    unit_price=pe.base_price,
                    unit=pe.unit.value,
                    amount=payment,
                ))

            else:
                raise NotImplementedError(
                    f"不支持公式类型 {pe.formula_type}，元素 {pe.element}"
                )

    # 杂质扣款
    for imp in contract_pricing.impurity_deductions:
        attr = _ELEMENT_ATTR.get(imp.element)
        if attr is None:
            raise ValueError(f"未知杂质元素：{imp.element}")
        for unit in batch_view.batch_units:
            grade: Decimal | None = getattr(unit.assay_report, attr, None)
            if grade is None:
                continue
            tier = find_impurity_tier(grade, imp.tiers)
            if tier is None:
                continue
            amount = calc_impurity_amount(unit.total_wet_weight, tier.rate)
            # 档位说明
            if tier.upper is None:
                tier_note = f"{imp.element} ≥{tier.lower}% → {tier.rate}元/吨"
            else:
                tier_note = f"{imp.element} [{tier.lower}%, {tier.upper}%) → {tier.rate}元/吨"
            items.append(SettlementItemRecord(
                contract_id=contract.contract_id,
                sample_id=unit.sample_id,
                row_type=SettlementRowType.IMPURITY_DEDUCTION,
                direction=SettlementDirection.EXPENSE,
                element=imp.element,
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
