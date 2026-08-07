from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal, TypeAlias
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)


NonEmptyStr: TypeAlias = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ActionParseError(ValueError):
    pass


class InvalidStateTransition(ValueError):
    pass


class ReadFileAction(StrictModel):
    type: Literal["read_file"]
    path: NonEmptyStr


class ListFilesAction(StrictModel):
    type: Literal["list_files"]
    glob: NonEmptyStr = "**/*"
    limit: int = Field(default=100, ge=1, le=500)


class SearchTextAction(StrictModel):
    type: Literal["search_text"]
    query: NonEmptyStr
    glob: NonEmptyStr | None = None
    limit: int = Field(default=50, ge=1, le=200)


class ApplyPatchAction(StrictModel):
    type: Literal["apply_patch"]
    patch: NonEmptyStr


class RunCheckAction(StrictModel):
    type: Literal["run_check"]
    name: NonEmptyStr


class RememberAction(StrictModel):
    type: Literal["remember"]
    kind: Literal[
        "project_convention",
        "user_decision",
        "failure_summary",
        "run_result",
    ]
    content: NonEmptyStr
    tags: list[NonEmptyStr] = Field(default_factory=list)


class FinishAction(StrictModel):
    type: Literal["finish"]
    status: Literal["completed", "failed", "needs_input"]
    message: NonEmptyStr


AgentAction: TypeAlias = Annotated[
    ReadFileAction
    | ListFilesAction
    | SearchTextAction
    | ApplyPatchAction
    | RunCheckAction
    | RememberAction
    | FinishAction,
    Field(discriminator="type"),
]

_ACTION_ADAPTER = TypeAdapter(AgentAction)


def parse_action(raw: str | dict[str, Any]) -> AgentAction:
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        return _ACTION_ADAPTER.validate_python(data)
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise ActionParseError("invalid action") from exc


class RunStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED_FOR_APPROVAL = "paused_for_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    BUDGET_EXHAUSTED = "budget_exhausted"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc)


class RunState(StrictModel):
    run_id: NonEmptyStr
    status: RunStatus
    step: int = Field(default=0, ge=0)
    pending_action_id: NonEmptyStr | None = None
    updated_at: datetime = Field(default_factory=_utc_now)

    @field_validator("updated_at")
    @classmethod
    def _updated_at_must_be_aware(cls, value: datetime) -> datetime:
        return _normalize_aware_datetime(value)

    @model_validator(mode="after")
    def _approval_state_must_match_pending_action(self) -> RunState:
        if self.status == RunStatus.PAUSED_FOR_APPROVAL:
            if self.pending_action_id is None:
                raise ValueError("pending_action_id is required for paused_for_approval")
        elif self.pending_action_id is not None:
            raise ValueError("pending_action_id is only valid for paused_for_approval")
        return self


_ALLOWED_TRANSITIONS: dict[RunStatus, set[RunStatus]] = {
    RunStatus.CREATED: {RunStatus.RUNNING, RunStatus.CANCELED},
    RunStatus.RUNNING: {
        RunStatus.RUNNING,
        RunStatus.PAUSED_FOR_APPROVAL,
        RunStatus.COMPLETED,
        RunStatus.FAILED,
        RunStatus.CANCELED,
        RunStatus.BUDGET_EXHAUSTED,
    },
    RunStatus.PAUSED_FOR_APPROVAL: {
        RunStatus.RUNNING,
        RunStatus.FAILED,
        RunStatus.CANCELED,
    },
    RunStatus.COMPLETED: set(),
    RunStatus.FAILED: set(),
    RunStatus.CANCELED: set(),
    RunStatus.BUDGET_EXHAUSTED: set(),
}


def transition_run_state(
    state: RunState,
    target: RunStatus,
    *,
    pending_action_id: str | None = None,
    now: datetime | None = None,
) -> RunState:
    target = RunStatus(target)
    if pending_action_id is not None and target != RunStatus.PAUSED_FOR_APPROVAL:
        raise ValueError("pending_action_id is only valid for paused_for_approval")
    if target == RunStatus.PAUSED_FOR_APPROVAL and not pending_action_id:
        raise ValueError("pending_action_id is required for paused_for_approval")
    if target not in _ALLOWED_TRANSITIONS[state.status]:
        message = f"invalid run status transition: {state.status.value} -> {target.value}"
        raise InvalidStateTransition(message)
    if now is None:
        updated_at = _utc_now()
    else:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        updated_at = now.astimezone(timezone.utc)
    return RunState(
        run_id=state.run_id,
        status=target,
        step=state.step,
        pending_action_id=pending_action_id
        if target == RunStatus.PAUSED_FOR_APPROVAL
        else None,
        updated_at=updated_at,
    )


class ResultCategory(str, Enum):
    SUCCESS = "success"
    PARSE_ERROR = "parse_error"
    POLICY_DENIED = "policy_denied"
    APPROVAL_REQUIRED = "approval_required"
    APPROVAL_REJECTED = "approval_rejected"
    PATCH_CONFLICT = "patch_conflict"
    CHECK_FAILED = "check_failed"
    TIMEOUT = "timeout"
    TOOL_ERROR = "tool_error"


class ToolResult(StrictModel):
    action_id: NonEmptyStr
    success: bool
    category: ResultCategory
    observation: NonEmptyStr
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    finished_at: datetime | None = None


class EventType(str, Enum):
    RUN_CREATED = "run_created"
    CONTEXT_BUILT = "context_built"
    LLM_REQUESTED = "llm_requested"
    LLM_RESPONSE = "llm_response"
    ACTION_PARSED = "action_parsed"
    PARSE_FAILED = "parse_failed"
    POLICY_DECISION = "policy_decision"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_DECIDED = "approval_decided"
    TOOL_STARTED = "tool_started"
    TOOL_FINISHED = "tool_finished"
    FEEDBACK_BUILT = "feedback_built"
    STATE_CHANGED = "state_changed"
    RUN_FINISHED = "run_finished"


class Event(StrictModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: NonEmptyStr
    sequence: int = Field(ge=1)
    type: EventType
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utc_now)

    @field_validator("id")
    @classmethod
    def _id_must_be_uuid(cls, value: str) -> str:
        return str(UUID(value))

    @field_validator("created_at")
    @classmethod
    def _created_at_must_be_aware(cls, value: datetime) -> datetime:
        return _normalize_aware_datetime(value)
