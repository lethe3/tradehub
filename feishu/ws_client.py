"""
飞书 Bot WebSocket 客户端 - 只负责连接管理和事件反序列化

职责边界：
- WebSocket 连接（自动重连）
- SDK 事件注册（消息事件 + 卡片回调）
- 原始事件 → 标准化 dict（类型、消息ID、发送者、内容）
- 去重（processed_messages）

不包含：
- 消息类型解析（text/image/post → 消息对象）
- 业务逻辑（OCR、Bitable 写入）
- 错误回复（飞书消息通知）

这些逻辑全部在 feishu/handler.py 中实现。
"""

import logging
import os
from collections import deque
from typing import Callable, Optional

from lark_oapi.core.enum import LogLevel
from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
from lark_oapi.ws import Client as LarkClient

logger = logging.getLogger(__name__)


class WebSocketBot:
    """飞书 WebSocket Bot 客户端"""

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        on_message: Callable[[dict], None],
        on_card_action: Callable[[dict], None],
        verification_token: str = "",
        encrypt_key: str = "",
    ):
        """
        Args:
            app_id: 飞书应用 ID
            app_secret: 飞书应用密钥
            on_message: 消息事件回调，接收标准化 dict
            on_card_action: 卡片按钮回调，接收标准化 dict
            verification_token: 验证 token
            encrypt_key: 加密密钥
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self._on_message = on_message
        self._on_card_action = on_card_action
        self._verification_token = verification_token
        self._encrypt_key = encrypt_key
        self._ws_client: Optional[LarkClient] = None
        # 去重缓存：maxlen=1000，自动淘汰旧条目，避免长期运行内存泄漏
        self._processed_messages: deque[str] = deque(maxlen=1000)

    def start(self):
        """启动 WebSocket 连接"""
        handler = EventDispatcherHandler()
        builder = handler.builder(self._encrypt_key, self._verification_token)

        # 注册消息接收事件
        for event_type in ["im.message.receive", "im.message.receive_v1"]:
            try:
                builder.register_p1_customized_event(event_type, self._handle_raw_message)
                logger.debug(f"注册成功: p1.{event_type}")
            except Exception as e:
                logger.debug(f"注册失败: p1.{event_type}: {e}")
            try:
                builder.register_p2_customized_event(event_type, self._handle_raw_message)
                logger.debug(f"注册成功: p2.{event_type}")
            except Exception as e:
                logger.debug(f"注册失败: p2.{event_type}: {e}")

        # 注册卡片按钮回调（必须用 SDK 专用方法）
        try:
            builder.register_p2_card_action_trigger(self._handle_raw_card_action)
            logger.debug("注册成功: register_p2_card_action_trigger")
        except Exception as e:
            logger.debug(f"注册失败: register_p2_card_action_trigger: {e}")

        built_handler = builder.build()
        logger.info(f"已注册的处理器: {list(built_handler._processorMap.keys())}")

        self._ws_client = LarkClient(
            app_id=self.app_id,
            app_secret=self.app_secret,
            log_level=LogLevel.DEBUG,
            event_handler=built_handler,
            auto_reconnect=True,
        )

        logger.info("连接飞书 WebSocket...")
        self._ws_client.start()

    def stop(self):
        """停止 WebSocket 连接"""
        pass

    # ==================== 内部方法：原始事件 → 标准化 dict ====================

    def _handle_raw_message(self, event):
        """
        将 SDK 原始消息事件反序列化为标准化 dict，交给 on_message 回调

        标准化 dict 格式：
        {
            "msg_type": "text" | "image" | "post" | ...,
            "message_id": "om_xxx",
            "chat_id": "oc_xxx",
            "sender_id": {"open_id": "ou_xxx"},
            "content": "...",  # JSON 字符串
        }
        """
        try:
            event_data = self._extract_event_data(event)
            if not event_data:
                logger.warning(f"无法识别事件格式: event={type(event).__name__}")
                return

            message_id = event_data.get("message_id", "")

            # 去重
            if message_id and message_id in self._processed_messages:
                logger.debug(f"跳过重复消息: {message_id}")
                return
            if message_id:
                self._processed_messages.append(message_id)

            logger.info(f"收到消息: type={event_data.get('msg_type')}, message_id={message_id}")
            self._on_message(event_data)

        except Exception as e:
            logger.exception(f"处理消息事件失败: {e}")

    def _handle_raw_card_action(self, event):
        """
        将 SDK 原始卡片回调反序列化为标准化 dict，交给 on_card_action 回调

        标准化 dict 格式：
        {
            "open_id": "ou_xxx",
            "action_value": {...},  # 按钮 value 字段
        }
        """
        try:
            # 提取 event_data
            if hasattr(event, 'event') and isinstance(event.event, dict):
                event_data = event.event
            elif hasattr(event, 'event') and event.event is not None:
                event_data = event.event
            else:
                event_data = event

            # 提取 operator.open_id
            open_id = ""
            if isinstance(event_data, dict):
                open_id = event_data.get("operator", {}).get("open_id", "")
            elif hasattr(event_data, 'operator'):
                op = event_data.operator
                if isinstance(op, dict):
                    open_id = op.get("open_id", "")
                elif hasattr(op, 'open_id'):
                    open_id = op.open_id

            # 提取 action.value
            action_value = {}
            if isinstance(event_data, dict):
                action_value = event_data.get("action", {}).get("value", {})
            elif hasattr(event_data, 'action'):
                act = event_data.action
                if isinstance(act, dict):
                    action_value = act.get("value", {})
                elif hasattr(act, 'value'):
                    v = act.value
                    action_value = v if isinstance(v, dict) else {}

            logger.info(f"卡片回调: open_id={open_id}")
            self._on_card_action({
                "open_id": open_id,
                "action_value": action_value,
            })

        except Exception as e:
            logger.exception(f"处理卡片回调失败: {e}")

    def _extract_event_data(self, event) -> Optional[dict]:
        """
        从 SDK 事件对象中提取标准化消息数据

        飞书 SDK 的事件对象格式不统一（dict / 类型化对象 / 嵌套对象），
        这里统一处理各种情况，返回标准 dict。
        """
        event_data = {}

        # 情况 1: event.event 是 dict 且包含 message
        if hasattr(event, 'event') and isinstance(event.event, dict):
            raw = event.event
            if 'message' in raw:
                msg = raw.get('message', {})
                sender = raw.get('sender', {}).get('sender_id', {})
                return {
                    'msg_type': msg.get('message_type', ''),
                    'content': msg.get('content', ''),
                    'message_id': msg.get('message_id', ''),
                    'chat_id': msg.get('chat_id', ''),
                    'sender_id': sender,
                }
            return raw

        # 情况 2: event 本身有 message 属性（类型化对象）
        msg_obj = None
        if hasattr(event, 'message'):
            msg_obj = event
        elif hasattr(event, 'event') and hasattr(event.event, 'message'):
            msg_obj = event.event

        if msg_obj:
            msg_wrapper = getattr(msg_obj, 'message', None)
            if msg_wrapper:
                msg_info = getattr(msg_wrapper, 'message', None) or msg_wrapper
                event_data = {
                    'msg_type': getattr(msg_info, 'message_type', ''),
                    'content': getattr(msg_info, 'content', ''),
                    'message_id': getattr(msg_info, 'message_id', ''),
                    'chat_id': getattr(msg_info, 'chat_id', ''),
                }
                sender_wrapper = getattr(msg_wrapper, 'sender', None)
                if sender_wrapper:
                    sender_id = getattr(sender_wrapper, 'sender_id', {})
                    if not isinstance(sender_id, dict):
                        sender_id = {"open_id": getattr(sender_id, 'open_id', '')}
                    event_data['sender_id'] = sender_id
                return event_data

        return None


def create_ws_bot(config_path: str = ".env") -> WebSocketBot:
    """
    从环境变量创建 WebSocket Bot

    组装逻辑：
    1. 创建 FeishuBot（飞书 API 客户端）
    2. 创建 EventRouter（事件桥接层）
    3. 创建 WebSocketBot，将 EventRouter 的方法作为回调传入
    """
    from dotenv import load_dotenv
    load_dotenv(config_path)

    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")
    verification_token = os.getenv("FEISHU_VERIFICATION_TOKEN", "")
    encrypt_key = os.getenv("FEISHU_ENCRYPT_KEY", "")

    if not app_id or not app_secret:
        raise ValueError("FEISHU_APP_ID 和 FEISHU_APP_SECRET 必须设置")

    from feishu.bot import FeishuBot
    from feishu.handler import EventRouter

    feishu_bot = FeishuBot({
        "app_id": app_id,
        "app_secret": app_secret,
    })

    router = EventRouter(feishu_bot)

    return WebSocketBot(
        app_id=app_id,
        app_secret=app_secret,
        on_message=router.handle_message_event,
        on_card_action=router.handle_card_action,
        verification_token=verification_token,
        encrypt_key=encrypt_key,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bot = create_ws_bot()
    print("启动 WebSocket Bot（按 Ctrl+C 退出）...")
    bot.start()
