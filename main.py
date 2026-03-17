"""
TradeHub 入口文件
只做组装和调度，不写具体业务逻辑
"""
from feishu import create_ws_bot


if __name__ == '__main__':
    bot = create_ws_bot()
    print("TradeHub 服务已启动，正在连接飞书 WebSocket...")
    bot.start()
