"""
TradeHub - 飞书 Bitable 磅单表插入测试
最简版本：直接往磅单表插入一条测试记录

配置通过 .env 文件读取：
- FEISHU_APP_ID
- FEISHU_APP_SECRET
- FEISHU_BITABLE_APP_TOKEN
- FEISHU_BITABLE_TABLE_ID
"""
import os
from datetime import datetime
from dotenv import load_dotenv
from lark_oapi import Client
from lark_oapi.api.bitable.v1 import CreateAppTableRecordRequest, AppTableRecord

# 加载 .env 文件
load_dotenv()


def main():
    # 读取环境变量
    app_id = os.environ.get("FEISHU_APP_ID")
    app_secret = os.environ.get("FEISHU_APP_SECRET")
    app_token = os.environ.get("FEISHU_BITABLE_APP_TOKEN")
    table_id = os.environ.get("FEISHU_BITABLE_TABLE_ID")

    # 检查配置
    if not all([app_id, app_secret, app_token, table_id]):
        print("✗ 请配置 .env 文件，参考 .env.example")
        return

    # 创建飞书客户端
    client = Client.builder().app_id(app_id).app_secret(app_secret).build()

    # 测试数据（基于实际表结构）
    # 日期字段需要用时间戳格式
    record = AppTableRecord.builder().fields({
        "货物品名": "铜精矿",
        "净重(吨)": 24.300,
        "过磅日期": int(datetime(2026, 3, 14).timestamp() * 1000)  # 毫秒时间戳
    }).build()

    # 创建请求
    request = CreateAppTableRecordRequest.builder() \
        .app_token(app_token) \
        .table_id(table_id) \
        .request_body(record) \
        .build()

    # 发送请求
    response = client.bitable.v1.app_table_record.create(request)

    # 打印结果
    if response.success():
        print(f"✓ 插入成功！record_id: {response.data.record.record_id}")
    else:
        print(f"✗ 插入失败: {response.msg}")


if __name__ == "__main__":
    main()
