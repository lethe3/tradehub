"""
FastAPI 应用工厂

create_app(store) 创建并配置 FastAPI 实例：
  - CORS：允许所有本地来源（开发期）
  - 路由：挂载 contracts 路由器
  - 健康检查：GET /api/health
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.contracts import router as contracts_router


def create_app() -> FastAPI:
    """创建并返回配置好的 FastAPI 应用。"""
    app = FastAPI(
        title="TradeHub API",
        description="有色金属散货贸易工作台 API",
        version="0.1.0",
    )

    # CORS（开发期允许 localhost:5173 / 3000 / 5000）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://localhost:3000",
            "http://localhost:5000",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 路由
    app.include_router(contracts_router)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "service": "tradehub-api"}

    return app
