"""
独立验证脚本 - 验证磅单模型和提取流程

不依赖 LLM，用构造数据验证：
1. Pydantic 模型校验（含 weight consistency validator）
2. 脏数据清洗（LLM 常见的带单位字符串）
3. 单位换算逻辑
4. 接口兼容性
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai.models.weigh_ticket_model import (
    WeighTicketExtract,
    WeighTicketRecord,
    WeightUnit,
    extract_to_record,
    record_to_dict,
    _calc_net_weight_ton,
    _normalize_date,
    _parse_weight_str,
)


def test_parse_weight_str():
    """测试 0: 重量字符串清洗"""
    print("=" * 60)
    print("测试 0: 重量字符串清洗（_parse_weight_str）")
    print("=" * 60)

    cases = [
        (None, None, "None"),
        (33340, 33340.0, "int"),
        (50.225, 50.225, "float"),
        ("33340", 33340.0, "纯数字字符串"),
        ("50.225(t)", 50.225, "带(t)"),
        ("18,800 kg", 18800.0, "带逗号和kg"),
        ("15.16吨", 15.16, "带吨"),
        ("14540千克", 14540.0, "带千克"),
        ("0.5", 0.5, "小数字符串"),
        ("", None, "空字符串"),
        ("abc", None, "非数字"),
    ]

    all_pass = True
    for input_val, expected, desc in cases:
        result = _parse_weight_str(input_val)
        ok = result == expected
        status = "✅" if ok else "❌"
        if not ok:
            all_pass = False
        print(f"  {status} {desc:20s} | {str(input_val):15s} → {result} (期望 {expected})")

    print()
    return all_pass


def test_pydantic_model():
    """测试 1: Pydantic 模型定义"""
    print("=" * 60)
    print("测试 1: Pydantic 模型（接受 LLM 脏输出）")
    print("=" * 60)

    # 模拟 LLM 真实输出（数字是字符串）
    ext = WeighTicketExtract(
        磅单编号="A2025040300001",
        货物品名="铜精矿",
        过磅日期="2025-04-03",
        毛重="33340",
        皮重="14540",
        净重="18800",
        重量单位=WeightUnit.KG,
        车牌号="皖HM2729",
        confidence="0.9",
    )
    assert ext.磅单编号 == "A2025040300001"
    assert ext.毛重 == "33340"
    assert ext.毛重_float == 33340.0
    assert ext.净重_float == 18800.0
    assert ext.confidence_float == 0.9
    print("  ✅ LLM 字符串数字 → float 转换正确")

    # 带单位的输出
    ext2 = WeighTicketExtract(
        毛重="50.225(t)",
        皮重="14.845(t)",
        净重="35.380(t)",
    )
    assert ext2.毛重_float == 50.225
    assert ext2.净重_float == 35.380
    assert ext2.重量单位 == WeightUnit.TON  # 自动从字符串推断
    print("  ✅ 带(t)单位 → 自动识别为吨")

    # 空值
    ext_empty = WeighTicketExtract()
    assert ext_empty.净重_float is None
    assert ext_empty.confidence_float == 0.5
    print("  ✅ 空值默认值正确")

    # 重量不一致检测
    ext_bad = WeighTicketExtract(毛重="23480", 皮重="8320", 净重="10000")
    assert "⚠️" in ext_bad.备注
    print(f"  ✅ 重量不一致检测: {ext_bad.备注.strip()}")

    print()


def test_unit_conversion():
    """测试 2: 单位换算逻辑"""
    print("=" * 60)
    print("测试 2: 单位换算逻辑")
    print("=" * 60)

    cases = [
        (WeighTicketExtract(净重="15160", 重量单位=WeightUnit.KG), 15.16, "kg → 吨"),
        (WeighTicketExtract(净重="15.16", 重量单位=WeightUnit.TON), 15.16, "吨 → 吨"),
        (WeighTicketExtract(净重="23480", 重量单位=WeightUnit.UNKNOWN), 23.48, "未知 >100 → 按kg"),
        (WeighTicketExtract(净重="15.16", 重量单位=WeightUnit.UNKNOWN), 15.16, "未知 <100 → 按吨"),
        (WeighTicketExtract(毛重="23480", 皮重="8320", 重量单位=WeightUnit.KG), 15.16, "毛重-皮重 fallback"),
        (WeighTicketExtract(净重="50.225(t)", 毛重="50.225(t)"), 50.225, "带(t)自动识别为吨"),
        (WeighTicketExtract(), 0.0, "全空 → 0"),
    ]

    all_pass = True
    for ext, expected, desc in cases:
        result = _calc_net_weight_ton(ext)
        ok = abs(result - expected) < 0.001
        status = "✅" if ok else "❌"
        if not ok:
            all_pass = False
        print(f"  {status} {desc:30s} → {result} (期望 {expected})")

    print()
    return all_pass


def test_date_normalize():
    """测试 3: 日期标准化"""
    print("=" * 60)
    print("测试 3: 日期标准化")
    print("=" * 60)

    cases = [
        ("2025-04-03", "2025-04-03", "已标准格式"),
        ("2025/04/03", "2025-04-03", "斜杠格式"),
        ("2025年4月3日", "2025-04-03", "中文格式"),
        ("2025.04.03", "2025-04-03", "点分格式"),
        ("", "", "空值"),
    ]

    all_pass = True
    for input_val, expected, desc in cases:
        result = _normalize_date(input_val)
        ok = result == expected
        status = "✅" if ok else "❌"
        if not ok:
            all_pass = False
        print(f"  {status} {desc:15s} | {input_val:15s} → {result} (期望 {expected})")

    print()
    return all_pass


def test_extract_to_record():
    """测试 4: Extract → Record（含 LLM 脏输出场景）"""
    print("=" * 60)
    print("测试 4: Extract → Record 转换")
    print("=" * 60)

    # 场景 A: LLM 返回字符串数字 + kg
    ext_a = WeighTicketExtract(
        磅单编号="A2025040300001",
        货物品名="铜精矿",
        过磅日期="2025年4月3日",
        毛重="33340",
        皮重="14540",
        净重="18800",
        重量单位=WeightUnit.KG,
    )
    rec_a = extract_to_record(ext_a)
    assert abs(rec_a.净重吨 - 18.8) < 0.001
    assert rec_a.过磅日期 == "2025-04-03"
    print(f"  ✅ 场景A (kg字符串): 净重={rec_a.净重吨}吨")

    # 场景 B: LLM 返回带(t)的字符串
    ext_b = WeighTicketExtract(
        磅单编号="A2025040300001",
        货物品名="黄铜块",
        过磅日期="2025-04-03",
        毛重="50.225(t)",
        皮重="14.845(t)",
        净重="35.380(t)",
    )
    rec_b = extract_to_record(ext_b)
    assert abs(rec_b.净重吨 - 35.380) < 0.001
    print(f"  ✅ 场景B (吨带单位): 净重={rec_b.净重吨}吨")

    # 场景 C: 全空
    ext_c = WeighTicketExtract()
    rec_c = extract_to_record(ext_c)
    assert rec_c.净重吨 == 0.0
    print(f"  ✅ 场景C (全空): 净重={rec_c.净重吨}")

    print()


def test_interface_compat():
    """测试 5: 接口兼容性"""
    print("=" * 60)
    print("测试 5: 接口兼容性")
    print("=" * 60)

    from ai.weigh_ticket import WeighTicket, weigh_ticket_to_dict

    assert WeighTicket is WeighTicketRecord
    print("  ✅ WeighTicket 别名兼容")

    record = WeighTicketRecord(
        磅单编号="TEST-001",
        货物品名="废铜",
        **{"净重(吨)": 5.5},
        过磅日期="2025-04-03",
    )
    d = weigh_ticket_to_dict(record)
    assert isinstance(d, dict)
    assert "净重(吨)" in d
    print(f"  ✅ weigh_ticket_to_dict: {d}")

    from ai.weigh_ticket import parse_ocr_to_weigh_ticket
    assert callable(parse_ocr_to_weigh_ticket)
    print("  ✅ parse_ocr_to_weigh_ticket 可导入")

    print()


def main():
    all_pass = True
    all_pass &= test_parse_weight_str()
    test_pydantic_model()
    all_pass &= test_unit_conversion()
    all_pass &= test_date_normalize()
    test_extract_to_record()
    test_interface_compat()

    print("=" * 60)
    if all_pass:
        print("全部测试通过 ✅")
    else:
        print("❌ 有测试未通过")
        sys.exit(1)
    print("=" * 60)
    print()
    print("下一步：用真实 OCR 样本 + Ollama 测试")
    print("  EXTRACTOR_MODEL=qwen3:latest PYTHONPATH=. python tests/test_extractor_e2e.py")


if __name__ == "__main__":
    main()
