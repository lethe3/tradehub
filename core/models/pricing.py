"""
计价规则模型

对应合同摘录卡（Obsidian YAML）中的计价规则。
两轴分离：轴一（基准价来源）+ 轴二（计价公式）。

纯 Pydantic，无外部依赖。
阶段二仅支持轴一=固定价、轴二=品位扣减（铜精矿标准计价）。
均价/点价留接口，但 M3D-1 不实现。
"""
from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class PriceSourceType(str, Enum):
    """基准价来源（轴一）"""
    FIXED = "fixed"      # 合同固定基准价（阶段二实现）
    AVERAGE = "average"  # 均价（留接口，暂不实现）
    SPOT = "spot"        # 点价（留接口，暂不实现）


class FormulaType(str, Enum):
    """计价公式类型（轴二）"""
    FIXED_PRICE = "fixed_price"       # 固定单价（与品位无关）
    GRADE_DEDUCTION = "grade_deduction"  # 品位扣减：有效品位 = 品位 - 扣减量
    COEFFICIENT = "coefficient"       # 系数：有效品位 = 品位 × 系数（留接口）
    SEGMENTED = "segmented"           # 分段（留接口）


class UnitType(str, Enum):
    """单价单位"""
    CNY_PER_TON = "元/吨"              # 以湿重为基数
    CNY_PER_DRY_TON = "元/干吨"        # 以干重为基数
    CNY_PER_METAL_TON = "元/金属吨"    # 以金属量为基数


class PricingElement(BaseModel):
    """单个计价元素的完整规则

    示例（铜精矿-铜）：
        element = "Cu"
        price_source_type = "fixed"
        base_price = 65000       # 元/金属吨
        unit = "元/金属吨"
        formula_type = "grade_deduction"
        grade_deduction = Decimal("1.0")   # 有效 Cu% = 化验 Cu% - 1.0%
    """
    element: str                            # Cu / Au / Ag / Pb / Zn / 无
    # 轴一：基准价
    price_source_type: PriceSourceType = PriceSourceType.FIXED
    base_price: Decimal                     # 基准价数值
    # 轴二：计价公式
    formula_type: FormulaType = FormulaType.GRADE_DEDUCTION
    unit: UnitType = UnitType.CNY_PER_METAL_TON
    # 品位扣减参数（formula_type = grade_deduction 时有效）
    grade_deduction: Decimal = Decimal("0")  # 品位扣减量（百分点）
    # 系数参数（formula_type = coefficient 时有效，暂留接口）
    grade_coefficient: Optional[Decimal] = None  # 有效品位 = 品位 × 系数

    def effective_grade(self, assay_grade: Decimal) -> Decimal:
        """计算有效品位（百分数，如 17.50 表示 17.50%）"""
        if self.formula_type == FormulaType.GRADE_DEDUCTION:
            return assay_grade - self.grade_deduction
        if self.formula_type == FormulaType.COEFFICIENT:
            if self.grade_coefficient is None:
                raise ValueError(f"系数计价需要设置 grade_coefficient，元素: {self.element}")
            return assay_grade * self.grade_coefficient
        raise NotImplementedError(f"公式类型 {self.formula_type} 暂未实现")


class ImpurityDeductionTier(BaseModel):
    """杂质扣款阶梯（M3D-2 使用）"""
    lower: Decimal   # 本档起点（含），单位：%
    upper: Decimal   # 本档终点（不含，最高档为 None）
    rate: Decimal    # 扣款金额，单位：元/吨（湿重）

    upper_open: bool = True  # 上限是否开区间（默认开区间）


class ImpurityDeduction(BaseModel):
    """某一杂质的扣款规则（阶梯累进，M3D-2）"""
    element: str                           # As / S / Pb / Zn 等
    tiers: list[ImpurityDeductionTier]     # 按 lower 升序排列


class ContractPricing(BaseModel):
    """合同计价规则（从合同摘录卡 YAML 加载）

    对应 tests/fixtures/mock_documents/scenario_01/contract.yaml 中的 pricing 节
    和 Obsidian Work/Contracts/*.yaml 中的 pricing 节。
    """
    contract_id: str                          # 与 ContractRecord.contract_id 对应
    dry_weight_formula: str = "wet * (1 - h2o)"  # 干重公式（可读说明）
    pricing_elements: list[PricingElement] = []   # 计价元素列表
    impurity_deductions: list[ImpurityDeduction] = []  # 杂质扣款列表
    freight_rate: Optional[Decimal] = None    # 运费单价（元/吨，如我方承担）
    assay_fee_total: Optional[Decimal] = None  # 化验费总额（如我方承担）
