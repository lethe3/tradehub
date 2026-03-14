"""
合同表 CRUD 操作模块

从 schema.yaml 读取字段定义，提供增删改查功能。
"""
import os
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv
from lark_oapi import Client
from lark_oapi.api.bitable.v1 import (
    CreateAppTableRecordRequest,
    DeleteAppTableRecordRequest,
    GetAppTableRecordRequest,
    ListAppTableRecordRequest,
    UpdateAppTableRecordRequest,
    AppTableRecord,
)

# 加载 .env
load_dotenv()

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
SCHEMA_FILE = PROJECT_ROOT / "schema" / "schema.yaml"


def load_schema() -> dict:
    """加载 schema.yaml"""
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_field_by_name(table_schema: dict, field_name: str) -> dict | None:
    """根据字段名获取字段定义"""
    for field in table_schema.get("fields", []):
        if field.get("name") == field_name:
            return field
    return None


def get_field_id(table_schema: dict, field_name: str) -> str | None:
    """根据字段名获取 field_id"""
    field = get_field_by_name(table_schema, field_name)
    return field.get("field_id") if field else None


class ContractsCRUD:
    """合同表 CRUD 操作类"""

    def __init__(self, client: Client | None = None):
        self.client = client or self._create_client()
        self.schema = load_schema()
        contracts_schema = self.schema.get("contracts", {})
        self.table_id = contracts_schema.get("table_id")
        self.app_token = os.environ.get("FEISHU_BITABLE_APP_TOKEN")
        if not self.table_id or not self.app_token:
            raise ValueError("未配置合同表 table_id 或 app_token")

    @staticmethod
    def _create_client() -> Client:
        """创建飞书客户端"""
        app_id = os.environ.get("FEISHU_APP_ID")
        app_secret = os.environ.get("FEISHU_APP_SECRET")
        if not app_id or not app_secret:
            raise ValueError("请配置 FEISHU_APP_ID 和 FEISHU_APP_SECRET")
        return Client.builder().app_id(app_id).app_secret(app_secret).build()

    def _prepare_fields(self, data: dict) -> dict:
        """准备写入字段，保持字段名格式"""
        result = {}
        contracts_schema = self.schema.get("contracts", {})

        for field_name, value in data.items():
            field = get_field_by_name(contracts_schema, field_name)
            if not field:
                print(f"⚠ 未知字段: {field_name}")
                continue

            field_type = field["type"]

            # 处理日期字段 (type=5) - 转换为毫秒时间戳
            if field_type == 5 and value:
                if isinstance(value, str):
                    # 尝试解析日期字符串
                    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"]:
                        try:
                            dt = datetime.strptime(value, fmt)
                            value = int(dt.timestamp() * 1000)
                            break
                        except ValueError:
                            continue
                elif isinstance(value, datetime):
                    value = int(value.timestamp() * 1000)

            # 飞书 Bitable API 使用字段名（不是 field_id）
            result[field_name] = value

        return result

    def create(self, data: dict) -> str | None:
        """
        创建合同记录

        Args:
            data: 字段名到值的字典，如 {"合同编号": "HT-2024-001", "我方主体": "公司A", ...}

        Returns:
            record_id 或 None
        """
        fields = self._prepare_fields(data)
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
        获取单条合同记录

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

        # 将 field_id 转换回字段名
        result = {}
        contracts_schema = self.schema.get("contracts", {})
        fields = response.data.record.fields

        field_id_to_name = {}
        for field in contracts_schema.get("fields", []):
            field_id_to_name[field["field_id"]] = field["name"]

        for field_id, value in fields.items():
            field_name = field_id_to_name.get(field_id, field_id)
            result[field_name] = value

        return result

    def list(self, filter_formula: str | None = None, page_size: int = 100) -> list[dict]:
        """
        列出合同记录

        Args:
            filter_formula: 过滤公式，如 '合同方向 == "采购"'
            page_size: 每页数量

        Returns:
            记录列表
        """
        request = ListAppTableRecordRequest.builder() \
            .app_token(self.app_token) \
            .table_id(self.table_id) \
            .page_size(page_size) \
            .build()

        if filter_formula:
            request.filter = filter_formula

        response = self.client.bitable.v1.app_table_record.list(request)
        if not response.success():
            print(f"✗ 列表获取失败: {response.msg}")
            return []

        # 将 field_id 转换回字段名
        contracts_schema = self.schema.get("contracts", {})
        field_id_to_name = {}
        for field in contracts_schema.get("fields", []):
            field_id_to_name[field["field_id"]] = field["name"]

        results = []
        for record in response.data.items:
            item = {}
            for field_id, value in record.fields.items():
                field_name = field_id_to_name.get(field_id, field_id)
                item[field_name] = value
            item["record_id"] = record.record_id
            results.append(item)

        return results

    def update(self, record_id: str, data: dict) -> bool:
        """
        更新合同记录

        Args:
            record_id: 记录 ID
            data: 字段名到值的字典

        Returns:
            是否成功
        """
        fields = self._prepare_fields(data)
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
        删除合同记录

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


# 便捷函数
def create_contract(data: dict) -> str | None:
    """创建合同"""
    return ContractsCRUD().create(data)


def get_contract(record_id: str) -> dict | None:
    """获取合同"""
    return ContractsCRUD().get(record_id)


def list_contracts(filter_formula: str | None = None) -> list[dict]:
    """列出合同"""
    return ContractsCRUD().list(filter_formula)


def update_contract(record_id: str, data: dict) -> bool:
    """更新合同"""
    return ContractsCRUD().update(record_id, data)


def delete_contract(record_id: str) -> bool:
    """删除合同"""
    return ContractsCRUD().delete(record_id)
