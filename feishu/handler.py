"""
飞书事件路由器 + 消息处理器

职责：
- EventRouter: 标准化事件 dict → 消息对象 → 业务处理 → 飞书回复
  - 消息类型解析（text/image/post）
  - 图片 OCR 调度
  - 卡片回调处理（审核通过 → Bitable 写入）
  - 统一错误处理（用户看飞书提示，开发看 logging）

- MessageHandler: 保持原有接口，处理已解析的消息对象（图片→OCR→卡片，文本→路由）

架构位置：feishu/handler.py 是"事件桥接层"
- 上游：ws_client.py 传入标准化 dict
- 下游：调用 core 层（dispatcher）和 ai 层（OCR + 提取）
- 回复：调用 feishu/bot.py 发送消息
"""

import json
import logging
import os
import tempfile
from decimal import Decimal
from typing import Optional

from core import get_dispatcher, HandlerResult
from core.fake_data import generate_fake_contract, generate_fake_recipe, generate_fake_weigh_tickets, generate_fake_assay_report
from core.models.batch import AssayReportRecord, BatchUnit, BatchView, ContractRecord, WeighTicketRecord
from core.models.settlement_item import SettlementItemRecord
from engine.recipe import evaluate_recipe
from engine.schema import Recipe
from feishu.bot import FeishuBot, ImageMessage, TextMessage
from feishu.cards import CardTemplate, create_card_template, parse_card_callback
from feishu.bitable import BitableTable
from feishu.settlement_card import build_settlement_card
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
    - 图片消息 → 下载 → OCR → 结构化提取 → 生成卡片
    - 文本消息 → dispatcher 路由

    不负责飞书回复（由 EventRouter 统一处理）
    """

    def __init__(self, bot: FeishuBot):
        self.bot = bot
        self.dispatcher = get_dispatcher()
        self.card_template = create_card_template()
        # 假数据流内存状态（最近一次生成的合同/磅单/化验单）
        self._last_contract_record_id: Optional[str] = None
        self._last_contract_data: Optional[dict] = None
        self._last_recipe: Optional[Recipe] = None
        self._last_weigh_tickets: list[dict] = []   # 含 _sample_id, _record_id
        self._last_assay_reports: list[dict] = []    # 含 _sample_id, _record_id

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
            return self._handle_text(message)

        return "暂不支持该类型消息"

    def _handle_image(self, message: ImageMessage) -> str | dict:
        """处理图片消息：下载 → OCR → 结构化提取 → 卡片"""
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

    def _handle_text(self, message: TextMessage) -> str:
        """处理文本消息：假数据命令 or dispatcher 路由"""
        text = getattr(message, "text", "") or ""
        text = text.strip()

        if text == "合同":
            return self._cmd_gen_contract()
        if text == "磅单":
            return self._cmd_gen_weigh_tickets()
        if text == "化验单":
            return self._cmd_gen_assay_reports()
        if text in ("结算", "结算单"):
            return self._cmd_settlement()  # type: ignore[return-value]

        result: HandlerResult = self.dispatcher.route(message)
        return result.message

    # ── 假数据命令 ──────────────────────────────────────────────

    def _cmd_gen_contract(self) -> str:
        """生成假合同 → 写 Bitable → 存状态"""
        try:
            data = generate_fake_contract()
            table = BitableTable(table_name="contracts")
            record_id = table.create(data)
            self._last_contract_record_id = record_id
            self._last_contract_data = data
            self._last_recipe = generate_fake_recipe(record_id)
            self._last_weigh_tickets = []
            self._last_assay_reports = []
            cu_elem = self._last_recipe.elements[0]
            price_step = next(s for s in cu_elem.price_pipeline if s.op == "fixed")
            url = table.record_url(record_id)
            return (
                f"✅ 合同已录入，请点击链接核对：\n{url}\n\n"
                f"  合同编号：{data['合同编号']}\n"
                f"  方向：{data['合同方向']}\n"
                f"  计价：Cu {float(price_step.value):,.0f} {cu_elem.unit}\n"
                f"  化验费：{data['化验费']:,.0f} 元（{data['化验费承担方']}承担）"
            )
        except Exception as e:
            logger.exception("生成假合同失败")
            return f"❌ 生成合同失败：{e}"

    def _cmd_gen_weigh_tickets(self) -> str:
        """生成假磅单 → 写 Bitable → 存状态"""
        if not self._last_contract_record_id:
            return "⚠️ 请先发送「合同」生成合同记录，再生成磅单"
        try:
            tickets = generate_fake_weigh_tickets(self._last_contract_record_id, count=2)
            table = BitableTable(table_name="weigh_tickets")
            lines = []
            for t in tickets:
                row = {k: v for k, v in t.items() if not k.startswith("_")}
                record_id = table.create(row)
                t["_record_id"] = record_id
                url = table.record_url(record_id)
                lines.append(f"  样号 {t['_sample_id']}  净重 {t['净重(吨)']}t\n  {url}")
            self._last_weigh_tickets = tickets
            return "✅ 磅单已录入（2 条），请点击链接核对：\n" + "\n".join(lines)
        except Exception as e:
            logger.exception("生成假磅单失败")
            return f"❌ 生成磅单失败：{e}"

    def _cmd_gen_assay_reports(self) -> str:
        """为每张磅单生成一条假化验单 → 写 Bitable → 存状态"""
        if not self._last_weigh_tickets:
            return "⚠️ 请先发送「磅单」生成磅单记录，再生成化验单"
        try:
            table = BitableTable(table_name="assay_reports")
            lines = []
            assay_list = []
            for t in self._last_weigh_tickets:
                data = generate_fake_assay_report(t["_sample_id"], self._last_contract_record_id)
                record_id = table.create(data)
                data["_record_id"] = record_id
                data["_sample_id"] = t["_sample_id"]
                assay_list.append(data)
                url = table.record_url(record_id)
                lines.append(f"  样号 {t['_sample_id']}  Cu%={data['Cu%']}  H2O%={data['H2O%']}\n  {url}")
            self._last_assay_reports = assay_list
            return "✅ 化验单已录入，请点击链接核对：\n" + "\n".join(lines)
        except Exception as e:
            logger.exception("生成假化验单失败")
            return f"❌ 生成化验单失败：{e}"

    def _cmd_settlement(self) -> str | dict:
        """用内存数据计算结算 → 写入结算明细表 → 返回记录链接"""
        if not self._last_contract_data:
            return "⚠️ 请先依次发送「合同」→「磅单」→「化验单」，再触发结算"
        if not self._last_recipe:
            return "⚠️ 缺少计价规则，请重新发送「合同」"
        if not self._last_weigh_tickets:
            return "⚠️ 缺少磅单数据，请先发送「磅单」"
        if not self._last_assay_reports:
            return "⚠️ 缺少化验单数据，请先发送「化验单」"
        try:
            cd = self._last_contract_data
            recipe = self._last_recipe

            # 构建 ContractRecord（仅需 settlement 必要字段）
            contract_rec = ContractRecord(
                contract_id=self._last_contract_record_id or "mock",
                contract_number=cd["合同编号"],
                direction=cd["合同方向"],
                counterparty="MOCK对手方",
            )

            # 构建 BatchUnit 列表（将 assay 与 weigh 按 sample_id 匹配）
            assay_by_sample = {a["_sample_id"]: a for a in self._last_assay_reports}
            tickets_by_sample: dict[str, list] = {}
            for t in self._last_weigh_tickets:
                tickets_by_sample.setdefault(t["_sample_id"], []).append(t)

            batch_units = []
            for sample_id, tickets in tickets_by_sample.items():
                assay_data = assay_by_sample.get(sample_id)
                if not assay_data:
                    continue
                weigh_records = [
                    WeighTicketRecord(
                        ticket_id=t.get("_record_id", "mock"),
                        ticket_number=t.get("磅单编号", "mock"),
                        contract_id=self._last_contract_record_id or "mock",
                        commodity=t.get("货物品名", "铜精矿"),
                        wet_weight=Decimal(str(t["净重(吨)"])),
                        sample_id=sample_id,
                    )
                    for t in tickets
                ]
                assay_record = AssayReportRecord(
                    report_id=assay_data.get("_record_id", "mock"),
                    contract_id=self._last_contract_record_id or "mock",
                    sample_id=sample_id,
                    cu_pct=Decimal(str(assay_data["Cu%"])),
                    au_gt=Decimal(str(assay_data["Au(g/t)"])),
                    ag_gt=Decimal(str(assay_data["Ag(g/t)"])),
                    pb_pct=Decimal(str(assay_data["Pb%"])),
                    as_pct=Decimal(str(assay_data["As%"])),
                    h2o_pct=Decimal(str(assay_data["H2O%"])),
                )
                batch_units.append(BatchUnit(
                    sample_id=sample_id,
                    weigh_tickets=weigh_records,
                    assay_report=assay_record,
                ))

            batch_view = BatchView(contract=contract_rec, batch_units=batch_units)
            items = evaluate_recipe(recipe, batch_view, cd["合同方向"])

            # 写入结算明细表，返回各条记录链接
            si_table = BitableTable(table_name="settlement_items")
            links = []
            for item in items:
                row = {
                    "关联合同": item.contract_id,
                    "样号": item.sample_id or "",
                    "行类型": item.row_type.value,
                    "方向": item.direction.value,
                    "计价元素": item.element or "",
                    "计价基准": item.pricing_basis.value if item.pricing_basis else "",
                    "基准价来源": item.price_source.value,
                    "单价公式": item.price_formula.value if item.price_formula else "",
                    "湿重(吨)": float(item.wet_weight) if item.wet_weight is not None else None,
                    "H2O(%)": float(item.h2o_pct) if item.h2o_pct is not None else None,
                    "干重(吨)": float(item.dry_weight) if item.dry_weight is not None else None,
                    "化验品位": float(item.assay_grade) if item.assay_grade is not None else None,
                    "金属量(吨)": float(item.metal_quantity) if item.metal_quantity is not None else None,
                    "单价": float(item.unit_price) if item.unit_price is not None else None,
                    "单价单位": item.unit or "",
                    "金额": float(item.amount),
                    "备注": item.note or "",
                }
                record_id = si_table.create(row)
                url = si_table.record_url(record_id)
                links.append(f"  {item.row_type.value}（{item.direction.value} {item.amount:,.2f} 元）{' ' + item.element if item.element else ''}\n  {url}")

            total_income = sum(i.amount for i in items if i.direction.value == "收")
            total_expense = sum(i.amount for i in items if i.direction.value == "付")
            header = (
                f"✅ 结算明细已录入（{len(items)} 条），请点击链接逐条核对：\n"
                f"  应收合计：{total_income:,.2f} 元  应付合计：{total_expense:,.2f} 元\n"
            )
            return header + "\n".join(links)

        except Exception as e:
            logger.exception("结算计算失败")
            return f"❌ 结算失败：{e}"


# ==================== 工厂函数（保持向后兼容） ====================


def create_message_handler(bot: FeishuBot) -> MessageHandler:
    """创建消息处理器"""
    return MessageHandler(bot)
