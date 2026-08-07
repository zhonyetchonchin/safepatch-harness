from safepatch.demo.mock_scenarios import (
    run_all_scenarios,
    run_dangerous_action_demo,
    run_feedback_recovery_demo,
    run_hitl_pause_demo,
)


def test_dangerous_action_demo_denies_without_tool_execution():
    result = run_dangerous_action_demo()

    assert result.passed is True
    assert result.name == "dangerous_action_block"
    assert result.details["run_status"] == "failed"
    assert result.details["feedback_category"] == "policy_denied"
    assert result.details["tool_calls"] == 0
    assert "dangerous command" in result.details["observation"]


def test_feedback_recovery_demo_feeds_failure_into_changed_action():
    result = run_feedback_recovery_demo()

    assert result.passed is True
    assert result.name == "failure_feedback_recovery"
    assert result.details["initial_feedback_category"] == "check_failed"
    assert result.details["feedback_seen_by_provider"] is True
    assert result.details["changed_action_type"] == "read_file"


def test_hitl_pause_demo_stops_before_tool_execution():
    result = run_hitl_pause_demo()

    assert result.passed is True
    assert result.name == "hitl_pause"
    assert result.details["run_status"] == "paused_for_approval"
    assert result.details["approval_status"] == "pending"
    assert result.details["tool_calls"] == 0


def test_all_scenarios_are_reported_in_stable_order():
    results = run_all_scenarios()

    assert [result.name for result in results] == [
        "dangerous_action_block",
        "failure_feedback_recovery",
        "hitl_pause",
    ]
    assert all(result.passed for result in results)
