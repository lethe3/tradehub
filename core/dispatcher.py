"""
意图路由模块 - 消息分发与 handler 注册表

核心规则：core/ 不依赖 feishu/ 或 ai/
"""

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)


class Intent(Enum):
    """支持的意图类型"""
    WEIGH_TICKET = "weigh_ticket"          # 磅单录入（OCR）
    ASSAY_REPORT = "assay_report"          # 化验单录入（OCR）
    QUERY_SUMMARY = "query_summary"        # 汇总查询
    GENERATE_CONTRACT = "gen_contract"     # 生成假合同记录
    GENERATE_WEIGH_TICKET = "gen_weigh"    # 生成假磅单记录
    GENERATE_ASSAY_REPORT = "gen_assay"    # 生成假化验单记录
    SETTLEMENT = "settlement"              # 触发结算计算 + 卡片
    UNKNOWN = "unknown"                    # 未知


@dataclass
class HandlerResult:
    """Handler 执行结果"""
    success: bool
    message: str
    data: Optional[dict] = None


class Handler(ABC):
    """Handler 基类"""

    intent: Intent

    @abstractmethod
    def can_handle(self, message: Any) -> bool:
        """判断是否能处理这条消息"""

    @abstractmethod
    def handle(self, message: Any) -> HandlerResult:
        """处理消息"""


# Handler 注册表
_handler_registry: dict[Intent, list[Handler]] = {}


def register_handler(handler: Handler):
    """注册 handler"""
    if handler.intent not in _handler_registry:
        _handler_registry[handler.intent] = []
    _handler_registry[handler.intent].append(handler)


def get_handlers(intent: Intent) -> list[Handler]:
    """获取指定意图的 handlers"""
    return _handler_registry.get(intent, [])


class Dispatcher:
    """消息分发器"""

    def __init__(self):
        self._rules: list[tuple[Callable, Intent]] = []

    def add_rule(self, matcher: Callable, intent: Intent):
        """添加路由规则"""
        self._rules.append((matcher, intent))

    def dispatch(self, message: Any) -> tuple[Intent, Handler | None]:
        """
        分发消息，返回匹配的意图和 handler

        Args:
            message: 原始消息对象（可以是文本、图片、文件等）

        Returns:
            (匹配的意图, handler 实例)
        """
        # 规则匹配
        for matcher, intent in self._rules:
            if matcher(message):
                handlers = get_handlers(intent)
                if handlers:
                    return intent, handlers[0]

        # 默认未知
        return Intent.UNKNOWN, None

    def route(self, message: Any) -> HandlerResult:
        """
        路由并执行

        Returns:
            HandlerResult
        """
        intent, handler = self.dispatch(message)

        if handler is None:
            return HandlerResult(
                success=False,
                message=f"暂不支持该类型消息，请发送磅单图片或使用「汇总查询」指令"
            )

        try:
            return handler.handle(message)
        except Exception as e:
            logger.exception(f"Handler 执行失败: {e}")
            return HandlerResult(
                success=False,
                message=f"处理失败: {str(e)}"
            )


# === 内置规则匹配器 ===

def is_image_message(message: Any) -> bool:
    """判断是否为图片消息"""
    # TODO: 根据实际消息格式实现
    # 这里先定义接口，实际在 feishu 层实现
    if hasattr(message, "type"):
        return message.type in ("image", "photo")
    return False


def is_text_with_keyword(message: Any, keywords: list[str]) -> bool:
    """判断文本消息是否包含关键词"""
    # TextMessage 使用 text 属性存储文本内容
    text = getattr(message, "text", None) or getattr(message, "content", None)
    if not text:
        return False

    if not isinstance(text, str):
        return False

    for kw in keywords:
        if kw in text:
            return True
    return False


# === 初始化默认规则 ===

_default_dispatcher: Optional[Dispatcher] = None


def get_dispatcher() -> Dispatcher:
    """获取默认 dispatcher（单例）"""
    global _default_dispatcher
    if _default_dispatcher is None:
        _default_dispatcher = Dispatcher()
        # 默认规则：图片 → 磅单
        _default_dispatcher.add_rule(is_image_message, Intent.WEIGH_TICKET)
        # 默认规则：包含"汇总" → 查询
        _default_dispatcher.add_rule(
            lambda m: is_text_with_keyword(m, ["汇总", "查询", "统计"]),
            Intent.QUERY_SUMMARY
        )
        # 注册默认 handler
        from . import handlers
        # 传递汇总查询函数
        query_func = handlers.get_query_summary_func()
        handlers.register_handlers(query_func=query_func)
    return _default_dispatcher
