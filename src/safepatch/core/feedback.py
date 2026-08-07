from __future__ import annotations

from safepatch.core.models import ToolResult
from safepatch.core.provider import LLMMessage


class FeedbackBuilder:
    def build_message(self, result: ToolResult) -> LLMMessage:
        metadata_lines = [
            f"{key}={value}"
            for key, value in sorted(result.metadata.items())
            if value not in (None, "")
        ]
        metadata = "\n".join(metadata_lines)
        content = "\n".join(
            part
            for part in [
                f"category={result.category.value}",
                f"success={result.success}",
                f"observation={result.observation}",
                metadata,
            ]
            if part
        )
        return LLMMessage(role="tool", content=content)
