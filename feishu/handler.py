"""
飞书事件路由器 + 消息处理器

职责：
- EventRouter: 标准化事件 dict → 消息对象 → 业务处理 → 飞书回复
  - 消息类型解析（text/image/post）
  - 图片 OCR 调度
  - 卡片回调处理（审核通过 → Bitable 写入）
  - 统一错误处理（用户看飞书提示，开发看 logging）

- MessageHandler: 图片→OCR→预录入→返回核实链接；文本→引导提示

架构位置：feishu/handler.py 是"事件桥接层"
- 上游：ws_client.py 传入标准化 dict
- 下游：调用 ai 层（OCR + 提取）
- 回复：调用 feishu/bot.py 发送消息
"""

import json
import logging
import os
import tempfile
from typing import Optional

from feishu.bot import FeishuBot, ImageMessage, TextMessage
from feishu.cards import parse_card_callback
from feishu.bitable import BitableTable
from ai.ocr import ocr_image
from ai.weigh_ticket import parse_ocr_to_weigh_ticket, weigh_ticket_to_dict
from ai.assay_report import parse_ocr_to_assay_report, assay_report_to_dict
from ai.classify import classify_doc_type

logger = logging.getLogger(__name__)


# ==================== EventRouter：事件桥接层 ====================


class EventRouter:
    """
    事件路由器 — 桥接 WebSocket 标准化事件与业务逻辑

    ws_client.py 调用 handle_message_event / handle_card_action，
    本类负责：
    1. 解析消息类型（text/image/post）→ 消息对象
    2. 调用 MessageHandler 处理
    3. 根据返回结果发送飞书回复（文本 or 卡片）
    4. 统一错误处理：用户看飞书提示，开发看 logging
    """

    def __init__(self, bot: FeishuBot):
        self.bot = bot
        self.message_handler = MessageHandler(bot)

    def handle_message_event(self, event: dict):
        """
        处理消息事件（ws_client 回调入口）

        Args:
            event: 标准化 dict，包含 msg_type, message_id, chat_id, sender_id, content
        """
        msg_type = event.get("msg_type", "")
        content = event.get("content", "")
        chat_id = event.get("chat_id", "")
        sender_id = event.get("sender_id", {})
        message_id = event.get("message_id", "")
        open_id = sender_id.get("open_id", "") if isinstance(sender_id, dict) else ""

        try:
            # Step 1: 解析消息类型 → 消息对象
            msg_obj = self._parse_message(msg_type, content)
            if msg_obj is None:
                logger.info(f"不支持的消息类型: {msg_type}")
                if open_id:
                    self.bot.send_message(open_id, f"暂不支持 {msg_type} 类型消息，请发送图片或文字。")
                return

            # 附加元信息
            msg_obj.chat_id = chat_id
            msg_obj.sender_id = sender_id
            msg_obj.message_id = message_id

            # Step 2: 图片消息先发"处理中"提示
            if isinstance(msg_obj, ImageMessage) and open_id:
                self.bot.send_message(open_id, "📥 收到图片，正在识别，请稍候...")

            # Step 3: 调用 MessageHandler 处理
            response = self.message_handler.handle(msg_obj)

            # Step 4: 发送回复
            self._send_response(open_id, response)

        except Exception as e:
            logger.exception(f"处理消息失败: {e}")
            if open_id:
                self.bot.send_message(open_id, "❌ 处理失败，请稍后重试。如持续出现请联系管理员。")

    def handle_card_action(self, event: dict):
        """
        处理卡片按钮回调（ws_client 回调入口）

        Args:
            event: 标准化 dict，包含 open_id, action_value
        """
        open_id = event.get("open_id", "")
        action_value = event.get("action_value", {})

        if not action_value:
            logger.warning("回调 action_value 为空，跳过")
            return

        try:
            # 解析回调数据
            callback = parse_card_callback(action_value)
            logger.info(f"卡片回调: action={callback.action}, table={callback.table_name}")

            if callback.action == "approve":
                self._handle_approve(open_id, callback)
            elif callback.action == "cancel":
                if open_id:
                    self.bot.send_message(open_id, "已取消操作。如需继续，请重新发送图片。")
            else:
                logger.warning(f"未知的卡片动作: {callback.action}")

        except ValueError as e:
            logger.error(f"解析卡片回调失败: {e}")
            if open_id:
                self.bot.send_message(open_id, "❌ 回调数据格式有误，请联系管理员。")
        except Exception as e:
            logger.exception(f"处理卡片回调失败: {e}")
            if open_id:
                self.bot.send_message(open_id, "❌ 操作失败，请稍后重试。")

    # ==================== 内部方法 ====================

    def _parse_message(self, msg_type: str, content: str) -> Optional[TextMessage | ImageMessage]:
        """
        解析消息类型，返回消息对象

        支持：text, image, post（富文本中提取图片）
        """
        if msg_type == "text":
            try:
                content_dict = json.loads(content) if isinstance(content, str) else content
            except json.JSONDecodeError:
                content_dict = {"text": content}
            return TextMessage(content_dict)

        elif msg_type == "image":
            try:
                content_dict = json.loads(content) if isinstance(content, str) else content
            except json.JSONDecodeError:
                content_dict = {"image_key": content}
            return ImageMessage(content_dict)

        elif msg_type == "post":
            # 富文本消息：提取第一张图片
            try:
                post_content = json.loads(content) if isinstance(content, str) else content
                for block in post_content.get("content", []):
                    for item in block:
                        if item.get("tag") == "img":
                            image_key = item.get("image_key")
                            if image_key:
                                return ImageMessage({"image_key": image_key})
                logger.info("富文本消息中未找到图片")
                return None
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"解析富文本消息失败: {e}")
                return None

        return None

    def _send_response(self, open_id: str, response):
        """发送回复（文本 or 卡片）"""
        if not open_id:
            logger.warning("无 open_id，无法发送回复")
            return

        if isinstance(response, dict) and response.get("type") == "card":
            card_json = response.get("content", "")
            result = self.bot.send_interactive_card(open_id, card_json)
            logger.info(f"卡片发送结果: {result}")
        else:
            response_text = response if isinstance(response, str) else str(response)
            self.bot.send_message(open_id, response_text)

    def _handle_approve(self, open_id: str, callback):
        """处理审核通过：写入 Bitable + 发送成功通知"""
        try:
            table = BitableTable(table_name=callback.table_name)
            record_id = table.create(callback.record_data)
            logger.info(f"写入成功: table={callback.table_name}, record_id={record_id}")

            if open_id:
                record_info = "\n".join([
                    f"• {k}: {v}" for k, v in callback.record_data.items() if v
                ])
                self.bot.send_message(open_id, f"✅ 已成功录入！\n\n{record_info}")

        except Exception as e:
            logger.exception(f"Bitable 写入失败: {e}")
            if open_id:
                self.bot.send_message(
                    open_id,
                    f"❌ 写入失败: {e}\n\n请检查数据后重新发送图片，或联系管理员。"
                )


