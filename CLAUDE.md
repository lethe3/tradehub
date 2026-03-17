# TradeHub — Claude Code 协议

## 项目

TradeHub：飞书 Bot + Bitable 的大宗商品贸易 AI 系统，当前从跟单切入验证。

## ⚠️ 启动检查（每次新会话）

**必读（每次，共 2 个文件）：**
1. `~/workspace/zen/Projects/TradeHub/status.md` — 当前状态仪表盘
2. `DEV_RULES.md` — 开发规范

**按需读（任务相关时才读）：**
- 涉及架构/历史背景 → `~/workspace/zen/Projects/TradeHub/context.md`
- 涉及历史技术选型 → `~/workspace/zen/Projects/TradeHub/decisions.md`
- 追溯近期细节 → `~/workspace/zen/Projects/TradeHub/log.md`（只读最近一个里程碑）
- 合同/测算 → `~/workspace/zen/Projects/TradeHub/Work/Contracts/` 或 `Work/Estimates/`

读完 status.md 后用一句话确认当前状态，再等待任务指令。

## 协作者

Zhang：统计学背景，擅长数据结构设计和业务逻辑，不擅长工程脚手架搭建。核心壁垒是大宗商品贸易经验。

协作原则：
- 生成完整可运行的代码，不给片段
- 用数据分析语言沟通业务逻辑
- 工程脚手架你主导，业务规则 Zhang 主导
- 每次生成代码后简要说明"这段在做什么"
- 不确定的业务逻辑先问，不要猜
- 结算相关的业务规则（计价公式、扣款阶梯、取整策略）由 Zhang 主导定义，通常以合同摘录卡 YAML 的形式提供

## ⚠️ 工作流程

**快速任务**（commit / 单文件改动 / 文档更新）→ 直接执行，≤3步，不读无关文件，不制定计划。
**里程碑任务**（新功能 / 集成调试 / 重构）→ 走下方完整流程：
```
Zhang 给出任务（里程碑）
    ↓
你拆解为子任务，每个子任务走 DEV_RULES.md 中的「开发循环」
    ↓
全部子任务通过自动化验证 → 告诉 Zhang "可以手动验证了"，说明测试方法
    ↓
Zhang 说"确认完成"后：
  ├── 你直接写：status.md / log.md
  ├── 你写草稿（⏳待确认）：合同卡、测算卡、decisions.md
  └── 你不能写的：列出具体差异和建议，等 Zhang 手动更新
    ↓
你 commit（代码仓库 + Obsidian vault）
```

**绝不自行宣布完成。** 未经 Zhang 确认，status.md 状态不得从"进行中"变为"已完成"。

## 文件权限

### 可直接写
- `status.md` — 任务进度更新
- `log.md` — 只追加，永不修改已有内容

### 可写草稿（标记 `⏳待确认`，等 Zhang 确认后改为 `✅已确认`）
- `Work/Contracts/` — 合同摘录卡草稿，YAML 加 `confirmed: false`
- `Work/Estimates/` — 测算记录卡，只追加新版本（v2、v3…），不改已有版本
- `Work/decisions.md` — 新增决策记录

### 绝不能写可以提建议（可以提交 commit）
- `context.md`、`Work/SOPs/*`、`Work/inbox.md`、`Memory/*`、`Projects/_index.md`

### 业务数据红线
- **绝不修改 `confirmed: true` 的内容**
- 测算记录卡只追加，不改已有版本

## 架构
```
tradehub/
├── feishu/       ← 平台层：飞书 Bot(WebSocket)、Bitable API、消息卡片
├── core/         ← 业务层：意图路由、技能模块、计价引擎、数据串联
│   └── models/   ← Pydantic 数据模型（batch · cash_flow · pricing）
├── ai/           ← AI 层：OCR/VLM 调用、Instructor 结构化解析、prompt 模板
├── schema/       ← Schema层：schema.yaml + loader + sync
└── main.py       ← 入口：只做组装和调度
```

**核心规则：`core/` 不允许 import `feishu/` 或 `ai/`。**

`core/models/` 是纯 Pydantic 数据模型，零外部依赖。`core/` 下的计算模块（linking.py、settlement.py）只接收和返回这些模型，Bitable 读写由 `feishu/` 层在外部完成。`feishu/` 将飞书事件转为标准输入交给 `core/`，`ai/` 负责 OCR/LLM 调用并返回标准输出。不需要写抽象基类或适配器模式，保持简单。

## 关键依赖

- 飞书集成：`lark_oapi`（官方 SDK）
- 结构化解析：`instructor` + `pydantic`
- OCR（开发期）：GLM-OCR API
- 业务推理（目标态）：Qwen3 32B（Ollama）
- 数值计算：`decimal`（标准库，结算金额必须用 Decimal，不用 float）

未列出的依赖不要自行引入，需要时先和 Zhang 确认。

## 飞书

- 使用官方 Python SDK `lark_oapi`。参考 `references/openclaw-lark/skills/` 了解能力边界和参数结构，但实际代码用 `lark_oapi` 写，不翻译 TypeScript。
- 同时集成了飞书 MCP。

**SDK 调用门控（不可跳过）：** 写任何 `feishu/` 或 `lark_oapi` 调用前，必须先跑：
```bash
python scripts/inspect_sdk.py <模块名>   # 例：python scripts/inspect_sdk.py im.v1
```
将输出贴在回复里，确认参数名和类型后再写代码。无 inspect 输出 = 禁止写调用代码。

**飞书调试标准开场：** 调试飞书问题时，第一步必须是：
1. `python -m pytest tests/ -v` — 看实际错误，不猜
2. 常见首选排查点：① 事件格式（`header`/`body` 路径） ② `sender_id` 路径 ③ 消息去重

## Git

- 代码仓库 `~/dev/tradehub/`：验证通过后 commit，里程碑打 tag（如 `v0.1-里程碑0`）
- Obsidian vault `~/workspace/zen/`：里程碑验证通过后 commit，只 commit 不 push
- commit message 统一用中文
- `.env` 和 `.obsidian/` 不提交

发现新技术经验时，主动告诉 Zhang 应该写到哪个文件。

## log 读取规则
- 默认只读 log.md 最近一个里程碑的条目（往上滚直到遇到上一个 ## 日期标题为止）
- 需要追溯历史时才继续往上读
- 每次里程碑闭合后，将超过 2 个里程碑前的条目归档到 log_archive.md（剪切追加），保持 log.md 轻量

## decisions.md 写入触发条件
遇到以下情况时，主动在 decisions.md 追加一条记录（不等 Zhang 指令）：
- 做了有 trade-off 的技术选型（选 A 放弃 B）
- 否定了一个看起来合理的方案
- 发现了一个"坑"并绕过去了

格式：
### [决策标题] YYYY-MM-DD
- 背景：
- 选择：
- 理由：
- 否定的方案：

写完后告知 Zhang（在回复中提一句）。