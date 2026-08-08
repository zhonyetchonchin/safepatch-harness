import asyncio

from safepatch.core.loop import AgentLoop
from safepatch.core.models import EventType, ResultCategory, RunStatus, ToolResult
from safepatch.core.provider import LLMRequest, LLMResponse, MockLLM
from safepatch.core.budget import RunBudget


def run(coro):
    return asyncio.run(coro)


def test_mock_finish_action_completes_run():
    loop = AgentLoop(
        provider=MockLLM(
            ['{"type": "finish", "status": "completed", "message": "done"}']
        )
    )

    result = run(loop.run(run_id="run-1", task="finish the task"))

    assert result.state.status == RunStatus.COMPLETED
    assert result.state.step == 1
    assert result.final_message == "done"
    assert [event.sequence for event in result.events] == list(
        range(1, len(result.events) + 1)
    )
    assert EventType.LLM_REQUESTED in {event.type for event in result.events}
    assert EventType.ACTION_PARSED in {event.type for event in result.events}
    assert EventType.RUN_FINISHED in {event.type for event in result.events}


def test_invalid_json_does_not_execute_tools_and_returns_parse_feedback():
    calls: list[object] = []

    async def tool_executor(action):
        calls.append(action)

    loop = AgentLoop(
        provider=MockLLM(["not-json"]),
        tool_executor=tool_executor,
    )

    result = run(loop.run(run_id="run-1", task="fix something"))

    assert calls == []
    assert result.state.status == RunStatus.FAILED
    assert result.feedback is not None
    assert result.feedback.category == ResultCategory.PARSE_ERROR
    assert result.feedback.success is False
    assert "invalid action" in result.feedback.observation
    assert EventType.PARSE_FAILED in {event.type for event in result.events}
    assert EventType.RUN_FINISHED in {event.type for event in result.events}


def test_step_budget_exhaustion_does_not_call_provider():
    provider = MockLLM(
        ['{"type": "finish", "status": "completed", "message": "should not run"}']
    )
    loop = AgentLoop(provider=provider, budget=RunBudget(max_steps=1))

    result = run(loop.run(run_id="run-1", task="finish", initial_step=1))

    assert result.state.status == RunStatus.BUDGET_EXHAUSTED
    assert result.feedback is not None
    assert result.feedback.category == ResultCategory.TIMEOUT
    assert result.feedback.observation == "step budget exhausted"
    assert EventType.LLM_REQUESTED not in {event.type for event in result.events}


class FeedbackAwareProvider:
    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if len(self.requests) == 1:
            content = '{"type": "run_check", "name": "unit-test"}'
        elif len(self.requests) == 2:
            assert any(
                message.role == "tool" and "AssertionError" in message.content
                for message in request.messages
            )
            content = '{"type": "read_file", "path": "tests/test_app.py"}'
        else:
            content = (
                '{"type": "finish", "status": "completed", '
                '"message": "recovered"}'
            )
        return LLMResponse(content=content, provider_name="feedback-aware")


def test_tool_feedback_drives_next_action_in_same_run():
    provider = FeedbackAwareProvider()
    calls: list[str] = []

    async def tool_executor(action):
        calls.append(action.type)
        if action.type == "run_check":
            return ToolResult(
                action_id="run_check",
                success=False,
                category=ResultCategory.CHECK_FAILED,
                observation="unit-test failed: AssertionError",
            )
        return ToolResult(
            action_id=action.type,
            success=True,
            category=ResultCategory.SUCCESS,
            observation="read test file",
        )

    loop = AgentLoop(provider=provider, tool_executor=tool_executor)

    result = run(loop.run(run_id="run-feedback", task="repair the tests"))

    assert result.state.status == RunStatus.COMPLETED
    assert result.state.step == 3
    assert result.final_message == "recovered"
    assert calls == ["run_check", "read_file"]
    assert len(provider.requests) == 3
    assert [
        event.type for event in result.events if event.type == EventType.TOOL_FINISHED
    ] == [EventType.TOOL_FINISHED, EventType.TOOL_FINISHED]


def test_step_budget_is_checked_between_tool_actions():
    provider = MockLLM(
        [
            '{"type": "read_file", "path": "README.md"}',
            '{"type": "finish", "status": "completed", "message": "late"}',
        ]
    )

    async def tool_executor(action):
        return ToolResult(
            action_id=action.type,
            success=True,
            category=ResultCategory.SUCCESS,
            observation="ok",
        )

    result = run(
        AgentLoop(
            provider=provider,
            tool_executor=tool_executor,
            budget=RunBudget(max_steps=1),
        ).run(run_id="run-budget", task="read then finish")
    )

    assert result.state.status == RunStatus.BUDGET_EXHAUSTED
    assert result.state.step == 1
    assert result.feedback is not None
    assert result.feedback.observation == "step budget exhausted"


def test_provider_failure_is_redacted_and_returned_without_raising():
    loop = AgentLoop(provider=MockLLM([RuntimeError("bad sk-secretvalue")]))

    result = run(loop.run(run_id="run-provider-error", task="finish"))

    assert result.state.status == RunStatus.FAILED
    assert result.feedback is not None
    assert result.feedback.category == ResultCategory.TOOL_ERROR
    assert "sk-secretvalue" not in result.feedback.observation
    assert "provider request failed" in result.feedback.observation


def test_tool_exception_is_returned_without_raising():
    async def exploding_tool(action):
        raise OSError("workspace unavailable")

    loop = AgentLoop(
        provider=MockLLM(['{"type": "read_file", "path": "README.md"}']),
        tool_executor=exploding_tool,
    )

    result = run(loop.run(run_id="run-tool-error", task="read"))

    assert result.state.status == RunStatus.FAILED
    assert result.feedback is not None
    assert result.feedback.category == ResultCategory.TOOL_ERROR
    assert result.feedback.observation == "tool execution failed: OSError"
