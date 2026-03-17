"""
M3C：数据串联引擎

核心函数：
  match_by_sample_id()  — 磅单 + 化验单 → 按样号匹配 → BatchUnit 列表
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

from .models.batch import (
    AssayReportRecord,
    BatchUnit,
    BatchView,
    ContractRecord,
    WeighTicketRecord,
)

logger = logging.getLogger(__name__)


# ── 公开类型别名 ────────────────────────────────────────────────

LinkingResult = tuple[list[BatchUnit], list[WeighTicketRecord]]
"""(已匹配 BatchUnit 列表, 未匹配磅单列表)"""


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
    将磅单按样号与化验单匹配，构建 BatchUnit 列表。

    Args:
        weigh_tickets:   全部磅单（通常来自某一合同下的记录）
        assay_reports:   全部化验单（通常来自同一合同）
        settlement_only: 若为 True，只取 is_settlement=True 的记录参与结算

    Returns:
        matched:   BatchUnit 列表，每个 BatchUnit = 一个样号 + 对应磅单组 + 化验单
        unmatched: 有 sample_id 但找不到化验单、或 sample_id 为空的磅单

    匹配规则：
        1. 可选过滤 is_settlement 标记
        2. 按 sample_id 将磅单分组
        3. 对每组：在化验单中找 sample_id 相同的记录（精确匹配）
        4. 找不到化验单 → 放入 unmatched，记录 WARNING
        5. sample_id 为空的磅单 → 放入 unmatched，记录 WARNING
        6. 化验单存在多条匹配时取 is_settlement=True 的优先；若仍有多条，取第一条并警告
    """
    # Step 1：过滤
    tickets = [t for t in weigh_tickets if not settlement_only or t.is_settlement]
    reports = [r for r in assay_reports if not settlement_only or r.is_settlement]

    # Step 2：化验单索引（sample_id → AssayReportRecord）
    report_index: dict[str, AssayReportRecord] = {}
    for r in reports:
        sid = r.sample_id.strip()
        if sid in report_index:
            # 重复样号：保留 is_settlement=True 的，否则保留先到的
            existing = report_index[sid]
            if r.is_settlement and not existing.is_settlement:
                report_index[sid] = r
                logger.warning("样号 %s 存在多张化验单，使用 is_settlement=True 的 %s", sid, r.report_id)
            else:
                logger.warning("样号 %s 存在多张化验单，忽略 %s，保留 %s", sid, r.report_id, existing.report_id)
        else:
            report_index[sid] = r

    # Step 3：磅单分组
    ticket_groups: dict[str, list[WeighTicketRecord]] = defaultdict(list)
    unmatched: list[WeighTicketRecord] = []

    for t in tickets:
        if not t.sample_id or not t.sample_id.strip():
            logger.warning("磅单 %s 无样号，无法串联，放入未匹配列表", t.ticket_number)
            unmatched.append(t)
        else:
            ticket_groups[t.sample_id.strip()].append(t)

    # Step 4：逐组匹配化验单，构建 BatchUnit
    matched: list[BatchUnit] = []
    for sample_id, group in ticket_groups.items():
        report = report_index.get(sample_id)
        if report is None:
            logger.warning(
                "样号 %s（%d 张磅单）找不到对应化验单，放入未匹配列表",
                sample_id, len(group),
            )
            unmatched.extend(group)
        else:
            matched.append(BatchUnit(
                sample_id=sample_id,
                weigh_tickets=group,
                assay_report=report,
            ))

    # 按样号排序，保证输出稳定
    matched.sort(key=lambda u: u.sample_id)

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
    view = BatchView(contract=contract, batch_units=matched)
    logger.info(
        "合同 %s 串联完成：%d 个批次，总湿重 %.3f t，未匹配磅单 %d 张",
        contract.contract_number,
        view.batch_count,
        float(view.total_wet_weight),
        len(unmatched),
    )
    return view, unmatched
