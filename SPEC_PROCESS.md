# SPEC_PROCESS

## 2026-08-08 初始流程记录

当前项目选择 Project A：Coding Agent Harness。已阅读并拼接以下要求文件：

- `要求.md`
- `AI4SE_Final_Project_A_Coding_Agent_Harness.md`
- `AI4SE_Final_Project_B_应用类项目.md` 仅作对比，最终不选 B。

关键设计决策：

1. 选择做 `SafePatch Harness`：一个本地 coding agent harness，而不是普通应用。
2. 主贡献维度选择“治理护栏 + HITL 状态机”，因为该维度可以完全用确定性代码和 mock LLM 测试验证。
3. 采用 mock LLM 作为一等 provider，保证无网络、无 API key 时也能测试核心机制。
4. 公网部署只提供 demo mode，不允许执行用户任意仓库命令，避免 WebUI 成为远程代码执行入口。
5. 技术栈暂定 Python 3.12 + FastAPI + SQLite + pytest + Docker，前端使用轻量 WebUI。

## Brainstorming 关键节点

本轮由主开发会话根据课程文档生成初始 brainstorm。当前 Codex 会话没有暴露可调用的 Superpowers 插件能力，因此这一步需要在安装 Superpowers 后补充正式技能调用证据。

已确认的问题：

- 项目必须自己实现 agent loop，不能使用高层 agent 框架。
- 机制必须能在移除真实 LLM 后用 mock/stub 确定性验证。
- SPEC / PLAN / 冷启动验证完成前禁止写 harness 实现代码。
- 凭据安全和 Docker 分发不是附加项，而是验收条件。
- CI 最终必须提供 `.gitlab-ci.yml`，且包含 `unit-test` job。

## 三轮关键迭代记录

### 迭代 1：项目边界

初始想法：做一个“能自动修代码的 agent”。

修订：限定为小规模本地修复任务，不做自动 push、自动部署、任意 shell 或大型重构。原因是课程强调 harness 机制深度，过宽范围会牺牲治理、反馈和测试确定性。

### 迭代 2：主贡献维度

初始想法：六个维度均衡实现。

修订：六个维度都做最小闭环，但把治理和 HITL 做深。原因是路径围栏、命令 allowlist、审批状态机、一次性授权、暂停恢复都能用代码和 mock LLM 验证，评分证据更清晰。

### 迭代 3：部署形态

初始想法：公网部署完整服务。

修订：公网部署只开放 demo mode，真实仓库执行仅限本地 Docker。原因是 Web 服务执行用户命令存在高风险，不应在公开地址暴露任意代码执行能力。

## AI 建议与人工决策

采纳：

- 将 governance/HITL 设为 main contribution。
- 将 mock LLM 作为核心测试入口，而不是只做真实 provider。
- 将 feedback builder 明确为代码机制。
- 将 WebUI 做成工作台而不是 landing page。

修正：

- 不做多 agent runtime，因为 Project A 的重点是 coding harness 内核，不是复刻开发工具的 subagent 系统。
- 不做自动 git push / PR，因为安全风险和范围过大。
- 不让部署版执行用户命令，只提供 demo mode。

## 冷启动验证计划

正式实现前需要用另一类 agent 的全新会话执行：

1. 只提供 `SPEC.md` 和 `PLAN.md`。
2. 要求其选择 T20 和 T21，遇到不确定立即暂停。
3. 记录其问题、误读、实现差距。
4. 根据反馈修订 SPEC / PLAN，并在本文件写入关键 diff。

当前状态：未完成。阻塞原因是需要不同类型 agent 与 Superpowers 流程证据。未完成前不得进入 harness 源码实现。

## 对 Superpowers 流程的当前偏离

课程要求必须安装并调用 Superpowers。当前 Codex 环境显示 Superpowers 是可推荐但未安装的插件，且没有可调用 skill。因此本次先完成本地文档化规约，后续必须补齐：

- Superpowers 安装记录。
- brainstorming / writing-plans 技能调用记录。
- 冷启动验证证据。
- 若流程有偏离，在 `AGENT_LOG.md` 中解释偏离原因和补救。

## 2026-08-08 Superpowers 安装状态更新

已向用户发起 Superpowers 插件安装建议，用户已确认安装。安装后重新执行工具发现，当前会话仍未暴露 `brainstorming`、`writing-plans`、`test-driven-development` 等 Superpowers 技能入口。

处理决策：

- 不声称已经完成 Superpowers 技能调用。
- T02 标记为进行中，而不是完成。
- 准备 `docs/COLD_START_PROMPT.md`，用于后续不同 agent 类型冷启动验证。
- 在未完成 T03 前，不进入 harness 源码实现。

## 2026-08-08 Superpowers brainstorming 补充记录

Superpowers 安装后，当前会话暴露了 `superpowers:brainstorming` skill。已读取该 skill 的完整说明，并按其硬门槛处理：

- 不进入 harness 源码实现。
- 先复核项目文件、要求文档和提交历史。
- 将既有设计沉淀到 `docs/superpowers/specs/2026-08-08-safepatch-harness-design.md`。
- 后续必须完成冷启动验证，再进入 `PLAN.md` 的实现任务。

本轮没有使用 Visual Companion，因为当前问题是规约和流程文本，不涉及需要视觉比较的 UI / 架构选项。

自检结果：已扫描 Superpowers design doc，未发现 TODO/TBD/placeholder；设计与 `SPEC.md` 的关键约束一致，包括自研 loop、mock LLM、HITL、Docker 分发和 `unit-test` CI。
