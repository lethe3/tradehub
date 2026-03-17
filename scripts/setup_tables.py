"""
Bitable 表结构初始化脚本

功能：
1. 给合同表添加扩展字段（单价、单价单位、计价元素、品位扣减、化验费）
2. 给磅单表添加扩展字段（样号、车号、毛重、皮重）
3. 创建化验单表（含所有字段）
4. 创建资金流水表（含所有字段）
5. 打印所有 field_id，用于手动更新 schema.yaml

运行：python scripts/setup_tables.py
"""
import os
import sys
from pathlib import Path

# 加入项目根路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from feishu.bitable import BitableApp, BitableTable, FieldConfig, FieldType


APP_TOKEN = os.environ["FEISHU_BITABLE_APP_TOKEN"]
CONTRACTS_TABLE_ID = os.environ["FEISHU_BITABLE_CONTRACTS_TABLE_ID"]
WEIGH_TICKETS_TABLE_ID = os.environ["FEISHU_BITABLE_WEIGH_TICKETS_TABLE_ID"]


def print_fields(table_id: str, label: str):
    """打印表的所有字段（field_id + name + type）"""
    from feishu.bitable import get_client
    client = get_client()
    t = BitableTable(table_id=table_id, client=client)
    fields = t.list_fields()
    print(f"\n{'='*50}")
    print(f"表：{label}  table_id={table_id}")
    print(f"{'='*50}")
    for f in fields:
        print(f"  field_id={f['field_id']}  type={f['type']:4d}  name={f['name']}")


def add_fields_if_missing(table_id: str, new_fields: list[FieldConfig]):
    """仅添加不存在的字段（按字段名去重）"""
    from feishu.bitable import get_client
    client = get_client()
    t = BitableTable(table_id=table_id, client=client)
    existing = {f["name"] for f in t.list_fields()}
    added = []
    for fc in new_fields:
        if fc.name in existing:
            print(f"  [skip] {fc.name} 已存在")
        else:
            fid = t.create_field(fc)
            added.append(fc.name)
            print(f"  [add]  {fc.name}  field_id={fid}")
    return added


def create_table_if_missing(app: BitableApp, name: str) -> str:
    """创建表（若已存在则返回现有 table_id）"""
    existing = app.get_table(name)
    if existing:
        print(f"  [skip] 表 '{name}' 已存在  table_id={existing['table_id']}")
        return existing["table_id"]
    table_id = app.create_table(name)
    print(f"  [create] 表 '{name}'  table_id={table_id}")
    return table_id


