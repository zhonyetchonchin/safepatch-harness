import pytest

from safepatch.core.models import ResultCategory
from safepatch.policy.approval import (
    ApprovalError,
    ApprovalManager,
    ApprovalStatus,
)


def test_request_creates_pending_approval():
    manager = ApprovalManager()

    record = manager.request("action-1", reason="protected path")

    assert record.action_id == "action-1"
    assert record.status == ApprovalStatus.PENDING
    assert record.reason == "protected path"


def test_approved_action_can_be_consumed_once():
    manager = ApprovalManager()
    manager.request("action-1", reason="protected path")
    manager.approve("action-1")

    assert manager.consume("action-1") is True
    with pytest.raises(ApprovalError) as exc_info:
        manager.consume("action-1")

    assert str(exc_info.value) == "approval already consumed"


def test_reject_returns_feedback_result():
    manager = ApprovalManager()
    manager.request("action-1", reason="protected path")

    feedback = manager.reject("action-1", reason="too risky")

    assert feedback.success is False
    assert feedback.category == ResultCategory.APPROVAL_REJECTED
    assert feedback.action_id == "action-1"
    assert "too risky" in feedback.observation


def test_expired_approval_cannot_be_approved_or_consumed():
    manager = ApprovalManager()
    manager.request("action-1", reason="protected path")
    manager.expire("action-1")

    with pytest.raises(ApprovalError) as approve_error:
        manager.approve("action-1")
    with pytest.raises(ApprovalError) as consume_error:
        manager.consume("action-1")

    assert str(approve_error.value) == "approval is expired"
    assert str(consume_error.value) == "approval is expired"
