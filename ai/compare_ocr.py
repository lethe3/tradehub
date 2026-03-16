"""对比 GLM-OCR 和 Qwen2.5VL 的 OCR 效果"""

import subprocess
import json
from pathlib import Path


def ollama_ocr(model: str, image_path: str, prompt: str = "请提取图片中的所有文字内容") -> str:
    """调用 ollama 模型进行 OCR"""
    abs_path = str(Path(image_path).resolve())
    cmd = f'echo "{prompt}" | ollama run {model} "{abs_path}"'
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


def main():
    image_dir = Path("samples/weigh_tickets")

    # 只测试前 3 张有代表性的图片
    test_files = ["p1.jpg", "p2.jpg", "p8.jpg"]

    models = ["glm-ocr:latest", "qwen2.5vl:7b"]

    results = {}

    for model in models:
        print(f"\n=== {model} ===")
        results[model] = {}

        for img in test_files:
            img_path = image_dir / img
            if not img_path.exists():
                continue

            print(f"Processing {img}...", end=" ", flush=True)
            try:
                text = ollama_ocr(model, str(img_path))
                results[model][img] = text.strip()[:200]  # 只保留前200字符
                print("OK")
            except Exception as e:
                print(f"FAILED: {e}")
                results[model][img] = f"ERROR: {e}"

    # 输出对比
    print("\n" + "="*60)
    print("=== 对比结果 ===")
    print("="*60)

    for img in test_files:
        print(f"\n--- {img} ---")
        for model in models:
            print(f"\n[{model}]")
            text = results.get(model, {}).get(img, "N/A")
            if text.startswith("ERROR"):
                print(text)
            else:
                print(text[:500])
                if len(text) > 500:
                    print("...")


if __name__ == "__main__":
    main()
