"""
Schema 加载器 - 加载和解析 schema.yaml

提供表结构的数据类和查询方法。
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
SCHEMA_FILE = PROJECT_ROOT / "schema" / "schema.yaml"


@dataclass
class FieldOption:
    """字段选项（单选/多选）"""
    id: str
    name: str
    color: int | None = None


@dataclass
class Field:
    """表字段定义"""
    field_id: str
    name: str
    type: int
    options: list[FieldOption] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Field":
        """从字典创建 Field 对象"""
        options = []
        if "options" in data:
            options = [
                FieldOption(
                    id=opt.get("id", ""),
                    name=opt.get("name", ""),
                    color=opt.get("color"),
                )
                for opt in data["options"]
            ]
        return cls(
            field_id=data.get("field_id", ""),
            name=data.get("name", ""),
            type=data.get("type", 1),
            options=options,
        )

    def get_option_id(self, option_name: str) -> str | None:
        """根据选项名称获取选项 ID"""
        for opt in self.options:
            if opt.name == option_name:
                return opt.id
        return None

    @property
    def type_name(self) -> str:
        """字段类型名称"""
        type_map = {
            1: "文本",
            2: "数字",
            3: "单选",
            4: "多选",
            5: "日期",
            7: "复选框",
            8: "下拉组合",
            9: "下拉多选",
            10: "成员",
            11: "部门",
            15: "邮箱",
            16: "电话",
            17: "链接",
            18: "单向关联",
            19: "双向关联",
            20: "公式",
            21: "汇总",
            22: "分段式",
            23: "检查框",
            1005: "自动编号",
        }
        return type_map.get(self.type, f"未知({self.type})")


@dataclass
class Table:
    """表结构定义"""
    table_id: str
    name: str
    fields: list[Field] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Table":
        """从字典创建 Table 对象"""
        fields = [Field.from_dict(f) for f in data.get("fields", [])]
        return cls(
            table_id=data.get("table_id", ""),
            name=data.get("name", ""),
            fields=fields,
        )

    def get_field(self, field_name: str) -> Field | None:
        """根据字段名获取字段定义"""
        for f in self.fields:
            if f.name == field_name:
                return f
        return None

    def get_field_id(self, field_name: str) -> str | None:
        """根据字段名获取 field_id"""
        f = self.get_field(field_name)
        return f.field_id if f else None

    def get_field_by_id(self, field_id: str) -> Field | None:
        """根据 field_id 获取字段定义"""
        for f in self.fields:
            if f.field_id == field_id:
                return f
        return None


class Schema:
    """Schema 加载器"""

    def __init__(self, data: dict | None = None):
        self._data = data or {}
        self._tables: dict[str, Table] = {}
        self._build_tables()

    def _build_tables(self):
        """构建表对象缓存"""
        for table_name, table_data in self._data.items():
            if isinstance(table_data, dict):
                self._tables[table_name] = Table.from_dict(table_data)

    @classmethod
    def load(cls, schema_file: Path | None = None) -> "Schema":
        """从文件加载 schema"""
        path = schema_file or SCHEMA_FILE
        if not path.exists():
            raise FileNotFoundError(f"Schema 文件不存在: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls(data)

    def get_table(self, table_name: str) -> Table | None:
        """获取表定义"""
        return self._tables.get(table_name)

    def get_table_id(self, table_name: str) -> str | None:
        """获取表的 table_id"""
        table = self.get_table(table_name)
        return table.table_id if table else None

    def table_names(self) -> list[str]:
        """获取所有表名"""
        return list(self._tables.keys())

    @property
    def raw(self) -> dict:
        """获取原始数据"""
        return self._data


# 全局单例（延迟加载）
_schema: Schema | None = None


def get_schema() -> Schema:
    """获取全局 Schema 实例（延迟加载）"""
    global _schema
    if _schema is None:
        _schema = Schema.load()
    return _schema


def reload_schema():
    """重新加载 schema"""
    global _schema
    _schema = Schema.load()
    return _schema
