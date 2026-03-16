"""
通用 Bitable 框架

基于 schema.yaml 定义，提供双向同步能力：
- 拉取模式（Bitable → schema）：从飞书拉取表结构
- 创建模式（schema → Bitable）：用 schema 定义创建新表
- CRUD 操作：通用的增删改查

核心类：
- BitableApp: 应用级别操作（创建表）
- BitableTable: 表级别操作（CRUD）
"""
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import Any, List, Tuple

logger = logging.getLogger(__name__)


class BitableError(Exception):
    """Bitable 操作异常"""
    pass


class FieldType(IntEnum):
    """飞书 Bitable 字段类型枚举"""
    TEXT = 1
    NUMBER = 2
    SINGLE_SELECT = 3
    MULTI_SELECT = 4
    DATE = 5
    CHECKBOX = 7
    DROP_DOWN = 8
    DROP_DOWN_MULTIPLE = 9
    USER = 10
    DEPARTMENT = 11
    PHONE = 13
    URL = 15
    EMAIL = 15  # 邮箱是 type=1 + ui_type=Email，但保留兼容
    ATTACHMENT = 17
    SINGLE_LINK = 18
    LOOKUP = 19
    FORMULA = 20
    DUPLEX_LINK = 21
    LOCATION = 22
    GROUP = 23
    CREATED_TIME = 1001
    UPDATED_TIME = 1002
    AUTO_NUMBER = 1005

from dotenv import load_dotenv
from lark_oapi import Client
from lark_oapi.api.bitable.v1 import (
    CreateAppTableFieldRequest,
    CreateAppTableRecordRequest,
    CreateAppTableRequest,
    DeleteAppTableRecordRequest,
    GetAppTableRecordRequest,
    ListAppTableFieldRequest,
    ListAppTableRecordRequest,
    ListAppTableRequest,
    UpdateAppTableRecordRequest,
    AppTableRecord,
)
from lark_oapi.core import JSON

from schema import get_schema, Schema


# 加载 .env
load_dotenv()

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent


