from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal, Protocol

from pydantic import Field

from safepatch.core.models import NonEmptyStr, StrictModel


class LLMMessage(StrictModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: NonEmptyStr


class LLMRequest(StrictModel):
    run_id: NonEmptyStr
    step: int = Field(ge=0)
    messages: list[LLMMessage] = Field(min_length=1)


class LLMResponse(StrictModel):
    content: str
    provider_name: NonEmptyStr
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMProvider(Protocol):
    async def complete(self, request: LLMRequest) -> LLMResponse:
        ...


class ProviderExhaustedError(RuntimeError):
    pass


class MockLLM:
    def __init__(
        self,
        script: Sequence[str | Exception],
        provider_name: str = "mock",
    ) -> None:
        self._script = list(script)
        self._provider_name = provider_name
        self._index = 0

    async def complete(self, request: LLMRequest) -> LLMResponse:
        if not self._script:
            raise ProviderExhaustedError("mock llm script exhausted")

        item = self._script.pop(0)
        index = self._index
        self._index += 1

        if isinstance(item, Exception):
            raise item

        return LLMResponse(
            content=item,
            provider_name=self._provider_name,
            metadata={"mock_index": index},
        )
