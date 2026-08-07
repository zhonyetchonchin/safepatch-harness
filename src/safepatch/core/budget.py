from __future__ import annotations

from datetime import datetime, timezone

from pydantic import Field

from safepatch.core.models import StrictModel


class BudgetDecision(StrictModel):
    should_stop: bool
    reason: str | None = None


class RunBudget(StrictModel):
    max_steps: int = Field(default=20, ge=1)
    max_seconds: int = Field(default=600, ge=1)
    max_consecutive_failures: int = Field(default=3, ge=1)

    def check(
        self,
        *,
        step: int,
        started_at: datetime | None = None,
        now: datetime | None = None,
        consecutive_failures: int = 0,
    ) -> BudgetDecision:
        if step >= self.max_steps:
            return BudgetDecision(
                should_stop=True,
                reason="step budget exhausted",
            )

        if started_at is not None:
            current_time = now or datetime.now(timezone.utc)
            if _to_utc(current_time) - _to_utc(started_at) >= self._duration:
                return BudgetDecision(
                    should_stop=True,
                    reason="time budget exhausted",
                )

        if consecutive_failures >= self.max_consecutive_failures:
            return BudgetDecision(
                should_stop=True,
                reason="consecutive failure budget exhausted",
            )

        return BudgetDecision(should_stop=False, reason=None)

    @property
    def _duration(self):
        from datetime import timedelta

        return timedelta(seconds=self.max_seconds)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc)
