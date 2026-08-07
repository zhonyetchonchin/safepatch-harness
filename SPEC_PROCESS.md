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

## 2026-08-08 冷启动验证第一轮

执行方式：创建新的 Codex task `019fdd1d-c115-7f43-bf92-e3d666d6f847`，在独立 worktree 中运行，要求只阅读 `SPEC.md` 和 `PLAN.md`，选择 T20 / T21，遇到不确定立即暂停。

结果：冷启动 agent 暂停，未写实现代码，未运行测试。

暴露的问题：

- `RunState` 未明确是枚举、状态快照还是状态机。
- 合法 run 状态集合和状态转换表缺失。
- Action schema 缺少字段级契约，不清楚是 discriminated union 还是宽松 payload。
- `ToolResult`、`Event` 字段、默认值和必填性不明确。
- Provider 边界不明确：返回原始 JSON 文本还是已验证 Action。
- MockLLM 队列耗尽时的错误类型和稳定信息未定义。
- PLAN 要求 T20/T21 冷启动实现，但 T20 依赖 T10，且正式实现门禁写得容易误读。

修订决策：

- 在 `SPEC.md` 增加“核心类型契约”章节。
- 明确 Action 使用 `type` discriminated union，不使用松散 payload 袋。
- 明确 Provider 返回原始 `LLMResponse.content`，解析属于 loop。
- 明确 `ProviderExhaustedError("mock llm script exhausted")`。
- 在 `PLAN.md` 明确冷启动实现只在独立 worktree 中作为验证证据，不直接合并。
- 细化 T20 / T21 的失败测试。

## 2026-08-08 冷启动验证第二轮

执行方式：创建新的 Codex task `019fdd20-3da9-7991-a712-826ebe5f680e`，在独立 worktree 中运行，仍要求只读 `SPEC.md` 和 `PLAN.md`。

结果：冷启动 agent 再次暂停，未写实现代码，未运行测试。总体目标和架构已清楚，但公共 API 级别仍有歧义。

暴露的问题：

- `RunState` 虽称为状态快照，但字段未定义。
- 未规定 Pydantic model 是否拒绝额外字段。
- 未规定下游统一使用什么公开入口解析 Action。
- T20/T21 依赖 T10，但冷启动任务未明确是否可临时创建最小包骨架。

修订决策：

- 明确 `RunState` 是 Pydantic 快照，字段为 `run_id`、`status`、`step`、`pending_action_id`、`updated_at`。
- 明确 `transition_run_state()` 签名和非法转换错误信息。
- 明确所有公开 Pydantic model 使用 `extra="forbid"`。
- 明确 `parse_action()` 是唯一公开 action 解析入口。
- 明确 `safepatch.core.models` 和 `safepatch.core.provider` 的公开导入符号。
- 明确冷启动 worktree 可以临时创建最小 T10 骨架，但不直接合并。

## 2026-08-08 冷启动验证第三轮

执行方式：创建新的 Codex task `019fdd22-95c2-7e51-a24b-2809e8f035b0`，在独立 worktree 中运行，仍要求只读 `SPEC.md` 和 `PLAN.md`。

结果：冷启动 agent 第三次暂停，未写实现代码，未运行测试。剩余问题集中在可测试的边界细节。

暴露的问题：

- 未固定 Pydantic 主版本。
- `run_check.name` 的 allowlist 校验归属不明确。
- 时间戳默认值、状态转换是否更新时间、step 是否递增未定义。
- `pending_action_id` 在非审批转换中传入时的行为未定义。
- `Event.id` 是否验证 UUID 未定义。
- 空白字符串是否视为非法未定义。
- `MockLLM` 构造函数、默认 provider name、metadata、FIFO 和异常消费行为未定义。
- `SPEC.md` 与 `PLAN.md` 的 T20 公开符号列表不完全一致。

修订决策：

- 固定 Pydantic v2：`pydantic>=2.7,<3`。
- 明确 action schema 只校验 `run_check.name` 非空，allowlist 属于 policy/config 层。
- 明确时间戳默认当前 UTC；`transition_run_state()` 接受可注入 `now`。
- 明确 `transition_run_state()` 不递增 step。
- 明确非审批目标传入 `pending_action_id` 抛出固定 `ValueError`。
- 明确 Event id 使用可解析 UUID 字符串，默认 UUID4。
- 明确公开 model 必填字符串拒绝空白。
- 明确 `MockLLM(script, provider_name="mock")` 的 FIFO、metadata 和异常消费行为。

## 2026-08-08 冷启动验证第四轮

执行方式：创建新的 Codex task `019fdd25-ae24-7ee3-9e8c-3321855c7147`，在独立 worktree 中运行，仍要求只读 `SPEC.md` 和 `PLAN.md`。

结果：冷启动 agent 第四次暂停，未写实现代码，未运行测试。剩余问题仅集中在 `LLMResponse.content` 是否允许空字符串。

暴露的问题：

- `SPEC.md` 一方面要求公开 model 必填字符串拒绝空白，另一方面 `MockLLM` 需要返回原始模型文本。若脚本元素为空字符串，应该原样返回以测试 parser 失败，还是在 provider 层失败，未明确。

修订决策：

- 明确 `LLMResponse.content` 是唯一允许为空或纯空白的公开字符串字段。
- 明确 `MockLLM` 字符串脚本元素原样返回，包括空字符串和纯空白字符串。
- `parse_action()` 负责把空响应转为解析失败。

## 2026-08-08 冷启动验证第五轮

