"""
飞书交互卡片生成器 - 从 Schema 生成卡片 JSON

支持根据表结构自动生成卡片：
- 文本 → plain_text_input
- 数字 → plain_text_input
- 单选 → option（从 schema 读取选项）
- 日期 → date_picker
- 关联 → plain_text_input
"""

import json
from dataclasses import dataclass
from typing import Any
from schema.loader import Schema, get_schema


class CardTemplate:
    """飞书交互卡片模板生成器"""

    # 飞书字段类型到卡片元素的映射
    FIELD_TYPE_MAP = {
        1: "plain_text_input",    # 文本
        2: "plain_text_input",    # 数字
        3: "option",              # 单选
        5: "date_picker",         # 日期
        18: "plain_text_input",   # 单向关联
        19: "plain_text_input",   # 双向关联
    }

    def __init__(self, schema: Schema | None = None):
        self.schema = schema or get_schema()

    def generate(
        self,
        table_name: str,
        record_data: dict[str, Any],
        title: str | None = None,
    ) -> str:
        """
        生成卡片 JSON 字符串

        Args:
            table_name: 表名（如 "weigh_tickets"）
            record_data: 记录数据，key 为字段名
            title: 卡片标题，默认使用表名

        Returns:
            卡片 JSON 字符串
        """
        table = self.schema.get_table(table_name)
        if not table:
            raise ValueError(f"表 {table_name} 不存在于 schema 中")

        # 构建卡片结构
        card = {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title or f"{table.name} - 待确认",
                },
                "template": "blue",
            },
            "elements": self._build_elements(table, record_data),
            "actions": self._build_actions(table_name),
        }

        return json.dumps(card, ensure_ascii=False)

    def _build_elements(self, table, record_data: dict) -> list[dict]:
        """构建卡片元素"""
        elements = []

        # 遍历字段，生成对应的输入元素
        for field in table.fields:
            # 跳过自动编号字段
            if field.type == 1005:
                continue

            value = record_data.get(field.name, "")

            # 构建字段元素
            element = self._build_field_element(field, value)
            if element:
                elements.append(element)

        return elements

    def _build_field_element(self, field, value: Any) -> dict | None:
        """根据字段类型构建对应的卡片元素"""
        field_type = field.type

        # 获取当前值（转为字符串）
        value_str = ""
        if value is not None:
            value_str = str(value)

        # 简化格式：字段名: 值，显示为一行
        # 关联字段加提示
        extra = "（填写合同号或名称）" if (field_type == 18 or field_type == 19) else ""

        # 使用 markdown 格式，更兼容
        return {
            "tag": "markdown",
            "content": f"**{field.name}**: {value_str}{extra}",
        }

    def generate_with_inputs(
        self,
        table_name: str,
        record_data: dict[str, Any],
        title: str | None = None,
    ) -> str:
        """
        生成带输入控件的卡片（用于编辑态）

        Args:
            table_name: 表名
            record_data: 记录数据
            title: 卡片标题

        Returns:
            卡片 JSON 字符串
        """
        table = self.schema.get_table(table_name)
        if not table:
            raise ValueError(f"表 {table_name} 不存在于 schema 中")

        card = {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title or f"{table.name} - 审核/编辑",
                },
                "template": "blue",
            },
            "elements": self._build_input_elements(table, record_data),
            "actions": self._build_actions(table_name),
        }

        return json.dumps(card, ensure_ascii=False)

    def _build_input_elements(self, table, record_data: dict) -> list[dict]:
        """构建带输入控件的元素"""
        elements = []

        for field in table.fields:
            # 跳过自动编号字段
            if field.type == 1005:
                continue

            value = record_data.get(field.name, "")
            value_str = str(value) if value else ""

            # 根据字段类型选择不同的输入控件
            if field.type == 3 and field.options:
                # 单选 - 使用下拉菜单
                options = [
                    {"text": {"tag": "plain_text", "content": opt.name}, "value": opt.name}
                    for opt in field.options
                ]
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**{field.name}**",
                    },
                })
                elements.append({
                    "tag": "select_static",
                    "name": field.name,
                    "options": options,
                    "value": value_str,
                })
            elif field.type == 5:
                # 日期 - 使用日期选择器
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**{field.name}**",
                    },
                })
                elements.append({
                    "tag": "date_picker",
                    "name": field.name,
                    "value": value_str,
                })
            elif field.type == 18 or field.type == 19:
                # 关联字段
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**{field.name}**（填写合同号或名称）",
                    },
                })
                elements.append({
                    "tag": "plain_text_input",
                    "name": field.name,
                    "value": value_str,
                })
            else:
                # 文本、数字等 - 使用文本输入
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**{field.name}**",
                    },
                })
                elements.append({
                    "tag": "plain_text_input",
                    "name": field.name,
                    "value": value_str,
                })

        return elements

    def _build_actions(self, table_name: str) -> list[dict]:
        """构建操作按钮"""
        return [
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "✅ 审核通过",
                        },
                        "type": "primary",
                        "value": {
                            "action": "approve",
                            "table": table_name,
                        },
                    },
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "✏️ 先录入",
                        },
                        "type": "default",
                        "value": {
                            "action": "edit",
                            "table": table_name,
                        },
                    },
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "❌ 取消",
                        },
                        "type": "default",
                        "value": {
                            "action": "cancel",
                            "table": table_name,
                        },
                    },
                ],
            },
        ]


def create_card_template() -> CardTemplate:
    """创建卡片模板生成器"""
    return CardTemplate(get_schema())


@dataclass
class CardCallback:
    """卡片回调数据"""
    action: str  # "approve", "edit", "cancel"
    table_name: str
    record_data: dict[str, Any]


def parse_card_callback(callback_data: dict) -> CardCallback:
    """
    解析卡片回调数据

    Args:
        callback_data: 飞书回调中的 value 字段数据

    Returns:
        CardCallback 对象

    Raises:
        ValueError: 解析失败
    """
    # 从回调数据中提取动作信息
    action = callback_data.get("action", "")
    table_name = callback_data.get("table", "")

    # 提取用户输入的数据
    # 飞书回调会将输入控件的值放在根级别
    record_data = {}
    for key, value in callback_data.items():
        if key not in ("action", "table"):
            record_data[key] = value

    if not action:
        raise ValueError("回调数据中缺少 action 字段")

    return CardCallback(
        action=action,
        table_name=table_name,
        record_data=record_data,
    )


# 导出
__all__ = ["CardTemplate", "create_card_template", "CardCallback", "parse_card_callback"]
