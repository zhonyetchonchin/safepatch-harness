# SafePatch Harness PLAN

状态说明：`[ ]` 未开始，`[~]` 进行中，`[x]` 完成。每个实现 task 必须先写失败测试，再写最小实现，再重构。正式 harness 源码实现必须等 SPEC / PLAN 和冷启动验证完成后开始。

## 0. 流程基线

- [x] T00 初始化仓库与安全忽略规则
  - 目标：建立 Git 仓库和防泄漏 `.gitignore`。
  - 文件：`.gitignore`。
  - 验证：`git status --short` 不显示 `.env`、数据库、日志、依赖目录。
  - commit：`7b7f413`。

- [x] T01 产出 SPEC / PLAN / 过程文档初稿
  - 目标：完成实现前规约。
  - 文件：`SPEC.md`、`PLAN.md`、`SPEC_PROCESS.md`、`AGENT_LOG.md`。
  - 验证：检查 SPEC 覆盖问题、故事、模块、架构、安全、凭据、分发、机制设计；PLAN 每个 task 有验证步骤。
  - commit：`7b7f413`。

- [~] T02 Superpowers 安装与流程确认
  - 目标：安装并启用 Superpowers，确认 brainstorming、writing-plans、test-driven-development 等技能可用。
  - 文件：`SPEC_PROCESS.md`、`AGENT_LOG.md`。
  - 验证：记录插件 / skill 调用证据；若偏离，写明原因和补救。
  - 依赖：用户安装或授权 Superpowers 插件。

- [x] T03 冷启动验证
  - 目标：用不同类型 agent 的新会话，仅凭 `SPEC.md` + `PLAN.md` 尝试 1-2 个 task。
  - 文件：`docs/COLD_START_PROMPT.md`、`SPEC_PROCESS.md`，必要时修订 `SPEC.md`、`PLAN.md`。
  - 验证：记录暂停问题、误解、修订前后 diff；第六轮冷启动临时实现 T20/T21，合并验证 `45 passed in 0.36s`。
  - 依赖：T01、T02。
  - 说明：冷启动 agent 可在独立 worktree 中做临时 T20/T21 实现尝试，包括最小 T10 骨架：`pyproject.toml`、`src/safepatch/__init__.py`、`src/safepatch/core/__init__.py`、`tests/core/`。这些改动只作为验证证据，不直接合并为正式实现。若遇到歧义必须暂停，主开发会修订 SPEC / PLAN 后重新验证。
  - 设计批准：用户已在主会话授权“接着做”，且 `SPEC.md`、`PLAN.md` 与 Superpowers design doc 已提交；冷启动验证 agent 可以进入 TDD 红灯测试，不需要另写或访问 `docs/superpowers`。
  - commit：`50465e3`。

## 1. 项目骨架

- [x] T10 Python 包与测试骨架
  - 目标：创建 `safepatch` 包、pytest、Makefile、基础配置。
  - 文件：`pyproject.toml`、`Makefile`、`scripts/test.ps1`、`src/safepatch/__init__.py`、`tests/`。
  - 依赖约束：`pyproject.toml` 使用 Pydantic v2，约束 `pydantic>=2.7,<3`。
  - 失败测试：导入 `safepatch` 并断言版本存在，初始因包不存在失败：`ModuleNotFoundError: No module named 'safepatch'`。
  - 验证：`.\scripts\test.ps1` 通过，`1 passed`。本机无 `make`，保留 `Makefile` 给 CI/Linux。
  - 依赖：T03。
  - commit：`050c781`。

- [ ] T11 API / WebUI 骨架
  - 目标：FastAPI app 可启动并服务静态 WebUI。
  - 文件：`src/safepatch/api/app.py`、`src/safepatch/web/`、`tests/api/test_health.py`。
  - 失败测试：`GET /health` 期望 200，初始失败。
  - 验证：`pytest tests/api/test_health.py`。
  - 依赖：T10。

## 2. 核心 Loop 与 Provider

