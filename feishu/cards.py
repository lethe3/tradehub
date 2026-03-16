"""
飞书交互卡片生成器 - 从 Schema 生成卡片 JSON

修复点：
1. 卡片顶层添加 config: {wide_screen_mode: true}
2. action 组件放入 elements 数组内（不是顶层 actions 字段）
3. 按钮前加 hr 分隔线
4. 按钮 value 携带 record_data（JSON 序列化为字符串）
5. 使用 div + fields 布局替代单独 markdown，更紧凑
"""

import json
from dataclasses import dataclass
from typing import Any
from schema.loader import Schema, get_schema


class CardTemplate:
    """飞书交互卡片模板生成器"""

    def __init__(self, schema: Schema | None = None):
        self.schema = schema or get_schema()

    def generate(
        self,
        table_name: str,
        record_data: dict[str, Any],
        title: str | None = None,
    ) -> str:
        """
        生成只读展示卡片 JSON 字符串

        Args:
            table_name: 表名（如 "weigh_tickets"）
            record_data: 记录数据，key 为字段名
            title: 卡片标题

        Returns:
            卡片 JSON 字符串
        """
        table = self.schema.get_table(table_name)
        if not table:
            raise ValueError(f"表 {table_name} 不存在于 schema 中")

        # 构建 elements（内容 + 分隔线 + 按钮）
        elements = self._build_display_elements(table, record_data)
        elements.append({"tag": "hr"})
        elements.append(self._build_action_element(table_name, record_data))

        card = {
            "config": {
                "wide_screen_mode": True,
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title or f"{table.name} - 待确认",
                },
                "template": "blue",
            },
            "elements": elements,
        }

        return json.dumps(card, ensure_ascii=False)

    def _build_display_elements(self, table, record_data: dict) -> list[dict]:
        """构建只读展示元素 - 使用 div + fields 双列布局"""
        fields_content = []

        for field in table.fields:
            # 跳过自动编号字段
            if field.type == 1005:
                continue

            value = record_data.get(field.name, "")
            value_str = str(value) if value else "-"

            # 关联字段加提示
            if field.type in (18, 19):
                value_str = value_str + "（关联）" if value_str != "-" else "待关联"

            fields_content.append({
                "is_short": True,
                "text": {
                    "tag": "lark_md",
                    "content": f"**{field.name}**\n{value_str}",
                },
            })

        # 如果字段数是奇数，补一个空占位
        if len(fields_content) % 2 != 0:
            fields_content.append({
                "is_short": True,
                "text": {
                    "tag": "lark_md",
                    "content": "",
                },
            })

        return [
            {
                "tag": "div",
                "fields": fields_content,
            }
        ]

    def _build_action_element(self, table_name: str, record_data: dict) -> dict:
        """
        构建按钮操作元素（放在 elements 数组内）

        关键：value 中携带 record_data，回调时能拿到完整数据
        """
        # 将 record_data 序列化为 JSON 字符串，放入 value
        record_json = json.dumps(record_data, ensure_ascii=False)

        return {
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {
                        "tag": "plain_text",
                        "content": "✅ 确认录入",
                    },
                    "type": "primary",
                    "value": {
                        "action": "approve",
                        "table": table_name,
                        "record_data": record_json,
                    },
                },
                {
                    "tag": "button",
                    "text": {
                        "tag": "plain_text",
                        "content": "❌ 取消",
                    },
                    "type": "danger",
                    "value": {
                        "action": "cancel",
                        "table": table_name,
                    },
                },
            ],
        }

    def generate_with_inputs(
        self,
        table_name: str,
        record_data: dict[str, Any],
        title: str | None = None,
    ) -> str:
        """
        生成带输入控件的卡片（编辑态）

        注意：飞书对 plain_text_input 等组件有版本限制，
        部分客户端可能不支持。先保留此方法供后续使用。
        """
        table = self.schema.get_table(table_name)
        if not table:
            raise ValueError(f"表 {table_name} 不存在于 schema 中")

        elements = self._build_input_elements(table, record_data)
        elements.append({"tag": "hr"})
        elements.append(self._build_action_element(table_name, record_data))

        card = {
            "config": {
                "wide_screen_mode": True,
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title or f"{table.name} - 审核/编辑",
                },
                "template": "blue",
            },
            "elements": elements,
        }

        return json.dumps(card, ensure_ascii=False)

    def _build_input_elements(self, table, record_data: dict) -> list[dict]:
        """构建带输入控件的元素"""
        elements = []

        for field in table.fields:
            if field.type == 1005:
                continue

            value = record_data.get(field.name, "")
            value_str = str(value) if value else ""

            if field.type == 3 and field.options:
                # 单选 - 下拉菜单
                options = [
                    {"text": {"tag": "plain_text", "content": opt.name}, "value": opt.name}
                    for opt in field.options
                ]
                elements.append({
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"**{field.name}**"},
                })
                elements.append({
                    "tag": "select_static",
                    "name": field.name,
                    "options": options,
                    "placeholder": {"tag": "plain_text", "content": f"选择{field.name}"},
                })
            elif field.type == 5:
                # 日期
                elements.append({
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"**{field.name}**"},
                })
                elements.append({
                    "tag": "date_picker",
                    "name": field.name,
                    "placeholder": {"tag": "plain_text", "content": "选择日期"},
                })
            else:
                # 文本/数字/关联 - 显示为 markdown（飞书 plain_text_input 兼容性差）
                extra = "（填写合同号或名称）" if field.type in (18, 19) else ""
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**{field.name}**{extra}: {value_str}",
                    },
                })

        return elements


def create_card_template() -> CardTemplate:
    """创建卡片模板生成器"""
    return CardTemplate(get_schema())


@dataclass
class CardCallback:
    """卡片回调数据"""
    action: str  # "approve", "cancel"
    table_name: str
    record_data: dict[str, Any]


def parse_card_callback(callback_data: dict) -> CardCallback:
    """
    解析卡片回调数据

    飞书卡片按钮点击回调：
    - callback_data 是按钮的 value 字段内容
    - record_data 是 JSON 字符串，需要反序列化

    Args:
        callback_data: 飞书回调中按钮的 value 字段

    Returns:
        CardCallback 对象

    Raises:
        ValueError: 解析失败
    """
    action = callback_data.get("action", "")
    table_name = callback_data.get("table", "")

    if not action:
        raise ValueError("回调数据中缺少 action 字段")

    # record_data 是 JSON 字符串，需要反序列化
    record_data = {}
    record_json = callback_data.get("record_data", "")
    if record_json:
        try:
            record_data = json.loads(record_json)
        except json.JSONDecodeError:
            # 如果不是 JSON，当作普通字符串处理
            record_data = {"raw": record_json}

    return CardCallback(
        action=action,
        table_name=table_name,
        record_data=record_data,
    )


# 导出
__all__ = ["CardTemplate", "create_card_template", "CardCallback", "parse_card_callback"]
