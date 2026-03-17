"""
Schema 同步模块 - 双向同步本地 schema.yaml 与飞书 Bitable

用法:
    python -m schema.sync                      # pull：Bitable → schema.yaml（全部表）
    python -m schema.sync --tables contracts   # pull：只同步指定表
    python -m schema.sync --list               # 列出 Bitable 中所有表
    python -m schema.sync --push               # push：schema.yaml → Bitable（全部表）
    python -m schema.sync --push contracts     # push：只推指定表
    python -m schema.sync --create contracts   # 仅建表（不删字段，旧模式，已被 --push 替代）
    python -m schema.sync --watch              # 监听模式（TODO）

push 模式行为：
    1. 表不存在 → 创建表
    2. 表已存在 → 对比字段
       - 本地有 Bitable 无 → 新增字段
       - 本地无 Bitable 有（且非只读系统字段）→ 删除字段
    3. 推送完成后自动回拉，将 table_id / field_id 写回 schema.yaml
"""
import argparse
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from lark_oapi import Client
from lark_oapi.api.bitable.v1 import (
    CreateAppTableFieldRequest,
    CreateAppTableRequest,
    DeleteAppTableFieldRequest,
    ListAppTableFieldRequest,
    ListAppTableRequest,
)
from lark_oapi.api.bitable.v1.model import ReqTable

# 加载 .env
load_dotenv()

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
SCHEMA_FILE = PROJECT_ROOT / "schema" / "schema.yaml"

# 只读字段类型（不可删除，Bitable 自动维护）
_READONLY_TYPES = {1001, 1002, 1005}


def get_client() -> Client:
    """创建飞书客户端"""
    app_id = os.environ.get("FEISHU_APP_ID")
    app_secret = os.environ.get("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        raise ValueError("请配置 FEISHU_APP_ID 和 FEISHU_APP_SECRET")
    return Client.builder().app_id(app_id).app_secret(app_secret).build()


def get_app_token() -> str:
    app_token = os.environ.get("FEISHU_BITABLE_APP_TOKEN")
    if not app_token:
        raise ValueError("请配置 FEISHU_BITABLE_APP_TOKEN")
    return app_token


def get_table_id(table_name: str) -> str | None:
    """获取表名对应的 table_id"""
    env_key = f"FEISHU_BITABLE_{table_name.upper()}_TABLE_ID"
    return os.environ.get(env_key)


# ══════════════════════════════════════════════════════════════
# Bitable 读操作
# ══════════════════════════════════════════════════════════════

def list_tables(client: Client, app_token: str) -> list[dict]:
    """列出 Bitable 中所有表"""
    request = ListAppTableRequest.builder().app_token(app_token).build()
    response = client.bitable.v1.app_table.list(request)
    if not response.success():
        print(f"✗ 获取表列表失败: {response.msg}")
        return []
    return [{"table_id": t.table_id, "name": t.name} for t in response.data.items]


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
        field_info = {
            "field_id": f.field_id,
            "type": f.type,
            "name": getattr(f, "field_name", None) or getattr(f, "name", ""),
        }
        if f.type in [3, 4] and hasattr(f, "property") and f.property:
            field_info["options"] = [
                {"id": o.id, "name": o.name, "color": getattr(o, "color", None)}
                for o in (getattr(f.property, "options", []) or [])
            ]
        fields.append(field_info)
    return fields


# ══════════════════════════════════════════════════════════════
# Bitable 写操作
# ══════════════════════════════════════════════════════════════

def create_bitable_table(client: Client, app_token: str, display_name: str) -> str:
    """在 Bitable 中新建表，返回 table_id"""
    from lark_oapi.api.bitable.v1 import CreateAppTableRequestBody
    req_table = ReqTable.builder().name(display_name).build()
    req_body = CreateAppTableRequestBody.builder().table(req_table).build()
    request = CreateAppTableRequest.builder() \
        .app_token(app_token) \
        .request_body(req_body) \
        .build()
    response = client.bitable.v1.app_table.create(request)
    if not response.success():
        raise RuntimeError(f"创建表 {display_name} 失败: {response.msg}")
    return response.data.table_id


def create_field(client: Client, app_token: str, table_id: str, field_name: str, field_type: int) -> str:
    """在表中新建字段，返回 field_id"""
    request = CreateAppTableFieldRequest.builder() \
        .app_token(app_token) \
        .table_id(table_id) \
        .request_body({"field_name": field_name, "type": field_type}) \
        .build()
    response = client.bitable.v1.app_table_field.create(request)
    if not response.success():
        raise RuntimeError(f"创建字段 {field_name} 失败: {response.msg}")
    return response.data.field.field_id


def delete_field(client: Client, app_token: str, table_id: str, field_id: str) -> bool:
    """删除表中的字段"""
    request = DeleteAppTableFieldRequest.builder() \
        .app_token(app_token) \
        .table_id(table_id) \
        .field_id(field_id) \
        .build()
    response = client.bitable.v1.app_table_field.delete(request)
    return response.success()


# ══════════════════════════════════════════════════════════════
# schema.yaml 读写
# ══════════════════════════════════════════════════════════════

def load_schema() -> dict:
    if SCHEMA_FILE.exists():
        with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def save_schema(schema: dict):
    SCHEMA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SCHEMA_FILE, "w", encoding="utf-8") as f:
        yaml.dump(schema, f, allow_unicode=True, default_flow_style=False)
    print(f"✓ 已写回 {SCHEMA_FILE}")