- [x] T20 定义 action / result / state schema
  - 目标：用 Pydantic 定义 Action、ToolResult、RunState、Event。
  - 文件：`src/safepatch/core/models.py`、`tests/core/test_models.py`。
  - 公开 API：从 `safepatch.core.models` 导入 `parse_action`、`AgentAction`、`ReadFileAction`、`ListFilesAction`、`SearchTextAction`、`ApplyPatchAction`、`RunCheckAction`、`RememberAction`、`FinishAction`、`ActionParseError`、`RunStatus`、`RunState`、`InvalidStateTransition`、`transition_run_state`、`ToolResult`、`ResultCategory`、`Event`、`EventType`。
  - 失败测试：未知 action type 通过 `parse_action()` 抛出 `ActionParseError`；额外字段因 `extra="forbid"` 失败；缺少 `read_file.path` 失败；空白字符串字段失败；`completed -> running` 抛出 `InvalidStateTransition` 且消息包含 `invalid run status transition: completed -> running`；`running -> paused_for_approval` 需要非空 `pending_action_id` 并返回新 `RunState`；直接构造 `RunState(status="paused_for_approval")` 且无 `pending_action_id` 失败；非审批状态带 `pending_action_id` 失败；非审批目标传入 `pending_action_id` 抛出固定 `ValueError`；`transition_run_state()` 不递增 step；`transition_run_state(now=<naive datetime>)` 抛出固定 `ValueError`；`Event.sequence=0` 失败；`Event.id` 可被 `uuid.UUID()` 解析；`ToolResult.started_at` / `finished_at` 可省略且默认为 `None`；合法 `run_check` action 可解析但不校验 allowlist。红灯为缺少 `safepatch.core`。
  - 验证：`pytest tests/core/test_models.py` 通过，`14 passed`；全量 `.\scripts\test.ps1` 通过，`15 passed`。
  - 依赖：T10。
  - commit：`74da2e6`。

- [x] T21 Mock LLM 与 provider port
  - 目标：实现可注入 provider 抽象和脚本化 MockLLM。
  - 文件：`src/safepatch/core/provider.py`、`tests/core/test_provider.py`。
  - 公开 API：从 `safepatch.core.provider` 导入 `LLMMessage`、`LLMRequest`、`LLMResponse`、`LLMProvider`、`MockLLM`、`ProviderExhaustedError`。
  - 失败测试：`MockLLM.complete()` 返回 `LLMResponse.content` 原始字符串而不是 Action；空字符串和纯空白脚本元素也原样返回；默认 `provider_name` 为 `mock`；`metadata.mock_index` 从 0 递增；队列为空时抛出 `ProviderExhaustedError("mock llm script exhausted")`；预设异常先被消费再原样抛出；异常后的下一次调用读取后续脚本元素；`LLMRequest.messages` 为空时 schema validation error；provider models 的额外字段因 `extra="forbid"` 失败。红灯为缺少 `safepatch.core.provider`。
  - 验证：`pytest tests/core/test_provider.py` 通过，`7 passed`；全量 `.\scripts\test.ps1` 通过，`22 passed`。
  - 依赖：T20。
  - commit：`ef6b691`。

- [x] T22 Agent 主循环最小闭环
  - 目标：实现 context -> provider -> parse -> policy -> dispatch -> feedback -> stop。
  - 文件：`src/safepatch/core/loop.py`、`tests/core/test_loop.py`。
  - 失败测试：mock LLM 输出 `finish` 时 run 结束；非法 JSON 不执行工具。红灯为缺少 `safepatch.core.loop`。
  - 验证：`pytest tests/core/test_loop.py` 通过，`2 passed`；全量 `.\scripts\test.ps1` 通过，`24 passed`。
  - 依赖：T20、T21。
  - commit：`7de1d97`。

- [x] T23 停机预算
  - 目标：实现 step、时间、连续失败次数预算。
  - 文件：`src/safepatch/core/budget.py`、`tests/core/test_budget.py`。
  - 失败测试：超过 step budget 后不再调用 provider；时间预算和连续失败预算达到阈值时停止。红灯为缺少 `safepatch.core.budget`，loop 集成红灯为 `AgentLoop.__init__()` 不接受 `budget`。
  - 验证：`pytest tests/core/test_budget.py` 通过，`4 passed`；`pytest tests/core/test_loop.py` 通过，`3 passed`；全量 `.\scripts\test.ps1` 通过，`29 passed`。
  - 依赖：T22。
  - commit：`a038b94`。

## 3. 工具与反馈

