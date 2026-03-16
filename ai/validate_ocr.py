"""OCR 准确率验证脚本 - 对比 OCR 结果与标注数据"""

import json
import yaml
from pathlib import Path
from typing import Dict, List, Any


def load_data_yaml(path: str = "samples/data.yaml") -> dict:
    """加载标注数据"""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_ocr_results(path: str = "samples/ocr_results.json") -> dict:
    """加载 OCR 结果"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_text(text: str) -> str:
    """文本归一化：去除空格、换行、转小写"""
    if not text:
        return ""
    return "".join(text.split()).lower()


def extract_field(ocr_text: str, field_name: str) -> List[str]:
    """从 OCR 文本中提取字段值（简单关键词匹配）"""
    import re

    patterns = {
        "slip_no": [r"流水号[：:\s]*([A-Z0-9]+)", r"编号[：:\s]*([A-Z0-9]+)", r"No[:.\s]*([0-9]+)"],
        "vehicle_no": [r"车号[：:\s]*([^\s\n]+)", r"车牌号[：:\s]*([^\s\n]+)"],
        "cargo_name": [r"物品名称[：:\s]*([^\s\n]+)", r"货名[：:\s]*([^\s\n]+)", r"货物名称[：:\s]*([^\s\n]+)", r"名称[：:\s]*([^\s\n]+)"],
        "gross_weight": [r"毛重[：:\s]*([0-9.]+)", r"总重[：:\s]*([0-9.]+)", r"毛重[^\n]*(\d+)"],
        "tare_weight": [r"空重[：:\s]*([0-9.]+)", r"皮重[：:\s]*([0-9.]+)"],
        "net_weight": [r"净重[：:\s]*([0-9.]+)", r"净重[^\n]*(\d+)"],
    }

    results = []
    for pattern in patterns.get(field_name, []):
        matches = re.findall(pattern, ocr_text)
        results.extend(matches)

    return results[:5]  # 最多返回5个匹配


def compare_sample(ocr_text: str, label: dict) -> dict:
    """对比单个样本"""
    raw = label.get("raw", {})
    bitable = label.get("bitable", {})

    issues = []

    # 对比关键字段
    for field in ["slip_no", "vehicle_no", "cargo_name"]:
        if field in raw and raw[field]:
            extracted = extract_field(ocr_text, field)
            expected = normalize_text(str(raw[field]))

            # 简单匹配：检查提取结果中是否包含期望值
            matched = any(normalize_text(e) in expected or expected in normalize_text(e) for e in extracted)

            if not matched:
                issues.append(f"{field}: 期望 '{raw[field]}', 提取 {extracted}")

    # 对比重量
    for weight_type in ["gross_weight", "tare_weight", "net_weight"]:
        raw_field = f"{weight_type}_raw"
        if raw_field in raw and raw[raw_field]:
            extracted = extract_field(ocr_text, weight_type)
            expected = str(raw[raw_field]).replace(",", "").replace(" ", "")

            matched = any(expected in normalize_text(e) or normalize_text(e).replace(".", "").startswith(expected.split(".")[0]) for e in extracted if e)

            if not matched:
                issues.append(f"{weight_type}: 期望 '{raw[raw_field]}', 提取 {extracted}")

    return {
        "file": label.get("file", "unknown"),
        "document_type": label.get("document_type", ""),
        "has_issues": len(issues) > 0,
        "issues": issues,
    }


def main():
    # 加载数据
    data = load_data_yaml()
    ocr_results = load_ocr_results()

    results = []

    for item in data.get("weighing_slip_files", []):
        filename = item["file"]

        # 处理特殊文件名
        if filename == "图片1":
            filename = "p1.jpg"

        # 查找 OCR 结果
        ocr_text = ""
        for key, value in ocr_results.items():
            # 忽略扩展名大小写
            if key.lower().replace(".", "") == filename.lower().replace(".", "").replace("p", "p"):
                ocr_text = value.get("raw_text", "")
                break

        if not ocr_text or ocr_text.startswith("/"):
            results.append({
                "file": filename,
                "status": "NO_OCR",
                "message": f"OCR 结果为空或无效: {ocr_text[:50] if ocr_text else 'empty'}",
            })
            continue

        # 对比每条 slip
        for slip in item.get("slips", []):
            comparison = compare_sample(ocr_text, slip)
            comparison["document_type"] = item.get("document_type", "")
            results.append(comparison)

    # 统计
    total = len(results)
    no_ocr = sum(1 for r in results if r.get("status") == "NO_OCR")
    with_issues = sum(1 for r in results if r.get("has_issues", False))
    ok = total - no_ocr - with_issues

    print(f"\n=== OCR 验证结果 ===")
    print(f"总样本数: {total}")
    print(f"无 OCR 结果: {no_ocr}")
    print(f"有疑问: {with_issues}")
    print(f"通过: {ok}")

    print("\n=== 有疑问的样本 ===")
    for r in results:
        if r.get("has_issues"):
            print(f"\n{r['file']} ({r.get('document_type', '')}):")
            for issue in r.get("issues", []):
                print(f"  - {issue}")

    print("\n=== 无 OCR 结果的样本 ===")
    for r in results:
        if r.get("status") == "NO_OCR":
            print(f"  - {r['file']}: {r.get('message', '')}")


if __name__ == "__main__":
    main()
