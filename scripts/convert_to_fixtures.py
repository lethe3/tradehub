"""
将 export_data.py 导出的 JSON 转换为测试 fixture

每个合同生成一个目录：tests/fixtures/mock_documents/real_01/
包含：
    contract.yaml           合同字段（原始中文字段名）
    weigh_tickets.yaml      磅单列表
    assay_reports.yaml      化验单列表
    settlement_items.yaml   结算明细（若有）
    expected_results.yaml   空壳，等 Zhang 人工填入预期值后用于断言

用法：
    python scripts/convert_to_fixtures.py data/exports/2026-03-17_1200.json
    python scripts/convert_to_fixtures.py data/exports/2026-03-17_1200.json --prefix real
    python scripts/convert_to_fixtures.py data/exports/2026-03-17_1200.json --dry-run
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures" / "mock_documents"

# 写入 YAML 时过滤掉的内部字段（以 _ 开头的嵌套子表，单独写文件）
_NESTED_KEYS = {"_weigh_tickets", "_assay_reports", "_settlement_items", "_cash_flows"}


def _clean_record(record: dict) -> dict:
    """移除内部 _ 字段，保留 Bitable 字段 + record_id"""
    return {k: v for k, v in record.items() if k not in _NESTED_KEYS}


def _dump_yaml(data: Any, path: Path):
    """写 YAML，支持中文，保持可读缩进"""
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def contract_label(contract: dict, idx: int) -> str:
    """取合同编号作为标签，fallback 用序号"""
    return (
        contract.get("合同编号")
        or contract.get("record_id", "")[:8]
        or str(idx)
    )


def convert_contract(contract: dict, out_dir: Path, dry_run: bool = False):
    """将单个合同数据写入 fixture 目录"""
    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    # contract.yaml：合同本体字段
    contract_data = _clean_record(contract)
    if not dry_run:
        _dump_yaml(contract_data, out_dir / "contract.yaml")

    # weigh_tickets.yaml
    wt_list = [_clean_record(r) for r in contract.get("_weigh_tickets", [])]
    if not dry_run:
        _dump_yaml({"weigh_tickets": wt_list}, out_dir / "weigh_tickets.yaml")

    # assay_reports.yaml
    ar_list = [_clean_record(r) for r in contract.get("_assay_reports", [])]
    if not dry_run:
        _dump_yaml({"assay_reports": ar_list}, out_dir / "assay_reports.yaml")

    # settlement_items.yaml（若有）
    si_list = [_clean_record(r) for r in contract.get("_settlement_items", [])]
    if si_list and not dry_run:
        _dump_yaml({"settlement_items": si_list}, out_dir / "settlement_items.yaml")

    # expected_results.yaml：空壳，Zhang 人工校验后填入
    if not dry_run and not (out_dir / "expected_results.yaml").exists():
        _dump_yaml(
            {
                "_comment": "请填入人工验算的预期结算结果，用于 pytest 断言",
                "total_income": None,
                "total_expense": None,
                "items": [],
            },
            out_dir / "expected_results.yaml",
        )

    return {
        "dir": str(out_dir),
        "weigh_tickets": len(wt_list),
        "assay_reports": len(ar_list),
        "settlement_items": len(si_list),
    }


def convert(export_path: Path, prefix: str = "real", dry_run: bool = False) -> list[dict]:
    with open(export_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    contracts = data.get("contracts", [])
    meta = data.get("_meta", {})
    print(f"\n读取导出文件：{export_path}")
    print(f"  导出时间：{meta.get('exported_at', '未知')}")
    print(f"  合同数：{len(contracts)}")

    results = []
    for idx, contract in enumerate(contracts, start=1):
        label = contract_label(contract, idx)
        dir_name = f"{prefix}_{idx:02d}"
        out_dir = FIXTURES_DIR / dir_name

        summary = convert_contract(contract, out_dir, dry_run=dry_run)
        summary["label"] = label
        results.append(summary)

        status = "[dry-run]" if dry_run else "✅"
        print(
            f"  {status} {dir_name}  合同={label}"
            f"  磅单={summary['weigh_tickets']}"
            f"  化验单={summary['assay_reports']}"
            f"  结算明细={summary['settlement_items']}"
        )

    if not dry_run:
        print(f"\n生成 {len(results)} 个 fixture 目录 → {FIXTURES_DIR}")

    return results


def main():
    parser = argparse.ArgumentParser(description="导出 JSON → pytest fixture")
    parser.add_argument("export_file", help="export_data.py 生成的 JSON 文件路径")
    parser.add_argument(
        "--prefix", default="real",
        help="fixture 目录前缀（默认 real，生成 real_01, real_02, ...）"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="只打印预览，不写文件"
    )
    args = parser.parse_args()

    export_path = Path(args.export_file)
    if not export_path.exists():
        print(f"❌ 文件不存在：{export_path}")
        sys.exit(1)

    convert(export_path, prefix=args.prefix, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
