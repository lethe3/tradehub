"""
假数据生成器（用于端到端流程验证，不依赖 OCR）

生成铜精矿固定计价场景的假数据，写入飞书 Bitable。
"""
from __future__ import annotations

import random
import string
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from core.models.pricing import ContractPricing, FormulaType, PricingElement, PriceSourceType, UnitType


def _today_ms() -> int:
    """当前时间戳，毫秒"""
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _rand_suffix(n: int = 4) -> str:
    return "".join(random.choices(string.digits, k=n))


def generate_fake_contract() -> dict[str, Any]:
    """生成一条假合同记录（字段名 = Bitable 列名）。

    仅包含合同本体字段（不含计价细节，计价规则由 generate_fake_contract_pricing 单独生成）。
    """
    contract_no = f"HT-MOCK-{date.today().strftime('%Y%m%d')}-{_rand_suffix()}"
    return {
        "合同编号": contract_no,
        "我方主体": "我司A",
        "交易对手": "测试供应商",
        "签订日期": _today_ms(),
        "合同方向": "采购",
        "化验费": 2000.0,
        "化验费承担方": "我方",
    }


def generate_fake_contract_pricing(contract_id: str) -> ContractPricing:
    """生成假合同计价规则（用于结算测试，不写入 Bitable）。

    Args:
        contract_id: 合同 Bitable record_id
    """
    unit_types = [UnitType.CNY_PER_TON, UnitType.CNY_PER_METAL_TON]
    unit_type = random.choice(unit_types)
    base_price = Decimal(str(round(random.uniform(55000, 75000), 0)))
    grade_deduction = Decimal("1.0") if unit_type == UnitType.CNY_PER_METAL_TON else Decimal("0")

    pe = PricingElement(
        element="Cu",
        price_source_type=PriceSourceType.FIXED,
        base_price=base_price,
        unit=unit_type,
        formula_type=FormulaType.FIXED_PRICE,
        grade_deduction=grade_deduction,
    )
    return ContractPricing(
        contract_id=contract_id,
        pricing_elements=[pe],
        assay_fee_total=Decimal("2000"),  # 化验费我方承担
    )


def generate_fake_weigh_tickets(contract_record_id: str, count: int = 2) -> list[dict[str, Any]]:
    """生成若干条假磅单记录。

    Args:
        contract_record_id: 合同 record_id（关联合同字段）
        count: 生成条数，默认 2
    """
    tickets = []
    for _ in range(count):
        gross = round(random.uniform(30000, 40000), 0)      # 毛重 kg
        tare = round(random.uniform(12000, 16000), 0)       # 皮重 kg
        net_kg = gross - tare
        net_ton = round(net_kg / 1000, 3)
        sample_id = f"S-MOCK-{date.today().strftime('%Y%m%d')}-{_rand_suffix()}"
        tickets.append({
            "磅单编号": f"PD-MOCK-{_rand_suffix()}",
            "货物品名": "铜精矿",
            "样号": sample_id,
            "车号": f"皖A{_rand_suffix(5)}",
            "毛重": gross / 1000,   # 吨
            "皮重": tare / 1000,    # 吨
            "净重(吨)": net_ton,
            "过磅日期": _today_ms(),
            "_contract_record_id": contract_record_id,   # 内部使用，不直接写字段
            "_sample_id": sample_id,
        })
    return tickets


def generate_fake_assay_report(sample_id: str, contract_record_id: str) -> dict[str, Any]:
    """生成一条假化验单记录。

    Args:
        sample_id: 样号（与磅单一致）
        contract_record_id: 合同 record_id
    """
    cu_pct = round(random.uniform(18.0, 28.0), 2)
    h2o_pct = round(random.uniform(8.0, 12.0), 2)
    return {
        "关联合同": contract_record_id,
        "样号": sample_id,
        "化验类型": "结算化验",
        "是否结算化验单": True,
        "Cu%": cu_pct,
        "Au(g/t)": round(random.uniform(0.5, 2.0), 3),
        "Ag(g/t)": round(random.uniform(50, 150), 1),
        "Pb%": round(random.uniform(0.1, 0.5), 2),
        "Zn%": round(random.uniform(0.1, 0.5), 2),
        "As%": round(random.uniform(0.01, 0.5), 3),
        "H2O%": h2o_pct,
        "化验日期": _today_ms(),
        "化验机构": "MOCK检测中心",
    }
