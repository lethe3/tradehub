"""
文档类型分类器

classify_doc_type(ocr_text) → "weigh_ticket" | "assay_report"

两级判断：
1. 规则优先：关键词计分，达到阈值直接返回（零 LLM 成本）
2. LLM fallback：规则无法判断时调用 Instructor（可通过 use_llm_fallback=False 禁用）

无法判断时降级到 "weigh_ticket"（保持现有行为，记录 warning）。
"""

from __future__ import annotations

import logging
from typing import Literal, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DocType = Literal["weigh_ticket", "assay_report"]

# ── 关键词配置 ────────────────────────────────────────────────

# 化验单特征词 → 分值
_ASSAY_KEYWORDS: dict[str, int] = {
    "化验报告": 3,
    "检验报告": 3,
    "化验单": 3,
    "检验单": 2,
    "检测报告": 3,
    "分析报告": 2,
    "品位": 2,
    "含量": 1,
    "Cu%": 2,
    "Au(g/t)": 2,
    "Ag(g/t)": 2,
    "g/t": 1,
    "化验": 1,
    "矿样": 2,
    "样品编号": 2,
    "样号": 1,
    "水分": 1,
    "H2O": 1,
    "H₂O": 1,
    "As%": 1,
    "Pb%": 1,
    "Zn%": 1,
    "S%": 1,
}

# 磅单特征词 → 分值
_WEIGH_KEYWORDS: dict[str, int] = {
    "磅单": 3,
    "过磅": 2,
    "称重": 2,
    "毛重": 2,
    "皮重": 2,
    "净重": 2,
    "车牌": 2,
    "车号": 1,
    "吨位": 1,
    "磅房": 2,
    "地磅": 2,
    "扣重": 1,
}

_SCORE_THRESHOLD = 3  # 达到此分值即可确定类型


def _keyword_score(text: str) -> tuple[int, int]:
    """返回 (assay_score, weigh_score)"""
    assay = sum(score for kw, score in _ASSAY_KEYWORDS.items() if kw in text)
    weigh = sum(score for kw, score in _WEIGH_KEYWORDS.items() if kw in text)
    return assay, weigh


# ── LLM fallback 模型 ─────────────────────────────────────────

class _DocTypeClassify(BaseModel):
    doc_type: Literal["weigh_ticket", "assay_report", "unknown"] = Field(
        description=(
            "文档类型：磅单(weigh_ticket)含称重数据(毛重/皮重/净重)；"
            "化验单(assay_report)含品位数据(Cu%/Au g/t等元素含量)；"
            "无法判断填 unknown"
        )
    )
    reason: str = Field(default="", description="判断理由（一句话）")


def _llm_classify(ocr_text: str) -> Optional[DocType]:
    """用 LLM 判断文档类型，失败返回 None"""
    try:
        from ai.extractor import extract as _extract
        result = _extract(
            text=ocr_text[:800],  # 只取前 800 字符，减少 token
            model=_DocTypeClassify,
            context="请判断这段 OCR 文本来自磅单还是化验报告单。",
        )
        logger.debug(f"LLM 分类结果: doc_type={result.doc_type}, reason={result.reason}")
        if result.doc_type in ("weigh_ticket", "assay_report"):
            return result.doc_type
        return None
    except Exception as e:
        logger.warning(f"LLM 分类失败: {e}")
        return None


# ── 公开接口 ──────────────────────────────────────────────────

def classify_doc_type(
    ocr_text: str,
    use_llm_fallback: bool = True,
) -> DocType:
    """
    判断 OCR 文本属于磅单还是化验单

    Args:
        ocr_text: OCR 识别的文本
        use_llm_fallback: 规则无法判断时是否调用 LLM（测试时传 False）

    Returns:
        "weigh_ticket" 或 "assay_report"
    """
    assay_score, weigh_score = _keyword_score(ocr_text)
    logger.debug(f"关键词分数: assay={assay_score}, weigh={weigh_score}")

    # 规则可以确定
    if assay_score >= _SCORE_THRESHOLD and assay_score > weigh_score:
        return "assay_report"
    if weigh_score >= _SCORE_THRESHOLD and weigh_score > assay_score:
        return "weigh_ticket"

    # 规则无法判断 → LLM fallback
    if use_llm_fallback:
        result = _llm_classify(ocr_text)
        if result is not None:
            return result

    # 最终降级：保持现有磅单行为
    logger.warning(
        f"文档类型无法判断（assay={assay_score}, weigh={weigh_score}），"
        f"降级为 weigh_ticket"
    )
    return "weigh_ticket"


__all__ = ["classify_doc_type", "DocType"]
