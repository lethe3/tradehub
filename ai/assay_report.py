"""
化验单提取 - 对外接口

parse_ocr_to_assay_report(ocr_text) → AssayReportBitableRecord
assay_report_to_dict(record) → dict（用于卡片显示和 Bitable 写入）
"""

import logging

from .extractor import extract
from .models.assay_report_model import (
    AssayReportExtract,
    AssayReportBitableRecord,
    extract_to_record,
    record_to_dict,
)

logger = logging.getLogger(__name__)

_ASSAY_CONTEXT = (
    "这是一张矿产品化验报告单（检验报告/化验单），不是磅单。"
    "不要寻找毛重/皮重/净重字段。"
    "重点提取：样号、各元素品位（Cu%/Au g/t/Ag g/t/Pb%/Zn%/S%/As%）、水分（H₂O%）、化验日期、化验机构。"
)


def parse_ocr_to_assay_report(ocr_text: str) -> AssayReportBitableRecord:
    """
    从 OCR 文本解析化验单数据

    流程：OCR 文本 → LLM 结构化提取 → 品位清洗 → AssayReportBitableRecord

    Args:
        ocr_text: OCR 识别的文本

    Returns:
        AssayReportBitableRecord 对象（可直接用于卡片显示和 Bitable 写入）
    """
    raw_extract = extract(
        text=ocr_text,
        model=AssayReportExtract,
        context=_ASSAY_CONTEXT,
    )

    logger.info(
        f"化验单提取结果: 样号={raw_extract.样号}, "
        f"Cu%={raw_extract.Cu_pct}, H2O%={raw_extract.H2O_pct}, "
        f"confidence={raw_extract.confidence}"
    )

    if raw_extract.备注:
        logger.warning(f"提取备注: {raw_extract.备注}")

    return extract_to_record(raw_extract)


def assay_report_to_dict(record: AssayReportBitableRecord) -> dict:
    """将 AssayReportBitableRecord 转为 dict（用于卡片显示和 Bitable 写入）"""
    return record_to_dict(record)


__all__ = [
    "AssayReportBitableRecord",
    "parse_ocr_to_assay_report",
    "assay_report_to_dict",
]
