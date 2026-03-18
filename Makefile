# TradeHub Makefile

.PHONY: api web dev test seed clean help

# ── 服务启动 ─────────────────────────────────────────────────

api:  ## 启动 FastAPI 后端（端口 8000）
	python main.py --web

web:  ## 启动前端开发服务器（端口 5173）
	cd web && npm run dev

dev:  ## 并发启动前端 + 后端（需要 concurrently）
	@if command -v concurrently > /dev/null 2>&1; then \
		concurrently "python main.py --web" "cd web && npm run dev"; \
	else \
		echo "提示：安装 concurrently 可同时启动前后端"; \
		echo "  npm install -g concurrently"; \
		echo "现在分别在两个终端运行："; \
		echo "  make api"; \
		echo "  make web"; \
	fi

# ── 测试 ────────────────────────────────────────────────────

test:  ## 运行所有 Python 测试
	python -m pytest tests/ -v

test-sprint1:  ## 只跑 Sprint 1 测试（store + recipe engine）
	python -m pytest tests/test_store.py tests/test_recipe_engine.py -v

test-api:  ## 只跑 API 集成测试
	python -m pytest tests/test_api.py -v

test-all:  ## 运行所有测试（含旧有测试）
	python -m pytest tests/ -v --tb=short

# ── 数据 ────────────────────────────────────────────────────

seed:  ## 用 fixture 数据填充本地 JSON 存储
	python scripts/seed_data.py

seed-clean:  ## 清空并重新填充数据
	python scripts/seed_data.py --clear

# ── 前端 ────────────────────────────────────────────────────

web-install:  ## 安装前端依赖
	cd web && npm install

web-build:  ## 构建前端生产包
	cd web && npm run build

# ── 清理 ────────────────────────────────────────────────────

clean:  ## 清空 data/ 目录中的测试数据
	@rm -f data/*.json
	@echo "data/ 已清空"

# ── 帮助 ────────────────────────────────────────────────────

help:  ## 显示帮助信息
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
