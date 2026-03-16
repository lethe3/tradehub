"""
通用结构化提取器

核心函数 extract()：OCR 文本 + Pydantic 模型 → 结构化数据
底层用 Instructor + OpenAI 兼容 API（支持 Ollama 本地模型）

设计原则：
- 提取器不关心具体单据类型，只关心 Pydantic 模型
- 新增单据类型只需在 ai/models/ 下定义模型，不需要改提取器
- LLM provider 通过环境变量切换（Ollama / Claude / OpenAI）
"""

import logging
import os
from typing import TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# 默认配置
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"
DEFAULT_OLLAMA_MODEL = "qwen2.5vl:7b"


def _get_client():
    """
    创建 Instructor 客户端

    通过环境变量控制 provider：
    - EXTRACTOR_PROVIDER=ollama（默认）: 用本地 Ollama
    - EXTRACTOR_PROVIDER=openai: 用 OpenAI API
    - EXTRACTOR_PROVIDER=anthropic: 用 Claude API
    """
    import instructor
    from openai import OpenAI

    provider = os.environ.get("EXTRACTOR_PROVIDER", "ollama").lower()

    if provider == "ollama":
        base_url = os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)
        client = OpenAI(base_url=base_url, api_key="ollama")
        # Ollama 用 JSON 模式，不支持 TOOLS
        return instructor.from_openai(client, mode=instructor.Mode.JSON)

    elif provider == "openai":
        client = OpenAI()  # 从 OPENAI_API_KEY 环境变量读取
        return instructor.from_openai(client, mode=instructor.Mode.TOOLS)

    elif provider == "anthropic":
        import anthropic
        client = anthropic.Anthropic()
        return instructor.from_anthropic(client)

    else:
        raise ValueError(f"不支持的 provider: {provider}，可选: ollama, openai, anthropic")


def _get_model() -> str:
    """获取模型名称"""
    provider = os.environ.get("EXTRACTOR_PROVIDER", "ollama").lower()

    if provider == "ollama":
        return os.environ.get("EXTRACTOR_MODEL", DEFAULT_OLLAMA_MODEL)
    elif provider == "openai":
        return os.environ.get("EXTRACTOR_MODEL", "gpt-4o-mini")
    elif provider == "anthropic":
        return os.environ.get("EXTRACTOR_MODEL", "claude-sonnet-4-20250514")
    else:
        return os.environ.get("EXTRACTOR_MODEL", DEFAULT_OLLAMA_MODEL)


# 缓存客户端，避免重复创建
_cached_client = None


def get_client():
    """获取缓存的 Instructor 客户端"""
    global _cached_client
    if _cached_client is None:
        _cached_client = _get_client()
    return _cached_client


def reset_client():
    """重置客户端缓存（provider 切换后调用）"""
    global _cached_client
    _cached_client = None


def extract(
    text: str,
    model: type[T],
    context: str = "",
    max_retries: int = 2,
) -> T:
    """
    通用结构化提取

    Args:
        text: OCR 识别的原始文本
        model: Pydantic 模型类（如 WeighTicketExtract）
        context: 额外上下文提示（如"这是一张电子磅单"）
        max_retries: 最大重试次数

    Returns:
        填充好的 Pydantic 模型实例
    """
    client = get_client()
    llm_model = _get_model()

    # 构建 system prompt
    system_prompt = _build_system_prompt(model, context)

    logger.info(f"结构化提取: model={model.__name__}, llm={llm_model}")
    logger.debug(f"OCR 文本（前200字）: {text[:200]}")

    try:
        result = client.chat.completions.create(
            model=llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            response_model=model,
            max_retries=max_retries,
        )
        logger.info(f"提取成功: confidence={getattr(result, 'confidence', 'N/A')}")
        return result

    except Exception as e:
        logger.error(f"结构化提取失败: {e}")
        raise


def _build_system_prompt(model: type[BaseModel], context: str = "") -> str:
    """
    构建 system prompt

    从 Pydantic 模型的 field descriptions 自动生成提取指令
    """
    # 提取字段说明
    field_descriptions = []
    for name, field_info in model.model_fields.items():
        desc = field_info.description or ""
        default = field_info.default
        field_descriptions.append(f"- {name}: {desc}")

    fields_text = "\n".join(field_descriptions)

    prompt = f"""你是一个专业的单据信息提取助手。你的任务是从 OCR 识别的文本中提取结构化信息。

## 提取规则

1. **如实提取**：只提取文本中明确出现的信息，不推测、不编造
2. **保留原始值**：数值保留原始数字，不做单位换算
3. **识别单位**：注意区分 kg/公斤/千克 和 吨/t 的区别
4. **标记不确定**：如果某个字段不确定，留空并在备注中说明
5. **置信度评估**：根据文本清晰度和提取完整度给出 0.0-1.0 的置信度

## 需要提取的字段

{fields_text}

## 常见磅单格式提示

- 磅单通常包含：编号、日期、车牌号、货物名称、毛重、皮重、净重
- 重量单位可能是 kg（千克/公斤）或 吨（t），注意单位标注
- 有些磅单只有净重没有毛重皮重，这是正常的
- 日期格式多样：2025-04-03、2025/04/03、2025年4月3日"""

    if context:
        prompt += f"\n\n## 额外上下文\n\n{context}"

    return prompt


__all__ = ["extract", "get_client", "reset_client"]
