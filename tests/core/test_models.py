from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from safepatch.core.models import (
    ActionParseError,
    Event,
    EventType,
    InvalidStateTransition,
    ResultCategory,
    RunState,
    RunStatus,
    ToolResult,
    parse_action,
    transition_run_state,
)


def test_parse_action_rejects_unknown_type():
    with pytest.raises(ActionParseError):
        parse_action({"type": "unknown"})


def test_parse_action_rejects_extra_fields():
    with pytest.raises(ActionParseError):
        parse_action({"type": "read_file", "path": "src/app.py", "extra": True})


def test_parse_action_requires_read_file_path():
    with pytest.raises(ActionParseError):
        parse_action({"type": "read_file"})


def test_parse_action_rejects_blank_required_strings():
    with pytest.raises(ActionParseError):
        parse_action({"type": "read_file", "path": "   "})

    with pytest.raises(ActionParseError):
        parse_action(
            {
                "type": "remember",
                "kind": "project_convention",
                "content": "Use pytest.",
                "tags": ["tests", "  "],
            }
        )


def test_run_check_action_parses_without_allowlist_validation():
    action = parse_action({"type": "run_check", "name": "unit-test"})

    assert action.type == "run_check"
    assert action.name == "unit-test"


def test_terminal_state_cannot_transition_to_running():
    state = RunState(run_id="run-1", status=RunStatus.COMPLETED)

    with pytest.raises(InvalidStateTransition) as exc_info:
        transition_run_state(state, RunStatus.RUNNING)

    assert "invalid run status transition: completed -> running" in str(exc_info.value)


def test_transition_to_paused_requires_pending_action_id():
    state = RunState(run_id="run-1", status=RunStatus.RUNNING, step=4)
    now = datetime(2026, 8, 8, 9, 0, tzinfo=timezone.utc)

    with pytest.raises(ValueError):
        transition_run_state(state, RunStatus.PAUSED_FOR_APPROVAL)

    updated = transition_run_state(
        state,
        RunStatus.PAUSED_FOR_APPROVAL,
        pending_action_id="action-1",
        now=now,
    )

    assert updated is not state
    assert updated.status == RunStatus.PAUSED_FOR_APPROVAL
    assert updated.pending_action_id == "action-1"
    assert updated.step == 4
    assert updated.updated_at == now


def test_run_state_constructor_enforces_approval_invariants():
    with pytest.raises(ValueError):
        RunState(run_id="run-1", status=RunStatus.PAUSED_FOR_APPROVAL)

    with pytest.raises(ValueError):
        RunState(
            run_id="run-1",
            status=RunStatus.RUNNING,
            pending_action_id="action-1",
        )


def test_pending_action_id_is_only_valid_for_paused_target():
    state = RunState(
        run_id="run-1",
        status=RunStatus.PAUSED_FOR_APPROVAL,
        pending_action_id="action-1",
    )

    with pytest.raises(ValueError) as exc_info:
        transition_run_state(
            state,
            RunStatus.RUNNING,
            pending_action_id="action-2",
        )

    assert str(exc_info.value) == "pending_action_id is only valid for paused_for_approval"


def test_leaving_paused_state_clears_pending_action_id():
    state = RunState(
        run_id="run-1",
        status=RunStatus.PAUSED_FOR_APPROVAL,
        pending_action_id="action-1",
        step=2,
    )

    updated = transition_run_state(state, RunStatus.RUNNING)

    assert updated.status == RunStatus.RUNNING
    assert updated.pending_action_id is None
    assert updated.step == 2


def test_transition_rejects_naive_now():
    state = RunState(run_id="run-1", status=RunStatus.CREATED)
    naive = datetime(2026, 8, 8, 9, 0)

    with pytest.raises(ValueError) as exc_info:
        transition_run_state(state, RunStatus.RUNNING, now=naive)

    assert str(exc_info.value) == "now must be timezone-aware"


def test_transition_normalizes_non_utc_now():
    state = RunState(run_id="run-1", status=RunStatus.CREATED)
    non_utc = datetime(2026, 8, 8, 17, 0, tzinfo=timezone(timedelta(hours=8)))

    updated = transition_run_state(state, RunStatus.RUNNING, now=non_utc)

    assert updated.updated_at == datetime(2026, 8, 8, 9, 0, tzinfo=timezone.utc)


def test_event_requires_positive_sequence_and_uuid_id():
    with pytest.raises(ValueError):
        Event(run_id="run-1", sequence=0, type=EventType.RUN_CREATED)

    event = Event(run_id="run-1", sequence=1, type=EventType.RUN_CREATED)

    assert str(UUID(event.id)) == event.id


def test_tool_result_time_fields_default_to_none():
    result = ToolResult(
        action_id="action-1",
        success=True,
        category=ResultCategory.SUCCESS,
        observation="ok",
    )

    assert result.started_at is None
    assert result.finished_at is None
