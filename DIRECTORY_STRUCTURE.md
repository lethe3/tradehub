# TradeHub 项目目录结构说明

## 目录总览

```
tradehub/
├── core/           # 业务核心层（纯 Pydantic，无外部依赖）
├── engine/         # Recipe 双引擎
├── api/            # FastAPI 路由层
├── store/          # 存储抽象层
├── web/            # React SPA 前端
├── feishu/         # 飞书集成（暂冻结）
├── ai/             # AI/OCR 模块（暂冻结）
├── schema/         # Schema 层
├── scripts/        # 脚本工具
├── tests/          # 测试套件
├── data/           # JSON 数据存储
└── samples/        # 样本数据
```

---

## 1. `core/` — 业务核心层

**作用**：纯业务逻辑，无任何外部依赖（不 import feishu、api、store、web）

| 文件 | 作用 |
|------|------|
| `models/batch.py` | 批次模型：ContractRecord, WeighTicketRecord, AssayReportRecord, BatchUnit, BatchView |
| `models/pricing.py` | 计价模型：PricingRule, PriceComponent |
| `models/cash_flow.py` | 资金流水模型：CashFlowRecord |
| `models/settlement_item.py` | 结算明细模型：SettlementItemRecord |
| `settlement.py` | 结算计算引擎：calc_dry_weight, calc_metal_quantity, calc_element_payment, generate_cash_flows |
| `linking.py` | 数据串联引擎：将合同/磅单/化验单关联起来 |
| `dispatcher.py` | 意图分发器：路由用户意图（GENERATE_CONTRACT, WEIGH, ASSAY, SETTLEMENT） |
| `handlers.py` | 业务处理器：调用 dispatcher 处理业务逻辑 |
| `fake_data.py` | 假数据生成器：生成测试用合同/磅单/化验单数据 |

---

## 2. `engine/` — Recipe 双引擎

**作用**：计价配方引擎，Python (Decimal) + JS (前端) 双实现

| 文件 | 作用 |
|------|------|
| `schema.py` | Recipe Schema 定义：计价规则的结构化描述（供 Python/JS 共享） |
| `recipe.py` | Python 版 Recipe Evaluator：Decimal 精度，用于正式结算 |
| `recipe.js` | JS 版 Recipe Evaluator：前端实时预览，与 Python 版交叉验证 |

---

## 3. `api/` — FastAPI 路由层

**作用**：REST API 接口层

| 文件 | 作用 |
|------|------|
| `app.py` | FastAPI 应用入口，配置 CORS、中间件 |
| `contracts.py` | 合同 CRUD 路由 + 子资源路由（磅单/化验单/配方/结算） |
| `schemas.py` | Pydantic 请求/响应模型 |
| `deps.py` | 依赖注入：DataStore 注入、认证等 |

---

## 4. `store/` — 存储抽象层

**作用**：数据存储抽象，支持切换存储后端

| 文件 | 作用 |
|------|------|
| `base.py` | DataStore 接口定义 |
| `json_store.py` | JSON 文件存储实现（开发期使用） |

> 计划生产期切换到 BitableStore（暂未实现）

---

## 5. `web/` — React SPA 前端

**作用**：独立工作台 Web UI

| 目录/文件 | 作用 |
|----------|------|
| `src/App.jsx` | React 应用入口 |
| `src/main.jsx` | 渲染入口 |
| `src/api/client.js` | API 客户端（fetch 封装） |
| `src/theme.js` | 主题样式系统 |
| `src/stores/contractStore.js` | Zustand 合同状态管理 |
| `src/stores/settlementStore.js` | Zustand 结算状态管理 |
| `src/pages/ContractList.jsx` | 合同列表页面 |
| `src/pages/ContractDetail.jsx` | 合同详情页面 |
| `src/components/` | 公共组件：Modal, Sidebar, StageBar |
| `src/stages/StageParsing.jsx` | 阶段1 - 解析（配方编辑器） |
| `src/stages/StageSettlement.jsx` | 阶段4 - 结算 |
| `src/stages/StagePlaceholder.jsx` | 阶段2/3/5 占位组件 |
| `vite.config.js` | Vite 构建配置 |
| `package.json` | 前端依赖 |

