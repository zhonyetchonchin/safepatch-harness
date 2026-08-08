from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from safepatch.core.models import ToolResult
from safepatch.policy.approval import ApprovalError, ApprovalManager, ApprovalRecord


class RejectApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1)


def approval_router() -> APIRouter:
    router = APIRouter(prefix="/approvals", tags=["approvals"])

    @router.get("/{action_id}")
    def get_approval(action_id: str, request: Request):
        manager = _approval_manager(request)
        try:
            return _approval_response(manager.get(action_id))
        except ApprovalError as exc:
            _raise_approval_error(exc)

    @router.post("/{action_id}/approve")
    def approve(action_id: str, request: Request):
        manager = _approval_manager(request)
        try:
            record = manager.approve(action_id)
            handler = getattr(request.app.state, "approval_handler", None)
            if handler is not None:
                handler.approve(action_id)
            return _approval_response(record)
        except ApprovalError as exc:
            _raise_approval_error(exc)

    @router.post("/{action_id}/reject")
    def reject(
        action_id: str,
        body: RejectApprovalRequest,
        request: Request,
    ):
        manager = _approval_manager(request)
        try:
            feedback = manager.reject(action_id, reason=body.reason)
            record = manager.get(action_id)
            handler = getattr(request.app.state, "approval_handler", None)
            if handler is not None:
                handler.reject(action_id, feedback)
            response = _approval_response(record)
            response["feedback"] = _feedback_response(feedback)
            return response
        except ApprovalError as exc:
            _raise_approval_error(exc)

    return router


def _approval_manager(request: Request) -> ApprovalManager:
    return request.app.state.approval_manager


def _approval_response(record: ApprovalRecord) -> dict[str, str | None]:
    return {
        "action_id": record.action_id,
        "status": record.status.value,
        "reason": record.reason,
        "created_at": record.created_at.isoformat(),
        "decided_at": record.decided_at.isoformat()
        if record.decided_at is not None
        else None,
    }


def _feedback_response(result: ToolResult) -> dict[str, object]:
    return {
        "action_id": result.action_id,
        "success": result.success,
        "category": result.category.value,
        "observation": result.observation,
        "metadata": result.metadata,
    }


def _raise_approval_error(exc: ApprovalError) -> None:
    status_code = 404 if str(exc) == "approval not found" else 409
    raise HTTPException(status_code=status_code, detail=str(exc)) from exc
