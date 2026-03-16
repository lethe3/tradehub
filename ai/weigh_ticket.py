"""
磅单提取 - 对外接口（兼容层）

保持 parse_ocr_to_weigh_ticket / weigh_ticket_to_dict 接口不变，
内部改为调用通用提取器 + 磅单模型。
feishu/handler.py 不需要改动。
"""

import logging

from .extractor import extract
from .models.weigh_ticket_model import (
    WeighTicketExtract,
    WeighTicketRecord,
    extract_to_record,
    record_to_dict,
)

logger = logging.getLogger(__name__)

# 保持向后兼容的别名
WeighTicket = WeighTicketRecord


def parse_ocr_to_weigh_ticket(ocr_text: str) -> WeighTicketRecord:
    """
    从 OCR 文本解析磅单数据

    流程：OCR 文本 → LLM 结构化提取 → 单位换算 → WeighTicketRecord

    Args:
        ocr_text: OCR 识别的文本

    Returns:
        WeighTicketRecord 对象（可直接用于卡片显示和 Bitable 写入）
    """
    # Step 1: LLM 结构化提取
    raw_extract = extract(
        text=ocr_text,
        model=WeighTicketExtract,
    )

    logger.info(
        f"磅单提取结果: 编号={raw_extract.磅单编号}, "
        f"净重={raw_extract.净重}{raw_extract.重量单位.value}, "
        f"confidence={raw_extract.confidence}"
    )

    if raw_extract.备注:
        logger.warning(f"提取备注: {raw_extract.备注}")

    # Step 2: 转换为 Bitable 记录（确定性换算）
    record = extract_to_record(raw_extract)

    return record


def weigh_ticket_to_dict(ticket: WeighTicketRecord) -> dict:
    """将 WeighTicketRecord 转为 dict（用于卡片显示）"""
    return record_to_dict(ticket)


# === 高级接口：需要原始提取结果时使用 ===

def parse_ocr_full(ocr_text: str) -> tuple[WeighTicketExtract, WeighTicketRecord]:
    """
    返回完整提取结果（原始 + 转换后）

    用于需要查看置信度、备注、原始重量的场景
    """
    raw_extract = extract(text=ocr_text, model=WeighTicketExtract)
    record = extract_to_record(raw_extract)
    return raw_extract, record


__all__ = [
    "WeighTicket",
    "WeighTicketRecord",
    "parse_ocr_to_weigh_ticket",
    "weigh_ticket_to_dict",
    "parse_ocr_full",
]
