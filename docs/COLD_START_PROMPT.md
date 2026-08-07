# Cold Start Validation Prompt

Use this prompt in a fresh session with a different agent type from the main development agent. Do not provide prior conversation history, hidden assumptions, or extra oral explanation.

```text
你是一个全新的 coding agent。请只阅读当前仓库中的 SPEC.md 和 PLAN.md，不要读取 AGENT_LOG.md、SPEC_PROCESS.md 或任何之前的对话记录。

任务：
1. 根据 SPEC.md 和 PLAN.md 判断项目目标与架构是否足够清晰。
2. 从 PLAN.md 中选择 T20 和 T21 两个任务进行冷启动实现尝试。
3. 如果你遇到任何不确定、歧义、缺失前提或冲突要求，请立即暂停并提问，不要凭猜测继续。
4. 必须遵守 TDD：先写失败测试并记录失败，再写最小实现让测试通过。
5. 不要接入真实 LLM，不要使用真实 API key；只能使用 mock/stub。
6. 完成后输出：
   - 你选择的任务。
   - 你最初不确定的点。
   - SPEC / PLAN 哪些地方让你误解或暂停。
   - 你实际改动的文件。
   - 测试命令和结果。
   - 对 SPEC / PLAN 的修订建议。
```

Expected evidence to record in `SPEC_PROCESS.md`:

- The fresh agent's first blocking question.
- Any interpretation that differs from the intended design.
- Whether the task granularity was really 2-5 minutes.
- Concrete revisions made to `SPEC.md` / `PLAN.md`.
- Before/after diff snippets for important revisions.
