"""
种子数据脚本 — 用 fixture 数据预填充 JsonFileStore

用法：
  python scripts/seed_data.py                # 填充 scenario_01 和 scenario_02
  python scripts/seed_data.py --clear        # 清空现有数据后重新填充
  python scripts/seed_data.py --scenario 01  # 只填充特定场景

数据写入 data/ 目录（JsonFileStore 默认路径）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 确保能 import 项目模块
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml

from store.json_store import JsonFileStore


FIXTURES = Path(__file__).parent.parent / "tests" / "fixtures" / "mock_documents"


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def clear_store(store: JsonFileStore) -> None:
    """清空所有表。"""
    for table in ["contracts", "weigh_tickets", "assay_reports", "recipes"]:
        path = store._path(table)
        if path.exists():
            path.unlink()
    print("✓ 已清空所有数据")


def seed_scenario(store: JsonFileStore, scenario_name: str) -> str:
    """填充一个场景的全部数据，返回 contract_id。"""
    d = FIXTURES / scenario_name
    if not d.exists():
        print(f"✗ 场景目录不存在：{d}")
        return ""

    # 合同
    contract_data = _load_yaml(d / "contract.yaml")
    contract_record = store.create("contracts", {
        "id": contract_data["contract_id"],
        "contract_number": contract_data["contract_number"],
        "direction": contract_data["direction"],
        "counterparty": contract_data["counterparty"],
        "commodity": contract_data.get("commodity"),
        "signing_date": contract_data.get("signing_date"),
        "tax_included": contract_data.get("tax_included"),
        "freight_bearer": contract_data.get("freight_bearer"),
        "assay_fee_bearer": contract_data.get("assay_fee_bearer"),
        "settlement_ticket_rule": contract_data.get("settlement_ticket_rule"),
        "settlement_assay_rule": contract_data.get("settlement_assay_rule"),
    })
    contract_id = contract_record["id"]
    print(f"  合同: {contract_data['contract_number']} (id={contract_id})")

    # 磅单
    wt_data = _load_yaml(d / "weigh_tickets.yaml")
    for wt in wt_data["weigh_tickets"]:
        store.create("weigh_tickets", {
            "id": wt["ticket_id"],
            "ticket_number": wt["ticket_number"],
            "contract_id": contract_id,
            "commodity": wt["commodity"],
            "wet_weight": str(wt["wet_weight"]),
            "sample_id": wt.get("sample_id"),
            "weighing_date": str(wt["weighing_date"]) if wt.get("weighing_date") else None,
            "vehicle_number": wt.get("vehicle_number"),
            "gross_weight": str(wt["gross_weight"]) if wt.get("gross_weight") else None,
            "tare_weight": str(wt["tare_weight"]) if wt.get("tare_weight") else None,
            "deduction_weight": str(wt["deduction_weight"]) if wt.get("deduction_weight") else None,
            "is_settlement": wt.get("is_settlement", True),
            "price_group": wt.get("price_group"),
        })
    print(f"  磅单: {len(wt_data['weigh_tickets'])} 张")

    # 化验单
    ar_data = _load_yaml(d / "assay_reports.yaml")
    for ar in ar_data["assay_reports"]:
        record = {
            "id": ar["report_id"],
            "contract_id": contract_id,
            "sample_id": ar["sample_id"],
            "is_settlement": ar.get("is_settlement", True),
            "assay_type": ar.get("assay_type", "结算化验"),
        }
        for field in ["cu_pct", "au_gt", "ag_gt", "pb_pct", "zn_pct", "s_pct", "as_pct", "h2o_pct"]:
            if ar.get(field) is not None:
                record[field] = str(ar[field])
        store.create("assay_reports", record)
    print(f"  化验单: {len(ar_data['assay_reports'])} 张")

    # Recipe
    recipe_data = _load_yaml(d / "recipe.yaml")
    recipe_record = dict(recipe_data)
    recipe_record["contract_id"] = contract_id
    # 序列化 Decimal 字段
    recipe_json = json.loads(json.dumps(recipe_record, default=str))
    store.create("recipes", recipe_json)
    print(f"  配方: 已写入 ({len(recipe_data.get('elements', []))} 个元素)")

    return contract_id


def main():
    parser = argparse.ArgumentParser(description="TradeHub 种子数据脚本")
    parser.add_argument("--clear", action="store_true", help="清空现有数据后重新填充")
    parser.add_argument("--scenario", choices=["01", "02"], help="只填充指定场景")
    parser.add_argument("--data-dir", default="data", help="数据目录（默认 data/）")
    args = parser.parse_args()

    store = JsonFileStore(data_dir=args.data_dir)

    if args.clear:
        clear_store(store)

    scenarios = [f"scenario_{args.scenario}"] if args.scenario else ["scenario_01", "scenario_02"]

    print(f"\n填充场景数据到 {Path(args.data_dir).resolve()}/\n")
    for scenario in scenarios:
        print(f"► {scenario}")
        contract_id = seed_scenario(store, scenario)
        if contract_id:
            print(f"  ✓ contract_id = {contract_id}")
        print()

    print("种子数据填充完成。")
    print(f"启动 API：python main.py --web")


if __name__ == "__main__":
    main()
