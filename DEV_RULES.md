# TradeHub 开发规范

## 代码规范

- Python 为主语言，注释用中文
- Bitable 字段名和类型从 `schema/schema.yaml` 读取，不硬编码

## 开发循环（你独立完成，不等 Zhang）
```
接到子任务
  → Inspect：确认 API/SDK 方法签名
  → Standalone Test：写独立脚本验证，必须能独立运行并打印结果
  → Assert Pass：测试通过
  → Integrate：写入主流程
  → Auto Verify：用 fixture 跑集成测试
  → 全部通过 → 进入下一个子任务
```

**判断标准：如果你需要让 Zhang 手动操作来验证某个功能是否正确，说明你跳过了 Standalone Test。退回去补。**

## ⚠️ Inspect → Test → Integrate（不可跳过任何一步）

| 步骤 | 做什么 | 完成标志 | 没完成则 |
|------|--------|----------|----------|
| Inspect | `inspect_sdk.py` / grep 源码 / 查文档，确认方法签名和参数名 | 终端输出了参数列表 | 禁止写调用代码 |
| Standalone Test | 在 `tests/` 下写独立脚本，用真实或 mock 数据调用 | 脚本独立运行，打印成功结果 | 禁止集成到主流程 |
| Integrate | 将验证通过的调用写入主流程 | 自动化测试通过 | 禁止 commit |

**禁止凭记忆写任何 SDK/API 调用。** "我记得参数是 xxx" ≠ 确认。只有当前会话中的 inspect 输出才算确认。

飞书 SDK 专用：
```bash
python scripts/inspect_sdk.py im.v1
```

## ⚠️ 失败熔断
```
第 1 次失败：读错误信息 → 回到 Inspect 确认假设 → 修复 → 重跑
第 2 次失败：检查前置条件（权限、字段类型、请求格式）→ 修复 → 重跑
第 3 次失败：停下来。输出诊断报告：
            - 已确认的事实
            - 仍不确定的假设
            - 建议排查方向
            等 Zhang 指令，不继续猜。
```

**禁止：**
- 连续盲试超过 3 次
- 在集成环境中调试 API 参数（应在独立脚本中）
- 失败后只改代码不重新 inspect

## 自动化验证

### 原则

开发过程中的功能验证不依赖人工触发。Zhang 的手动验证只用于里程碑验收。

### Test Fixtures
```
tests/
├── fixtures/
│   ├── webhook_payloads/   ← webhook JSON（脱敏）
│   ├── sample_images/      ← 测试用图片
│   └── mock_responses/     ← API 返回值 mock
├── test_api_*.py           ← 独立 API 验证脚本
└── test_integration.py     ← 端到端集成测试
```

每次调试通过新场景后，将真实请求/响应脱敏保存为 fixture。

### 常见替代方案

| 依赖人的做法 | 应该的做法 |
|-------------|-----------|
| 让 Zhang 手动触发来验证 | 用 fixture + 脚本自动触发 |
| 让 Zhang 看系统确认数据 | 脚本写入后立即读取，assert 匹配 |
| 让 Zhang 确认 UI 渲染 | 脚本验证发送成功，渲染留给里程碑验收 |

## 反模式清单（遇到时立即停下来纠正）

1. **"让 Zhang 试一下"** → 用 fixture 自己测
2. **"我记得参数是..."** → 先 inspect
3. **"改了一行，重启看看"** → 独立脚本验证
4. **"第 4 次修同一个问题"** → 停，输出诊断报告
5. **"这个简单，不用测试"** → 正是这种想法导致 30 分钟浪费