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
    async def failing_check_executor(action: AgentAction) -> ToolResult:
        return ToolResult(
            action_id=action.type,
            success=False,
            category=ResultCategory.CHECK_FAILED,
            observation="unit-test failed: AssertionError: expected green",
            metadata={"name": "unit-test", "returncode": 1},
        )

    first_loop = AgentLoop(
        provider=MockLLM([_json_action({"type": "run_check", "name": "unit-test"})]),
        tool_executor=failing_check_executor,
        policy_engine=PolicyEngine(allowed_checks={"unit-test"}),
    )
    first = _run(
        first_loop.run(run_id="demo-feedback-1", task="run unit tests")
    )
    if first.feedback is None:
        return ScenarioResult(
            name="failure_feedback_recovery",
            passed=False,
            details={"error": "first run did not produce feedback"},
        )

    provider = _FeedbackAwareMockLLM()
    changed_actions: list[AgentAction] = []

    async def recording_executor(action: AgentAction) -> ToolResult:
        changed_actions.append(action)
        return ToolResult(
            action_id=action.type,
            success=True,
            category=ResultCategory.SUCCESS,
            observation=f"executed changed action: {action.type}",
        )

    second_loop = AgentLoop(
        provider=provider,
        tool_executor=recording_executor,
    )
    _run(
        second_loop.run(
            run_id="demo-feedback-2",
            task="recover from failed unit test",
            prior_feedback=[first.feedback],
        )
    )

    changed_action_type = changed_actions[0].type if changed_actions else None
    details = {
        "initial_feedback_category": first.feedback.category.value,
        "feedback_seen_by_provider": provider.feedback_seen,
        "changed_action_type": changed_action_type,
    }
    return ScenarioResult(
        name="failure_feedback_recovery",
        passed=(
            first.feedback.category == ResultCategory.CHECK_FAILED
            and provider.feedback_seen
            and changed_action_type == "read_file"
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

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.feedback_seen = any(
            message.role == "tool" and "AssertionError" in message.content
            for message in request.messages
        )
        if self.feedback_seen:
            content = _json_action(
                {"type": "read_file", "path": "tests/core/test_loop.py"}
            )
        else:
            content = _json_action(
                {
                    "type": "finish",
                    "status": "failed",
                    "message": "feedback was not present",
                }
            )
        return LLMResponse(content=content, provider_name="feedback-aware-mock")


def _json_action(payload: dict[str, Any]) -> str:
    return json.dumps(payload)


def _run(coro):
    return asyncio.run(coro)
