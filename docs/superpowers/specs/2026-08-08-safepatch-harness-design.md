# SafePatch Harness Design

## Context

This project implements AI4SE Project A: a Coding Agent Harness. The deliverable is not a prompt wrapper and not an application built on a high-level agent framework. The project must implement its own harness loop:

context assembly -> LLM provider call -> action parsing -> policy evaluation -> tool dispatch -> feedback construction -> stop decision.

The product is SafePatch Harness, a local coding agent harness for small code repair tasks. A user gives a repository path and a task. The harness lets an LLM read files, propose patches, and run configured checks, while deterministic code governs every action.

## Recommended Approach

The selected approach is a local-first Python harness with a WebUI and Docker distribution.

Rejected alternatives:

- Building a generic multi-agent platform: too broad for the project and would weaken the required mechanism depth.
- Using LangChain AgentExecutor, AutoGen, CrewAI, or LlamaIndex agent runners: disallowed by Project A because the agent loop must be implemented in this repository.
- Deploying a public service that executes arbitrary user repositories: unsafe for this course project; the public deployment should run only demo mode.

## Architecture

The system is split into focused modules:

- `core`: action schemas, provider port, agent loop, budgets, feedback.
- `policy`: deterministic guardrails, path containment, command classification, HITL approval state.
- `tools`: file read/list/search, atomic patch application, allowlisted check commands.
- `store`: SQLite events, runs, approvals, and memory.
- `security`: encrypted credential vault and log/API redaction.
- `api`: FastAPI routes for runs, approvals, credentials, and static WebUI.
- `web`: a workbench-style UI for run timeline, approvals, check output, and final diff.
- `demo`: mock LLM scenarios proving key mechanisms without network or API keys.

The main contribution is governance plus HITL, because it remains testable when the real LLM is removed. Dangerous actions are rejected or paused by code, not by prompt wording.

## Core Mechanisms

The LLM outputs one structured JSON action per step. Pydantic validation rejects malformed actions before any tool can run.

The provider boundary is before JSON parsing: providers return raw text in `LLMResponse.content`, and the loop parses that text into an `Action`. Mock LLM uses the same boundary, so tests exercise the real parsing path.

Actions are discriminated by `type`, not by an untyped payload bag. The first release supports `read_file`, `list_files`, `search_text`, `apply_patch`, `run_check`, `remember`, and `finish`. Public Pydantic models use `extra="forbid"`; unknown fields are validation failures.

The policy engine returns one of three decisions:

- `allow`: execute the action.
- `requires_approval`: persist a pending action and pause the run.
- `deny`: do not execute; feed the denial reason back to the loop.

The tool layer can only operate inside the normalized workspace root. Path traversal, symlink escape, sensitive files, non-allowlisted commands, and destructive shell patterns are deterministic failures.

The feedback builder converts policy decisions, command results, patch conflicts, test failures, and timeouts into compact structured feedback for the next loop iteration.

The memory system stores short project facts and failure summaries in SQLite. It does not inject full history into every prompt.

Run state is a Pydantic snapshot containing `run_id`, `status`, `step`, `pending_action_id`, and `updated_at`. Transitions are validated by a public transition function. Terminal states are `completed`, `failed`, `canceled`, and `budget_exhausted`; they cannot transition back to `running`.

The implementation targets Pydantic v2 (`pydantic>=2.7,<3`). Timestamp defaults use current UTC time. Event IDs are UUID strings. Action parsing validates JSON and schema but does not check project policy such as whether a `run_check.name` is allowlisted; that belongs to the policy/config layer.

`LLMResponse.content` is the only public string field that may be empty or whitespace because it represents raw model output; empty output must reach the parser so parse-failure feedback can be tested.

`RunState` enforces approval invariants at model construction and through the transition function. `ToolResult.started_at` and `finished_at` default to `None`. Injected transition timestamps must be timezone-aware; non-UTC values are normalized to UTC.

## Security

The threat model assumes the LLM may produce dangerous actions, attempt to read secrets, or accidentally include credentials in logs.

Mitigations:

- Workspace containment and symlink resolution.
- Command allowlist with argv execution.
- Sensitive path denylist.
- Secret redaction before writing events or logs.
- Encrypted credential vault using a user-provided master password.
- WebUI defaults to `127.0.0.1`; public deployment runs demo mode only.
- One approval authorizes exactly one action id.

## Testing Strategy

All harness mechanisms must be verified with mock or stub LLMs. Required deterministic tests include:

- Dangerous command is denied.
- Path traversal and symlink escape are denied.
- Approval-required action pauses the run and does not call the next LLM step.
- Approval cannot be reused to execute an action twice.
- Injected test failure appears in the next LLM context.
- Mock LLM changes its second action after receiving failure feedback.
- Budgets stop the loop.
- Credential values never appear in event payloads, logs, or API status responses.

Implementation must follow red-green-refactor. Each task in `PLAN.md` names its expected failing test before implementation.

## Distribution

Docker is the required distribution path. The image starts a WebUI and defaults to demo mode. Local real mode uses mounted workspace and data directories. CI must include a `.gitlab-ci.yml` job named `unit-test`; Docker build runs in CI after tests.

## Open Decisions

Current decisions are intentionally conservative:

- Public deployment does not execute user repositories.
- The first release supports one OpenAI-compatible provider plus mock LLM.
- Frontend uses a lightweight workbench UI rather than a full SPA framework unless implementation complexity requires otherwise.

The remaining gate before implementation is cold-start validation with a fresh, different agent context using only `SPEC.md` and `PLAN.md`.