# ══════════════════════════════════════════════════════════════
# Pull 模式：Bitable → schema.yaml
# ══════════════════════════════════════════════════════════════

def pull_table(client: Client, app_token: str, table_key: str, table_id: str) -> dict:
    """从 Bitable 拉取单张表的结构"""
    print(f"\n>>> pull: {table_key} ({table_id})")
    bitable_tables = list_tables(client, app_token)
    display_name = table_key
    for t in bitable_tables:
        if t["table_id"] == table_id:
            display_name = t["name"]
            break

    fields = get_table_fields(client, app_token, table_id)
    print(f"    {len(fields)} 个字段")
    for f in fields:
        print(f"    - {f['name']} (type={f['type']}, id={f['field_id']})")

    return {"table_id": table_id, "name": display_name, "fields": fields}


def pull_tables(table_keys: list[str] | None = None):
    """Pull：Bitable → schema.yaml"""
    client = get_client()
    app_token = get_app_token()
    schema = load_schema()

    # 确定要拉取的 key→table_id 映射
    if table_keys:
        targets = {}
        for key in table_keys:
            tid = schema.get(key, {}).get("table_id") or get_table_id(key)
            if tid and not tid.startswith("PENDING"):
                targets[key] = tid
            else:
                print(f"⚠ {key}: 无有效 table_id，跳过")
    else:
        # 拉取 schema.yaml 中有有效 table_id 的全部表
        targets = {
            key: cfg["table_id"]
            for key, cfg in schema.items()
            if cfg and cfg.get("table_id") and not str(cfg.get("table_id", "")).startswith("PENDING")
        }

    print("=" * 50)
    print(f"Pull: Bitable → schema.yaml  ({len(targets)} 张表)")
    print("=" * 50)

    for key, tid in targets.items():
        schema[key] = pull_table(client, app_token, key, tid)

    save_schema(schema)
    print("\n✓ Pull 完成!")


# ══════════════════════════════════════════════════════════════
# Push 模式：schema.yaml → Bitable
# ══════════════════════════════════════════════════════════════

