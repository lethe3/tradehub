"""
飞书 Bot WebSocket 客户端 - 接收实时消息事件

修复：使用 SDK 专用方法 register_p2_card_action_trigger
     （不能用 register_p2_customized_event 注册卡片回调）
"""

import os
from typing import Callable, Optional
from lark_oapi.core.enum import LogLevel
from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
from lark_oapi.ws import Client as LarkClient


class WebSocketBot:
    """飞书 WebSocket Bot 客户端"""

    def __init__(self, app_id: str, app_secret: str, event_handler: Callable,
                 verification_token: str = None, encrypt_key: str = None):
        self.app_id = app_id
        self.app_secret = app_secret
        self.verification_token = verification_token or ""
        self.encrypt_key = encrypt_key or ""
        self._event_handler = event_handler
        self._interactive_handler = None
        self._ws_client: Optional[LarkClient] = None

    def start(self):
        """启动 WebSocket 连接"""
        handler = EventDispatcherHandler()
        builder = handler.builder(self.encrypt_key, self.verification_token)

        # 注册消息接收事件
        for event_type in ["im.message.receive", "im.message.receive_v1"]:
            try:
                builder.register_p1_customized_event(event_type, self._handle_message_event)
                print(f"注册成功: p1.{event_type}")
            except Exception as e:
                print(f"注册失败: p1.{event_type}: {e}")
            try:
                builder.register_p2_customized_event(event_type, self._handle_message_event)
                print(f"注册成功: p2.{event_type}")
            except Exception as e:
                print(f"注册失败: p2.{event_type}: {e}")

        # 注册卡片按钮回调 - 必须用 SDK 专用方法
        # register_p2_customized_event("card.action.trigger", ...) 不生效
        # SDK 内部对卡片回调走独立的匹配路径
        try:
            builder.register_p2_card_action_trigger(self._handle_card_action)
            print("注册成功: register_p2_card_action_trigger")
        except Exception as e:
            print(f"注册失败: register_p2_card_action_trigger: {e}")

        handler = builder.build()
        print(f"已注册的处理器: {list(handler._processorMap.keys())}")

        self._ws_client = LarkClient(
            app_id=self.app_id,
            app_secret=self.app_secret,
            log_level=LogLevel.DEBUG,
            event_handler=handler,
            auto_reconnect=True,
        )

        print(f"Connecting to Feishu WebSocket...")
        self._ws_client.start()

    def _handle_message_event(self, event):
        """处理消息接收事件"""
        try:
            event_type = getattr(event, 'type', None) or getattr(event.header, 'event_type', 'unknown')

            event_data = {}
            msg_obj = None

            if hasattr(event, 'event') and isinstance(event.event, dict):
                if 'message' in event.event:
                    raw_event = event.event
                    msg_wrapper = raw_event.get('message', {})
                    sender_wrapper = raw_event.get('sender', {})
                    sender_id_wrapper = sender_wrapper.get('sender_id', {})
                    event_data = {
                        'msg_type': msg_wrapper.get('message_type', ''),
                        'content': msg_wrapper.get('content', ''),
                        'message_id': msg_wrapper.get('message_id', ''),
                        'chat_id': msg_wrapper.get('chat_id', ''),
                        'sender_id': sender_id_wrapper,
                    }
                else:
                    event_data = event.event
            elif hasattr(event, 'message'):
                msg_obj = event
            elif hasattr(event, 'event') and hasattr(event.event, 'message'):
                msg_obj = event.event
            else:
                print(f"[WARN] 无法识别事件格式: event={type(event).__name__}")
                return

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

            if isinstance(event_data, dict):
                msg_type = event_data.get('msg_type', '')
                message_id = event_data.get('message_id', '')
                print(f"收到消息: type={msg_type}, message_id={message_id}")

                if self._event_handler:
                    self._event_handler({
                        "type": msg_type,
                        "message_id": message_id,
                        "chat_id": event_data.get('chat_id', ''),
                        "sender_id": event_data.get('sender_id', {}),
                        "content": event_data.get('content', ''),
                    })

        except Exception as e:
            print(f"处理消息事件失败: {e}")
            import traceback
            traceback.print_exc()

    def _handle_card_action(self, event):
        """
        处理卡片按钮回调事件（card.action.trigger）

        使用 register_p2_card_action_trigger 注册时，
        SDK 会传入类型化的事件对象。先打印完整结构用于调试。
        """
        try:
            print(f"DEBUG card_action: event type = {type(event).__name__}")
            print(f"DEBUG card_action: dir = {[a for a in dir(event) if not a.startswith('_')]}")

            # 尝试多种方式提取数据
            event_data = None

            if hasattr(event, 'event') and isinstance(event.event, dict):
                event_data = event.event
            elif hasattr(event, 'event') and event.event is not None:
                event_data = event.event
            else:
                event_data = event

            print(f"DEBUG card_action: event_data type = {type(event_data).__name__}")
            if hasattr(event_data, '__dict__'):
                print(f"DEBUG card_action: event_data.__dict__ = {event_data.__dict__}")

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

            print(f"卡片回调: open_id={open_id}, action_value={action_value}")

            if self._interactive_handler:
                self._interactive_handler({
                    "type": "card_action",
                    "open_id": open_id,
                    "action_value": action_value,
                    "event": event_data,
                })
            else:
                print("[WARN] 未设置 interactive_handler")

        except Exception as e:
            print(f"处理卡片回调失败: {e}")
            import traceback
            traceback.print_exc()

    def set_interactive_handler(self, handler: Callable):
        """设置交互事件处理器"""
        self._interactive_handler = handler

    def stop(self):
        """停止 WebSocket 连接"""
        pass