# ==================== MessageHandler：消息处理器 ====================


class MessageHandler:
    """
    消息处理器 — 处理已解析的消息对象

    职责：
    - 图片消息 → 下载 → OCR → 结构化提取 → 预录入 Bitable → 返回核实链接
    - 文本消息 → 引导用户使用工作台

    不负责飞书回复（由 EventRouter 统一处理）
    """

    def __init__(self, bot: FeishuBot):
        self.bot = bot

    def handle(self, message) -> str | dict:
        """
        处理消息，返回响应

        Returns:
            str: 文本消息
            dict: 包含 "type": "card" 的字典，用于发送卡片
        """
        if isinstance(message, ImageMessage):
            return self._handle_image(message)

        if isinstance(message, TextMessage):
            return "请发送磅单或化验单图片，我会帮您识别和录入。合同管理请使用工作台。"

        return "暂不支持该类型消息"

    def _handle_image(self, message: ImageMessage) -> str | dict:
        """处理图片消息：下载 → OCR → 结构化提取 → 预录入 → 返回链接"""
        image_key = message.image_key
        message_id = getattr(message, 'message_id', None)
        logger.info(f"处理图片: image_key={image_key}, message_id={message_id}")

        # Step 1: 下载图片
        image_data = self.bot.get_image(image_key, message_id)
        if not image_data:
            return "❌ 图片下载失败，请重试"

        # 保存到临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
            f.write(image_data)
            temp_path = f.name

        try:
            # Step 2: OCR 提取文字
            ocr_text = ocr_image(temp_path)
            if not ocr_text:
                return "❌ OCR 未识别到内容，请检查图片清晰度后重新发送"

            # Step 3: 图片分类（磅单 or 化验单）
            try:
                doc_type = classify_doc_type(ocr_text)
            except Exception as classify_err:
                logger.warning(f"图片分类失败，降级为磅单: {classify_err}")
                doc_type = "weigh_ticket"

            logger.info(f"图片分类结果: doc_type={doc_type}, image_key={image_key}")

            # Step 4a: 磅单路径
            if doc_type == "weigh_ticket":
                weigh_ticket = parse_ocr_to_weigh_ticket(ocr_text)
                record_data = weigh_ticket_to_dict(weigh_ticket)
                table = BitableTable(table_name="weigh_tickets")
                record_id = table.create(record_data)
                url = table.record_url(record_id)
                return f"✅ 磅单已录入，请点击链接核对：\n{url}"

            # Step 4b: 化验单路径
            assay_report = parse_ocr_to_assay_report(ocr_text)
            record_data = assay_report_to_dict(assay_report)
            table = BitableTable(table_name="assay_reports")
            record_id = table.create(record_data)
            url = table.record_url(record_id)
            return f"✅ 化验单已录入，请点击链接核对：\n{url}"

        except Exception as e:
            logger.exception(f"图片识别失败: {e}")
            return f"❌ 识别失败: {e}\n\n请检查图片是否为磅单或化验单，或尝试更清晰的照片。"

        finally:
            os.unlink(temp_path)