def push_table(client: Client, app_token: str, table_key: str, table_config: dict) -> dict:
    """
    Push 单张表：schema.yaml → Bitable

    返回更新后的 table_config（含真实 table_id 和 field_id）
    """
    display_name = table_config.get("name", table_key)
    schema_fields = table_config.get("fields", [])
    current_table_id = table_config.get("table_id", "")

    print(f"\n>>> push: {table_key} ({display_name})")

    # ── 1. 确认表存在，获取真实 table_id ──────────────────────
    bitable_tables = list_tables(client, app_token)
    bitable_by_name = {t["name"]: t["table_id"] for t in bitable_tables}
    bitable_by_id = {t["table_id"]: t["name"] for t in bitable_tables}

    if display_name in bitable_by_name:
        real_table_id = bitable_by_name[display_name]
        print(f"    表已存在: {real_table_id}")
    elif current_table_id and current_table_id in bitable_by_id:
        real_table_id = current_table_id
        print(f"    表已存在（by id）: {real_table_id}")
    else:
        # 建表
        real_table_id = create_bitable_table(client, app_token, display_name)
        print(f"    ✅ 新建表: {real_table_id}")

    # ── 2. 拉取 Bitable 当前字段 ──────────────────────────────
    bitable_fields = get_table_fields(client, app_token, real_table_id)
    bitable_by_fname = {f["name"]: f for f in bitable_fields}

    # ── 3. 本地 schema 中不是只读的字段集合 ──────────────────
    schema_field_names = {
        f["name"] for f in schema_fields
        if f.get("type") not in _READONLY_TYPES
    }

    # ── 4. 新增：本地有 Bitable 无 ───────────────────────────
    added = 0
    for sf in schema_fields:
        fname = sf["name"]
        ftype = sf.get("type", 1)
        if ftype in _READONLY_TYPES:
            continue
        if fname not in bitable_by_fname:
            try:
                create_field(client, app_token, real_table_id, fname, ftype)
                print(f"    ✅ 新增字段: {fname} (type={ftype})")
                added += 1
            except Exception as e:
                print(f"    ❌ 新增字段失败: {fname} — {e}")

    # ── 5. 删除：Bitable 有 本地无（跳过只读字段）───────────
    deleted = 0
    for bf in bitable_fields:
        fname = bf["name"]
        ftype = bf["type"]
        fid = bf["field_id"]
        if ftype in _READONLY_TYPES:
            continue
        if fname not in schema_field_names:
            ok = delete_field(client, app_token, real_table_id, fid)
            if ok:
                print(f"    🗑  删除字段: {fname} ({fid})")
                deleted += 1
            else:
                print(f"    ❌ 删除字段失败: {fname} ({fid})")

    print(f"    新增 {added} 个，删除 {deleted} 个")

    # ── 6. 回拉最新字段（含真实 field_id）────────────────────
    updated_fields = get_table_fields(client, app_token, real_table_id)
    return {"table_id": real_table_id, "name": display_name, "fields": updated_fields}


def push_tables(table_keys: list[str] | None = None):
    """Push：schema.yaml → Bitable，完成后自动回拉更新 field_id"""
    client = get_client()
    app_token = get_app_token()
    schema = load_schema()

    targets = list(table_keys) if table_keys else list(schema.keys())

    print("=" * 50)
    print(f"Push: schema.yaml → Bitable  ({len(targets)} 张表)")
    print("=" * 50)

    for key in targets:
        cfg = schema.get(key)
        if not cfg:
            print(f"⚠ {key}: 不在 schema.yaml 中，跳过")
            continue
        updated = push_table(client, app_token, key, cfg)
        schema[key] = updated

    save_schema(schema)
    print("\n✓ Push 完成（schema.yaml 已更新 table_id / field_id）!")


# ══════════════════════════════════════════════════════════════
# 旧接口（兼容原有调用，内部转发到新函数）
# ══════════════════════════════════════════════════════════════

def sync_table(client, app_token, table_name, table_id):
    return pull_table(client, app_token, table_name, table_id)


def sync_all():
    pull_tables()


def sync_specific_tables(table_names):
    pull_tables(table_names)


def load_existing_schema():
    return load_schema()


# ══════════════════════════════════════════════════════════════
# CLI 入口
# ══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Schema 双向同步工具")
    parser.add_argument("--tables", nargs="+", help="指定要 pull 的表 key（默认全部）")
    parser.add_argument("--list", action="store_true", help="列出 Bitable 中所有表")
    parser.add_argument(
        "--push", nargs="*", metavar="TABLE_KEY",
        help="Push schema.yaml → Bitable（可选指定表 key，默认全部）"
    )
    parser.add_argument("--create", nargs="*", help="[旧] 同 --push，保留兼容")
    parser.add_argument("--watch", action="store_true", help="监听模式（TODO）")

    args = parser.parse_args()

    if args.list:
        client = get_client()
        app_token = get_app_token()
        tables = list_tables(client, app_token)
        print("\nBitable 中的表:")
        for t in tables:
            print(f"  - {t['name']}: {t['table_id']}")
        return

    if args.push is not None:
        push_tables(args.push if args.push else None)
        return

    if args.create is not None:
        # 旧 --create 转发到 push
        push_tables(args.create if args.create else None)
        return

    if args.watch:
        print("⚠ 监听模式暂未实现")
        return

    # 默认：pull
    pull_tables(args.tables)


if __name__ == "__main__":
    main()
