import asyncio

import pytest

from safepatch.core.provider import (
    LLMMessage,
    LLMRequest,
    LLMResponse,
    MockLLM,
    ProviderExhaustedError,
)


def run(coro):
    return asyncio.run(coro)


def request() -> LLMRequest:
    return LLMRequest(
        run_id="run-1",
        step=0,
        messages=[LLMMessage(role="user", content="fix the failing test")],
    )


def test_llm_request_requires_at_least_one_message():
    with pytest.raises(ValueError):
        LLMRequest(run_id="run-1", step=0, messages=[])


def test_provider_models_forbid_extra_fields():
    with pytest.raises(ValueError):
        LLMMessage(role="user", content="hello", extra=True)

    with pytest.raises(ValueError):
        LLMRequest(run_id="run-1", step=0, messages=[LLMMessage(role="user", content="hello")], extra=True)

    with pytest.raises(ValueError):
        LLMResponse(content="{}", provider_name="mock", extra=True)


def test_llm_response_content_allows_empty_and_blank_raw_output():
    empty = LLMResponse(content="", provider_name="mock")
    blank = LLMResponse(content="   ", provider_name="mock")

    assert empty.content == ""
    assert blank.content == "   "


def test_mock_llm_returns_raw_content_not_action():
    provider = MockLLM(['{"type": "finish", "status": "completed", "message": "done"}'])

    response = run(provider.complete(request()))

    assert isinstance(response, LLMResponse)
    assert response.content == '{"type": "finish", "status": "completed", "message": "done"}'
    assert response.provider_name == "mock"
    assert response.metadata == {"mock_index": 0}


def test_mock_llm_preserves_empty_and_blank_script_items():
    provider = MockLLM(["", "   "])

    first = run(provider.complete(request()))
    second = run(provider.complete(request()))

    assert first.content == ""
    assert first.metadata == {"mock_index": 0}
    assert second.content == "   "
    assert second.metadata == {"mock_index": 1}


def test_mock_llm_exhaustion_error_is_stable():
    provider = MockLLM([])

    with pytest.raises(ProviderExhaustedError) as exc_info:
        run(provider.complete(request()))

    assert str(exc_info.value) == "mock llm script exhausted"


def test_mock_llm_consumes_exception_then_reads_next_item():
    error = RuntimeError("boom")
    provider = MockLLM([error, "next"])

    with pytest.raises(RuntimeError) as exc_info:
        run(provider.complete(request()))

    assert exc_info.value is error

    response = run(provider.complete(request()))

    assert response.content == "next"
    assert response.metadata == {"mock_index": 1}