执行方式：创建新的 Codex task `019fdd28-3258-71b1-adee-7987883aab82`，在独立 worktree 中运行，仍要求只读 `SPEC.md` 和 `PLAN.md`。

结果：冷启动 agent 判断项目目标、整体架构和 T20/T21 主要契约已经足够清晰，但在进入 TDD 前暂停。

暴露的问题：

- `ToolResult.started_at` / `finished_at` 写为 `datetime | None` 但未明确是否可省略。
- `RunState` 的审批不变量是否在模型构造时校验未定义。
- `transition_run_state(now=...)` 对 naive / 非 UTC datetime 的处理未定义。
- 冷启动 agent 将 Superpowers brainstorming 的设计批准门槛理解为仍需额外批准。

修订决策：

- 明确 `ToolResult.started_at` / `finished_at` 默认 `None`，可省略。
- 明确 `RunState` 构造时也校验审批不变量。
- 明确 `now` 必须 timezone-aware，naive 抛出固定 `ValueError`，非 UTC 统一转换为 UTC。
- 在 `PLAN.md` T03 中明确用户已授权继续，冷启动 agent 可进入 TDD 红灯测试，不需要访问或重写 `docs/superpowers`。

## 2026-08-08 冷启动验证第六轮

执行方式：创建新的 Codex task `019fdd2a-d6b8-7fe1-9e63-896b2b98ce1f`，在独立 worktree `C:\Users\钟\.codex\worktrees\2f9f\engi` 中运行，仍要求只读 `SPEC.md` 和 `PLAN.md`，允许临时创建最小 T10 骨架。

结果：通过。冷启动 agent 未遇到阻断歧义，完成临时 T20 / T21 TDD 实现，未提交改动，未读取或修改受禁止文档。

TDD 证据：

- 红灯：运行 `.\.venv\Scripts\python.exe -m pytest tests\core\test_models.py tests\core\test_provider.py`，结果为 `collected 0 items / 2 errors`，分别缺少 `safepatch.core.models` 和 `safepatch.core.provider`。
- 绿灯：实现最小 T20 / T21 后，`tests/core/test_models.py` 为 `29 passed in 0.16s`，`tests/core/test_provider.py` 为 `16 passed in 0.16s`。
- 合并验证：`45 passed in 0.36s`。

实际临时改动：

- `pyproject.toml`
- `src/safepatch/__init__.py`
- `src/safepatch/core/__init__.py`
- `src/safepatch/core/models.py`
- `src/safepatch/core/provider.py`
- `tests/core/test_models.py`
- `tests/core/test_provider.py`
- 本地 `.venv`

仍建议正式实现时补强：

- 明确 Python 3.12 是精确验证版本还是最低版本。
- 明确 `list_files.glob`、`search_text.glob` 等可选字符串显式传入空白时是否拒绝。
- 明确显式传入的 `RunState.updated_at`、`Event.created_at`、`ToolResult` 时间是否必须 timezone-aware。
- 在 T03 中补充最小骨架建议测试环境命令。

主开发判断：`SPEC.md` / `PLAN.md` 已经足以支持正式实现 T10 / T20 / T21。

## Superpowers 工具状态

当前会话可用 Superpowers skill 只有 `superpowers:brainstorming`。重新工具发现后仍未暴露 `writing-plans`、`test-driven-development`、`requesting-code-review` 等技能。后续实现会按这些流程要求手动执行并记录，但不能声称完成了未暴露 skill 的实际调用。

## 2026-08-08 最终交付检查

实现范围：

- T10-T11：Python 包、测试骨架、FastAPI/WebUI 静态骨架。
- T20-T23：核心 action schema、provider port、agent loop、预算停机。
- T30-T33：安全文件工具、原子 patch、受控检查命令、反馈构建器。
- T40-T43：policy engine、路径围栏、审批状态机、HITL loop 集成。
- T50-T53：SQLite store、配置加载、加密 vault、secret redaction。
- T60-T64：Run API、Approval API、Credential API、WebUI 工作台、机制演示。
- T70-T72：Docker demo runtime、GitLab CI、README。
- T73：最终交付文档与反思占位。

最终验证：

- `.\.venv\Scripts\python.exe -m pytest -q`：`88 passed, 1 skipped`。
- `.\.venv\Scripts\python.exe -m safepatch.demo`：3 个 deterministic mock 场景均 `passed: true`。
- `.\.venv\Scripts\python.exe -m safepatch --help`：CLI 可加载。
- `.\.venv\Scripts\python.exe -m pip wheel . -w .\.safepatch-wheel-check`：wheel 构建成功。

已知限制与偏离：

- Superpowers 当前只暴露 `superpowers:brainstorming`；`writing-plans`、`test-driven-development`、`requesting-code-review` 未暴露。实现阶段按同等流程手工执行并在 `AGENT_LOG.md` 逐项记录红灯、绿灯、回归和人工决策。
- Docker CLI 存在，但 Docker Desktop daemon 未运行；`docker build -t safepatch .` 失败为无法连接 `dockerDesktopLinuxEngine`，因此未执行 `docker run`。
- 当前未 push 到 GitLab 远端，`.gitlab-ci.yml` 只完成本地 contract 测试，未验证远端 pipeline。
- Windows 环境下 symlink escape 测试因权限 / 平台限制跳过；路径围栏实现使用 `Path.resolve()` + `relative_to(root)`，支持 symlink 的 CI/Linux 环境会执行该测试。
- `REFLECTION.md` 是占位说明，真实课程反思应由学生本人完成。
