"""
字段映射表：逻辑名（英文）→ Bitable 字段名（中文）

用途：解耦业务代码与飞书字段名。修改字段名时只需更新此文件。
每表一个 dict。使用 field_maps.CONTRACTS["direction"] 而非硬编码 "合同方向"。
"""

CONTRACTS = {
    "contract_number": "合同编号",
    "our_entity": "我方主体",
    "direction": "合同方向",
    "counterparty": "交易对手",
    "sign_date": "签订日期",
    "assay_fee": "化验费",
    "assay_fee_bearer": "化验费承担方",
}

WEIGH_TICKETS = {
    "ticket_number": "磅单编号",
    "contract_link": "关联合同",
    "commodity": "货物品名",
    "sample_id": "样号",
    "vehicle_number": "车号",
    "gross_weight": "毛重",
    "tare_weight": "皮重",
    "wet_weight": "净重(吨)",
    "weigh_date": "过磅日期",
}

ASSAY_REPORTS = {
    "contract_link": "关联合同",
    "sample_id": "样号",
    "assay_type": "化验类型",
    "is_settlement": "是否结算化验单",
    "cu_pct": "Cu%",
    "au_gt": "Au(g/t)",
    "ag_gt": "Ag(g/t)",
    "pb_pct": "Pb%",
    "zn_pct": "Zn%",
    "s_pct": "S%",
    "as_pct": "As%",
    "h2o_pct": "H2O%",
    "assay_date": "化验日期",
    "assay_org": "化验机构",
}

CASH_FLOWS = {
    "contract_link": "关联合同",
    "payment_type": "款项类型",
    "direction": "方向",
    "amount": "金额",
    "date": "日期",
    "summary": "摘要",
}

SETTLEMENT_ITEMS = {
    "contract_link": "关联合同",
    "weigh_ticket_link": "关联磅单",
    "sample_id": "样号",
    "row_type": "行类型",
    "direction": "方向",
    "element": "计价元素",
    "pricing_basis": "计价基准",
    "price_source": "基准价来源",
    "price_formula": "单价公式",
    "wet_weight": "湿重(吨)",
    "h2o_pct": "H2O(%)",
    "dry_weight": "干重(吨)",
    "assay_grade": "化验品位",
    "metal_quantity": "金属量(吨)",
    "unit_price": "单价",
    "unit": "单价单位",
    "amount": "金额",
    "note": "备注",
}

# 表名 → 字段映射表（用于 validate_against_schema）
_TABLE_MAPS = {
    "contracts": CONTRACTS,
    "weigh_tickets": WEIGH_TICKETS,
    "assay_reports": ASSAY_REPORTS,
    "cash_flows": CASH_FLOWS,
    "settlement_items": SETTLEMENT_ITEMS,
}


def reverse(mapping: dict) -> dict:
    """中文名 → 逻辑名，用于读取时转换"""
    return {v: k for k, v in mapping.items()}


def validate_against_schema(schema) -> None:
    """
    启动时校验：field_maps 中所有字段名都存在于 schema.yaml

    Args:
        schema: Schema 实例（来自 schema.loader）

    Raises:
        ValueError: 如有字段名不匹配，报告具体哪个字段在哪个表中缺失
    """
    errors = []
    for table_name, field_map in _TABLE_MAPS.items():
        table = schema.get_table(table_name)
        if table is None:
            errors.append(f"表 '{table_name}' 在 schema.yaml 中不存在")
            continue
        existing_names = {f.name for f in table.fields}
        for logical_name, chinese_name in field_map.items():
            if chinese_name not in existing_names:
                errors.append(
                    f"表 '{table_name}' 缺少字段 '{chinese_name}'（逻辑名: {logical_name}）"
                )
    if errors:
        raise ValueError(
            "field_maps 与 schema.yaml 不一致，请同步更新：\n"
            + "\n".join(f"  - {e}" for e in errors)
        )
