"""
磅单数据模型 - 使用 Pydantic 定义结构
"""

from datetime import date
from typing import Optional
from pydantic import BaseModel, Field


class WeighTicket(BaseModel):
    """磅单数据模型"""
    磅单编号: str = Field(default="", description="磅单号")
    关联合同: str = Field(default="", description="关联合同号")
    货物品名: str = Field(default="", description="物品名称")
    净重吨: float = Field(default=0.0, alias="净重(吨)", description="净重（吨）")
    过磅日期: Optional[date] = Field(default=None, description="过磅日期")

    class Config:
        populate_by_name = True


def parse_ocr_to_weigh_ticket(ocr_text: str) -> WeighTicket:
    """
    从 OCR 文本解析磅单数据

    这是一个简单的基于规则的解析，后续可以用 LLM 增强

    Args:
        ocr_text: OCR 识别的文本

    Returns:
        WeighTicket 对象
    """
    # 简单的正则匹配
    import re

    result = {}

    # 磅单号/流水号
    patterns = [
        r"磅单[号:]?\s*([A-Z0-9\-]+)",
        r"编号[号:]?\s*([A-Z0-9\-]+)",
        r"流水号\s*([A-Z0-9\-]+)",
        r"PD[\-_]?\d+",
    ]
    for p in patterns:
        match = re.search(p, ocr_text, re.IGNORECASE)
        if match:
            result["磅单编号"] = match.group(1)
            break

    # 合同号
    patterns = [
        r"合同[号:]?\s*([A-Z0-9\-]+)",
        r"(HT[\-_]?\d+)",
    ]
    for p in patterns:
        match = re.search(p, ocr_text, re.IGNORECASE)
        if match:
            result["关联合同"] = match.group(1)
            break

    # 货物品名
    for item in ["黄铜块", "铜精矿", "废铜", "铜杆", "铜线"]:
        if item in ocr_text:
            result["货物品名"] = item
            break

    # 净重
    patterns = [
        r"净重[：:]\s*([\d,]+)\s*吨?",
        r"净重\s+(\d+)",
        r"重量[：:]\s*([\d,]+)\s*吨?",
        r"([\d,]+)\s*吨",
    ]
    for p in patterns:
        match = re.search(p, ocr_text, re.IGNORECASE)
        if match:
            try:
                # 移除逗号
                weight_str = match.group(1).replace(",", "")
                result["净重(吨)"] = float(weight_str) / 1000 if float(weight_str) > 1000 else float(weight_str)
            except ValueError:
                pass
            break

    # 日期
    patterns = [
        r"(\d{4})[年\-/](\d{1,2})[月\-/](\d{1,2})",
    ]
    for p in patterns:
        match = re.search(p, ocr_text)
        if match:
            try:
                year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                result["过磅日期"] = f"{year:04d}-{month:02d}-{day:02d}"
            except ValueError:
                pass
            break

    return WeighTicket(**result)


def weigh_ticket_to_dict(ticket: WeighTicket) -> dict:
    """将 WeighTicket 转为 dict（用于卡片显示）"""
    return {
        "磅单编号": ticket.磅单编号,
        "关联合同": ticket.关联合同,
        "货物品名": ticket.货物品名,
        "净重(吨)": str(ticket.净重吨),
        "过磅日期": ticket.过磅日期.isoformat() if ticket.过磅日期 else "",
    }


__all__ = ["WeighTicket", "parse_ocr_to_weigh_ticket", "weigh_ticket_to_dict"]
