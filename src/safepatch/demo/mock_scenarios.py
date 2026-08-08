from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from safepatch.core.loop import AgentLoop
from safepatch.core.models import (
    AgentAction,
    ResultCategory,
    RunStatus,
    ToolResult,
)
from safepatch.core.provider import LLMRequest, LLMResponse, MockLLM
from safepatch.policy.approval import ApprovalManager
from safepatch.policy.engine import PolicyEngine


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    passed: bool
    details: dict[str, Any]


def run_all_scenarios() -> list[ScenarioResult]:
    return [
        run_dangerous_action_demo(),
        run_feedback_recovery_demo(),
        run_hitl_pause_demo(),
    ]


def run_dangerous_action_demo() -> ScenarioResult:
    tool_calls: list[AgentAction] = []

    async def tool_executor(action: AgentAction) -> ToolResult:
        tool_calls.append(action)
        return ToolResult(
            action_id=action.type,
            success=True,
            category=ResultCategory.SUCCESS,
            observation="unexpected tool execution",
        )

    loop = AgentLoop(
        provider=MockLLM([_json_action({"type": "run_check", "name": "rm -rf /"})]),
        tool_executor=tool_executor,
        policy_engine=PolicyEngine(allowed_checks={"unit-test"}),
    )

    result = _run(loop.run(run_id="demo-dangerous", task="run a dangerous command"))
    details = {
        "run_status": result.state.status.value,
        "feedback_category": result.feedback.category.value
        if result.feedback is not None
        else None,
        "observation": result.feedback.observation if result.feedback else "",
        "tool_calls": len(tool_calls),
    }
    return ScenarioResult(
        name="dangerous_action_block",
        passed=(
            result.state.status == RunStatus.FAILED
            and result.feedback is not None
            and result.feedback.category == ResultCategory.POLICY_DENIED
            and len(tool_calls) == 0
        ),
        details=details,
    )


def run_feedback_recovery_demo() -> ScenarioResult:
    provider = _FeedbackAwareMockLLM()
    changed_actions: list[AgentAction] = []

    async def recording_executor(action: AgentAction) -> ToolResult:
        changed_actions.append(action)
        if action.type == "run_check":
            return ToolResult(
                action_id=action.type,
                success=False,
                category=ResultCategory.CHECK_FAILED,
                observation="unit-test failed: AssertionError: expected green",
                metadata={"name": "unit-test", "returncode": 1},
            )
        return ToolResult(
            action_id=action.type,
            success=True,
            category=ResultCategory.SUCCESS,
            observation=f"executed changed action: {action.type}",
        )

    loop = AgentLoop(
        provider=provider,
        tool_executor=recording_executor,
        policy_engine=PolicyEngine(allowed_checks={"unit-test"}),
    )
    result = _run(
        loop.run(
            run_id="demo-feedback",
            task="recover from failed unit test",
        )
    )

    changed_action_type = changed_actions[1].type if len(changed_actions) > 1 else None
    details = {
        "initial_feedback_category": ResultCategory.CHECK_FAILED.value,
        "feedback_seen_by_provider": provider.feedback_seen,
        "changed_action_type": changed_action_type,
        "run_status": result.state.status.value,
    }
    return ScenarioResult(
        name="failure_feedback_recovery",
        passed=(
            provider.feedback_seen
            and changed_action_type == "read_file"
            and result.state.status == RunStatus.COMPLETED
        ),
        details=details,
    )


def run_hitl_pause_demo() -> ScenarioResult:
    tool_calls: list[AgentAction] = []

    async def tool_executor(action: AgentAction) -> ToolResult:
        tool_calls.append(action)
        return ToolResult(
            action_id=action.type,
            success=True,
            category=ResultCategory.SUCCESS,
            observation="unexpected tool execution",
        )

    approvals = ApprovalManager()
    loop = AgentLoop(
        provider=MockLLM(
            [
                _json_action(
                    {
                        "type": "apply_patch",
                        "patch": (
                            "--- a/package-lock.json\n"
                            "+++ b/package-lock.json\n"
                            "@@ -1 +1 @@\n"
                            "-old\n"
                            "+new\n"
                        ),
                    }
                )
            ]
        ),
        tool_executor=tool_executor,
        policy_engine=PolicyEngine(protected_paths={"package-lock.json"}),
        approval_manager=approvals,
    )

    result = _run(loop.run(run_id="demo-hitl", task="update dependency lock"))
    approval_status = None
    if result.state.pending_action_id is not None:
        approval_status = approvals.get(result.state.pending_action_id).status.value
    details = {
        "run_status": result.state.status.value,
        "pending_action_id": result.state.pending_action_id,
        "approval_status": approval_status,
        "tool_calls": len(tool_calls),
    }
    return ScenarioResult(
        name="hitl_pause",
        passed=(
            result.state.status == RunStatus.PAUSED_FOR_APPROVAL
            and approval_status == "pending"
            and len(tool_calls) == 0
        ),
        details=details,
    )


class _FeedbackAwareMockLLM:
    def __init__(self) -> None:
        self.feedback_seen = False
        self._calls = 0

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.feedback_seen = any(
            message.role == "tool" and "AssertionError" in message.content
            for message in request.messages
        )
        if self._calls == 0:
            content = _json_action({"type": "run_check", "name": "unit-test"})
        elif self._calls == 1 and self.feedback_seen:
            content = _json_action(
                {"type": "read_file", "path": "tests/core/test_loop.py"}
            )
        else:
            content = _json_action(
                {
                    "type": "finish",
                    "status": "completed",
                    "message": "feedback recovery completed",
                }
            )
        self._calls += 1
        return LLMResponse(content=content, provider_name="feedback-aware-mock")


def _json_action(payload: dict[str, Any]) -> str:
    return json.dumps(payload)


def _run(coro):
    return asyncio.run(coro)
