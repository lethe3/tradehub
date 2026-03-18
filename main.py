"""
TradeHub 入口文件
只做组装和调度，不写具体业务逻辑

使用方式：
  python main.py              — 启动飞书 WebSocket Bot（阶段三暂冻结）
  python main.py --web        — 启动 FastAPI Web 工作台 API
  python main.py --web --port 8000 --host 0.0.0.0
"""
import argparse
import sys


def run_feishu():
    """启动飞书 WebSocket Bot（Phase 3+ 再对接）。"""
    from feishu import create_ws_bot
    bot = create_ws_bot()
    print("TradeHub 服务已启动，正在连接飞书 WebSocket...")
    bot.start()


def run_web(host: str = "0.0.0.0", port: int = 8000):
    """启动 FastAPI Web 工作台 API。"""
    try:
        import uvicorn
    except ImportError:
        print("错误：未安装 uvicorn，请运行 pip install uvicorn", file=sys.stderr)
        sys.exit(1)

    from api.app import create_app
    app = create_app()
    print(f"TradeHub API 启动中：http://{host}:{port}")
    print(f"API 文档：http://{host}:{port}/docs")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TradeHub 服务入口")
    parser.add_argument("--web", action="store_true", help="启动 Web API 模式")
    parser.add_argument("--host", default="0.0.0.0", help="API 监听地址（默认 0.0.0.0）")
    parser.add_argument("--port", type=int, default=8000, help="API 监听端口（默认 8000）")
    args = parser.parse_args()

    if args.web:
        run_web(host=args.host, port=args.port)
    else:
        run_feishu()
