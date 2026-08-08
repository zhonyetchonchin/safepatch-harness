from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import Field

from safepatch.core.models import NonEmptyStr, ResultCategory, StrictModel, ToolResult


class ApprovalError(ValueError):
    pass


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CONSUMED = "consumed"


class ApprovalRecord(StrictModel):
    action_id: NonEmptyStr
    status: ApprovalStatus
    reason: NonEmptyStr
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    decided_at: datetime | None = None


class ApprovalManager:
    def __init__(self) -> None:
        self._records: dict[str, ApprovalRecord] = {}

    def request(self, action_id: str, *, reason: str) -> ApprovalRecord:
        record = ApprovalRecord(
            action_id=action_id,
            status=ApprovalStatus.PENDING,
            reason=reason,
        )
        self._records[action_id] = record
        return record

    def approve(self, action_id: str) -> ApprovalRecord:
        record = self._require(action_id)
        self._ensure_pending(record)
        updated = record.model_copy(
            update={
                "status": ApprovalStatus.APPROVED,
                "decided_at": datetime.now(timezone.utc),
            }
        )
        self._records[action_id] = updated
        return updated

    def reject(self, action_id: str, *, reason: str) -> ToolResult:
        record = self._require(action_id)
        self._ensure_pending(record)
        updated = record.model_copy(
            update={
                "status": ApprovalStatus.REJECTED,
                "decided_at": datetime.now(timezone.utc),
            }
        )
        self._records[action_id] = updated
        return ToolResult(
            action_id=action_id,
            success=False,
            category=ResultCategory.APPROVAL_REJECTED,
            observation=f"approval rejected: {reason}",
            metadata={"approval_reason": record.reason, "rejection_reason": reason},
        )

    def expire(self, action_id: str) -> ApprovalRecord:
        record = self._require(action_id)
        self._ensure_pending(record)
        updated = record.model_copy(
            update={
                "status": ApprovalStatus.EXPIRED,
                "decided_at": datetime.now(timezone.utc),
            }
        )
        self._records[action_id] = updated
        return updated

    def consume(self, action_id: str) -> bool:
        record = self._require(action_id)
        if record.status == ApprovalStatus.CONSUMED:
            raise ApprovalError("approval already consumed")
        if record.status == ApprovalStatus.EXPIRED:
            raise ApprovalError("approval is expired")
        if record.status != ApprovalStatus.APPROVED:
            raise ApprovalError(f"approval is not approved: {record.status.value}")
        self._records[action_id] = record.model_copy(
            update={"status": ApprovalStatus.CONSUMED}
        )
        return True

    def get(self, action_id: str) -> ApprovalRecord:
        return self._require(action_id)

    def _require(self, action_id: str) -> ApprovalRecord:
        try:
            return self._records[action_id]
        except KeyError as exc:
            raise ApprovalError("approval not found") from exc

    def _ensure_pending(self, record: ApprovalRecord) -> None:
        if record.status == ApprovalStatus.EXPIRED:
            raise ApprovalError("approval is expired")
        if record.status != ApprovalStatus.PENDING:
            raise ApprovalError(f"approval is not pending: {record.status.value}")
