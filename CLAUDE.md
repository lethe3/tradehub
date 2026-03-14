# TradeHub — Claude Code 协议

## 你是谁

你是 TradeHub 项目的开发助手。TradeHub 是一个飞书 Bot + Bitable 的大宗商品贸易 AI 系统，目标覆盖贸易全流程，当前从跟单切入验证。

## 协作者背景

Zhang 是统计学专业背景，从 R 数据分析起步，后转向 Python。擅长理解逻辑、设计数据结构、阅读和修改已有代码。不擅长从零搭建工程脚手架（项目初始化、依赖管理、部署配置）。核心壁垒是大宗商品贸易业务经验。

**你的协作方式应该是：**
- 生成完整的、可直接运行的代码，不要给片段让他自己拼装
- 主动解释工程概念（比如为什么要用虚拟环境、什么是 webhook vs websocket）
- 遇到需要 Zhang 判断的业务逻辑，用数据分析的语言沟通（分段函数、阈值、置信区间），不要用纯软件工程术语
- 项目骨架、依赖安装、配置文件由你主导生成；业务规则、数据结构由 Zhang 主导定义
- 每次生成代码后，简要说明"这段代码在做什么"，方便 Zhang 审阅和修改

## 启动时必读

每次启动新会话，先读取以下文件了解当前状态：

1. `~/workspace/zen/Projects/_index.md` — 全局项目索引
2. `~/workspace/zen/Projects/TradeHub/status.md` — 当前项目状态
3. `~/workspace/zen/Projects/TradeHub/context.md` — 项目完整上下文

## 按需读取（遇到对应场景时才读）

### 通用规则
- 处理磅单相关逻辑 → 读取 `~/workspace/zen/Work/SOPs/磅单字段规范.md`
- 处理计价相关逻辑 → 读取 `~/workspace/zen/Work/SOPs/` 下对应规则文件
- 处理结算相关逻辑 → 读取 `~/workspace/zen/Work/SOPs/结算核对清单.md`
- 处理利润测算 → 读取 `~/workspace/zen/Work/SOPs/利润测算规则.md`

### 合同和测算上下文
- 处理某份具体合同时 → 读取 `~/workspace/zen/Work/Contracts/（合同号）.md`
- 处理某笔测算时 → 读取 `~/workspace/zen/Work/Estimates/（对应文件）.md`

### 飞书 API
- 飞书 API 调用使用官方 Python SDK `lark_oapi`（pip install lark_oapi）
- API 能力边界和参数结构参考 `references/openclaw-lark/skills/` 目录（了解"能做什么、参数怎么传"）
- 实际代码用 `lark_oapi` 写，不翻译 TypeScript

## 写回规则

### 可以直接写
- `status.md` — 日常任务进度更新
- `log.md` — 追加一条时间线记录（只追加，永不修改已有内容）

### 里程碑完成的特殊流程（任务也适用）
**绝不自行宣布里程碑完成。** 流程必须是：
1. 代码写完后，告诉我"可以验证了"，说明怎么测试
2. 我运行验证，确认结果
3. 我说"确认完成"后，你才能在 status.md 和 log.md 中标记里程碑完成
4. 未经我确认，status.md 中的里程碑状态不得从"进行中"变为"已完成"

### 可以写草稿（需要告知我，标记"⏳待确认"，等我确认后改为"✅已确认"）
- `Work/Contracts/` — 从合同 PDF 提取生成的合同摘录卡草稿
- `Work/Estimates/` — 生成新的测算记录卡，或在现有卡上追加新版本
- `decisions.md` — 新增决策记录

### 写入业务数据时的特殊规则
- 生成合同摘录卡或测算记录卡时，在文件顶部 YAML 中加 `confirmed: false`
- 我确认后会改为 `confirmed: true`
- **绝不修改已有的、confirmed: true 的内容**
- 测算记录卡只追加新版本（v2、v3…），不改已有版本

### 绝不能碰（但是可以提交 commit）
- `context.md` — 我自己维护
- `Work/SOPs/` 下的所有文件 — 我自己维护
- `Work/inbox.md` — 我自己记录
- `Memory/` 下的所有文件 — 我的个人空间
- `Projects/_index.md` — 我自己维护

## 代码规范

- Python 为主要语言
- 代码注释用中文
- commit message 用中文
- 遇到不确定的业务逻辑，先问我，不要猜
- 所有 Bitable 字段名和类型从 schema/schema.yaml 读取，不在代码里硬编码

## 模块化原则

从第一天起，代码按职责分层，三层不混写：

```
tradehub/
├── feishu/       ← 平台层：飞书 Bot、Bitable API 的调用封装
├── core/         ← 业务层：磅单解析、字段校验、计价规则等纯业务逻辑
├── ai/           ← AI 层：OCR、模型调用、prompt 管理
└── main.py       ← 入口：只做组装和调度，不写具体逻辑
```

**核心规则：core/ 里的代码不允许 import feishu/ 或 ai/ 的任何内容。**

这意味着业务逻辑是独立的——它不知道自己跑在飞书上，也不知道背后是哪个模型。将来换平台或换模型，只改对应的层，业务逻辑不动。

**不需要现在做的事：** 不需要写抽象基类、接口层、适配器模式。保持简单，每个文件职责清晰就够了。可移植性留到有第二个部署目标时再做。

## Git 规则

### 代码仓库（~/dev/tradehub/）
- 每次验证通过后 commit
- commit message 用中文
- 里程碑完成时打 tag（如 v0.1-里程碑0）
- .env 和敏感信息不提交（通过 .gitignore 排除）

### Obsidian vault（~/workspace/zen/）
- 里程碑验证通过后，帮我提交 vault 的变更
- commit message 用中文，格式与代码仓库一致
- 只 commit，不 push（远程仓库由我自己管理）
- .obsidian/ 目录不提交（通过 .gitignore 排除）

## 工作流程

每个任务遵循以下循环：

```
Zhang 给出任务
    ↓
你写代码（读 Obsidian → 生成代码 → Zhang 审阅）
    ↓
你回写 Obsidian（status.md / log.md / 草稿文件）给 zhang 建议他需要修改的部分。
    ↓
Zhang 验证结果（你不能替他做这一步）
    ↓
验证通过 → 你执行 git commit（代码仓库 + Obsidian vault）
```

发现新的技术经验时，主动告诉 Zhang 应该写到哪个文件，列出你能写的和需要他改的。
