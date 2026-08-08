import asyncio

from safepatch.core.feedback import FeedbackBuilder
from safepatch.core.loop import AgentLoop
from safepatch.core.models import ResultCategory, ToolResult
from safepatch.core.provider import LLMRequest, LLMResponse


def run(coro):
    return asyncio.run(coro)


class RecordingProvider:
    def __init__(self) -> None:
        self.request: LLMRequest | None = None

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.request = request
        return LLMResponse(
            content='{"type": "finish", "status": "completed", "message": "done"}',
            provider_name="recording",
        )


def failed_check() -> ToolResult:
    return ToolResult(
        action_id="run_check",
        success=False,
        category=ResultCategory.CHECK_FAILED,
        observation="check failed",
        metadata={
            "name": "unit-test",
            "returncode": 1,
            "stdout": "assert 1 == 2\n",
            "stderr": "",
        },
    )


def test_feedback_builder_turns_tool_result_into_tool_message():
    message = FeedbackBuilder().build_message(failed_check())

    assert message.role == "tool"
    assert "category=check_failed" in message.content
    assert "success=False" in message.content
    assert "check failed" in message.content
    assert "assert 1 == 2" in message.content


def test_loop_includes_prior_feedback_in_provider_context():
    provider = RecordingProvider()
    loop = AgentLoop(provider=provider)

    run(loop.run(run_id="run-1", task="fix tests", prior_feedback=[failed_check()]))

    assert provider.request is not None
    assert any(
        message.role == "tool" and "assert 1 == 2" in message.content
        for message in provider.request.messages
    )
