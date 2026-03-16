"""
飞书 Bot 模块 - WebSocket 事件接收与消息卡片
"""

import json
from typing import Callable, Optional, Any
from lark_oapi import Client


class FeishuBot:
    """飞书 Bot WebSocket 事件接收"""

    def __init__(self, config: dict):
        """
        Args:
            config: 飞书配置，包含 app_id, app_secret, verification_token, encryption_key
        """
        self.app_id = config.get("app_id")
        self.app_secret = config.get("app_secret")
        self.verification_token = config.get("verification_token")
        self.encryption_key = config.get("encryption_key")

        # 飞书客户端
        self.client = Client.builder().app_id(self.app_id).app_secret(self.app_secret).build()

        # 消息处理器
        self._message_handler: Optional[Callable] = None

    def set_message_handler(self, handler: Callable):
        """设置消息处理器"""
        self._message_handler = handler

    def handle_event(self, event: dict) -> dict:
        """
        处理飞书事件

        Args:
            event: 飞书 Webhook 事件

        Returns:
            处理结果
        """
        event_type = event.get("type")
        event_data = event.get("event", {})

        if event_type == "url_verification":
            # URL 验证
            return {"challenge": event_data.get("challenge")}

        if event_type == "event_callback":
            callback_type = event_data.get("type")

            if callback_type == "message":
                # 处理消息事件
                return self._handle_message(event_data)

        return {"code": 0, "msg": "success"}

    def _handle_message(self, event_data: dict) -> dict:
        """处理消息"""
        message = event_data.get("message", {})
        msg_type = message.get("msg_type")
        content = message.get("content", {})

        # 解析消息内容
        message_obj = self._parse_message(msg_type, content)
        if message_obj:
            message_obj.sender_id = message.get("sender_id", {})
            message_obj.chat_id = event_data.get("chat_id", "")
            message_obj.message_id = message.get("message_id", "")

        # 调用消息处理器
        if self._message_handler and message_obj:
            try:
                result = self._message_handler(message_obj)
                return {"code": 0, "msg": "success", "result": result}
            except Exception as e:
                return {"code": 1, "msg": str(e)}

        return {"code": 0, "msg": "success"}

    def _parse_message(self, msg_type: str, content: Any) -> Optional["BotMessage"]:
        """解析消息为 BotMessage 对象"""
        if msg_type == "text":
            return TextMessage(content)
        elif msg_type == "image":
            return ImageMessage(content)
        elif msg_type == "file":
            return FileMessage(content)

        return None

    def send_message(self, receive_id: str, content: str, msg_type: str = "text") -> dict:
        """
        发送消息

        Args:
            receive_id: 接收者 ID（用户 open_id 或群 chat_id）
            content: 消息内容
            msg_type: 消息类型

        Returns:
            发送结果
        """
        import requests

        # 获取 token
        token_resp = requests.post(
            'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
            json={"app_id": self.app_id, "app_secret": self.app_secret}
        )
        token_data = token_resp.json()
        if token_data.get('code') != 0:
            return {"code": token_data.get('code'), "msg": token_data.get('msg')}

        token = token_data.get('tenant_access_token')

        # 构造消息内容
        if msg_type == "text":
            content_json = json.dumps({"text": content})
        else:
            content_json = content

        # 发送消息
        resp = requests.post(
            'https://open.feishu.cn/open-apis/im/v1/messages',
            headers={'Authorization': f'Bearer {token}'},
            params={'receive_id_type': 'open_id'},
            json={
                'receive_id': receive_id,
                'msg_type': msg_type,
                'content': content_json
            }
        )
        data = resp.json()
        if data.get('code') == 0:
            return {"code": 0, "data": data.get('data')}
        else:
            return {"code": data.get('code'), "msg": data.get('msg')}

    def send_interactive_card(self, receive_id: str, card_json: str) -> dict:
        """发送卡片消息"""
        import requests

        # 获取 token
        token_resp = requests.post(
            'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
            json={"app_id": self.app_id, "app_secret": self.app_secret}
        )
        token_data = token_resp.json()
        if token_data.get('code') != 0:
            return {"code": token_data.get('code'), "msg": token_data.get('msg')}

        token = token_data.get('tenant_access_token')

        # 飞书 API：content 需要双重 JSON 序列化
        # 1. 先把 card_json 字符串解析为 dict
        # 2. 再把整个请求序列化为 JSON 字符串
        card_dict = json.loads(card_json)

        resp = requests.post(
            'https://open.feishu.cn/open-apis/im/v1/messages',
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json; charset=utf-8',
            },
            params={'receive_id_type': 'open_id'},
            data=json.dumps({
                'receive_id': receive_id,
                'msg_type': 'interactive',
                'content': json.dumps(card_dict, ensure_ascii=False),
            }, ensure_ascii=False)
        )
        data = resp.json()
        if data.get('code') == 0:
            return {"code": 0, "data": data.get('data')}
        else:
            return {"code": data.get('code'), "msg": data.get('msg')}

    def upload_image(self, image_path: str) -> Optional[str]:
        """上传图片，返回 image_key"""
        with open(image_path, "rb") as f:
            response = self.client.im.v1.image.upload({
                "image_type": "message",
                "image": f.read(),
            })

        if response.success():
            return response.data.get("image_key")
        return None

    def get_image(self, image_key: str, message_id: str | None = None) -> Optional[bytes]:
        """下载图片 - 使用 message_resource API"""
        import requests

        # 获取 token
        token_resp = requests.post(
            'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
            json={"app_id": self.app_id, "app_secret": self.app_secret}
        )
        token_data = token_resp.json()
        if token_data.get('code') != 0:
            print(f"获取 token 失败: {token_data}")
            return None

        token = token_data.get('tenant_access_token')

        # 优先使用 message_resource API（通过 message_id 下载）
        if message_id and image_key:
            # 使用飞书 SDK 的 message_resource.get，需要传 file_key
            from lark_oapi.api.im.v1.model import GetMessageResourceRequest
            request = GetMessageResourceRequest.builder().message_id(message_id).type('image').file_key(image_key).build()
            response = self.client.im.v1.message_resource.get(request)
            if response.success():
                # file 是 BytesIO，转为 bytes
                if hasattr(response.file, 'read'):
                    return response.file.read()
                return response.file
            else:
                print(f"message_resource 下载失败: {response.code} {response.msg}")

        # 备用：尝试直接用 image_key 下载
        # 注意：消息中的图片 key 是临时的，可能已过期
        resp = requests.get(
            f'https://open.feishu.cn/open-apis/im/v1/images/{image_key}/content',
            headers={'Authorization': f'Bearer {token}'}
        )

        if resp.status_code == 200:
            return resp.content
        else:
            print(f"下载图片失败: {resp.status_code} {resp.text}")
            return None


class BotMessage:
    """Bot 消息基类"""

    def __init__(self, content: Any):
        self.content = content
        self.type = "unknown"
        self.sender_id = {}
        self.chat_id = ""
        self.message_id = ""


class TextMessage(BotMessage):
    """文本消息"""

    def __init__(self, content: Any):
        super().__init__(content)
        self.type = "text"
        if isinstance(content, dict):
            self.text = content.get("text", "")
        else:
            self.text = str(content)


class ImageMessage(BotMessage):
    """图片消息"""

    def __init__(self, content: Any):
        super().__init__(content)
        self.type = "image"
        if isinstance(content, dict):
            self.image_key = content.get("image_key", "")
        else:
            self.image_key = str(content)


class FileMessage(BotMessage):
    """文件消息"""

    def __init__(self, content: Any):
        super().__init__(content)
        self.type = "file"
        if isinstance(content, dict):
            self.file_key = content.get("file_key", "")
        else:
            self.file_key = str(content)
