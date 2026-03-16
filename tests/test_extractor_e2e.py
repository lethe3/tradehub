"""
E2E 验证脚本 - 用真实 OCR 样本测试 Instructor 提取效果

前置条件：
- Ollama 运行中，已拉取 qwen3:32b（或 .env 中配置的模型）
- samples/ocr_results.json 存在（里程碑 2 产出）
- samples/data.yaml 存在（标注数据）

用法：
  PYTHONPATH=. python tests/test_extractor_e2e.py
  PYTHONPATH=. python tests/test_extractor_e2e.py --sample p1.jpg   # 只测单个样本
"""

import json
import sys
import os
import yaml
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai.extractor import extract
from ai.models.weigh_ticket_model import (
    WeighTicketExtract,
    WeighTicketRecord,
    extract_to_record,
    record_to_dict,
)


def load_ocr_results(path="samples/ocr_results.json") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_labels(path="samples/data.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def compare_one(filename: str, ocr_text: str, label: dict) -> dict:
    """测试单个样本"""
    print(f"\n{'='*60}")
    print(f"样本: {filename}")
    print(f"{'='*60}")

    # Step 1: LLM 提取
    try:
        raw = extract(text=ocr_text, model=WeighTicketExtract)
    except Exception as e:
        print(f"  ❌ 提取失败: {e}")
        return {"file": filename, "status": "EXTRACT_FAILED", "error": str(e)}

    print(f"  提取结果:")
    print(f"    磅单编号: {raw.磅单编号}")
    print(f"    货物品名: {raw.货物品名}")
    print(f"    毛重: {raw.毛重} {raw.重量单位.value}")
    print(f"    皮重: {raw.皮重}")
    print(f"    净重: {raw.净重}")
    print(f"    过磅日期: {raw.过磅日期}")
    print(f"    车牌号: {raw.车牌号}")
    print(f"    置信度: {raw.confidence}")
    if raw.备注:
        print(f"    备注: {raw.备注}")

    # Step 2: 转换
    record = extract_to_record(raw)
    d = record_to_dict(record)
    print(f"\n  Bitable 记录:")
    for k, v in d.items():
        print(f"    {k}: {v}")

    # Step 3: 与标注对比
    issues = []
    bitable = label.get("bitable", {})

    if bitable.get("cargo_name") and raw.货物品名:
        if bitable["cargo_name"] not in raw.货物品名 and raw.货物品名 not in bitable["cargo_name"]:
            issues.append(f"货物品名: 期望'{bitable['cargo_name']}', 提取'{raw.货物品名}'")

    if bitable.get("net_weight_ton"):
        expected_ton = float(bitable["net_weight_ton"])
        if abs(record.净重吨 - expected_ton) > 0.01:
            issues.append(f"净重(吨): 期望{expected_ton}, 提取{record.净重吨}")

    if issues:
        print(f"\n  ⚠️ 与标注不一致:")
        for issue in issues:
            print(f"    - {issue}")
    else:
        print(f"\n  ✅ 与标注一致")

    return {
        "file": filename,
        "status": "OK" if not issues else "MISMATCH",
        "issues": issues,
        "confidence": raw.confidence,
        "extract": raw.model_dump(),
        "record": d,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", help="只测试指定样本（如 p1.jpg）")
    args = parser.parse_args()

    ocr_results = load_ocr_results()
    labels = load_labels()

    # 建立 filename → label 映射
    label_map = {}
    for item in labels.get("weighing_slip_files", []):
        fname = item["file"]
        if fname == "图片1":
            fname = "p1.jpg"
        for slip in item.get("slips", []):
            label_map[fname] = slip

    results = []

    for filename, ocr_data in ocr_results.items():
        if args.sample and filename != args.sample:
            continue

        ocr_text = ocr_data.get("raw_text", "")
        if not ocr_text or ocr_text.startswith("/"):
            print(f"\n⏭️  {filename}: 无有效 OCR 文本，跳过")
            continue

        label = label_map.get(filename, {})
        result = compare_one(filename, ocr_text, label)
        results.append(result)

    # 汇总
    print(f"\n{'='*60}")
    print("汇总")
    print(f"{'='*60}")
    total = len(results)
    ok = sum(1 for r in results if r["status"] == "OK")
    mismatch = sum(1 for r in results if r["status"] == "MISMATCH")
    failed = sum(1 for r in results if r["status"] == "EXTRACT_FAILED")
    avg_conf = sum(float(r.get("confidence", 0)) for r in results if "confidence" in r) / max(total, 1)

    print(f"  总样本: {total}")
    print(f"  通过: {ok}")
    print(f"  不一致: {mismatch}")
    print(f"  提取失败: {failed}")
    print(f"  平均置信度: {avg_conf:.2f}")

    if total > 0:
        print(f"\n  准确率: {ok}/{total} = {ok/total*100:.0f}%")
        print(f"  (对比旧正则: 3/18 = 17%)")


if __name__ == "__main__":
    main()