- [x] T30 安全文件读取 / 列表 / 搜索
  - 目标：实现 workspace 内文件工具。
  - 文件：`src/safepatch/tools/files.py`、`tests/tools/test_files.py`。
  - 失败测试：`../`、绝对路径逃逸、敏感路径读取被拒绝；列表忽略 denied 目录；搜索返回匹配行。红灯为缺少 `safepatch.tools`。
  - 验证：`pytest tests/tools/test_files.py` 通过，`6 passed`；全量 `.\scripts\test.ps1` 通过，`35 passed`。
  - 依赖：T20。
  - commit：待提交。

- [ ] T31 原子 patch 工具
  - 目标：实现上下文校验 patch；失败时不写入。
  - 文件：`src/safepatch/tools/patch.py`、`tests/tools/test_patch.py`。
  - 失败测试：上下文不匹配时文件内容不变。
  - 验证：`pytest tests/tools/test_patch.py`。
  - 依赖：T30。

- [ ] T32 受控检查命令
  - 目标：只运行配置 allowlist 中的检查命令。
  - 文件：`src/safepatch/tools/checks.py`、`tests/tools/test_checks.py`。
  - 失败测试：非 allowlist 命令不执行；超时返回 timeout。
  - 验证：`pytest tests/tools/test_checks.py`。
  - 依赖：T20。

- [ ] T33 反馈构建器
  - 目标：把工具结果、检查失败、策略拒绝转为下一轮上下文。
  - 文件：`src/safepatch/core/feedback.py`、`tests/core/test_feedback.py`。
  - 失败测试：测试失败摘要必须出现在下一轮 prompt/context。
  - 验证：`pytest tests/core/test_feedback.py`。
  - 依赖：T22、T32。

## 4. 治理与 HITL 主贡献

- [ ] T40 Policy engine 基础规则
  - 目标：实现 allow / requires_approval / deny 三态决策。
  - 文件：`src/safepatch/policy/engine.py`、`tests/policy/test_engine.py`。
  - 失败测试：危险命令 deny，依赖锁文件修改 requires_approval。
  - 验证：`pytest tests/policy/test_engine.py`。
  - 依赖：T20、T30。

- [ ] T41 路径和符号链接围栏
  - 目标：统一 resolve path，拒绝 symlink escape。
  - 文件：`src/safepatch/policy/paths.py`、`tests/policy/test_paths.py`。
  - 失败测试：仓库内 symlink 指向仓库外时读取被拒绝。
  - 验证：`pytest tests/policy/test_paths.py`。
  - 依赖：T30。

- [ ] T42 审批状态机
  - 目标：实现 pending / approved / rejected / expired 和一次性 action 授权。
  - 文件：`src/safepatch/policy/approval.py`、`tests/policy/test_approval.py`。
  - 失败测试：同一 approval 不能执行两次；reject 反馈进入下一轮。
  - 验证：`pytest tests/policy/test_approval.py`。
  - 依赖：T40。

- [ ] T43 loop 与 HITL 集成
  - 目标：requires_approval 时 run 暂停，approve 后继续执行原 action。
  - 文件：`src/safepatch/core/loop.py`、`tests/core/test_hitl_loop.py`。
  - 失败测试：暂停状态下不调用下一轮 provider。
  - 验证：`pytest tests/core/test_hitl_loop.py`。
  - 依赖：T22、T42。

## 5. 记忆、配置、凭据

- [ ] T50 SQLite event / memory store
  - 目标：持久化 runs、events、memories。
  - 文件：`src/safepatch/store/sqlite.py`、`tests/store/test_sqlite.py`。
  - 失败测试：event sequence 递增；memory 可按 tag 检索。
  - 验证：`pytest tests/store/test_sqlite.py`。
  - 依赖：T20。

- [ ] T51 配置加载与安全默认值
  - 目标：读取 `safepatch.yml`，缺省时采用安全配置。
  - 文件：`src/safepatch/config.py`、`tests/test_config.py`。
  - 失败测试：未知检查命令默认不可运行。
  - 验证：`pytest tests/test_config.py`。
  - 依赖：T20。

- [ ] T52 加密凭据 vault
  - 目标：实现 key set/status/update/delete/lock，状态不回显明文。
  - 文件：`src/safepatch/security/vault.py`、`tests/security/test_vault.py`。
  - 失败测试：API 响应和日志不包含 key；错误主密码不能解密。
  - 验证：`pytest tests/security/test_vault.py`。
  - 依赖：T10。

