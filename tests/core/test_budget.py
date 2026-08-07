from datetime import datetime, timedelta, timezone

from safepatch.core.budget import BudgetDecision, RunBudget


def test_step_budget_stops_before_provider_call():
    budget = RunBudget(max_steps=2)

    decision = budget.check(step=2)

    assert decision == BudgetDecision(
        should_stop=True,
        reason="step budget exhausted",
    )


def test_step_budget_allows_lower_step():
    budget = RunBudget(max_steps=2)

    decision = budget.check(step=1)

    assert decision == BudgetDecision(should_stop=False, reason=None)


def test_time_budget_stops_after_deadline():
    started = datetime(2026, 8, 8, 9, 0, tzinfo=timezone.utc)
    now = started + timedelta(seconds=11)
    budget = RunBudget(max_seconds=10)

    decision = budget.check(step=0, started_at=started, now=now)

    assert decision == BudgetDecision(
        should_stop=True,
        reason="time budget exhausted",
    )


def test_consecutive_failure_budget_stops_at_limit():
    budget = RunBudget(max_consecutive_failures=3)

    decision = budget.check(step=0, consecutive_failures=3)

    assert decision == BudgetDecision(
        should_stop=True,
        reason="consecutive failure budget exhausted",
    )
