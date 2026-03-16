"""
飞书消息处理器 - 桥接飞书事件与 core 层
"""

from typing import Optional
from core import get_dispatcher, HandlerResult
from feishu.bot import FeishuBot, ImageMessage, TextMessage
from ai.ocr import ocr_image


class MessageHandler:
    """飞书消息处理器"""

    def __init__(self, bot: FeishuBot):
        self.bot = bot
        self.dispatcher = get_dispatcher()

    def handle(self, message) -> str:
        """
        处理消息，返回响应文本

        Args:
            message: BotMessage 对象（ImageMessage 或 TextMessage）

        Returns:
            响应文本
        """
        # 图片消息 → 下载图片 → OCR
        if isinstance(message, ImageMessage):
            return self._handle_image(message)

        # 文本消息 → 路由
        if isinstance(message, TextMessage):
            return self._handle_text(message)

        return "暂不支持该类型消息"

    def _handle_image(self, message: ImageMessage) -> str:
        """处理图片消息"""
        # Step 1: 下载图片
        image_key = message.image_key
        message_id = getattr(message, 'message_id', None)
        print(f"下载图片: image_key={image_key}, message_id={message_id}")
        image_data = self.bot.get_image(image_key, message_id)

        if not image_data:
            return "图片下载失败，请重试"

        # 保存到临时文件
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
            f.write(image_data)
            temp_path = f.name

        try:
            # Step 2: OCR 提取
            ocr_text = ocr_image(temp_path)

            # Step 3: 返回 OCR 结果（待实现结构化解析）
            return f"磅单已识别，请确认以下信息：\n\n{ocr_text[:500]}"

        finally:
            # 清理临时文件
            os.unlink(temp_path)

    def _handle_text(self, message: TextMessage) -> str:
        """处理文本消息"""
        # 调用 dispatcher
        result: HandlerResult = self.dispatcher.route(message)

        if result.success:
            return result.message
        else:
            return result.message


def create_message_handler(bot: FeishuBot) -> MessageHandler:
    """创建消息处理器"""
    return MessageHandler(bot)