- [ ] T53 secret redaction
  - 目标：日志、事件 payload、错误输出统一脱敏。
  - 文件：`src/safepatch/security/redaction.py`、`tests/security/test_redaction.py`。
  - 失败测试：类似 `sk-...` 的值写入事件前被替换。
  - 验证：`pytest tests/security/test_redaction.py`。
  - 依赖：T50。

## 6. API / WebUI / Demo

- [ ] T60 Run API
  - 目标：创建、查询、取消 run，获取事件。
  - 文件：`src/safepatch/api/routes_runs.py`、`tests/api/test_runs.py`。
  - 失败测试：创建 run 后可查询状态。
  - 验证：`pytest tests/api/test_runs.py`。
  - 依赖：T22、T50。

- [ ] T61 Approval API
  - 目标：批准 / 拒绝待审批动作。
  - 文件：`src/safepatch/api/routes_approval.py`、`tests/api/test_approval_routes.py`。
  - 失败测试：重复 approve 返回冲突，不重复执行动作。
  - 验证：`pytest tests/api/test_approval_routes.py`。
  - 依赖：T43、T50。

- [ ] T62 Credential API
  - 目标：WebUI 可设置、更新、清除 key；状态不回显。
  - 文件：`src/safepatch/api/routes_credentials.py`、`tests/api/test_credentials.py`。
  - 失败测试：status 响应不包含明文 key。
  - 验证：`pytest tests/api/test_credentials.py`。
  - 依赖：T52。

- [ ] T63 WebUI 工作台
  - 目标：实现 run 列表、时间线、审批面板、检查结果、diff 视图。
  - 文件：`src/safepatch/web/index.html`、`src/safepatch/web/app.js`、`src/safepatch/web/styles.css`。
  - 失败测试：API contract 测试；手工浏览器验证页面可操作。
  - 验证：`pytest tests/api`；本地打开 `http://127.0.0.1:8000`。
  - 依赖：T60、T61、T62。

- [ ] T64 机制演示
  - 目标：mock LLM 下确定性复现危险动作拦截、失败反馈改动作、HITL 暂停。
  - 文件：`demo/mock_scenarios.py`、`tests/demo/test_mechanism_demo.py`。
  - 失败测试：三类演示断言都失败后实现。
  - 验证：`python -m safepatch.demo` 或 `pytest tests/demo/test_mechanism_demo.py`。
  - 依赖：T43、T33。

## 7. 分发、CI、文档

- [ ] T70 Dockerfile
  - 目标：构建可运行 WebUI 的容器，默认 demo mode。
  - 文件：`Dockerfile`、`.dockerignore`。
  - 失败测试：容器内 `python -m safepatch --demo` 可启动。
  - 验证：`docker build -t safepatch .`，`docker run -p 8000:8000 safepatch`。
  - 依赖：T63、T64。

- [ ] T71 GitLab CI
  - 目标：配置 `.gitlab-ci.yml`，包含名为 `unit-test` 的 job。
  - 文件：`.gitlab-ci.yml`。
  - 失败测试：CI lint / 本地模拟前 job 缺失。
  - 验证：push 后最后一次 CI pass。
  - 依赖：T10。

- [ ] T72 README
  - 目标：写明简介、安装、运行、key 配置、目录结构、安全边界、部署。
  - 文件：`README.md`。
  - 验证：按 README 在干净环境启动 demo。
  - 依赖：T70。

- [ ] T73 最终交付检查
  - 目标：补全 commit hash、AGENT_LOG、SPEC_PROCESS、REFLECTION 占位说明。
  - 文件：`PLAN.md`、`AGENT_LOG.md`、`SPEC_PROCESS.md`、`REFLECTION.md`。
  - 验证：交付清单逐项通过；真实反思由学生本人完成。
  - 依赖：全部实现 task。

## 并行策略

T20-T23 是核心依赖链，必须先完成。T30-T33 可与 T40-T42 在不同 worktree 中并行，但合并前要通过 loop 集成测试。T50-T53 可在核心 schema 稳定后并行。T60-T63 依赖核心和存储，最后与 T70-T72 收口。

## Worktree / PR 规划

- `feature/core-loop`：T20-T23。
- `feature/tools-feedback`：T30-T33。
- `feature/policy-hitl`：T40-T43。
- `feature/store-security`：T50-T53。
- `feature/api-web`：T60-T64。
- `feature/distribution-ci-docs`：T70-T73。

每个 worktree / PR 完成后，先做 SPEC 合规检查，再做代码质量检查；Critical issue 修复后才能合并。
