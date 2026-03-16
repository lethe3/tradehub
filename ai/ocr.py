"""OCR 模块 - 调用本地 GLM-OCR 模型"""

import subprocess
import json
import os
from pathlib import Path
from typing import Optional


def ocr_image(image_path: str, prompt: str = "请提取图片中的所有文字内容") -> str:
    """
    调用本地 GLM-OCR 模型提取图片文字

    Args:
        image_path: 图片文件路径
        prompt: 提示词

    Returns:
        OCR 提取的文本内容
    """
    # 转换为绝对路径
    abs_path = os.path.abspath(image_path)

    # 使用 shell 方式调用，echo 传 prompt，图片路径作为参数
    cmd = f'echo "{prompt}" | ollama run glm-ocr:latest "{abs_path}"'
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    if result.returncode != 0:
        raise RuntimeError(f"OCR failed: {result.stderr}")

    return result.stdout


def ocr_image_to_json(image_path: str) -> dict:
    """
    调用 GLM-OCR，返回清洗后的 JSON 结构

    尝试解析为结构化数据，失败则返回原始文本
    """
    raw_text = ocr_image(image_path)

    # 尝试提取 JSON（如果模型输出包含 JSON）
    # 这里先返回原始文本，后续用 instructor 解析
    return {"raw_text": raw_text.strip()}


def batch_ocr(image_dir: str, output_path: Optional[str] = None) -> dict:
    """
    批量处理目录下所有图片

    Args:
        image_dir: 图片目录
        output_path: 可选，输出 JSON 文件路径

    Returns:
        {filename: ocr_result}
    """
    image_dir = Path(image_dir)
    results = {}

    # 支持的图片格式
    extensions = {".jpg", ".jpeg", ".png", ".pdf", ".bmp"}

    image_files = sorted([
        f for f in image_dir.iterdir()
        if f.suffix.lower() in extensions
    ])

    for img_file in image_files:
        print(f"Processing: {img_file.name}...", end=" ", flush=True)
        try:
            result = ocr_image(str(img_file))
            results[img_file.name] = {"raw_text": result.strip()}
            print("OK")
        except Exception as e:
            print(f"FAILED: {e}")
            results[img_file.name] = {"error": str(e)}

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\nResults saved to: {output_path}")

    return results


if __name__ == "__main__":
    # 测试
    import sys

    if len(sys.argv) > 1:
        # 单图测试
        result = ocr_image(sys.argv[1])
        print(result)
    else:
        # 批量处理 samples/
        batch_ocr("samples/weigh_tickets", "samples/ocr_results.json")
