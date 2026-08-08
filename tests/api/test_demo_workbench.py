from pathlib import Path

from fastapi.testclient import TestClient

from safepatch.runtime import create_demo_app


def client_for(tmp_path: Path) -> TestClient:
    return TestClient(create_demo_app(data_dir=tmp_path, public_demo=True))


def create_scenario(client: TestClient, scenario: str):
    response = client.post(
        "/runs",
        json={"task": f"Demonstrate {scenario}", "scenario": scenario},
    )
    assert response.status_code == 201
    return response.json()


def event_payloads(client: TestClient, run_id: str) -> list[dict[str, object]]:
    response = client.get(f"/runs/{run_id}/events")
    assert response.status_code == 200
    return response.json()["events"]


def test_safe_repair_demo_completes_with_check_and_diff(tmp_path: Path):
    client = client_for(tmp_path)

    run = create_scenario(client, "safe_repair")
    events = event_payloads(client, run["run_id"])

    assert run["status"] == "completed"
    assert any(
        event["type"] == "tool_finished"
        and event["payload"].get("metadata", {}).get("name") == "unit-test"
        for event in events
    )
    assert any(
        event["type"] == "action_parsed"
        and "diff --git" in str(event["payload"])
        for event in events
    )


def test_feedback_recovery_demo_changes_action_and_finishes(tmp_path: Path):
    client = client_for(tmp_path)

    run = create_scenario(client, "feedback_recovery")
    events = event_payloads(client, run["run_id"])

    categories = [
        event["payload"].get("category")
        for event in events
        if event["type"] == "tool_finished"
    ]
    action_types = [
        event["payload"].get("type")
        for event in events
        if event["type"] == "action_parsed"
    ]
    assert run["status"] == "completed"
    assert "check_failed" in categories
    assert action_types[:3] == ["run_check", "read_file", "apply_patch"]


def test_policy_block_demo_denies_before_tool_execution(tmp_path: Path):
    client = client_for(tmp_path)

    run = create_scenario(client, "policy_block")
    events = event_payloads(client, run["run_id"])

    assert run["status"] == "failed"
    assert any(
        event["type"] == "policy_decision"
        and event["payload"].get("status") == "deny"
        for event in events
    )
    assert not any(event["type"] == "tool_started" for event in events)


def test_hitl_demo_approve_resumes_exact_action_and_completes(tmp_path: Path):
    client = client_for(tmp_path)

    paused = create_scenario(client, "hitl_patch")
    action_id = paused["pending_action_id"]
    assert paused["status"] == "paused_for_approval"
    assert action_id.startswith(f"{paused['run_id']}:")

    approved = client.post(f"/approvals/{action_id}/approve")
    finished = client.get(f"/runs/{paused['run_id']}").json()
    events = event_payloads(client, paused["run_id"])

    assert approved.status_code == 200
    assert finished["status"] == "completed"
    assert finished["pending_action_id"] is None
    assert any(event["type"] == "approval_decided" for event in events)
    assert sum(event["type"] == "tool_started" for event in events) == 2


def test_hitl_demo_reject_records_feedback_without_execution(tmp_path: Path):
    client = client_for(tmp_path)
    paused = create_scenario(client, "hitl_patch")

    rejected = client.post(
        f"/approvals/{paused['pending_action_id']}/reject",
        json={"reason": "Dependency change not approved"},
    )
    finished = client.get(f"/runs/{paused['run_id']}").json()
    events = event_payloads(client, paused["run_id"])

    assert rejected.status_code == 200
    assert finished["status"] == "failed"
    assert not any(event["type"] == "tool_started" for event in events)
    assert any(
        event["type"] == "feedback_built"
        and event["payload"].get("category") == "approval_rejected"
        for event in events
    )


def test_paused_demo_can_be_approved_after_app_restart(tmp_path: Path):
    first_client = client_for(tmp_path)
    paused = create_scenario(first_client, "hitl_patch")

    restarted_client = client_for(tmp_path)
    approved = restarted_client.post(
        f"/approvals/{paused['pending_action_id']}/approve"
    )
    finished = restarted_client.get(f"/runs/{paused['run_id']}").json()

    assert approved.status_code == 200
    assert finished["status"] == "completed"


def test_public_demo_disables_shared_credentials_and_reports_capabilities(
    tmp_path: Path,
):
    client = client_for(tmp_path)

    metadata = client.get("/meta")
    credentials = client.get("/credentials/openai/status")

    assert metadata.status_code == 200
    assert metadata.json()["demo_mode"] is True
    assert metadata.json()["public_demo"] is True
    assert metadata.json()["credentials_enabled"] is False
    assert set(metadata.json()["scenarios"]) == {
        "safe_repair",
        "feedback_recovery",
        "policy_block",
        "hitl_patch",
    }
    assert credentials.status_code == 503
