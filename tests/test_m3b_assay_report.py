"""
M3B 化验单模型 + 分类器测试

覆盖：
1. _parse_grade_str()：正常值 / 带单位 / 未检出 / 边界值
2. _normalize_date()：多种格式标准化
3. extract_to_record()：完整字段 / 部分字段 / None 处理
4. record_to_dict()：无 "None" 字符串 / 字段名与 schema 一致
5. classify_doc_type()：化验单关键词 / 磅单关键词 / 混合 / 降级行为
   （全部 use_llm_fallback=False，不发起真实 LLM 请求）
"""
from __future__ import annotations

import pytest

from ai.models.assay_report_model import (
    AssayReportExtract,
    AssayReportBitableRecord,
    _parse_grade_str,
    _normalize_date,
    extract_to_record,
    record_to_dict,
)
from ai.classify import classify_doc_type


# ══════════════════════════════════════════════════════════════
# _parse_grade_str
# ══════════════════════════════════════════════════════════════

class TestParseGradeStr:

    def test_plain_number_str(self):
        assert _parse_grade_str("28.50") == pytest.approx(28.50)

    def test_int_input(self):
        assert _parse_grade_str(28) == pytest.approx(28.0)

    def test_float_input(self):
        assert _parse_grade_str(1.25) == pytest.approx(1.25)

    def test_strip_percent(self):
        assert _parse_grade_str("28.5%") == pytest.approx(28.5)

    def test_strip_g_per_t(self):
        assert _parse_grade_str("1.25g/t") == pytest.approx(1.25)
        assert _parse_grade_str("120.5G/T") == pytest.approx(120.5)

    def test_lt_boundary(self):
        # "<0.01" → 取界限值 0.01
        assert _parse_grade_str("<0.01") == pytest.approx(0.01)

    def test_undetected_returns_none(self):
        for v in ("N/D", "ND", "未检出", "—", "-", "", None, "无"):
            assert _parse_grade_str(v) is None, f"expected None for {v!r}"

    def test_comma_in_number(self):
        # 千分位逗号（罕见但兼容）
        assert _parse_grade_str("1,25") == pytest.approx(125.0)  # 逗号当作分隔符被去掉


# ══════════════════════════════════════════════════════════════
# _normalize_date
# ══════════════════════════════════════════════════════════════

class TestNormalizeDate:

    def test_iso_format(self):
        assert _normalize_date("2025-04-03") == "2025-04-03"

    def test_slash_format(self):
        assert _normalize_date("2025/04/03") == "2025-04-03"

    def test_chinese_format(self):
        assert _normalize_date("2025年4月3日") == "2025-04-03"

    def test_dot_format(self):
        assert _normalize_date("2025.4.3") == "2025-04-03"

    def test_empty_returns_empty(self):
        assert _normalize_date("") == ""


# ══════════════════════════════════════════════════════════════
# extract_to_record
# ══════════════════════════════════════════════════════════════

class TestExtractToRecord:

    def test_full_fields(self):
        ext = AssayReportExtract(
            样号="S2025-001",
            化验类型="结算化验",
            是否结算化验单=True,
            化验日期="2025/04/03",
            化验机构="XX检测中心",
            Cu_pct="28.50%",
            Au_gt="1.25g/t",
            Ag_gt="120.5",
            Pb_pct="0.35",
            Zn_pct=None,
            As_pct="0.40",
            H2O_pct="9.50",
        )
        rec = extract_to_record(ext)
        assert rec.样号 == "S2025-001"
        assert rec.化验日期 == "2025-04-03"
        assert rec.Cu_pct == pytest.approx(28.50)
        assert rec.Au_gt == pytest.approx(1.25)
        assert rec.Ag_gt == pytest.approx(120.5)
        assert rec.Pb_pct == pytest.approx(0.35)
        assert rec.Zn_pct is None
        assert rec.As_pct == pytest.approx(0.40)
        assert rec.H2O_pct == pytest.approx(9.50)

    def test_partial_fields(self):
        ext = AssayReportExtract(样号="S2025-002", Cu_pct="25.0", H2O_pct="8.0")
        rec = extract_to_record(ext)
        assert rec.Cu_pct == pytest.approx(25.0)
        assert rec.H2O_pct == pytest.approx(8.0)
        assert rec.Au_gt is None
        assert rec.As_pct is None

    def test_undetected_grade_becomes_none(self):
        ext = AssayReportExtract(样号="S001", Cu_pct="N/D", As_pct="未检出")
        rec = extract_to_record(ext)
        assert rec.Cu_pct is None
        assert rec.As_pct is None


# ══════════════════════════════════════════════════════════════
# record_to_dict
# ══════════════════════════════════════════════════════════════

class TestRecordToDict:

    def test_no_none_string(self):
        """dict 中不应出现字符串 None"""
        rec = AssayReportBitableRecord(样号="S001", Cu_pct=None, As_pct=None)
        d = record_to_dict(rec)
        for v in d.values():
            assert str(v) != "None", f"Found 'None' string in dict value: {v!r}"

    def test_bitable_field_names(self):
        """key 必须与 schema.yaml assay_reports 字段名一致"""
        rec = AssayReportBitableRecord(样号="S001")
        d = record_to_dict(rec)
        assert "Cu%" in d
        assert "Au(g/t)" in d
        assert "Ag(g/t)" in d
        assert "As%" in d
        assert "H2O%" in d
        assert "样号" in d

    def test_present_value_not_empty(self):
        rec = AssayReportBitableRecord(样号="S001", Cu_pct=28.5, As_pct=0.40)
        d = record_to_dict(rec)
        assert d["Cu%"] == "28.5"
        assert d["As%"] == "0.4"


# ══════════════════════════════════════════════════════════════
# classify_doc_type
# ══════════════════════════════════════════════════════════════

class TestClassifyDocType:

    def test_assay_keywords_detected(self):
        text = "矿产品化验报告 样品编号：S2025-001 Cu% 28.50 品位 H₂O% 9.5"
        assert classify_doc_type(text, use_llm_fallback=False) == "assay_report"

    def test_weigh_keywords_detected(self):
        text = "磅单编号：PD-001 毛重：33340kg 皮重：14540kg 净重：18800kg 车牌：皖A12345"
        assert classify_doc_type(text, use_llm_fallback=False) == "weigh_ticket"

    def test_strong_assay_wins_over_weak_weigh(self):
        # 化验单上有时会出现"净重"字样，但化验词分更高
        text = "化验报告单 检验报告 Cu% 28.50 品位 Au(g/t) 1.25 净重 9.5吨"
        assert classify_doc_type(text, use_llm_fallback=False) == "assay_report"

    def test_low_score_no_llm_falls_back_to_weigh(self):
        # 两类词都很少，无 LLM → 降级磅单
        text = "2025年4月3日 编号A001"
        result = classify_doc_type(text, use_llm_fallback=False)
        assert result == "weigh_ticket"

    def test_assay_report_label_in_text(self):
        text = "检验报告 铜精矿 Cu% 25.83 As% 0.40 H2O 9.50 化验日期 2025-04-03 化验机构 某检测中心"
        assert classify_doc_type(text, use_llm_fallback=False) == "assay_report"
