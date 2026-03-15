# TradeHub — Claude Code 协议

## 项目

TradeHub：飞书 Bot + Bitable 的大宗商品贸易 AI 系统，当前从跟单切入验证。

## 协作者

Zhang：统计学背景，擅长数据结构设计和业务逻辑，不擅长工程脚手架搭建。核心壁垒是大宗商品贸易经验。

协作原则：
- 生成完整可运行的代码，不给片段
- 用数据分析语言沟通业务逻辑
- 工程脚手架你主导，业务规则 Zhang 主导
- 每次生成代码后简要说明"这段在做什么"
- 不确定的业务逻辑先问，不要猜

## ⚠️ 启动检查（每次新会话必须执行，不可跳过）

依次读取以下 3 个文件，全部读完后用一句话确认当前状态，再等待任务指令：

1. `~/workspace/zen/Projects/_index.md`
2. `~/workspace/zen/Projects/TradeHub/status.md`
3. `~/workspace/zen/Projects/TradeHub/decisious.md`
4. `~/workspace/zen/Projects/TradeHub/context.md`


## 飞书 API

使用官方 Python SDK `lark_oapi`。参考 `references/openclaw-lark/skills/` 了解能力边界和参数结构，但实际代码用 `lark_oapi` 写，不翻译 TypeScript。

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

## 架构

```
tradehub/
├── feishu/       ← 平台层：飞书 Bot、Bitable API 封装
├── core/         ← 业务层：磅单解析、校验、计价等纯业务逻辑
├── ai/           ← AI 层：OCR、模型调用、prompt 管理
└── main.py       ← 入口：只做组装和调度
```

**核心规则：`core/` 不允许 import `feishu/` 或 `ai/`。** 业务逻辑不依赖平台和模型。

不需要写抽象基类或适配器模式，保持简单。

## Git

- 代码仓库 `~/dev/tradehub/`：验证通过后 commit，里程碑打 tag（如 `v0.1-里程碑0`）
- Obsidian vault `~/workspace/zen/`：里程碑验证通过后 commit，只 commit 不 push
- commit message 统一用中文
- `.env` 和 `.obsidian/` 不提交

## 工作循环

```
Zhang 给出任务(里程碑) → 你写代码 → 回写 Obsidian（status/log/草稿）+ 你不修改文件的建议
→ Zhang 验证 → 验证通过 → 你 commit（代码 + vault）
```

发现新技术经验时，主动告诉 Zhang 应该写到哪个文件。
