"""
结算单卡片渲染

build_settlement_card(summary) → 飞书交互卡片 JSON 字符串

纯函数，只 import core/ 层模型，不调用任何飞书 SDK。
"""
from __future__ import annotations

import json
from decimal import Decimal

from core.models.cash_flow import CashFlowRecord, CashFlowType, SettlementSummary


def _fmt(amount: Decimal) -> str:
    return f"{amount:,.2f}"


def _build_element_section(records: list[CashFlowRecord]) -> list[dict]:
    elements: list[dict] = [
        {
            "tag": "div",
            "text": {"tag": "lark_md", "content": "**元素货款**"},
        }
    ]
    for r in records:
        line = (
            f"**{r.sample_id}** {r.element}"
            f"｜干重 {r.dry_weight}t"
            f"｜金属量 {r.metal_quantity}t"
            f"｜{r.unit_price} {r.unit}"
            f"｜**{_fmt(r.amount)} 元**"
        )
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": line}})
    return elements


def _build_impurity_section(records: list[CashFlowRecord]) -> list[dict]:
    elements: list[dict] = [
        {
            "tag": "div",
            "text": {"tag": "lark_md", "content": "**杂质扣款**"},
        }
    ]
    for r in records:
        line = f"**{r.sample_id}** {r.element}｜**{_fmt(r.amount)} 元**"
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": line}})
    return elements


def _build_other_section(records: list[CashFlowRecord]) -> list[dict]:
    elements: list[dict] = [
        {
            "tag": "div",
            "text": {"tag": "lark_md", "content": "**其他费用**"},
        }
    ]
    for r in records:
        line = f"{r.flow_type.value}｜**{_fmt(r.amount)} 元**"
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": line}})
    return elements


def build_settlement_card(summary: SettlementSummary) -> str:
    """SettlementSummary → 飞书卡片 JSON 字符串"""
    element_records = [r for r in summary.records if r.flow_type == CashFlowType.ELEMENT_PAYMENT]
    impurity_records = [r for r in summary.records if r.flow_type == CashFlowType.IMPURITY_DEDUCTION]
    other_records = [
        r for r in summary.records
        if r.flow_type not in (CashFlowType.ELEMENT_PAYMENT, CashFlowType.IMPURITY_DEDUCTION)
    ]

    elements: list[dict] = []

    if element_records:
        elements.extend(_build_element_section(element_records))

    if impurity_records:
        elements.extend(_build_impurity_section(impurity_records))

    if other_records:
        elements.extend(_build_other_section(other_records))

    elements.append({"tag": "hr"})

    settled_label = "已结清" if summary.is_settled else "未结清"
    elements.append({
        "tag": "div",
        "fields": [
            {
                "is_short": True,
                "text": {
                    "tag": "lark_md",
                    "content": f"**应付合计**\n{_fmt(summary.total_expense)} 元",
                },
            },
            {
                "is_short": True,
                "text": {
                    "tag": "lark_md",
                    "content": f"**应收合计**\n{_fmt(summary.total_income)} 元",
                },
            },
            {
                "is_short": True,
                "text": {
                    "tag": "lark_md",
                    "content": f"**净额**\n{_fmt(summary.net_amount)} 元",
                },
            },
            {
                "is_short": True,
                "text": {
                    "tag": "lark_md",
                    "content": f"**状态**\n{settled_label}",
                },
            },
        ],
    })

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {
                "tag": "plain_text",
                "content": f"结算预览 — {summary.contract_number}",
            },
            "template": "green",
        },
        "elements": elements,
    }

    return json.dumps(card, ensure_ascii=False)
