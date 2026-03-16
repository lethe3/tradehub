"""
飞书消息处理器 - 桥接飞书事件与 core 层
"""

import logging
import os
import tempfile
from typing import Optional

from core import get_dispatcher, HandlerResult
from feishu.bot import FeishuBot, ImageMessage, TextMessage
from feishu.cards import CardTemplate, create_card_template
from ai.ocr import ocr_image
from ai.weigh_ticket import parse_ocr_to_weigh_ticket, weigh_ticket_to_dict

logger = logging.getLogger(__name__)


class MessageHandler:
    """飞书消息处理器"""

    def __init__(self, bot: FeishuBot):
        self.bot = bot
        self.dispatcher = get_dispatcher()
        self.card_template = create_card_template()

    def handle(self, message) -> str | dict:
        """
        处理消息，返回响应

        Returns:
            str: 文本消息
            dict: 包含 "type": "card" 的字典，用于发送卡片
        """
        # 图片消息 → 下载图片 → OCR → 卡片
        if isinstance(message, ImageMessage):
            return self._handle_image(message)

        # 文本消息 → 路由
        if isinstance(message, TextMessage):
            return self._handle_text(message)

        return "暂不支持该类型消息"

    def _handle_image(self, message: ImageMessage) -> str | dict:
        """处理图片消息，返回卡片"""
        # Step 1: 下载图片
        image_key = message.image_key
        message_id = getattr(message, 'message_id', None)
        logger.info(f"下载图片: image_key={image_key}, message_id={message_id}")
        image_data = self.bot.get_image(image_key, message_id)

        if not image_data:
            return "图片下载失败，请重试"

        # 保存到临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
            f.write(image_data)
            temp_path = f.name

        try:
            # Step 2: OCR 提取
            ocr_text = ocr_image(temp_path)
            if not ocr_text:
                return "OCR 未识别到内容，请检查图片清晰度"

            # Step 3: 解析为结构化数据
            weigh_ticket = parse_ocr_to_weigh_ticket(ocr_text)
            record_data = weigh_ticket_to_dict(weigh_ticket)

            # Step 4: 生成只读卡片（飞书不支持 plain_text_input）
            card_json = self.card_template.generate(
                table_name="weigh_tickets",
                record_data=record_data,
                title="磅单 OCR 结果确认",
            )

            # 返回卡片
            return {
                "type": "card",
                "content": card_json,
            }

        except Exception as e:
            logger.exception(f"磅单识别失败: {e}")
            return f"磅单识别失败: {e}"

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