---

## 6. `feishu/` — 飞书集成（暂冻结）

**作用**：飞书 Bot + Bitable 集成（方向已转，Phase 3+ 再对接）

| 文件 | 作用 |
|------|------|
| `bot.py` | 飞书 Bot 入口 |
| `handler.py` | 消息处理器：路由文本命令到业务逻辑 |
| `bitable.py` | Bitable API 封装 |
| `cards.py` | 消息卡片构造 |
| `settlement_card.py` | 结算结果卡片渲染 |
| `ws_client.py` | WebSocket 客户端（接收飞书事件） |

---

## 7. `ai/` — AI/OCR 模块（暂冻结）

**作用**：OCR/VLM 提取、LLM 结构化解析（Phase 3+ 再启用）

| 文件 | 作用 |
|------|------|
| `ocr.py` | OCR 通用接口 |
| `assay_report.py` | 化验单 OCR 解析 |
| `weigh_ticket.py` | 磅单 OCR 解析 |
| `extractor.py` | LLM 结构化提取（Instructor） |
| `classify.py` | 文档分类器 |

---

## 8. `schema/` — Schema 层

**作用**：飞书 Bitable 表结构定义（与飞书对齐）

| 文件 | 作用 |
|------|------|
| `schema.yaml` | 五表结构定义（合同、磅单、化验单、资金流水、结算明细） |
| `loader.py` | Schema 加载器 |
| `field_maps.py` | 逻辑名→中文名映射 |
| `sync.py` | Schema 同步工具 |

---

## 9. `scripts/` — 脚本工具

| 文件 | 作用 |
|------|------|
| `seed_data.py` | 种子数据脚本，初始化 JSON 存储 |
| `setup_tables.py` | Bitable 建表脚本 |
| `inspect_sdk.py` | 飞书 SDK 方法检查脚本 |
| `export_data.py` | 导出 Bitable 数据到 JSON |
| `convert_to_fixtures.py` | 导出 JSON 转 pytest fixture |

---

## 10. `tests/` — 测试套件

**作用**：185 个测试，全部通过

| 文件 | 作用 |
|------|------|
| `test_recipe_engine.py` | Recipe 双引擎一致性验证（185 tests） |
| `test_api.py` | FastAPI 路由测试 |
| `test_store.py` | 存储层 CRUD 测试 |
| `test_m3a_models.py` | 数据模型测试 |
| `test_m3b_assay_report.py` | 化验单解析测试 |
| `test_m3c_linking.py` | 数据串联测试 |
| `test_m3d_settlement.py` | 结算计算测试 |
| `test_m3d2_impurity.py` | 杂质扣款测试 |
| `test_m3d3_settlement_card.py` | 结算卡片渲染测试 |
| `test_e2e_workflow.py` | 端到端工作流测试 |
| `fixtures/` | 测试数据：mock_documents/（场景1/2） |

---

## 11. `data/` — JSON 数据存储

**作用**：开发期本地 JSON 存储

| 文件 | 作用 |
|------|------|
| `contracts.json` | 合同数据 |
| `weigh_tickets.json` | 磅单数据 |
| `assay_reports.json` | 化验单数据 |
| `recipes.json` | 计价配方数据 |

---

## 12. 其他根目录文件

| 文件 | 作用 |
|------|------|
| `main.py` | 应用入口：组装 FastAPI + 静态文件服务 |
| `Makefile` | 开发命令：run, test, seed, clean |
| `requirements.txt` | Python 依赖 |
| `package.json` | 项目元信息（主仓库） |
| `CLAUDE.md` | Claude Code 协议 |
| `DEV_RULES.md` | 开发规范 |

---

## 架构约束

> **核心规则**：`core/` 不允许 import `feishu/`、`ai/`、`api/`、`store/` 或 `web/`

- `core/models/` 是纯 Pydantic 数据模型，零外部依赖
- `engine/` 实现 Recipe 双引擎，两者共享同一 Recipe Schema
- `store/` 定义 DataStore 接口，切换存储只改配置
