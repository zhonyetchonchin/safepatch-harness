import asyncio

from safepatch.core.loop import AgentLoop
from safepatch.core.models import ResultCategory, RunStatus, ToolResult
from safepatch.core.provider import MockLLM
from safepatch.policy.approval import ApprovalManager, ApprovalStatus
from safepatch.policy.engine import PolicyEngine


def run(coro):
    return asyncio.run(coro)


def protected_patch_action() -> str:
    return """{"type": "apply_patch", "patch": "--- a/package-lock.json\\n+++ b/package-lock.json\\n@@ -1 +1 @@\\n-old\\n+new\\n"}"""


def test_requires_approval_pauses_without_executing_tool():
    calls = []

    async def tool_executor(action):
        calls.append(action)
        return ToolResult(
            action_id="tool",
            success=True,
            category=ResultCategory.SUCCESS,
            observation="ok",
        )

    approvals = ApprovalManager()
    loop = AgentLoop(
        provider=MockLLM([protected_patch_action()]),
        tool_executor=tool_executor,
        policy_engine=PolicyEngine(protected_paths={"package-lock.json"}),
        approval_manager=approvals,
    )

    result = run(loop.run(run_id="run-1", task="update dependency lock"))

    assert calls == []
    assert result.state.status == RunStatus.PAUSED_FOR_APPROVAL
    assert result.state.pending_action_id is not None
    assert result.pending_action is not None
    assert approvals.get(result.state.pending_action_id).status == ApprovalStatus.PENDING


def test_approve_resume_executes_original_action_once():
    calls = []

    async def tool_executor(action):
        calls.append(action)
        return ToolResult(
            action_id="apply_patch",
            success=True,
            category=ResultCategory.SUCCESS,
            observation="ok",
        )

    approvals = ApprovalManager()
    loop = AgentLoop(
        provider=MockLLM([protected_patch_action()]),
        tool_executor=tool_executor,
        policy_engine=PolicyEngine(protected_paths={"package-lock.json"}),
        approval_manager=approvals,
    )
    paused = run(loop.run(run_id="run-1", task="update dependency lock"))
    approvals.approve(paused.state.pending_action_id)

    resumed = run(loop.resume_approved(paused.state, paused.pending_action))

    assert len(calls) == 1
    assert calls[0] == paused.pending_action
    assert resumed.state.status == RunStatus.RUNNING
    assert resumed.feedback is not None
    assert resumed.feedback.success is True

    second = run(loop.resume_approved(paused.state, paused.pending_action))
    assert len(calls) == 1
    assert second.feedback is not None
    assert second.feedback.category == ResultCategory.APPROVAL_REJECTED
    assert "approval already consumed" in second.feedback.observation


def test_pending_action_ids_are_unique_across_runs():
    approvals = ApprovalManager()
    first = AgentLoop(
        provider=MockLLM([protected_patch_action()]),
        policy_engine=PolicyEngine(protected_paths={"package-lock.json"}),
        approval_manager=approvals,
    )
    second = AgentLoop(
        provider=MockLLM([protected_patch_action()]),
        policy_engine=PolicyEngine(protected_paths={"package-lock.json"}),
        approval_manager=approvals,
    )

    first_result = run(first.run(run_id="run-one", task="update lock"))
    second_result = run(second.run(run_id="run-two", task="update lock"))

    assert first_result.state.pending_action_id != second_result.state.pending_action_id
    assert first_result.state.pending_action_id.startswith("run-one:")
    assert second_result.state.pending_action_id.startswith("run-two:")