def get_client() -> Client:
    """创建飞书客户端"""
    app_id = os.environ.get("FEISHU_APP_ID")
    app_secret = os.environ.get("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        raise ValueError("请配置 FEISHU_APP_ID 和 FEISHU_APP_SECRET")
    return Client.builder().app_id(app_id).app_secret(app_secret).build()


def get_app_token() -> str:
    """获取 app_token"""
    app_token = os.environ.get("FEISHU_BITABLE_APP_TOKEN")
    if not app_token:
        raise ValueError("请配置 FEISHU_BITABLE_APP_TOKEN")
    return app_token


# 飞书 Bitable 字段类型映射（兼容字符串到枚举的转换）
FIELD_TYPE_MAP = {
    "text": FieldType.TEXT,
    "number": FieldType.NUMBER,
    "single_select": FieldType.SINGLE_SELECT,
    "multi_select": FieldType.MULTI_SELECT,
    "date": FieldType.DATE,
    "checkbox": FieldType.CHECKBOX,
    "drop_down": FieldType.DROP_DOWN,
    "drop_down_multiple": FieldType.DROP_DOWN_MULTIPLE,
    "user": FieldType.USER,
    "department": FieldType.DEPARTMENT,
    "phone": FieldType.PHONE,
    "url": FieldType.URL,
    "attachment": FieldType.ATTACHMENT,
    "single_link": FieldType.SINGLE_LINK,
    "formula": FieldType.FORMULA,
    "duplex_link": FieldType.DUPLEX_LINK,
    "auto_number": FieldType.AUTO_NUMBER,
}


@dataclass
class FieldConfig:
    """字段配置（用于创建表）"""
    name: str
    field_type: str | int  # 如 "text", "number" 或直接用数字 1, 2
    description: str | None = None


class BitableApp:
    """
    Bitable 应用级操作

    用于列出表、创建表等操作。
    """

    def __init__(self, client: Client | None = None, app_token: str | None = None):
        self.client = client or get_client()
        self.app_token = app_token or get_app_token()

    def list_tables(self) -> List[dict]:
        """列出所有表"""
        request = ListAppTableRequest.builder().app_token(self.app_token).build()
        response = self.client.bitable.v1.app_table.list(request)
        if not response.success():
            raise RuntimeError(f"获取表列表失败: {response.msg}")
        return [
            {
                "table_id": t.table_id,
                "name": t.name,
            }
            for t in (response.data.items or [])
        ]

    def get_table(self, table_name: str) -> dict | None:
        """根据表名获取表信息"""
        tables = self.list_tables()
        for t in tables:
            if t["name"] == table_name:
                return t
        return None

    def create_table(self, table_name: str, fields: List[FieldConfig] | None = None) -> str:
        """
        创建新表

        Args:
            table_name: 表名
            fields: 字段配置列表

        Returns:
            新创建的 table_id
        """
        request = CreateAppTableRequest.builder() \
            .app_token(self.app_token) \
            .request_body(
                {"name": table_name}
            ) \
            .build()

        response = self.client.bitable.v1.app_table.create(request)
        if not response.success():
            raise RuntimeError(f"创建表失败: {response.msg}")

        table_id = response.data.table_id
        logger.info(f"创建表成功: {table_name} ({table_id})")

        if fields:
            table = BitableTable(table_id, app_token=self.app_token, client=self.client)
            for field in fields:
                table.create_field(field)

        return table_id

    def table_exists(self, table_name: str) -> bool:
        """检查表是否存在"""
        return self.get_table(table_name) is not None


class BitableTable:
    """
    Bitable 表级 CRUD 操作

    基于 schema.yaml 定义，提供通用的增删改查功能。
    自动处理字段类型转换（日期、数字、单选、多选、关联等）。
    """

    def __init__(
        self,
        table_name: str | None = None,
        table_id: str | None = None,
        schema: Schema | None = None,
        client: Client | None = None,
        app_token: str | None = None,
    ):
        self.client = client or get_client()
        self.app_token = app_token or get_app_token()
        self.schema = schema or get_schema()

        # 解析 table_id
        if table_id:
            self.table_id = table_id
        elif table_name:
            self.table_id = self.schema.get_table_id(table_name)
            if not self.table_id:
                raise ValueError(f"表 {table_name} 未在 schema.yaml 中定义")
        else:
            raise ValueError("必须提供 table_name 或 table_id")

        self.table_name = table_name or self._get_table_name_from_api()

        # 缓存 schema 表定义（修复：从 schema 获取，不自引用）
        self._cached_schema = self.schema.get_table(self.table_name)

    def _get_table_name_from_api(self) -> str:
        """从 API 获取表名"""
        tables = BitableApp(client=self.client, app_token=self.app_token).list_tables()
        for t in tables:
            if t["table_id"] == self.table_id:
                return t["name"]
        return self.table_id

    def _get_table_schema(self):
        """获取表对应的 schema 定义（从缓存）"""
        return self._cached_schema

    # ==================== 字段操作 ====================

    def list_fields(self) -> List[dict]:
        """列出所有字段"""
        request = ListAppTableFieldRequest.builder() \
            .app_token(self.app_token) \
            .table_id(self.table_id) \
            .build()

        response = self.client.bitable.v1.app_table_field.list(request)
        if not response.success():
            raise RuntimeError(f"获取字段列表失败: {response.msg}")

        fields = []
        for f in (response.data.items or []):
            field_info = {
                "field_id": f.field_id,
                "type": f.type,
                "name": getattr(f, "field_name", None) or getattr(f, "name", ""),
            }
            if f.type in [3, 4] and hasattr(f, "property") and f.property:
                field_info["options"] = [
                    {"id": o.id, "name": o.name, "color": getattr(o, "color", None)}
                    for o in getattr(f.property, "options", []) or []
                ]
            fields.append(field_info)
        return fields

    def create_field(self, field_config: FieldConfig) -> str:
        """创建字段"""
        if isinstance(field_config.field_type, str):
            field_type = FIELD_TYPE_MAP.get(field_config.field_type.lower())
            if field_type is None:
                raise ValueError(f"未知字段类型: {field_config.field_type}")
        else:
            field_type = field_config.field_type

        request = CreateAppTableFieldRequest.builder() \
            .app_token(self.app_token) \
            .table_id(self.table_id) \
            .request_body({
                "field_name": field_config.name,
                "type": field_type,
                "description": field_config.description,
            }) \
            .build()

        response = self.client.bitable.v1.app_table_field.create(request)
        if not response.success():
            raise RuntimeError(f"创建字段失败: {response.msg}")

        return response.data.field_id

    # ==================== 字段值转换 ====================

    @staticmethod
    def _to_timestamp_ms(value: Any) -> int | None:
        """日期值 → 毫秒时间戳"""
        if value is None or value == "":
            return None

        if isinstance(value, (int, float)):
            if value > 1_000_000_000_000:
                return int(value)
            elif value > 1_000_000_000:
                return int(value * 1000)
            return None

        if isinstance(value, datetime):
            return int(value.timestamp() * 1000)

        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
            for fmt in [
                "%Y-%m-%d",
                "%Y/%m/%d",
                "%Y%m%d",
                "%Y年%m月%d日",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d %H:%M:%S",
                "%Y/%m/%d %H:%M",
            ]:
                try:
                    dt = datetime.strptime(value, fmt)
                    return int(dt.timestamp() * 1000)
                except ValueError:
                    continue
        return None

    def _convert_value_for_write(self, field_name: str, value: Any) -> Any:
        """
        转换写入值，根据 schema 字段类型做类型转换

        飞书 Bitable API 对字段值的格式要求：
        ┌───────┬──────────────────────────────────────────────┐
        │ type  │ API 要求                                      │
        ├───────┼──────────────────────────────────────────────┤
        │ 1     │ str（文本，含条码/邮箱 ui_type 变体）          │
        │ 2     │ float/int（数字，含进度/货币/评分变体）         │
        │ 3     │ str（单选：选项名称）                          │
        │ 4     │ list[str]（多选：选项名称列表）                │
        │ 5     │ int（日期：毫秒时间戳）                        │
        │ 7     │ bool（复选框）                                │
        │ 11    │ list[dict]（人员：[{"id": "ou_xxx"}]）         │
        │ 13    │ str（电话号码）                                │
        │ 15    │ {"link": str, "text": str}（超链接）           │
        │ 17    │ 不支持直接写入（附件需上传接口）                │
        │ 18    │ list[str]（单向关联：record_id 数组）           │
        │ 19    │ 只读（查找引用）                               │
        │ 20    │ 只读（公式）                                   │
        │ 21    │ list[str]（双向关联：record_id 数组）           │
        │ 22    │ {"location": str, ...}（地理位置）              │
        │ 23    │ list[dict]（群组：[{"id": "oc_xxx"}]）         │
        │ 1001  │ 只读（创建时间）                               │
        │ 1002  │ 只读（最后更新时间）                           │
        │ 1005  │ 只读（自动编号）                               │
        └───────┴──────────────────────────────────────────────┘

        Returns:
            转换后的值，None 表示跳过该字段
        """
        if value is None:
            return None

        field = self._cached_schema.get_field(field_name) if self._cached_schema else None
        if not field:
            return value

        t = field.type

        # === 只读字段 - 不可写入 ===
        if t in (1005, 1001, 1002, 20, 19):
            return None

        # === 附件 (17) - 不支持直接写入 ===
        if t == 17:
            return None

        # === 文本 (1)，含条码/邮箱变体 ===
        if t == 1:
            s = str(value).strip()
            return s if s else None

        # === 数字 (2)，含进度/货币/评分变体 ===
        if t == 2:
            if isinstance(value, (int, float)):
                return value
            try:
                cleaned = str(value).replace(",", "").replace(" ", "").strip()
                if not cleaned:
                    return None
                return float(cleaned)
            except (ValueError, TypeError):
                return None

        # === 单选 (3) ===
        if t == 3:
            s = str(value).strip()
            return s if s else None

        # === 多选 (4) ===
        if t == 4:
            if isinstance(value, list):
                result = [str(v).strip() for v in value if str(v).strip()]
                return result if result else None
            s = str(value).strip()
            return [s] if s else None

        # === 日期 (5) - 毫秒时间戳 ===
        if t == 5:
            return self._to_timestamp_ms(value)

        # === 复选框 (7) ===
        if t == 7:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes", "是")
            return bool(value)

        # === 人员 (11) - [{"id": "ou_xxx"}] ===
        if t == 11:
            if isinstance(value, list):
                return value
            if isinstance(value, str) and value.strip():
                return [{"id": value.strip()}]
            return None

        # === 电话号码 (13) ===
        if t == 13:
            s = str(value).strip()
            return s if s else None

        # === 超链接 (15) - {"link": str, "text": str} ===
        if t == 15:
            if isinstance(value, dict):
                return value
            s = str(value).strip()
            return {"link": s, "text": s} if s else None

        # === 单向关联 (18) / 双向关联 (21) - list[str] ===
        if t in (18, 21):
            if isinstance(value, list):
                filtered = [str(v).strip() for v in value if str(v).strip()]
                return filtered if filtered else None
            if isinstance(value, str):
                s = value.strip()
                return [s] if s else None
            return None

        # === 地理位置 (22) ===
        if t == 22:
            if isinstance(value, dict):
                return value
            s = str(value).strip()
            return {"location": s} if s else None

        # === 群组 (23) - [{"id": "oc_xxx"}] ===
        if t == 23:
            if isinstance(value, list):
                return value
            if isinstance(value, str) and value.strip():
                return [{"id": value.strip()}]
            return None

        # === 未知类型 - 原样返回 ===
        return value

    def _convert_value_from_read(self, field_id: str, value: Any) -> Any:
        """
        转换读取值，将飞书格式转换为人可读格式

        ┌───────┬──────────────────────────────────────┐
        │ type  │ 转换规则                              │
        ├───────┼──────────────────────────────────────┤
        │ 5     │ 毫秒时间戳 → "YYYY-MM-DD" 字符串     │
        │ 1001  │ 同上                                 │
        │ 1002  │ 同上                                 │
        │ 3     │ 选项 ID → 选项名称                    │
        │ 4     │ 选项 ID 列表 → 名称列表               │
        │ 15    │ {"link": ..., "text": ...} → link    │
        │ 其他  │ 原样返回                              │
        └───────┴──────────────────────────────────────┘
        """
        if value is None:
            return None

        field = self._cached_schema.get_field_by_id(field_id) if self._cached_schema else None
        if not field:
            return value

        t = field.type

        # 日期类 (5, 1001, 1002) - 毫秒时间戳 → 日期字符串
        if t in (5, 1001, 1002) and isinstance(value, (int, float)):
            try:
                dt = datetime.fromtimestamp(value / 1000, tz=timezone.utc)
                return dt.strftime("%Y-%m-%d")
            except (ValueError, OSError):
                return str(value)

        # 单选 (3) - 选项 ID → 名称
        if t == 3 and isinstance(value, str):
            for opt in field.options:
                if opt.id == value:
                    return opt.name
            return value

        # 多选 (4) - 选项 ID 列表 → 名称列表
        if t == 4 and isinstance(value, list):
            id_to_name = {opt.id: opt.name for opt in field.options}
            return [id_to_name.get(v, v) for v in value]

        # 超链接 (15)
        if t == 15 and isinstance(value, dict):
            return value.get("link", value.get("text", str(value)))

        return value

    # ==================== 记录操作 ====================

    def create(self, data: dict) -> str | None:
        """
        创建记录

        Args:
            data: 字段名到值的字典，如 {"合同编号": "HT-2024-001"}

        Returns:
            record_id
        """
        # 转换字段值，跳过空值和不可写字段
        fields = {}
        for field_name, value in data.items():
            if value is None or value == "":
                continue
            converted = self._convert_value_for_write(field_name, value)
            if converted is not None:
                fields[field_name] = converted

        if not fields:
            raise BitableError("没有有效字段可写入")

        record = AppTableRecord.builder().fields(fields).build()

        request = CreateAppTableRecordRequest.builder() \
            .app_token(self.app_token) \
            .table_id(self.table_id) \
            .request_body(record) \
            .build()

        response = self.client.bitable.v1.app_table_record.create(request)
        if response.success():
            return response.data.record.record_id
        else:
            logger.error(f"创建记录失败: {response.msg}")
            raise BitableError(f"创建记录失败: {response.msg}")

    def get(self, record_id: str) -> dict | None:
        """
        获取单条记录

        Returns:
            字段名到值的字典
        """
        request = GetAppTableRecordRequest.builder() \
            .app_token(self.app_token) \
            .table_id(self.table_id) \
            .record_id(record_id) \
            .build()

        response = self.client.bitable.v1.app_table_record.get(request)
        if not response.success():
            logger.error(f"获取记录失败: {response.msg}")
            raise BitableError(f"获取记录失败: {response.msg}")

        result = {}
        raw_fields = response.data.record.fields

        table_schema = self._cached_schema
        field_id_to_name = {}
        if table_schema:
            for f in table_schema.fields:
                field_id_to_name[f.field_id] = f.name

        for field_id, value in raw_fields.items():
            field_name = field_id_to_name.get(field_id, field_id)
            result[field_name] = self._convert_value_from_read(field_id, value)

        return result

    def list(
        self,
        filter_formula: str | None = None,
        page_size: int = 100,
        page_token: str | None = None,
    ) -> Tuple[List[dict], str | None]:
        """
        列出记录

        Returns:
            (记录列表, 下一个 page_token)
        """
        request = ListAppTableRecordRequest.builder() \
            .app_token(self.app_token) \
            .table_id(self.table_id) \
            .page_size(page_size) \
            .build()

        if filter_formula:
            request.filter = filter_formula
        if page_token:
            request.page_token = page_token

        response = self.client.bitable.v1.app_table_record.list(request)
        if not response.success():
            logger.error(f"获取记录列表失败: {response.msg}")
            raise BitableError(f"获取记录列表失败: {response.msg}")

        table_schema = self._cached_schema
        field_id_to_name = {}
        if table_schema:
            for f in table_schema.fields:
                field_id_to_name[f.field_id] = f.name

        results = []
        for record in (response.data.items or []):
            item = {}
            for field_id, value in record.fields.items():
                field_name = field_id_to_name.get(field_id, field_id)
                item[field_name] = self._convert_value_from_read(field_id, value)
            item["record_id"] = record.record_id
            results.append(item)

        return results, response.data.page_token

    def list_all(self, filter_formula: str | None = None, page_size: int = 100) -> List[dict]:
        """列出所有记录（自动分页）"""
        all_records = []
        page_token = None

        while True:
            records, page_token = self.list(
                filter_formula=filter_formula,
                page_size=page_size,
                page_token=page_token,
            )
            all_records.extend(records)
            if not page_token:
                break

        return all_records

    def update(self, record_id: str, data: dict) -> bool:
        """
        更新记录

        Args:
            record_id: 记录 ID
            data: 字段名到值的字典

        Returns:
            是否成功
        """
        fields = {}
        for field_name, value in data.items():
            if value is None or value == "":
                continue
            converted = self._convert_value_for_write(field_name, value)
            if converted is not None:
                fields[field_name] = converted

        record = AppTableRecord.builder().fields(fields).build()

        request = UpdateAppTableRecordRequest.builder() \
            .app_token(self.app_token) \
            .table_id(self.table_id) \
            .record_id(record_id) \
            .request_body(record) \
            .build()

        response = self.client.bitable.v1.app_table_record.update(request)
        if response.success():
            return True
        else:
            logger.error(f"更新记录失败: {response.msg}")
            raise BitableError(f"更新记录失败: {response.msg}")

    def delete(self, record_id: str) -> bool:
        """
        删除记录

        Returns:
            是否成功
        """
        request = DeleteAppTableRecordRequest.builder() \
            .app_token(self.app_token) \
            .table_id(self.table_id) \
            .record_id(record_id) \
            .build()

        response = self.client.bitable.v1.app_table_record.delete(request)
        if response.success():
            return True
        else:
            logger.error(f"删除记录失败: {response.msg}")
            raise BitableError(f"删除记录失败: {response.msg}")


# ==================== 便捷函数 ====================

def table(table_name: str) -> BitableTable:
    """获取指定表的 BitableTable 实例"""
    return BitableTable(table_name=table_name)


def app() -> BitableApp:
    """获取 BitableApp 实例"""
    return BitableApp()
