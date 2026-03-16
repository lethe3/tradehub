"""
TradeHub 入口文件
只做组装和调度，不写具体业务逻辑
"""
import os
from dotenv import load_dotenv
from feishu import create_ws_bot


def load_config() -> dict:
    """从环境变量加载配置"""
    load_dotenv()

    return {
        "feishu": {
            "app_id": os.getenv("FEISHU_APP_ID"),
            "app_secret": os.getenv("FEISHU_APP_SECRET"),
            "verification_token": os.getenv("FEISHU_VERIFICATION_TOKEN", ""),
            "encrypt_key": os.getenv("FEISHU_ENCRYPT_KEY", ""),
        },
        "bitable": {
            "app_token": os.getenv("FEISHU_BITABLE_APP_TOKEN"),
            "contracts_table_id": os.getenv("FEISHU_BITABLE_CONTRACTS_TABLE_ID"),
            "weigh_tickets_table_id": os.getenv("FEISHU_BITABLE_WEIGH_TICKETS_TABLE_ID"),
            "stock_inflows_table_id": os.getenv("FEISHU_BITABLE_STOCK_INFLOWS_TABLE_ID"),
        },
    }


if __name__ == '__main__':
    config = load_config()

    # 创建并启动 WebSocket Bot
    bot = create_ws_bot()
    print("TradeHub 服务已启动，正在连接飞书 WebSocket...")

    # 阻塞运行
    bot.start()
