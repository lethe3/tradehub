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
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, List, Tuple

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


# 飞书 Bitable 字段类型映射
FIELD_TYPE_MAP = {
    "text": 1,
    "number": 2,
    "single_select": 3,
    "multi_select": 4,
    "date": 5,
    "checkbox": 7,
    "drop_down": 8,
    "drop_down_multiple": 9,
    "user": 10,
    "department": 11,
    "email": 15,
    "phone": 16,
    "url": 17,
    "single_link": 18,
    "formula": 20,
    "rollup": 21,
    "auto_number": 1005,
}

REVERSE_TYPE_MAP = {v: k for k, v in FIELD_TYPE_MAP.items()}


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
            for t in response.data.items
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
            fields: 字段配置列表（可选，先创建空表，后续再添加字段）

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
        print(f"✓ 创建表成功: {table_name} ({table_id})")

        # 如果提供了字段配置，批量添加字段
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
        """
        初始化 BitableTable

        Args:
            table_name: 表名（从 schema.yaml 查找 table_id）
            table_id: 直接指定 table_id（优先级高于 table_name）
            schema: Schema 实例（可选，默认自动加载）
            client: 飞书客户端（可选）
            app_token: app_token（可选）
        """
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

    def _get_table_name_from_api(self) -> str:
        """从 API 获取表名"""
        tables = BitableApp(client=self.client, app_token=self.app_token).list_tables()
        for t in tables:
            if t["table_id"] == self.table_id:
                return t["name"]
        return self.table_id

    def _get_table_schema(self):
        """获取表对应的 schema 定义"""
        for name, table in [(n, self.schema.get_table(n)) for n in self.schema.table_names()]:
            if table and table.table_id == self.table_id:
                return table
        return None

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
        for f in response.data.items:
            field_info = {
                "field_id": f.field_id,
                "type": f.type,
                "name": getattr(f, "field_name", None) or getattr(f, "name", ""),
            }
            # 单选/多选选项
            if f.type in [3, 4] and hasattr(f, "property") and f.property:
                field_info["options"] = [
                    {"id": o.id, "name": o.name, "color": getattr(o, "color", None)}
                    for o in getattr(f.property, "options", []) or []
                ]
            fields.append(field_info)
        return fields

    def create_field(self, field_config: FieldConfig) -> str:
        """
        创建字段

        Args:
            field_config: 字段配置

        Returns:
            新字段的 field_id
        """
        # 解析字段类型
        if isinstance(field_config.field_type, str):
            field_type = FIELD_TYPE_MAP.get(field_config.field_type.lower())
            if field_type is None:
                raise ValueError(f"未知字段类型: {field_config.field_type}")
        else:
            field_type = field_config.field_type

        # 构建字段属性
        field_property = {}
        if field_config.field_type in ["single_select", "multi_select"]:
            # TODO: 支持预设选项
            pass

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

    # ==================== 记录操作 ====================

    def _convert_value_for_write(self, field_name: str, value: Any) -> Any:
        """
        转换写入值，处理字段类型转换

        Args:
            field_name: 字段名
            value: 原始值

        Returns:
            飞书 API 格式的值
        """
        if value is None:
            return None

        table_schema = self._get_table_schema()
        if not table_schema:
            # 没有 schema 定义，直接返回原始值
            return value

        field = table_schema.get_field(field_name)
        if not field:
            return value

        field_type = field.type

        # 日期字段 (type=5) - 转换为毫秒时间戳
        if field_type == 5 and value:
            if isinstance(value, str):
                for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"]:
                    try:
                        dt = datetime.strptime(value, fmt)
                        return int(dt.timestamp() * 1000)
                    except ValueError:
                        continue
            elif isinstance(value, datetime):
                return int(value.timestamp() * 1000)

        # 单选字段 (type=3) - 直接传选项名称，不需要转换
        # 写入时飞书会自动匹配选项（不存在会自动创建）
        # 见: feishu-bitable SKILL - 单选字段传字符串

        # 多选字段 (type=4) - 直接传选项名称数组
        # 写入时飞书会自动匹配选项（不存在会自动创建）

        # 关联字段 (type=18 单向关联, type=21 双向关联)
        # 直接传字符串数组 ["record_id1", "record_id2"]
        # 见: feishu-bitable SKILL - 简化写入可直接传数组
        if field_type in [18, 21] and value:
            if isinstance(value, str):
                # 用户直接传单个 record_id，返回字符串
                return value
            elif isinstance(value, list):
                # 用户传数组，保持数组格式（飞书期望字符串数组）
                return value
            elif isinstance(value, dict):
                # 用户传了 dict，转为 link_record_ids 数组
                if "link_record_ids" in value:
                    return value["link_record_ids"]
                return value
            return value

        return value

    def _convert_value_from_read(self, field_id: str, value: Any) -> Any:
        """
        转换读取值，将飞书格式转换为人可读的格式

        Args:
            field_id: 字段 ID
            value: 飞书返回的原始值

        Returns:
            人可读的格式
        """
        if value is None:
            return None

        table_schema = self._get_table_schema()
        if not table_schema:
            return value

        field = table_schema.get_field_by_id(field_id)
        if not field:
            return value

        field_type = field.type
        field_name = field.name

        # 日期字段 (type=5) - 毫秒时间戳转换为日期字符串
        if field_type == 5 and value:
            if isinstance(value, (int, float)):
                try:
                    dt = datetime.fromtimestamp(value / 1000)
                    return dt.strftime("%Y-%m-%d")
                except (ValueError, OSError):
                    return str(value)

        # 单选字段 (type=3) - 选项 ID 转换为选项名称
        if field_type == 3 and value:
            if isinstance(value, str):
                for opt in field.options:
                    if opt.id == value:
                        return opt.name

        # 多选字段 (type=4) - 选项 ID 列表转换为选项名称列表
        if field_type == 4 and value:
            if isinstance(value, list):
                id_to_name = {opt.id: opt.name for opt in field.options}
                return [id_to_name.get(v, v) for v in value]

        return value

    def create(self, data: dict) -> str | None:
        """
        创建记录

        Args:
            data: 字段名到值的字典，如 {"合同编号": "HT-2024-001", "我方主体": "公司A"}

        Returns:
            record_id 或 None
        """
        # 转换字段值
        fields = {}
        for field_name, value in data.items():
            converted = self._convert_value_for_write(field_name, value)
            if converted is not None:
                fields[field_name] = converted

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
            print(f"✗ 创建失败: {response.msg}")
            return None

    def get(self, record_id: str) -> dict | None:
        """
        获取单条记录

        Args:
            record_id: 记录 ID

        Returns:
            字段名到值的字典，或 None
        """
        request = GetAppTableRecordRequest.builder() \
            .app_token(self.app_token) \
            .table_id(self.table_id) \
            .record_id(record_id) \
            .build()

        response = self.client.bitable.v1.app_table_record.get(request)
        if not response.success():
            print(f"✗ 获取失败: {response.msg}")
            return None

        # 转换字段 ID 为字段名，并转换值格式
        result = {}
        raw_fields = response.data.record.fields

        table_schema = self._get_table_schema()
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

        Args:
            filter_formula: 过滤公式，如 '合同方向 == "采购"'
            page_size: 每页数量（最大 100）
            page_token: 分页 token

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
            print(f"✗ 列表获取失败: {response.msg}")
            return [], None

        # 转换字段 ID 为字段名
        table_schema = self._get_table_schema()
        field_id_to_name = {}
        if table_schema:
            for f in table_schema.fields:
                field_id_to_name[f.field_id] = f.name

        results = []
        for record in response.data.items:
            item = {}
            for field_id, value in record.fields.items():
                field_name = field_id_to_name.get(field_id, field_id)
                item[field_name] = self._convert_value_from_read(field_id, value)
            item["record_id"] = record.record_id
            results.append(item)

        return results, response.data.page_token

    def list_all(self, filter_formula: str | None = None, page_size: int = 100) -> List[dict]:
        """
        列出所有记录（自动分页）

        Args:
            filter_formula: 过滤公式
            page_size: 每页数量

        Returns:
            所有记录列表
        """
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
        # 转换字段值
        fields = {}
        for field_name, value in data.items():
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
            print(f"✗ 更新失败: {response.msg}")
            return False

    def delete(self, record_id: str) -> bool:
        """
        删除记录

        Args:
            record_id: 记录 ID

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
            print(f"✗ 删除失败: {response.msg}")
            return False


# ==================== 便捷函数 ====================

def table(table_name: str) -> BitableTable:
    """获取指定表的 BitableTable 实例"""
    return BitableTable(table_name=table_name)


def app() -> BitableApp:
    """获取 BitableApp 实例"""
    return BitableApp()
