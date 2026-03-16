"""
飞书 Bot WebSocket 客户端 - 接收实时消息事件
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
        """
        Args:
            app_id: 飞书应用 ID
            app_secret: 飞书应用密钥
            event_handler: 事件处理函数
            verification_token: 飞书 verification_token
            encrypt_key: 飞书 encryption_key
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self.verification_token = verification_token or ""
        self.encrypt_key = encrypt_key or ""
        self._event_handler = event_handler
        self._ws_client: Optional[LarkClient] = None

    def start(self):
        """启动 WebSocket 连接"""
        # 创建事件分发处理器
        handler = EventDispatcherHandler()

        # 注册消息接收事件处理器
        builder = handler.builder(self.encrypt_key, self.verification_token)

        # 注册所有可能的消息事件（p1 是 v1 格式，p2 是 v2 格式）
        for event_type in ["im.message.receive", "im.message.receive_v1"]:
            # p1 格式
            try:
                builder.register_p1_customized_event(event_type, self._handle_message_event)
                print(f"注册成功: p1.{event_type}")
            except Exception as e:
                print(f"注册失败: p1.{event_type}: {e}")
            # p2 格式
            try:
                builder.register_p2_customized_event(event_type, self._handle_message_event)
                print(f"注册成功: p2.{event_type}")
            except Exception as e:
                print(f"注册失败: p2.{event_type}: {e}")

        # 注册交互式卡片回调事件（im.interactive）
        for event_type in ["im.interactive", "im.interactive_v1"]:
            try:
                builder.register_p1_customized_event(event_type, self._handle_interactive_event)
                print(f"注册成功: p1.{event_type}")
            except Exception as e:
                print(f"注册失败: p1.{event_type}: {e}")
            try:
                builder.register_p2_customized_event(event_type, self._handle_interactive_event)
                print(f"注册成功: p2.{event_type}")
            except Exception as e:
                print(f"注册失败: p2.{event_type}: {e}")

        # build 会返回新的 handler，需要重新赋值
        handler = builder.build()

        # 打印已注册的处理器
        print(f"已注册的处理器: {list(handler._processorMap.keys())}")

        # 创建飞书 WebSocket 客户端
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
        """
        处理消息接收事件

        Args:
            event: 飞书 CustomizedEvent 事件
        """
        try:
            # 打印所有收到的事件（调试用）
            print(f"DEBUG: 收到事件: type={getattr(event, 'type', getattr(event.header, 'event_type', 'unknown'))}")

            # p1 事件结构: event.type, event.event
            # p2 事件结构: event.header.event_type, event.event

            # 提取事件类型
            event_type = getattr(event, 'type', None) or getattr(event.header, 'event_type', 'unknown')

            # 提取事件内容（p1 和 p2 结构不同）
            event_data = {}
            msg_obj = None

            if hasattr(event, 'event') and isinstance(event.event, dict):
                # 检查是否是 p2 格式（event.event 是 dict 且包含 'message' 键）
                if 'message' in event.event:
                    # p2 格式：event.event 是字典，包含 message 和 sender
                    raw_event = event.event
                    msg_wrapper = raw_event.get('message', {})
                    sender_wrapper = raw_event.get('sender', {})
                    sender_id_wrapper = sender_wrapper.get('sender_id', {})

                    # 提取实际消息内容
                    event_data = {
                        'msg_type': msg_wrapper.get('message_type', ''),
                        'content': msg_wrapper.get('content', ''),
                        'message_id': msg_wrapper.get('message_id', ''),
                        'chat_id': msg_wrapper.get('chat_id', ''),
                        'sender_id': sender_id_wrapper,
                    }
                else:
                    # p1 格式：event.event 是字典，但没有 'message' 键
                    event_data = event.event
            elif hasattr(event, 'message'):
                # p2 格式 A：event.message 是消息对象（少见）
                msg_obj = event
            elif hasattr(event, 'event') and hasattr(event.event, 'message'):
                # p2 格式 B：event.event.message 是消息对象
                msg_obj = event.event
            else:
                # 未知格式
                print(f"[WARN] 无法识别事件格式: event={type(event).__name__}")
                return

            # 解析 p2 格式消息（格式 A/B）
            if msg_obj:
                # print(f"DEBUG: msg_obj = {msg_obj}, type = {type(msg_obj)}")
                pass

                # 获取 message 属性
                # p2 格式：event.message.message 才是实际消息内容
                msg_wrapper = getattr(msg_obj, 'message', None)

                if msg_wrapper:
                    # 尝试两种方式：直接获取 或 通过 .message 获取
                    msg_info = getattr(msg_wrapper, 'message', None) or msg_wrapper
                    event_data = {
                        'msg_type': getattr(msg_info, 'message_type', ''),
                        'content': getattr(msg_info, 'content', ''),
                        'message_id': getattr(msg_info, 'message_id', ''),
                        'chat_id': getattr(msg_info, 'chat_id', ''),
                    }
                    # 从 message wrapper 中获取 sender
                    sender_wrapper = getattr(msg_wrapper, 'sender', None)
                    if sender_wrapper:
                        sender_id = getattr(sender_wrapper, 'sender_id', {})
                        # 如果是对象，尝试转换为 dict
                        if not isinstance(sender_id, dict):
                            sender_id = {"open_id": getattr(sender_id, 'open_id', '')}
                        event_data['sender_id'] = sender_id

            print(f"收到事件: type={event_type}, event_data={event_data}")

            # 解析消息内容
            if isinstance(event_data, dict):
                msg_type = event_data.get('msg_type', '')
                content = event_data.get('content', '')
                message_id = event_data.get('message_id', '')
                chat_id = event_data.get('chat_id', '')
                sender_id = event_data.get('sender_id', {})

                print(f"收到消息: type={msg_type}, message_id={message_id}")

                # 调用事件处理器
                if self._event_handler:
                    self._event_handler({
                        "type": msg_type,
                        "message_id": message_id,
                        "chat_id": chat_id,
                        "sender_id": sender_id,
                        "content": content,
                    })

        except Exception as e:
            print(f"处理消息事件失败: {e}")
            import traceback
            traceback.print_exc()

    def _handle_interactive_event(self, event):
        """
        处理交互式卡片回调事件

        Args:
            event: 飞书交互事件
        """
        try:
            print(f"DEBUG: 收到交互事件: type={getattr(event, 'type', getattr(event.header, 'event_type', 'unknown'))}")

            # 提取事件数据
            event_data = {}
            if hasattr(event, 'event') and isinstance(event.event, dict):
                event_data = event.event

            # 解析回调数据
            callback_type = event_data.get("type", "")
            callback_content = event_data.get("content", {})

            print(f"交互事件: callback_type={callback_type}")

            # 调用交互处理器（如果已注册）
            if hasattr(self, '_interactive_handler') and self._interactive_handler:
                self._interactive_handler({
                    "type": callback_type,
                    "content": callback_content,
                    "event": event_data,
                })

        except Exception as e:
            print(f"处理交互事件失败: {e}")
            import traceback
            traceback.print_exc()

    def set_interactive_handler(self, handler: Callable):
        """设置交互事件处理器"""
        self._interactive_handler = handler

    def stop(self):
        """停止 WebSocket 连接"""
        # TODO: 实现停止逻辑
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

    # 创建消息处理器
    from feishu.bot import FeishuBot
    from feishu.handler import MessageHandler

    # API 客户端（用于发送消息）
    feishu_bot = FeishuBot({
        "app_id": app_id,
        "app_secret": app_secret,
    })

    # 消息处理器
    message_handler = MessageHandler(feishu_bot)

    # 已处理的消息 ID 集合（去重）
    processed_messages = set()

    def event_handler(event: dict):
        """处理收到的事件"""
        msg_type = event.get("type", "")
        chat_id = event.get("chat_id", "")
        sender_id = event.get("sender_id", {})
        content = event.get("content", "")
        message_id = event.get("message_id", "")

        # 去重：避免 p1 和 p2 格式重复处理
        if message_id and message_id in processed_messages:
            print(f"跳过重复消息: {message_id}")
            return
        if message_id:
            processed_messages.add(message_id)

        print(f"收到消息: type={msg_type}, chat_id={chat_id}")

        # 解析消息对象
        # 支持的类型: text, image, post (富文本)
        if msg_type == "text":
            from feishu.bot import TextMessage
            # content 可能是 JSON 字符串，需要先解析
            import json
            try:
                content_dict = json.loads(content) if isinstance(content, str) else content
            except json.JSONDecodeError:
                content_dict = {"text": content}
            msg_obj = TextMessage(content_dict)
        elif msg_type == "image":
            from feishu.bot import ImageMessage
            # image content 也是 JSON 字符串
            import json
            try:
                content_dict = json.loads(content) if isinstance(content, str) else content
            except json.JSONDecodeError:
                content_dict = {"image_key": content}
            msg_obj = ImageMessage(content_dict)
        elif msg_type == "post":
            # 富文本消息，可能包含图片
            import json
            try:
                post_content = json.loads(content) if isinstance(content, str) else content
                # 提取第一张图片
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

        # 设置必要的属性
        msg_obj.chat_id = chat_id
        msg_obj.sender_id = sender_id
        msg_obj.message_id = event.get("message_id", "")

        # 即时反馈：图片消息立即发送"收到"提示
        open_id = sender_id.get("open_id", "") if isinstance(sender_id, dict) else ""
        if open_id and msg_type == "image":
            # 立即发送"收到"反馈
            feishu_bot.send_message(open_id, "📥 收到图片，正在识别 OCR，请稍候...")

        # 处理消息并获取回复
        response = message_handler.handle(msg_obj)

        # 根据返回类型发送不同响应
        if isinstance(response, dict) and response.get("type") == "card":
            # 卡片消息：发送交互式卡片
            card_json = response.get("content", "")
            result = feishu_bot.send_interactive_card(open_id, card_json)
            print(f"卡片发送结果: {result}")
        else:
            # 文本消息
            response_text = response if isinstance(response, str) else str(response)
            if open_id:
                result = feishu_bot.send_message(open_id, response_text)
                print(f"回复结果: {result}")

    # 创建 WebSocket Bot
    ws_bot = WebSocketBot(app_id, app_secret, event_handler, verification_token, encrypt_key)

    # 注册交互事件处理器
    def interactive_handler(event: dict):
        """处理卡片交互回调"""
        from feishu.cards import parse_card_callback
        from feishu.bitable import BitableTable
        import json

        event_type = event.get("type", "")
        content = event.get("content", {})

        print(f"收到交互回调: type={event_type}")

        # 解析回调数据
        if event_type == "interactive":
            # 回调的 content 是 JSON 字符串
            callback_value = {}
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except json.JSONDecodeError:
                    print(f"解析回调内容失败: {content}")
                    return

            # 获取 value 字段
            callback_value = content.get("value", {})

            # 解析动作
            try:
                callback = parse_card_callback(callback_value)
            except ValueError as e:
                print(f"解析回调失败: {e}")
                return

            print(f"解析结果: action={callback.action}, table={callback.table_name}")
            print(f"用户输入数据: {callback.record_data}")

            # 根据动作处理
            if callback.action == "approve":
                # 审核通过：写入 Bitable
                try:
                    table = BitableTable(table_name=callback.table_name)
                    record_id = table.create(callback.record_data)
                    print(f"写入成功: record_id={record_id}")

                    # 发送成功通知
                    # 获取发送者 open_id
                    sender_id = content.get("sender_id", {})
                    open_id = sender_id.get("open_id", "") if isinstance(sender_id, dict) else ""

                    if open_id:
                        # 构建成功消息
                        record_info = "\n".join([
                            f"• {k}: {v}" for k, v in callback.record_data.items()
                        ])
                        success_msg = f"✅ 磅单已成功录入！\n\n{record_info}"
                        feishu_bot.send_message(open_id, success_msg)
                except Exception as e:
                    print(f"写入失败: {e}")
                    # 发送失败通知
                    sender_id = content.get("sender_id", {})
                    open_id = sender_id.get("open_id", "") if isinstance(sender_id, dict) else ""
                    if open_id:
                        feishu_bot.send_message(open_id, f"❌ 写入失败: {e}")

            elif callback.action == "edit":
                # 先录入：返回编辑态卡片
                sender_id = content.get("sender_id", {})
                open_id = sender_id.get("open_id", "") if isinstance(sender_id, dict) else ""

                if open_id:
                    from feishu.cards import CardTemplate
                    template = CardTemplate()
                    card_json = template.generate_with_inputs(
                        table_name=callback.table_name,
                        record_data=callback.record_data,
                        title="磅单编辑（修改后提交）",
                    )
                    result = feishu_bot.send_interactive_card(open_id, card_json)
                    print(f"编辑卡片发送结果: {result}")

            elif callback.action == "cancel":
                # 取消
                sender_id = content.get("sender_id", {})
                open_id = sender_id.get("open_id", "") if isinstance(sender_id, dict) else ""
                if open_id:
                    feishu_bot.send_message(open_id, "已取消操作。如需继续，请重新发送磅单图片。")

    # 设置交互处理器
    ws_bot.set_interactive_handler(interactive_handler)

    return ws_bot


if __name__ == "__main__":
    # 测试
    bot = create_ws_bot()
    print("启动 WebSocket Bot（按 Ctrl+C 退出）...")
    bot.start()
