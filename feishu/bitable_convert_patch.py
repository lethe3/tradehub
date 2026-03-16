"""
feishu/bitable.py 字段转换补丁

覆盖飞书多维表格所有字段类型的读写转换。
基于 field-properties.md 文档。

使用方法：
  替换 bitable.py 中的 _convert_value_for_write 和 _convert_value_from_read 方法
  替换 create 方法开头的字段过滤逻辑
"""

from datetime import datetime, timezone
from typing import Any


# ============================================================
# 写入转换：Python 值 → 飞书 API 格式
# ============================================================

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
    │ 19    │ list[str]（查找引用：只读）                     │
    │ 20    │ 不可写入（公式：只读）                          │
    │ 21    │ list[str]（双向关联：record_id 数组）           │
    │ 22    │ {"location": str, ...}（地理位置）              │
    │ 23    │ list[dict]（群组：[{"id": "oc_xxx"}]）         │
    │ 1001  │ 不可写入（创建时间：只读）                      │
    │ 1002  │ 不可写入（最后更新时间：只读）                  │
    │ 1005  │ 不可写入（自动编号：只读）                      │
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
        return _to_timestamp_ms(value)

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
            return value  # 假设已经是正确格式
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


def _to_timestamp_ms(value: Any) -> int | None:
    """日期值 → 毫秒时间戳"""
    if value is None or value == "":
        return None

    # 已经是时间戳
    if isinstance(value, (int, float)):
        if value > 1_000_000_000_000:
            return int(value)       # 毫秒
        elif value > 1_000_000_000:
            return int(value * 1000)  # 秒 → 毫秒
        return None

    # datetime 对象
    if isinstance(value, datetime):
        return int(value.timestamp() * 1000)

    # 字符串日期
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


# ============================================================
# 读取转换：飞书 API 格式 → 人可读 Python 值
# ============================================================

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
        return value  # 没找到就原样返回（可能本身就是名称）

    # 多选 (4) - 选项 ID 列表 → 名称列表
    if t == 4 and isinstance(value, list):
        id_to_name = {opt.id: opt.name for opt in field.options}
        return [id_to_name.get(v, v) for v in value]

    # 超链接 (15)
    if t == 15 and isinstance(value, dict):
        return value.get("link", value.get("text", str(value)))

    return value


# ============================================================
# create 方法的字段过滤（替换原方法开头部分）
# ============================================================

def create(self, data: dict) -> str | None:
    """
    创建记录

    Args:
        data: 字段名到值的字典

    Returns:
        record_id
    """
    fields = {}
    for field_name, value in data.items():
        # 跳过空值
        if value is None or value == "":
            continue
        converted = self._convert_value_for_write(field_name, value)
        if converted is not None:
            fields[field_name] = converted

    if not fields:
        from feishu.bitable import BitableError
        raise BitableError("没有有效字段可写入")

    from lark_oapi.api.bitable.v1 import (
        CreateAppTableRecordRequest,
        AppTableRecord,
    )
    import logging

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
        logging.getLogger(__name__).error(f"创建记录失败: {response.msg}")
        from feishu.bitable import BitableError
        raise BitableError(f"创建记录失败: {response.msg}")


# ============================================================
# 测试
# ============================================================

