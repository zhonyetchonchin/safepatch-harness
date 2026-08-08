from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

from safepatch.core.loop import AgentLoop
from safepatch.core.models import (
    AgentAction,
    ApplyPatchAction,
    EventType,
    ListFilesAction,
    ReadFileAction,
    ResultCategory,
    RunCheckAction,
    RunState,
    RunStatus,
    SearchTextAction,
    ToolResult,
    parse_action,
)
from safepatch.core.provider import MockLLM
from safepatch.policy.approval import ApprovalManager
from safepatch.policy.engine import PolicyEngine
from safepatch.store.sqlite import RunRecord, SQLiteStore


DEMO_SCENARIOS = (
    "safe_repair",
    "feedback_recovery",
    "policy_block",
    "hitl_patch",
)


@dataclass
class _PendingDemo:
    loop: AgentLoop
    state: RunState
    action: AgentAction
    task: str


class DemoWorkbench:
    """Runs curated scenarios through the real harness without touching a repo."""

    def __init__(self, store: SQLiteStore, approvals: ApprovalManager) -> None:
        self._store = store
        self._approvals = approvals
        self._pending: dict[str, _PendingDemo] = {}
        self._restore_pending_runs()

    def start(self, run_id: str, task: str, scenario: str) -> RunRecord:
        if scenario not in DEMO_SCENARIOS:
            raise ValueError(f"unknown demo scenario: {scenario}")
        executor = _DemoToolExecutor(scenario)
        loop = AgentLoop(
            provider=MockLLM(_scenario_script(scenario)),
            tool_executor=executor,
            policy_engine=PolicyEngine(allowed_checks={"unit-test"}),
            approval_manager=self._approvals,
        )
        result = asyncio.run(loop.run(run_id=run_id, task=task))
        self._persist_events(result.events)
        record = self._store.update_run(
            run_id,
            status=result.state.status,
            pending_action_id=result.state.pending_action_id,
        )
        if result.state.pending_action_id and result.pending_action is not None:
            self._pending[result.state.pending_action_id] = _PendingDemo(
                loop=loop,
                state=result.state,
                action=result.pending_action,
                task=task,
            )
        return record

    def approve(self, action_id: str) -> RunRecord | None:
        pending = self._pending.pop(action_id, None)
        if pending is None:
            return None
        result = asyncio.run(
            pending.loop.resume_approved(
                pending.state,
                pending.action,
                task=pending.task,
            )
        )
        self._persist_events(result.events)
        return self._store.update_run(
            pending.state.run_id,
            status=result.state.status,
            pending_action_id=result.state.pending_action_id,
        )

    def reject(self, action_id: str, feedback: ToolResult) -> RunRecord | None:
        pending = self._pending.pop(action_id, None)
        if pending is None:
            return None
        self._store.append_event(
            pending.state.run_id,
            EventType.APPROVAL_DECIDED,
            {"action_id": action_id, "status": "rejected"},
        )
        self._store.append_event(
            pending.state.run_id,
            EventType.FEEDBACK_BUILT,
            {
                "action_id": feedback.action_id,
                "success": feedback.success,
                "category": feedback.category.value,
                "observation": feedback.observation,
                "metadata": feedback.metadata,
            },
        )
        self._store.append_event(
            pending.state.run_id,
            EventType.RUN_FINISHED,
            {"status": "failed", "step": pending.state.step},
        )
        return self._store.update_run(pending.state.run_id, status="failed")

    def _persist_events(self, events) -> None:
        for event in events:
            self._store.append_event(event.run_id, event.type, event.payload)

    def _restore_pending_runs(self) -> None:
        for record in self._store.list_runs():
            if (
                record.status != RunStatus.PAUSED_FOR_APPROVAL
                or record.pending_action_id is None
                or record.scenario not in DEMO_SCENARIOS
            ):
                continue
            events = self._store.list_events(record.run_id)
            approval_event = next(
                (
                    event
                    for event in reversed(events)
                    if event.type == EventType.APPROVAL_REQUESTED
                    and event.payload.get("action_id") == record.pending_action_id
                ),
                None,
            )
            if approval_event is None or "action" not in approval_event.payload:
                continue
            action = parse_action(approval_event.payload["action"])
            reason = str(approval_event.payload.get("reason") or "approval required")
            self._approvals.request(record.pending_action_id, reason=reason)
            step = 0
            for event in reversed(events):
                if event.type == EventType.RUN_FINISHED:
                    step = int(event.payload.get("step", 0))
                    break
            loop = AgentLoop(
                provider=MockLLM(_scenario_script(record.scenario)[1:]),
                tool_executor=_DemoToolExecutor(record.scenario),
                policy_engine=PolicyEngine(allowed_checks={"unit-test"}),
                approval_manager=self._approvals,
            )
            state = RunState(
                run_id=record.run_id,
                status=RunStatus.PAUSED_FOR_APPROVAL,
                step=step,
                pending_action_id=record.pending_action_id,
                updated_at=record.updated_at,
            )
            self._pending[record.pending_action_id] = _PendingDemo(
                loop=loop,
                state=state,
                action=action,
                task=record.task,
            )


