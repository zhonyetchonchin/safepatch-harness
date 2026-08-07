from pathlib import Path

from fastapi.testclient import TestClient

from safepatch.api.app import create_app
from safepatch.policy.approval import ApprovalManager, ApprovalStatus
from safepatch.store.sqlite import SQLiteStore


def test_approve_pending_action_once_and_duplicate_returns_conflict(tmp_path: Path):
    store = SQLiteStore(tmp_path / "state.sqlite")
    approvals = ApprovalManager()
    approvals.request("action-1", reason="protected path")
    client = TestClient(create_app(store=store, approval_manager=approvals))

    approved = client.post("/approvals/action-1/approve")
    duplicate = client.post("/approvals/action-1/approve")

    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert duplicate.status_code == 409
    assert "not pending" in duplicate.json()["detail"]
    assert approvals.get("action-1").status == ApprovalStatus.APPROVED


def test_reject_pending_action_returns_feedback_without_secret_body(tmp_path: Path):
    store = SQLiteStore(tmp_path / "state.sqlite")
    approvals = ApprovalManager()
    approvals.request("action-2", reason="protected path")
    client = TestClient(create_app(store=store, approval_manager=approvals))

    rejected = client.post(
        "/approvals/action-2/reject",
        json={"reason": "too risky"},
    )

    assert rejected.status_code == 200
    body = rejected.json()
    assert body["status"] == "rejected"
    assert body["feedback"]["category"] == "approval_rejected"
    assert "too risky" in body["feedback"]["observation"]
    assert approvals.get("action-2").status == ApprovalStatus.REJECTED


def test_unknown_approval_returns_404(tmp_path: Path):
    store = SQLiteStore(tmp_path / "state.sqlite")
    client = TestClient(create_app(store=store, approval_manager=ApprovalManager()))

    response = client.post("/approvals/missing/approve")

    assert response.status_code == 404
    assert response.json()["detail"] == "approval not found"
