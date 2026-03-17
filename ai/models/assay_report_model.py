"""
化验单数据模型

两层设计：
- AssayReportExtract: LLM 提取层，如实记录 OCR 看到的原始数据
- AssayReportBitableRecord: Bitable 写入层，字段名与 schema.yaml 完全对应

注意：此模块的 AssayReportBitableRecord 是 ai 层的 Bitable 写入模型，
与 core/models/batch.py 的 AssayReportRecord（精算模型）是不同层的不同类：
前者用 float（写卡片/Bitable），后者用 Decimal（结算计算）。
"""

from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field


# ── 品位字段清洗 ──────────────────────────────────────────────

def _parse_grade_str(value) -> Optional[float]:
    """
    清洗品位值：接受 float、int、或带单位的字符串

    处理 LLM 常见的脏输出：
    - "28.5"        → 28.5
    - "28.5%"       → 28.5  （去掉百分号）
    - "1.25g/t"     → 1.25  （去掉单位）
    - "N/D"         → None  （未检出）
    - "未检出"      → None
    - "—" / "-"    → None
    - "<0.01"       → 0.01  （取界限值）
    - ""            → None
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip()
        if not s or s in ("-", "—", "N/D", "n/d", "ND", "nd", "N.D.", "未检出", "未测", "无"):
            return None
        # "<0.01" 等边界值：取界限数字
        lt_m = re.match(r"^[<＜](\d+\.?\d*)$", s)
        if lt_m:
            return float(lt_m.group(1))
        # 去掉百分号、空格、常见单位
        cleaned = re.sub(r"[%％\s]", "", s)
        cleaned = re.sub(r"(?i)(g/t|ppm)$", "", cleaned)
        cleaned = cleaned.replace(",", "")
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _normalize_date(date_str: str) -> str:
    """日期字符串标准化为 YYYY-MM-DD"""
    if not date_str:
        return ""
    m = re.match(r"(\d{4})[年\-/.](\d{1,2})[月\-/.](\d{1,2})", date_str)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y:04d}-{mo:02d}-{d:02d}"
    return date_str


# ── LLM 提取层 ────────────────────────────────────────────────

class AssayReportExtract(BaseModel):
    """
    LLM 提取的化验单原始数据

    设计原则：让 LLM 如实提取看到的内容，不推理、不换算。
    品位字段用 Optional[str] 接收，容忍 "28.5%" / "1.25g/t" / "未检出" 等脏输出。
    换算和清洗逻辑由确定性代码（_parse_grade_str）完成。
    """
    样号: str = Field(
        default="",
        description="样品编号/样号/Sample No，如 S2025-001、YH-240301",
    )
    化验类型: str = Field(
        default="结算化验",
        description="检测类型：快速摸底 或 结算化验，默认填 结算化验",
    )
    是否结算化验单: bool = Field(
        default=True,
        description="该报告是否作为结算依据：正式化验单填 true，摸底化验填 false",
    )
    化验日期: Optional[str] = Field(
        default=None,
        description="报告日期/检验日期，格式如 2025-04-03 或 2025年4月3日",
    )
    化验机构: str = Field(
        default="",
        description="检测单位/化验室名称，如 XX矿产品检测中心",
    )

    # 品位字段 — 用 str 接收，容忍 LLM 带单位的输出
    Cu_pct: Optional[str] = Field(
        default=None,
        description="铜含量（Cu%），只填数字，如 28.50，未检出或不含此元素填空",
    )
    Au_gt: Optional[str] = Field(
        default=None,
        description="金含量（Au g/t），只填数字，如 1.25，未检出填空",
    )
    Ag_gt: Optional[str] = Field(
        default=None,
        description="银含量（Ag g/t），只填数字，如 120.5，未检出填空",
    )
    Pb_pct: Optional[str] = Field(
        default=None,
        description="铅含量（Pb%），只填数字，如 0.35，未检出填空",
    )
    Zn_pct: Optional[str] = Field(
        default=None,
        description="锌含量（Zn%），只填数字，如 0.28，未检出填空",
    )
    S_pct: Optional[str] = Field(
        default=None,
        description="硫含量（S%），只填数字，如 28.60，未检出填空",
    )
    As_pct: Optional[str] = Field(
        default=None,
        description="砷含量（As%），只填数字，如 0.40，未检出填空",
    )
    H2O_pct: Optional[str] = Field(
        default=None,
        description="水分（H₂O%），只填数字，如 9.50，未检出填空",
    )

    confidence: Optional[str] = Field(
        default="0.5",
        description="对整体提取结果的置信度，0.0-1.0。文字模糊或字段大量缺失给低分",
    )
    备注: str = Field(
        default="",
        description="任何不确定的地方、异常情况、或需要人工关注的提示",
    )

    @property
    def confidence_float(self) -> float:
        v = _parse_grade_str(self.confidence)
        if v is not None and 0.0 <= v <= 1.0:
            return v
        return 0.5


# ── Bitable 写入层 ────────────────────────────────────────────

class AssayReportBitableRecord(BaseModel):
    """
    Bitable 写入用的化验单记录

    字段名与 schema.yaml 中 assay_reports 表字段对应（通过 record_to_dict 映射）。
    数值字段用 Optional[float]（ai 层不需要 Decimal 精度）。
    """
    样号: str = ""
    化验类型: str = "结算化验"
    是否结算化验单: bool = True
    化验日期: str = ""
    化验机构: str = ""
    Cu_pct: Optional[float] = None
    Au_gt: Optional[float] = None
    Ag_gt: Optional[float] = None
    Pb_pct: Optional[float] = None
    Zn_pct: Optional[float] = None
    S_pct: Optional[float] = None
    As_pct: Optional[float] = None
    H2O_pct: Optional[float] = None


# ── 层间转换 ──────────────────────────────────────────────────

def extract_to_record(extract: AssayReportExtract) -> AssayReportBitableRecord:
    """LLM 提取结果 → Bitable 写入记录（确定性换算，不依赖 LLM）"""
    return AssayReportBitableRecord(
        样号=extract.样号,
        化验类型=extract.化验类型,
        是否结算化验单=extract.是否结算化验单,
        化验日期=_normalize_date(extract.化验日期) if extract.化验日期 else "",
        化验机构=extract.化验机构,
        Cu_pct=_parse_grade_str(extract.Cu_pct),
        Au_gt=_parse_grade_str(extract.Au_gt),
        Ag_gt=_parse_grade_str(extract.Ag_gt),
        Pb_pct=_parse_grade_str(extract.Pb_pct),
        Zn_pct=_parse_grade_str(extract.Zn_pct),
        S_pct=_parse_grade_str(extract.S_pct),
        As_pct=_parse_grade_str(extract.As_pct),
        H2O_pct=_parse_grade_str(extract.H2O_pct),
    )


def record_to_dict(record: AssayReportBitableRecord) -> dict:
    """
    转为 dict，用于卡片显示和 Bitable 写入。

    key 与 schema.yaml 中 assay_reports 表的 Bitable 字段名完全一致。
    None 值输出为空字符串，防止 Bitable 写入时出现字符串 "None"。
    """
    def _fmt(v: Optional[float]) -> str:
        return str(v) if v is not None else ""

    return {
        "样号": record.样号,
        "化验类型": record.化验类型,
        "是否结算化验单": record.是否结算化验单,
        "化验日期": record.化验日期,
        "化验机构": record.化验机构,
        "Cu%": _fmt(record.Cu_pct),
        "Au(g/t)": _fmt(record.Au_gt),
        "Ag(g/t)": _fmt(record.Ag_gt),
        "Pb%": _fmt(record.Pb_pct),
        "Zn%": _fmt(record.Zn_pct),
        "S%": _fmt(record.S_pct),
        "As%": _fmt(record.As_pct),
        "H2O%": _fmt(record.H2O_pct),
    }


__all__ = [
    "AssayReportExtract",
    "AssayReportBitableRecord",
    "extract_to_record",
    "record_to_dict",
    "_parse_grade_str",
    "_normalize_date",
]
