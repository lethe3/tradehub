"""
磅单数据模型

两层设计：
- WeighTicketExtract: LLM 提取层，如实记录 OCR 看到的原始数据
- WeighTicketRecord: 业务层，转换后可直接写入 Bitable
"""

import re
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, model_validator


class WeightUnit(str, Enum):
    """重量单位"""
    KG = "kg"
    TON = "吨"
    UNKNOWN = "未知"


def _parse_weight_str(value) -> Optional[float]:
    """
    清洗重量值：接受 float、int、或带单位的字符串

    处理 LLM 常见的脏输出：
    - "33340"       → 33340.0
    - "50.225(t)"   → 50.225
    - "18,800 kg"   → 18800.0
    - "15.16吨"     → 15.16
    - ""            → None
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        # 去除单位和括号：(t), kg, 吨, 千克, t 等
        cleaned = re.sub(r'[()（）\s]', '', s)
        cleaned = re.sub(r'(kg|KG|吨|千克|公斤|t|T)$', '', cleaned)
        cleaned = cleaned.replace(',', '')
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


class WeighTicketExtract(BaseModel):
    """
    LLM 提取的磅单原始数据

    设计原则：让 LLM 如实提取看到的内容，不做推理或换算。
    重量字段用 str 接收（LLM 常返回带单位的字符串），换算逻辑由确定性代码完成。
    """
    # 基本信息
    磅单编号: str = Field(
        default="",
        description="磅单号/流水号/编号，如 A2025040300001、PD-2024-001、No.12345",
    )
    货物品名: str = Field(
        default="",
        description="货物名称/物品名称/品名，如 黄铜块、铜精矿、废铜、铜杆、铅锭",
    )
    过磅日期: Optional[str] = Field(
        default=None,
        description="过磅日期/称重日期，格式如 2025-04-03 或 2025/04/03 或 2025年4月3日",
    )

    # 重量 - 用 str 接收，容忍 LLM 带单位的输出如 "33340" 或 "50.225(t)"
    毛重: Optional[str] = Field(
        default=None,
        description="毛重/总重的数值，只填数字，如 33340 或 50.225",
    )
    皮重: Optional[str] = Field(
        default=None,
        description="皮重/空重/车重的数值，只填数字，如 14540 或 14.845",
    )
    净重: Optional[str] = Field(
        default=None,
        description="净重的数值，只填数字，如 18800 或 35.380",
    )
    重量单位: WeightUnit = Field(
        default=WeightUnit.KG,
        description="重量的单位：kg 或 吨。如果单据上写的是千克/公斤/kg 则选 kg，如果写的是吨/t 则选 吨",
    )

    # 辅助信息（不写入 Bitable，但有助于人工审核）
    车牌号: str = Field(
        default="",
        description="车牌号码，如 皖A12345",
    )
    供应商: str = Field(
        default="",
        description="供货单位/客户名称/交易对手",
    )

    # 置信度
    confidence: Optional[str] = Field(
        default="0.5",
        description="对整体提取结果的置信度，0.0-1.0。如果文字模糊、格式异常、多个值矛盾则给低分",
    )
    备注: str = Field(
        default="",
        description="任何不确定的地方、异常情况、或需要人工关注的提示",
    )

    @property
    def 毛重_float(self) -> Optional[float]:
        return _parse_weight_str(self.毛重)

    @property
    def 皮重_float(self) -> Optional[float]:
        return _parse_weight_str(self.皮重)

    @property
    def 净重_float(self) -> Optional[float]:
        return _parse_weight_str(self.净重)

    @property
    def confidence_float(self) -> float:
        v = _parse_weight_str(self.confidence)
        if v is not None and 0.0 <= v <= 1.0:
            return v
        return 0.5

    @model_validator(mode="after")
    def check_weight_consistency(self):
        """校验：如果毛重和皮重都有，净重应该 ≈ 毛重 - 皮重"""
        gross = self.毛重_float
        tare = self.皮重_float
        net = self.净重_float
        if gross is not None and tare is not None and net is not None:
            expected = gross - tare
            diff = abs(net - expected)
            tolerance = max(abs(expected) * 0.01, 10)
            if diff > tolerance:
                self.备注 += f" ⚠️ 净重({net})≠ 毛重({gross})-皮重({tare})={expected}"

        # 从重量字符串中推断单位
        for raw in [self.毛重, self.皮重, self.净重]:
            if raw and isinstance(raw, str):
                lower = raw.lower()
                if '(t)' in lower or '吨' in lower:
                    self.重量单位 = WeightUnit.TON
                    break
        return self


class WeighTicketRecord(BaseModel):
    """
    Bitable 写入用的磅单记录

    字段名与 schema.yaml 中磅单表完全对应
    """
    磅单编号: str = Field(default="")
    货物品名: str = Field(default="")
    净重吨: float = Field(default=0.0, alias="净重(吨)")
    过磅日期: str = Field(default="")

    class Config:
        populate_by_name = True


def extract_to_record(extract: WeighTicketExtract) -> WeighTicketRecord:
    """
    将 LLM 提取结果转换为 Bitable 记录

    这里做确定性的单位换算，不依赖 LLM
    """
    net_weight_ton = _calc_net_weight_ton(extract)
    date_str = _normalize_date(extract.过磅日期) if extract.过磅日期 else ""

    return WeighTicketRecord(
        磅单编号=extract.磅单编号,
        货物品名=extract.货物品名,
        **{"净重(吨)": net_weight_ton},
        过磅日期=date_str,
    )


def _calc_net_weight_ton(extract: WeighTicketExtract) -> float:
    """
    计算净重（吨）

    优先用提取的净重，否则用毛重-皮重。
    根据单位做换算。
    """
    net = extract.净重_float
    if net is None:
        gross = extract.毛重_float
        tare = extract.皮重_float
        if gross is not None and tare is not None:
            net = gross - tare

    if net is None or net <= 0:
        return 0.0

    if extract.重量单位 == WeightUnit.KG:
        return round(net / 1000, 3)
    elif extract.重量单位 == WeightUnit.TON:
        return round(net, 3)
    else:
        # 未知单位：>100 大概率是 kg
        if net > 100:
            return round(net / 1000, 3)
        return round(net, 3)


def _normalize_date(date_str: str) -> str:
    """日期字符串标准化为 YYYY-MM-DD"""
    if not date_str:
        return ""
    m = re.match(r"(\d{4})[年\-/.](\d{1,2})[月\-/.](\d{1,2})", date_str)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y:04d}-{mo:02d}-{d:02d}"
    return date_str


def record_to_dict(record: WeighTicketRecord) -> dict:
    """转为 dict，用于卡片显示和 Bitable 写入"""
    return {
        "磅单编号": record.磅单编号,
        "货物品名": record.货物品名,
        "净重(吨)": str(record.净重吨),
        "过磅日期": record.过磅日期,
    }


__all__ = [
    "WeightUnit",
    "WeighTicketExtract",
    "WeighTicketRecord",
    "extract_to_record",
    "record_to_dict",
]
