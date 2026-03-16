"""
技能模块 - 各个意图的 handler 实现

Core 层定义 handler 接口，实际实现在 feishu/ 或独立模块中
"""

from abc import ABC, abstractmethod
from typing import Any
from .dispatcher import Handler, HandlerResult, Intent, register_handler

INTRODUCE_TEXT = """👋 你好！我是 TradeHub 贸易助手，专为大宗商品跟单设计。

📋 **当前支持的功能：**

1. **磅单录入**（发送图片）
   - 发送磅单图片 → 自动 OCR 识别
   - 识别结果以卡片形式展示，确认后写入台账

2. **汇总查询**（发送文字）
   - 发送包含「汇总」「查询」「统计」的消息
   - 返回磅单总条数和总重量

📌 **使用方式：**
- 直接发图片 → 录磅单
- 发「汇总」或「查询」→ 看统计

如需帮助，随时@我或发送「帮助」获取此提示。"""


# === 汇总查询函数 ===

def create_query_summary_func():
    """
    创建汇总查询函数（延迟导入避免循环依赖）

    Returns:
        查询函数，接收 message，返回汇总数据 dict
    """
    from feishu.bitable import BitableTable

    def query_summary(message: Any) -> dict:
        """查询磅单汇总数据"""
        # 查询磅单表
        table = BitableTable(table_name="weigh_tickets")
        records, _ = table.list(page_size=100)

        # 统计
        total_count = len(records)
        total_weight = 0.0

        for record in records:
            # 净重字段
            weight = record.get("净重(吨)", 0)
            if weight is None:
                weight = 0
            try:
                total_weight += float(weight)
            except (ValueError, TypeError):
                pass

        return {
            "total_count": total_count,
            "total_weight": total_weight,
            "records": records[:5],  # 返回前5条示例
        }

    return query_summary


# === 创建全局查询函数 ===

_query_summary_func = None


def get_query_summary_func():
    """获取汇总查询函数（延迟创建）"""
    global _query_summary_func
    if _query_summary_func is None:
        _query_summary_func = create_query_summary_func()
    return _query_summary_func


class IntroduceHandler(Handler):
    """功能介绍 handler"""

    intent = Intent.INTRODUCE

    def can_handle(self, message: Any) -> bool:
        text = getattr(message, "text", None) or getattr(message, "content", None)
        if not text:
            return False
        keywords = ["介绍", "功能", "帮助", "help", "你能做什么", "怎么用"]
        return any(kw in str(text) for kw in keywords)

    def handle(self, message: Any) -> HandlerResult:
        return HandlerResult(success=True, message=INTRODUCE_TEXT)


class WeighTicketHandler(Handler):
    """磅单录入 handler"""

    intent = Intent.WEIGH_TICKET

    def __init__(self, ocr_func=None, bitable_writer=None):
        """
        Args:
            ocr_func: OCR 提取函数，接收图片路径，返回结构化数据
            bitable_writer: Bitable 写入函数，接收磅单数据
        """
        self._ocr_func = ocr_func
        self._bitable_writer = bitable_writer

    def can_handle(self, message: Any) -> bool:
        # 实际判断逻辑在 feishu 层实现
        return hasattr(message, "type") and message.type in ("image", "photo")

    def handle(self, message: Any) -> HandlerResult:
        """处理磅单图片"""
        # Step 1: 获取图片
        image_url = self._get_image_url(message)
        if not image_url:
            return HandlerResult(success=False, message="无法获取图片")

        # Step 2: OCR 提取
        ocr_result = None
        if self._ocr_func:
            try:
                ocr_result = self._ocr_func(image_url)
            except Exception as e:
                return HandlerResult(success=False, message=f"OCR 提取失败: {e}")

        # Step 3: 返回待审核的数据
        return HandlerResult(
            success=True,
            message="磅单已提取，请确认以下信息",
            data={
                "ocr_result": ocr_result,
                "image_url": image_url,
                "status": "pending_review"
            }
        )

    def _get_image_url(self, message: Any) -> str:
        """从消息中获取图片 URL"""
        # TODO: 根据实际消息格式实现
        if hasattr(message, "image_url"):
            return message.image_url
        return ""


class QuerySummaryHandler(Handler):
    """汇总查询 handler"""

    intent = Intent.QUERY_SUMMARY

    def __init__(self, query_func=None):
        self._query_func = query_func

    def can_handle(self, message: Any) -> bool:
        if hasattr(message, "content"):
            text = str(message.content)
            return "汇总" in text or "查询" in text or "统计" in text
        return False

    def handle(self, message: Any) -> HandlerResult:
        if self._query_func:
            try:
                result = self._query_func(message)

                # 格式化汇总文本
                total_count = result.get("total_count", 0)
                total_weight = result.get("total_weight", 0)

                # 构建回复文本
                reply_lines = [
                    f"📊 磅单汇总统计",
                    f"",
                    f"• 总条数：{total_count} 条",
                    f"• 总重量：{total_weight:.2f} 吨",
                ]

                # 添加最近几条示例
                records = result.get("records", [])
                if records:
                    reply_lines.append("")
                    reply_lines.append("📋 最近记录：")
                    for i, rec in enumerate(records, 1):
                        weight = rec.get("净重(吨)", "-")
                        date = rec.get("过磅日期", "-")
                        reply_lines.append(f"  {i}. {date} | {weight}吨")

                reply_text = "\n".join(reply_lines)
                return HandlerResult(success=True, message=reply_text, data=result)
            except Exception as e:
                return HandlerResult(success=False, message=f"查询失败: {e}")

        return HandlerResult(success=False, message="查询功能未配置")


# 注册 handler（需要在初始化时调用）
def register_handlers(ocr_func=None, bitable_writer=None, query_func=None):
    """注册所有 handler"""
    register_handler(IntroduceHandler())
    register_handler(WeighTicketHandler(ocr_func, bitable_writer))
    register_handler(QuerySummaryHandler(query_func))
