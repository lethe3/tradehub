"""
导出 Bitable 数据为 JSON

以合同为中心，展开关联的磅单、化验单、结算明细、资金流水。
输出到 data/exports/YYYY-MM-DD_HHmm.json

用法：
    python scripts/export_data.py
    python scripts/export_data.py --output data/exports/my_export.json
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from feishu.bitable import BitableTable


# ── 关联合同字段名（各子表里指向合同 record_id 的字段）──────────
_CONTRACT_LINK_FIELD = "关联合同"


def extract_link_ids(value: Any) -> list[str]:
    """
    从 Bitable link 字段值中提取 record_id 列表。

    飞书 type=18 link 字段读取时可能返回多种格式：
    - ["recXXX"]                          ← record_id 列表
    - [{"record_id": "recXXX", ...}]      ← 完整记录对象列表
    - "recXXX"                            ← 单个 record_id 字符串（type=1 存储时）
    """
    if not value:
        return []
    if isinstance(value, str):
        return [value] if value.startswith("rec") else []
    if isinstance(value, list):
        ids = []
        for item in value:
            if isinstance(item, str) and item:
                ids.append(item)
            elif isinstance(item, dict):
                rid = item.get("record_id") or item.get("id") or ""
                if rid:
                    ids.append(rid)
        return ids
    return []


def load_all(table_name: str) -> list[dict]:
    """加载表的全量记录（自动分页）"""
    print(f"  加载 {table_name} ...", end=" ", flush=True)
    t = BitableTable(table_name=table_name)
    records = t.list_all()
    print(f"{len(records)} 条")
    return records


def group_by_contract(records: list[dict]) -> dict[str, list[dict]]:
    """按「关联合同」字段分组，返回 {contract_record_id: [records]}"""
    groups: dict[str, list[dict]] = {}
    for rec in records:
        link_value = rec.get(_CONTRACT_LINK_FIELD)
        for cid in extract_link_ids(link_value):
            groups.setdefault(cid, []).append(rec)
    return groups


def export() -> dict:
    """导出全量数据，以合同为中心嵌套展开"""
    print("\n开始导出...")

    contracts       = load_all("contracts")
    weigh_tickets   = load_all("weigh_tickets")
    assay_reports   = load_all("assay_reports")
    settlement_items = load_all("settlement_items")
    cash_flows      = load_all("cash_flows")

    # 按合同分组
    wt_by_contract = group_by_contract(weigh_tickets)
    ar_by_contract = group_by_contract(assay_reports)
    si_by_contract = group_by_contract(settlement_items)
    cf_by_contract = group_by_contract(cash_flows)

    result_contracts = []
    for c in contracts:
        cid = c.get("record_id", "")
        entry = dict(c)
        entry["_weigh_tickets"]    = wt_by_contract.get(cid, [])
        entry["_assay_reports"]    = ar_by_contract.get(cid, [])
        entry["_settlement_items"] = si_by_contract.get(cid, [])
        entry["_cash_flows"]       = cf_by_contract.get(cid, [])
        result_contracts.append(entry)

    counts = {
        "contracts":        len(contracts),
        "weigh_tickets":    len(weigh_tickets),
        "assay_reports":    len(assay_reports),
        "settlement_items": len(settlement_items),
        "cash_flows":       len(cash_flows),
    }
    return {
        "contracts": result_contracts,
        "_meta": {
            "exported_at": datetime.now().isoformat(),
            "table_counts": counts,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="导出 Bitable 数据为 JSON")
    parser.add_argument("--output", help="输出文件路径（默认自动命名）")
    args = parser.parse_args()

    data = export()

    if args.output:
        output_path = Path(args.output)
    else:
        output_dir = Path(__file__).parent.parent / "data" / "exports"
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = datetime.now().strftime("%Y-%m-%d_%H%M") + ".json"
        output_path = output_dir / filename

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    meta = data["_meta"]
    counts = meta["table_counts"]
    print(f"\n导出完成：{output_path}")
    print(f"  合同：{counts['contracts']} 条")
    print(f"  磅单：{counts['weigh_tickets']} 条")
    print(f"  化验单：{counts['assay_reports']} 条")
    print(f"  结算明细：{counts['settlement_items']} 条")
    print(f"  资金流水：{counts['cash_flows']} 条")

    # 提示无关联数据的合同
    orphans = [
        c.get("合同编号") or c.get("record_id")
        for c in data["contracts"]
        if not c["_weigh_tickets"] and not c["_assay_reports"]
    ]
    if orphans:
        print(f"\n⚠  以下合同暂无关联子记录：{orphans}")

    return str(output_path)


if __name__ == "__main__":
    main()