class _DemoToolExecutor:
    def __init__(self, scenario: str) -> None:
        self._scenario = scenario
        self._check_count = 0

    async def __call__(self, action: AgentAction) -> ToolResult:
        if isinstance(action, RunCheckAction):
            self._check_count += 1
            if self._scenario == "feedback_recovery" and self._check_count == 1:
                return ToolResult(
                    action_id="run_check",
                    success=False,
                    category=ResultCategory.CHECK_FAILED,
                    observation="unit-test failed: AssertionError: expected 4, got 5",
                    metadata={
                        "name": action.name,
                        "returncode": 1,
                        "stdout": "1 failed, 17 passed",
                        "stderr": "AssertionError in tests/test_total.py:24",
                    },
                )
            return ToolResult(
                action_id="run_check",
                success=True,
                category=ResultCategory.SUCCESS,
                observation="unit-test passed",
                metadata={
                    "name": action.name,
                    "returncode": 0,
                    "stdout": "18 passed in 0.42s",
                    "stderr": "",
                },
            )
        if isinstance(action, ApplyPatchAction):
            return ToolResult(
                action_id="apply_patch",
                success=True,
                category=ResultCategory.SUCCESS,
                observation="patch validated and applied to the sample workspace",
                metadata={
                    "files": [_patch_target(action.patch)],
                    "diff": action.patch,
                },
            )
        if isinstance(action, ReadFileAction):
            return ToolResult(
                action_id="read_file",
                success=True,
                category=ResultCategory.SUCCESS,
                observation="def total(values):\n    return sum(values) + 1\n",
                metadata={"path": action.path, "bytes": 48},
            )
        if isinstance(action, ListFilesAction):
            return ToolResult(
                action_id="list_files",
                success=True,
                category=ResultCategory.SUCCESS,
                observation="3 sample files",
                metadata={
                    "paths": ["sample/app.py", "tests/test_total.py", "pyproject.toml"]
                },
            )
        if isinstance(action, SearchTextAction):
            return ToolResult(
                action_id="search_text",
                success=True,
                category=ResultCategory.SUCCESS,
                observation="1 match",
                metadata={
                    "matches": [
                        {"path": "sample/app.py", "line": 2, "text": "return sum(values) + 1"}
                    ]
                },
            )
        return ToolResult(
            action_id=action.type,
            success=True,
            category=ResultCategory.SUCCESS,
            observation=f"demo action completed: {action.type}",
        )


def _scenario_script(scenario: str) -> list[str]:
    finish = _action(
        {"type": "finish", "status": "completed", "message": "Demo run completed"}
    )
    safe_patch = _action(
        {
            "type": "apply_patch",
            "patch": (
                "diff --git a/sample/app.py b/sample/app.py\n"
                "--- a/sample/app.py\n"
                "+++ b/sample/app.py\n"
                "@@ -1,2 +1,2 @@\n"
                " def total(values):\n"
                "-    return sum(values) + 1\n"
                "+    return sum(values)\n"
            ),
        }
    )
    protected_patch = _action(
        {
            "type": "apply_patch",
            "patch": (
                "diff --git a/pyproject.toml b/pyproject.toml\n"
                "--- a/pyproject.toml\n"
                "+++ b/pyproject.toml\n"
                "@@ -1 +1 @@\n"
                "-version = \"0.1.0\"\n"
                "+version = \"0.1.1\"\n"
            ),
        }
    )
    if scenario == "safe_repair":
        return [
            _action({"type": "list_files", "glob": "**/*.py", "limit": 20}),
            safe_patch,
            _action({"type": "run_check", "name": "unit-test"}),
            finish,
        ]
    if scenario == "feedback_recovery":
        return [
            _action({"type": "run_check", "name": "unit-test"}),
            _action({"type": "read_file", "path": "sample/app.py"}),
            safe_patch,
            _action({"type": "run_check", "name": "unit-test"}),
            finish,
        ]
    if scenario == "policy_block":
        return [_action({"type": "run_check", "name": "rm -rf /"})]
    return [
        protected_patch,
        _action({"type": "run_check", "name": "unit-test"}),
        finish,
    ]


def _action(payload: dict[str, object]) -> str:
    return json.dumps(payload)


def _patch_target(patch: str) -> str:
    for line in patch.splitlines():
        if line.startswith("+++ b/"):
            return line[6:]
    return "sample/app.py"