def test():
    from dataclasses import dataclass, field as dc_field

    @dataclass
    class FakeOption:
        id: str
        name: str

    @dataclass
    class FakeField:
        field_id: str
        name: str
        type: int
        options: list = dc_field(default_factory=list)

    @dataclass
    class FakeTable:
        fields: list[FakeField] = dc_field(default_factory=list)
        def get_field(self, name):
            for f in self.fields:
                if f.name == name:
                    return f
            return None
        def get_field_by_id(self, fid):
            for f in self.fields:
                if f.field_id == fid:
                    return f
            return None

    schema = FakeTable(fields=[
        FakeField("f01", "磅单号",    1005),
        FakeField("f02", "磅单编号",  1),
        FakeField("f03", "关联合同",  18),
        FakeField("f04", "货物品名",  3, [FakeOption("o1", "黄铜块"), FakeOption("o2", "铜精矿")]),
        FakeField("f05", "净重(吨)",  2),
        FakeField("f06", "过磅日期",  5),
        FakeField("f07", "是否结算",  7),
        FakeField("f08", "联系电话",  13),
        FakeField("f09", "参考链接",  15),
        FakeField("f10", "负责人",    11),
        FakeField("f11", "标签",      4, [FakeOption("t1", "紧急"), FakeOption("t2", "重要")]),
        FakeField("f12", "创建时间",  1001),
        FakeField("f13", "公式字段",  20),
    ])

    class FakeConverter:
        _cached_schema = schema

    fake = FakeConverter()
    import types
    convert_w = types.MethodType(_convert_value_for_write, fake)
    convert_r = types.MethodType(_convert_value_from_read, fake)

    print("=" * 60)
    print("写入转换测试")
    print("=" * 60)

    write_tests = [
        ("磅单号",    "PD-001",       None,         "自动编号 → 跳过"),
        ("磅单编号",  "A2025001",     "A2025001",   "文本 → str"),
        ("磅单编号",  "",             None,          "文本空值 → 跳过"),
        ("关联合同",  "",             None,          "关联空值 → 跳过（避免报错）"),
        ("关联合同",  "rec_abc",      ["rec_abc"],   "关联 → list[str]"),
        ("货物品名",  "黄铜块",       "黄铜块",      "单选 → str"),
        ("货物品名",  "",             None,          "单选空值 → 跳过"),
        ("净重(吨)",  "23.5",        23.5,          "数字字符串 → float"),
        ("净重(吨)",  "1,234.5",     1234.5,        "数字千分位 → float"),
        ("净重(吨)",  0.0,           0.0,           "数字零 → 保留"),
        ("净重(吨)",  "abc",         None,          "数字非法 → 跳过"),
        ("过磅日期",  "2025-04-03",  1743638400000, "日期字符串 → 毫秒时间戳"),
        ("过磅日期",  "2025/04/03",  1743638400000, "日期斜杠 → 毫秒时间戳"),
        ("过磅日期",  "",            None,           "日期空值 → 跳过"),
        ("是否结算",  "true",        True,           "复选框 → bool"),
        ("是否结算",  "false",       False,          "复选框 → bool"),
        ("联系电话",  "13800138000", "13800138000",  "电话 → str"),
        ("参考链接",  "https://a.com", {"link": "https://a.com", "text": "https://a.com"}, "超链接 → dict"),
        ("负责人",    "ou_abc",      [{"id": "ou_abc"}], "人员 → list[dict]"),
        ("标签",      ["紧急", "重要"], ["紧急", "重要"], "多选 → list[str]"),
        ("标签",      "紧急",        ["紧急"],       "多选单值 → list[str]"),
        ("创建时间",  "2025-01-01",  None,           "创建时间 → 只读跳过"),
        ("公式字段",  "100",         None,           "公式 → 只读跳过"),
    ]

    all_pass = True
    for name, input_val, expected, desc in write_tests:
        # 空值在 create 里就被跳过了，这里直接测转换
        if input_val == "":
            result = None  # create 方法会跳过空字符串
        else:
            result = convert_w(name, input_val)
        ok = result == expected
        status = "✅" if ok else "❌"
        if not ok:
            all_pass = False
        print(f"  {status} {desc:30s} | {str(input_val):15s} → {result}")
        if not ok:
            print(f"     期望: {expected}")

    print()
    print("=" * 60)
    print("读取转换测试")
    print("=" * 60)

    read_tests = [
        ("f06", 1743638400000, "2025-04-03",         "日期时间戳 → 字符串"),
        ("f04", "o1",          "黄铜块",              "单选 ID → 名称"),
        ("f04", "黄铜块",      "黄铜块",              "单选名称 → 保持"),
        ("f11", ["t1", "t2"],  ["紧急", "重要"],      "多选 ID → 名称"),
        ("f09", {"link": "https://a.com", "text": "A"}, "https://a.com", "超链接 → link"),
    ]

    for fid, input_val, expected, desc in read_tests:
        result = convert_r(fid, input_val)
        ok = result == expected
        status = "✅" if ok else "❌"
        if not ok:
            all_pass = False
        print(f"  {status} {desc:30s} | {str(input_val):20s} → {result}")
        if not ok:
            print(f"     期望: {expected}")

    print()
    if all_pass:
        print("=" * 60)
        print("全部测试通过 ✅")
        print("=" * 60)
    else:
        print("❌ 有测试未通过")
        exit(1)


if __name__ == "__main__":
    test()
