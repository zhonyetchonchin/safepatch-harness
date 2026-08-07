import asyncio

from safepatch.core.loop import AgentLoop
from safepatch.core.models import EventType, ResultCategory, RunStatus
from safepatch.core.provider import MockLLM
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
