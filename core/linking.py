"""
M3C：数据串联引擎

核心函数：
  match_by_sample_id()  — 磅单 + 化验单 → 按样号/批次号匹配 → Batch 列表
  build_batch_view()    — ContractRecord + 匹配结果 → BatchView

设计原则：
  - 纯函数，输入/输出均为 core/models 中的 Pydantic 模型
  - 不 import feishu/ 或 ai/，不触碰 Bitable
  - 磅单↔化验单通过 sample_id 软关联（文本精确匹配）
  - 未匹配的磅单不抛异常，放入 unmatched 列表供上层处理
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date

from .models.batch import AssayReportRecord, Batch, BatchView, ContractRecord, WeighTicketRecord

logger = logging.getLogger(__name__)


# ── 公开类型别名 ────────────────────────────────────────────────

LinkingResult = tuple[list[Batch], list[WeighTicketRecord]]
"""(已匹配 Batch 列表, 未匹配磅单列表)"""


# ══════════════════════════════════════════════════════════════
# 核心函数
# ══════════════════════════════════════════════════════════════

def match_by_sample_id(
    weigh_tickets: list[WeighTicketRecord],
    assay_reports: list[AssayReportRecord],
    *,
    settlement_only: bool = True,
) -> LinkingResult:
    """
    将磅单按样号/批次号与化验单匹配，构建 Batch 列表。

    Args:
        weigh_tickets:   全部磅单（通常来自某一合同下的记录）
        assay_reports:   全部化验单（通常来自同一合同）
        settlement_only: 若为 True，只取 is_settlement=True 的记录参与结算

    Returns:
        matched:   Batch 列表，每个 Batch = 一次流转 + 对应磅单组 + 化验单组
        unmatched: 有 sample_id 但找不到化验单、或 sample_id 为空的磅单

    匹配规则：
        1. 可选过滤 is_settlement 标记
        2. 按 batch_id（缺省回退 sample_id）将磅单分组
        3. 对每组：在化验单中找 batch_id/sample_id 相同的记录（精确匹配）
        4. 找不到化验单 → 放入 unmatched，记录 WARNING
        5. batch_id/sample_id 为空的磅单 → 放入 unmatched，记录 WARNING
    """
    tickets = [t for t in weigh_tickets if not settlement_only or t.is_settlement]
    reports = [r for r in assay_reports if not settlement_only or r.is_settlement]

    def _batch_key_for_ticket(ticket: WeighTicketRecord) -> str | None:
        key = ticket.batch_id or ticket.sample_id
        if key is None:
            return None
        key = key.strip()
        return key or None

    def _batch_key_for_report(report: AssayReportRecord) -> str | None:
        key = report.batch_id or report.sample_id
        if key is None:
            return None
        key = key.strip()
        return key or None

    report_index: dict[str, list[AssayReportRecord]] = defaultdict(list)
    for r in reports:
        key = _batch_key_for_report(r)
        if not key:
            logger.warning("化验单 %s 无 batch_id/sample_id，忽略", r.report_id)
            continue
        report_index[key].append(r)

    ticket_groups: dict[str, list[WeighTicketRecord]] = defaultdict(list)
    unmatched: list[WeighTicketRecord] = []

    for t in tickets:
        key = _batch_key_for_ticket(t)
        if not key:
            logger.warning("磅单 %s 无 batch_id/sample_id，无法串联，放入未匹配列表", t.ticket_number)
            unmatched.append(t)
        else:
            ticket_groups[key].append(t)

    matched: list[Batch] = []
    for batch_id, group in ticket_groups.items():
        reports_for_batch = report_index.get(batch_id)
        if not reports_for_batch:
            logger.warning(
                "批次 %s（%d 张磅单）找不到对应化验单，放入未匹配列表",
                batch_id,
                len(group),
            )
            unmatched.extend(group)
        else:
            matched.append(Batch(
                batch_id=batch_id,
                contract_id=group[0].contract_id,
                sample_id=group[0].sample_id,
                weigh_tickets=group,
                assay_reports=sorted(
                    reports_for_batch,
                    key=lambda r: (r.assay_date or date.min, r.report_id),
                ),
            ))

    matched.sort(key=lambda batch: (batch.sample_id or batch.batch_id, batch.batch_id))

    if unmatched:
        numbers = [t.ticket_number for t in unmatched]
        logger.warning("共 %d 张磅单未匹配化验单：%s", len(unmatched), numbers)

    return matched, unmatched


def build_batch_view(
    contract: ContractRecord,
    weigh_tickets: list[WeighTicketRecord],
    assay_reports: list[AssayReportRecord],
    *,
    settlement_only: bool = True,
) -> tuple[BatchView, list[WeighTicketRecord]]:
    """
    构建合同的完整批次视图。

    Args:
        contract:        合同记录
        weigh_tickets:   该合同下的全部磅单
        assay_reports:   该合同下的全部化验单
        settlement_only: 只纳入结算磅单和结算化验单

    Returns:
        (BatchView, 未匹配磅单列表)

    BatchView 是 M3D 结算计算的输入。
    """
    matched, unmatched = match_by_sample_id(
        weigh_tickets, assay_reports, settlement_only=settlement_only
    )
    view = BatchView(contract=contract, batches=matched)
    logger.info(
        "合同 %s 串联完成：%d 个批次，总湿重 %.3f t，未匹配磅单 %d 张",
        contract.contract_number,
        view.batch_count,
        float(view.total_wet_weight),
        len(unmatched),
    )
    return view, unmatched
