# TradeHub — Claude Code 协议

## 项目

TradeHub：飞书 Bot + Bitable 的大宗商品贸易 AI 系统，当前从跟单切入验证。

## ⚠️工作流程

每个任务遵循以下循环：
```
Zhang 给出任务（里程碑）
    ↓
你写代码（读 Obsidian → 生成代码 → Zhang 审阅）
    ↓
Zhang 验证结果（你不能替他做这一步）
    ↓
回写 Obsidian + 更新建议
  ├── 你直接写：status.md / log.md / 草稿文件
  └── 你不能写的：列出具体差异和建议修改内容，等 Zhang 确认后手动更新
    ↓
验证通过 → 你 commit（代码仓库 + Obsidian vault）
```

## 协作者

Zhang：统计学背景，擅长数据结构设计和业务逻辑，不擅长工程脚手架搭建。核心壁垒是大宗商品贸易经验。

协作原则：
- 生成完整可运行的代码，不给片段
- 用数据分析语言沟通业务逻辑
- 工程脚手架你主导，业务规则 Zhang 主导
- 每次生成代码后简要说明"这段在做什么"
- 不确定的业务逻辑先问，不要猜

## ⚠️ 启动检查（每次新会话必须执行，不可跳过）

依次读取以下 4 个文件，全部读完后用一句话确认当前状态，再等待任务指令：

1. `~/workspace/zen/Projects/_index.md`
2. `~/workspace/zen/Projects/TradeHub/status.md`
3. `~/workspace/zen/Projects/TradeHub/decisions.md`
4. `~/workspace/zen/Projects/TradeHub/context.md`


## 关于飞书(feishu/lark)

* 使用官方 Python SDK `lark_oapi`。参考 `references/openclaw-lark/skills/` 了解能力边界和参数结构，但实际代码用 `lark_oapi` 写，不翻译 TypeScript。
* 同时集成了飞书 mcp

## Feishu SDK 使用规范

**禁止凭记忆写 SDK 调用**。每次使用新的 API 前，先运行：
```bash
python scripts/inspect_sdk.py im.v1
```

确认属性名后再写代码。

## API 调用原则

1. 优先查官方文档或用 inspect_sdk.py 确认，不猜
2. 遇到 AttributeError，先 inspect 再修，不要连续盲试
3. 新增一个 API 调用前，写一个最小可运行的独立测试脚本验证，
   确认通过后再集成进主流程

## 文件权限

### 可直接写
- `status.md` — 任务进度更新
- `log.md` — 只追加，永不修改已有内容

### 可写草稿（标记 `⏳待确认`，等 Zhang 确认后改为 `✅已确认`）
- `Work/Contracts/` — 合同摘录卡草稿，YAML 加 `confirmed: false`
- `Work/Estimates/` — 测算记录卡，只追加新版本（v2、v3…），不改已有版本
- `Work/decisions.md` — 新增决策记录

### 绝不能写（可以提交 commit）
- `context.md`、`Work/SOPs/*`、`Work/inbox.md`、`Memory/*`、`Projects/_index.md`

### 业务数据红线
- **绝不修改 `confirmed: true` 的内容**
- 测算记录卡只追加，不改已有版本

## ⚠️ 任务(里程碑)完成流程

**绝不自行宣布完成。** 必须按此顺序：
1. 代码写完 → 验证功能完整 → 告诉 Zhang "手动验证"，说明测试方法
2. Zhang 说"确认完成"后，你才能在 status.md 和 log.md 标记完成，同时给出你不可修改文件的修改建议。
3. 未经确认，status.md 中的状态不得从"进行中"变为"已完成"

## 代码规范

- Python 为主语言，注释用中文
- Bitable 字段名和类型从 `schema/schema.yaml` 读取，不硬编码

## 关键依赖

- 飞书集成：`lark_oapi`（官方 SDK）
- 结构化解析：`instructor` + `pydantic`
- OCR（开发期）：GLM-OCR API
- OCR（目标态）：GLM-OCR 0.9B / PaddleOCR-VL
- 业务推理（目标态）：Qwen3 32B（Ollama）

未列出的依赖不要自行引入（如 langchain、openai sdk），需要时先和 Zhang 确认。

## 架构

```
tradehub/
├── feishu/       ← 平台层：飞书 Bot(WebSocket)、Bitable API、消息卡片
├── core/         ← 业务层：意图路由(dispatcher+handler注册表)、技能模块、字段校验、计价
├── ai/           ← AI 层：OCR/VLM 调用、Instructor 结构化解析、prompt 模板
├── schema/       ← Schema层：schema.yaml + loader + sync
└── main.py       ← 入口：只做组装和调度
```

**核心规则：`core/` 不允许 import `feishu/` 或 `ai/`。** 业务逻辑不依赖平台和模型。

`feishu/` 负责将飞书事件转为标准输入交给 `core/`，`ai/` 负责 OCR/LLM 调用并返回标准输出。意图路由是纯 Python 调度逻辑，不绑定飞书消息格式，不依赖模型。

不需要写抽象基类或适配器模式，保持简单。

## Git

- 代码仓库 `~/dev/tradehub/`：验证通过后 commit，里程碑打 tag（如 `v0.1-里程碑0`）
- Obsidian vault `~/workspace/zen/`：里程碑验证通过后 commit，只 commit 不 push
- commit message 统一用中文
- `.env` 和 `.obsidian/` 不提交

发现新技术经验时，主动告诉 Zhang 应该写到哪个文件。