def main():
    app = BitableApp()

    # ── 1. 合同表：保留化验费字段，移除已迁移的计价字段 ─────────
    print("\n[1] 合同表：确认化验费字段存在 ...")
    add_fields_if_missing(CONTRACTS_TABLE_ID, [
        FieldConfig("化验费",       FieldType.NUMBER),     # 总额，如 2000
        FieldConfig("化验费承担方", FieldType.TEXT),       # 我方/对方/均摊
    ])
    print_fields(CONTRACTS_TABLE_ID, "合同表")

    # ── 2. 磅单表：扩展字段 ────────────────────────────────────
    print("\n[2] 给磅单表添加扩展字段 ...")
    add_fields_if_missing(WEIGH_TICKETS_TABLE_ID, [
        FieldConfig("样号",   FieldType.TEXT),     # 与化验单关联的核心字段
        FieldConfig("车号",   FieldType.TEXT),     # 车牌号
        FieldConfig("毛重",   FieldType.NUMBER),   # 毛重（吨）
        FieldConfig("皮重",   FieldType.NUMBER),   # 皮重（吨）
    ])
    print_fields(WEIGH_TICKETS_TABLE_ID, "磅单表")

    # ── 3. 化验单表：新建 ──────────────────────────────────────
    print("\n[3] 创建化验单表 ...")
    assay_table_id = create_table_if_missing(app, "化验单")
    add_fields_if_missing(assay_table_id, [
        FieldConfig("关联合同",     FieldType.TEXT),    # 合同 record_id
        FieldConfig("样号",         FieldType.TEXT),    # 与磅单匹配的核心字段
        FieldConfig("化验类型",     FieldType.TEXT),    # 快速摸底/结算化验
        FieldConfig("是否结算化验单", FieldType.CHECKBOX),
        FieldConfig("Cu%",          FieldType.NUMBER),
        FieldConfig("Au(g/t)",      FieldType.NUMBER),
        FieldConfig("Ag(g/t)",      FieldType.NUMBER),
        FieldConfig("Pb%",          FieldType.NUMBER),
        FieldConfig("Zn%",          FieldType.NUMBER),
        FieldConfig("S%",           FieldType.NUMBER),
        FieldConfig("As%",          FieldType.NUMBER),
        FieldConfig("H2O%",         FieldType.NUMBER),
        FieldConfig("化验日期",     FieldType.DATE),
        FieldConfig("化验机构",     FieldType.TEXT),
    ])
    print_fields(assay_table_id, "化验单")

    # ── 4. 资金流水表：精简为实际收付记录 ─────────────────────────
    print("\n[4] 创建/更新资金流水表（仅实际收付字段）...")
    cf_table_id = create_table_if_missing(app, "资金流水")
    add_fields_if_missing(cf_table_id, [
        FieldConfig("关联合同",   FieldType.TEXT),    # 合同 record_id
        FieldConfig("款项类型",   FieldType.TEXT),    # 预付款/结算款/运费/化验费/…
        FieldConfig("方向",       FieldType.TEXT),    # 收/付
        FieldConfig("金额",       FieldType.NUMBER),  # 实际金额
        FieldConfig("日期",       FieldType.DATE),    # 实际收付日期
        FieldConfig("摘要",       FieldType.TEXT),    # 银行摘要或备注
    ])
    print_fields(cf_table_id, "资金流水")

    # ── 5. 结算明细表：新建 ────────────────────────────────────
    print("\n[5] 创建结算明细表 ...")
    si_table_id = create_table_if_missing(app, "结算明细")
    add_fields_if_missing(si_table_id, [
        FieldConfig("关联合同",     FieldType.TEXT),    # 合同 record_id
        FieldConfig("关联磅单",     FieldType.TEXT),    # 磅单 record_id
        FieldConfig("样号",         FieldType.TEXT),    # 与磅单/化验单串联
        FieldConfig("行类型",       FieldType.TEXT),    # 元素货款 / 杂质扣款
        FieldConfig("方向",         FieldType.TEXT),    # 收 / 付
        FieldConfig("计价元素",     FieldType.TEXT),    # Cu / Au / Ag / As / S
        FieldConfig("计价基准",     FieldType.TEXT),    # 湿重 / 干重 / 金属量
        FieldConfig("基准价来源",   FieldType.TEXT),    # 固定 / 均价 / 点价
        FieldConfig("单价公式",     FieldType.TEXT),    # 固定单价 / 品位扣减 / 系数法
        FieldConfig("湿重(吨)",     FieldType.NUMBER),
        FieldConfig("H2O(%)",       FieldType.NUMBER),
        FieldConfig("干重(吨)",     FieldType.NUMBER),
        FieldConfig("化验品位",     FieldType.NUMBER),
        FieldConfig("品位扣减",     FieldType.NUMBER),
        FieldConfig("有效品位",     FieldType.NUMBER),
        FieldConfig("金属量(吨)",   FieldType.NUMBER),
        FieldConfig("单价",         FieldType.NUMBER),
        FieldConfig("单价单位",     FieldType.TEXT),    # 元/吨 / 元/干吨 / 元/金属吨
        FieldConfig("金额",         FieldType.NUMBER),
        FieldConfig("备注",         FieldType.TEXT),    # 杂质档位说明等
    ])
    print_fields(si_table_id, "结算明细")

    # ── 6. 汇总输出（复制到 schema.yaml）─────────────────────
    print(f"\n{'='*60}")
    print("请将以下 table_id 写入 .env 和 schema/schema.yaml：")
    print(f"  FEISHU_BITABLE_ASSAY_TABLE_ID={assay_table_id}")
    print(f"  FEISHU_BITABLE_CASHFLOW_TABLE_ID={cf_table_id}")
    print(f"  结算明细表 table_id={si_table_id}")
    print("\n⚠️  请将结算明细表 table_id 更新至 schema/schema.yaml 的 settlement_items.table_id")


if __name__ == "__main__":
    main()