def create_ws_bot(config_path: str = ".env") -> WebSocketBot:
    """从环境变量创建 WebSocket Bot"""
    from dotenv import load_dotenv

    load_dotenv(config_path)

    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")
    verification_token = os.getenv("FEISHU_VERIFICATION_TOKEN", "")
    encrypt_key = os.getenv("FEISHU_ENCRYPT_KEY", "")

    if not app_id or not app_secret:
        raise ValueError("FEISHU_APP_ID 和 FEISHU_APP_SECRET 必须设置")

    from feishu.bot import FeishuBot
    from feishu.handler import MessageHandler

    feishu_bot = FeishuBot({
        "app_id": app_id,
        "app_secret": app_secret,
    })

    message_handler = MessageHandler(feishu_bot)
    processed_messages = set()

    def event_handler(event: dict):
        """处理收到的消息事件"""
        msg_type = event.get("type", "")
        chat_id = event.get("chat_id", "")
        sender_id = event.get("sender_id", {})
        content = event.get("content", "")
        message_id = event.get("message_id", "")

        if message_id and message_id in processed_messages:
            print(f"跳过重复消息: {message_id}")
            return
        if message_id:
            processed_messages.add(message_id)

        print(f"收到消息: type={msg_type}, chat_id={chat_id}")

        if msg_type == "text":
            from feishu.bot import TextMessage
            import json
            try:
                content_dict = json.loads(content) if isinstance(content, str) else content
            except json.JSONDecodeError:
                content_dict = {"text": content}
            msg_obj = TextMessage(content_dict)
        elif msg_type == "image":
            from feishu.bot import ImageMessage
            import json
            try:
                content_dict = json.loads(content) if isinstance(content, str) else content
            except json.JSONDecodeError:
                content_dict = {"image_key": content}
            msg_obj = ImageMessage(content_dict)
        elif msg_type == "post":
            import json
            try:
                post_content = json.loads(content) if isinstance(content, str) else content
                image_key = None
                for block in post_content.get("content", []):
                    for item in block:
                        if item.get("tag") == "img":
                            image_key = item.get("image_key")
                            break
                    if image_key:
                        break
                if image_key:
                    from feishu.bot import ImageMessage
                    msg_obj = ImageMessage({"image_key": image_key})
                else:
                    print(f"富文本消息中未找到图片")
                    return
            except (json.JSONDecodeError, KeyError) as e:
                print(f"解析富文本消息失败: {e}")
                return
        else:
            print(f"不支持的消息类型: {msg_type}")
            return

        msg_obj.chat_id = chat_id
        msg_obj.sender_id = sender_id
        msg_obj.message_id = event.get("message_id", "")

        open_id = sender_id.get("open_id", "") if isinstance(sender_id, dict) else ""
        if open_id and msg_type == "image":
            feishu_bot.send_message(open_id, "📥 收到图片，正在识别 OCR，请稍候...")

        response = message_handler.handle(msg_obj)

        if isinstance(response, dict) and response.get("type") == "card":
            card_json = response.get("content", "")
            result = feishu_bot.send_interactive_card(open_id, card_json)
            print(f"卡片发送结果: {result}")
        else:
            response_text = response if isinstance(response, str) else str(response)
            if open_id:
                result = feishu_bot.send_message(open_id, response_text)
                print(f"回复结果: {result}")

    ws_bot = WebSocketBot(app_id, app_secret, event_handler, verification_token, encrypt_key)

    def interactive_handler(event: dict):
        """处理卡片按钮回调"""
        from feishu.cards import parse_card_callback
        from feishu.bitable import BitableTable

        event_type = event.get("type", "")
        open_id = event.get("open_id", "")

        print(f"收到交互回调: type={event_type}, open_id={open_id}")

        action_value = event.get("action_value", {})
        if not action_value:
            print("回调 action_value 为空，跳过")
            return

        try:
            callback = parse_card_callback(action_value)
        except ValueError as e:
            print(f"解析回调失败: {e}")
            return

        print(f"解析结果: action={callback.action}, table={callback.table_name}")
        print(f"record_data: {callback.record_data}")

        if callback.action == "approve":
            try:
                table = BitableTable(table_name=callback.table_name)
                record_id = table.create(callback.record_data)
                print(f"写入成功: record_id={record_id}")

                if open_id:
                    record_info = "\n".join([
                        f"• {k}: {v}" for k, v in callback.record_data.items() if v
                    ])
                    success_msg = f"✅ 磅单已成功录入！\n\n{record_info}"
                    feishu_bot.send_message(open_id, success_msg)

            except Exception as e:
                print(f"写入失败: {e}")
                if open_id:
                    feishu_bot.send_message(open_id, f"❌ 写入失败: {e}")

        elif callback.action == "cancel":
            if open_id:
                feishu_bot.send_message(open_id, "已取消操作。如需继续，请重新发送磅单图片。")

    ws_bot.set_interactive_handler(interactive_handler)

    return ws_bot


if __name__ == "__main__":
    bot = create_ws_bot()
    print("启动 WebSocket Bot（按 Ctrl+C 退出）...")
    bot.start()
