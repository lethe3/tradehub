"""
Schema 同步模块 - 从飞书 Bitable 拉取表结构

用法:
    python -m schema.sync                    # 同步所有配置的表
    python -m schema.sync --tables contracts # 只同步合同表
    python -m schema.sync --watch             # 监听模式（TODO）
"""
import argparse
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from lark_oapi import Client
from lark_oapi.api.bitable.v1 import (
    ListAppTableFieldRequest,
    ListAppTableRequest,
)

# 加载 .env
load_dotenv()

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
SCHEMA_FILE = PROJECT_ROOT / "schema" / "schema.yaml"


def get_client() -> Client:
    """创建飞书客户端"""
    app_id = os.environ.get("FEISHU_APP_ID")
    app_secret = os.environ.get("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        raise ValueError("请配置 FEISHU_APP_ID 和 FEISHU_APP_SECRET")
    return Client.builder().app_id(app_id).app_secret(app_secret).build()


def get_table_id(table_name: str) -> str | None:
    """获取表名对应的 table_id"""
    env_key = f"FEISHU_BITABLE_{table_name.upper()}_TABLE_ID"
    return os.environ.get(env_key)


def list_tables(client: Client, app_token: str) -> list[dict]:
    """列出所有表"""
    request = ListAppTableRequest.builder().app_token(app_token).build()
    response = client.bitable.v1.app_table.list(request)
    if not response.success():
        print(f"✗ 获取表列表失败: {response.msg}")
        return []
    return [
        {
            "table_id": t.table_id,
            "name": t.name,
        }
        for t in response.data.items
    ]


def get_table_fields(client: Client, app_token: str, table_id: str) -> list[dict]:
    """获取表的字段定义"""
    request = ListAppTableFieldRequest.builder() \
        .app_token(app_token) \
        .table_id(table_id) \
        .build()

    response = client.bitable.v1.app_table_field.list(request)
    if not response.success():
        print(f"✗ 获取字段列表失败: {response.msg}")
        return []

    fields = []
    for f in response.data.items:
        # 飞书 Bitable 字段类型：1=文本, 2=数字, 3=单选, 5=日期, 18=单向关联, 1005=自动编号
        field_info = {
            "field_id": f.field_id,
            "type": f.type,
        }

        # 字段名称 - 尝试多种属性
        if hasattr(f, "field_name") and f.field_name:
            field_info["name"] = f.field_name
        elif hasattr(f, "name") and f.name:
            field_info["name"] = f.name

        # 选项字段（单选 type=3, 多选 type=4）需要获取选项详情
        # 选项在 f.property.options 中
        if f.type in [3, 4]:  # 单选或多选
            field_info["options"] = []
            if hasattr(f, "property") and f.property and hasattr(f.property, "options") and f.property.options:
                for opt in f.property.options:
                    opt_info = {
                        "id": opt.id,
                        "name": opt.name,
                    }
                    if hasattr(opt, "color"):
                        opt_info["color"] = opt.color
                    field_info["options"].append(opt_info)

        fields.append(field_info)

    return fields


def load_existing_schema() -> dict:
    """加载现有的 schema.yaml"""
    if SCHEMA_FILE.exists():
        with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def save_schema(schema: dict):
    """保存 schema 到文件"""
    SCHEMA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SCHEMA_FILE, "w", encoding="utf-8") as f:
        yaml.dump(schema, f, allow_unicode=True, default_flow_style=False)
    print(f"✓ 已保存到 {SCHEMA_FILE}")


def sync_table(client: Client, app_token: str, table_name: str, table_id: str) -> dict:
    """同步单个表的字段定义"""
    print(f"\n>>> 同步表: {table_name} (ID: {table_id})")

    # 先尝试获取表名
    tables = list_tables(client, app_token)
    display_name = table_name
    for t in tables:
        if t["table_id"] == table_id:
            display_name = t.get("name", table_name)
            break

    fields = get_table_fields(client, app_token, table_id)
    print(f"    获取到 {len(fields)} 个字段")

    # 打印字段摘要
    for field in fields:
        field_type = field["type"]
        options_info = ""
        if "options" in field:
            opts = [o["name"] for o in field["options"][:3]]
            options_info = f" [{', '.join(opts)}{'...' if len(field['options']) > 3 else ''}]"
        print(f"    - {field['name']} (type={field_type}){options_info}")

    return {
        "table_id": table_id,
        "name": display_name,
        "fields": fields,
    }


def sync_all():
    """同步所有配置的表"""
    client = get_client()
    app_token = os.environ.get("FEISHU_BITABLE_APP_TOKEN")
    if not app_token:
        raise ValueError("请配置 FEISHU_BITABLE_APP_TOKEN")

    print("=" * 50)
    print("开始同步 Bitable 表结构")
    print("=" * 50)

    # 从环境变量读取三张表的 table_id
    # FEISHU_BITABLE_CONTRACTS_TABLE_ID
    # FEISHU_BITABLE_WEIGH_TICKETS_TABLE_ID
    # FEISHU_BITABLE_STOCK_INFLOWS_TABLE_ID
    tables_config = {
        "contracts": get_table_id("contracts"),
        "weigh_tickets": get_table_id("weigh_tickets"),
        "stock_inflows": get_table_id("stock_inflows"),
    }

    schema = load_existing_schema()

    for table_name, table_id in tables_config.items():
        if table_id:
            schema[table_name] = sync_table(client, app_token, table_name, table_id)
        else:
            print(f"\n⚠ 跳过 {table_name}: 未配置 table_id")

    save_schema(schema)
    print("\n✓ 同步完成!")


def sync_specific_tables(table_names: list[str]):
    """同步指定的表"""
    client = get_client()
    app_token = os.environ.get("FEISHU_BITABLE_APP_TOKEN")
    if not app_token:
        raise ValueError("请配置 FEISHU_BITABLE_APP_TOKEN")

    print("=" * 50)
    print(f"同步指定表: {', '.join(table_names)}")
    print("=" * 50)

    schema = load_existing_schema()

    for table_name in table_names:
        table_id = get_table_id(table_name)
        if not table_id:
            print(f"⚠ 跳过 {table_name}: 未配置 table_id")
            continue
        schema[table_name] = sync_table(client, app_token, table_name, table_id)

    save_schema(schema)
    print("\n✓ 同步完成!")


def main():
    parser = argparse.ArgumentParser(description="Schema 同步工具")
    parser.add_argument(
        "--tables",
        nargs="+",
        choices=["contracts", "weigh_tickets", "stock_inflows"],
        help="指定要同步的表（默认同步所有）",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="列出所有可用的表",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="监听模式（TODO: 暂未实现）",
    )

    args = parser.parse_args()

    if args.list:
        client = get_client()
        app_token = os.environ.get("FEISHU_BITABLE_APP_TOKEN")
        if not app_token:
            print("✗ 请配置 FEISHU_BITABLE_APP_TOKEN")
            return
        tables = list_tables(client, app_token)
        print("\n可用表:")
        for t in tables:
            print(f"  - {t['name']}: {t['table_id']}")
        return

    if args.watch:
        print("⚠ 监听模式暂未实现，请手动运行同步")
        return

    if args.tables:
        sync_specific_tables(args.tables)
    else:
        sync_all()


if __name__ == "__main__":
    main()
