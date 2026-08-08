from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from pydantic import Field

from safepatch.core.budget import RunBudget
from safepatch.core.feedback import FeedbackBuilder
from safepatch.core.models import (
    ActionParseError,
    AgentAction,
    Event,
    EventType,
    FinishAction,
    ResultCategory,
    RunState,
    RunStatus,
    StrictModel,
    ToolResult,
    parse_action,
    transition_run_state,
)
from safepatch.core.provider import LLMMessage, LLMProvider, LLMRequest
from safepatch.policy.approval import ApprovalError, ApprovalManager
from safepatch.policy.engine import DecisionStatus, PolicyEngine
from safepatch.security.redaction import redact_payload


ToolExecutor = Callable[[AgentAction], Awaitable[ToolResult]]


class LoopRunResult(StrictModel):
    state: RunState
    events: list[Event] = Field(default_factory=list)
    feedback: ToolResult | None = None
    final_message: str | None = None
    pending_action: AgentAction | None = None


class _EventRecorder:
    def __init__(self, run_id: str, *, start_sequence: int = 0) -> None:
        self._run_id = run_id
        self._sequence = start_sequence
        self.events: list[Event] = []

    def add(self, event_type: EventType, payload: dict[str, Any] | None = None) -> None:
        self._sequence += 1
        self.events.append(
            Event(
                run_id=self._run_id,
                sequence=self._sequence,
                type=event_type,
                payload=redact_payload(payload or {}),
            )
        )


class AgentLoop:
    def __init__(
        self,
        provider: LLMProvider,
        tool_executor: ToolExecutor | None = None,
        budget: RunBudget | None = None,
        feedback_builder: FeedbackBuilder | None = None,
        policy_engine: PolicyEngine | None = None,
        approval_manager: ApprovalManager | None = None,
    ) -> None:
        self._provider = provider
        self._tool_executor = tool_executor
        self._budget = budget or RunBudget()
        self._feedback_builder = feedback_builder or FeedbackBuilder()
        self._policy_engine = policy_engine
        self._approval_manager = approval_manager or ApprovalManager()

    async def run(
        self,
        run_id: str,
        task: str,
        *,
        initial_step: int = 0,
        prior_feedback: list[ToolResult] | None = None,
    ) -> LoopRunResult:
        recorder = _EventRecorder(run_id)
        state = RunState(run_id=run_id, status=RunStatus.CREATED, step=initial_step)
        recorder.add(EventType.RUN_CREATED, {"task": task})
        state = transition_run_state(state, RunStatus.RUNNING)
        recorder.add(
            EventType.STATE_CHANGED,
            {"status": state.status.value, "step": state.step},
        )
        feedback = prior_feedback or []
        return await self._continue(
            state=state,
            messages=self._build_messages(task, feedback),
            recorder=recorder,
            started_at=datetime.now(timezone.utc),
            consecutive_failures=sum(not item.success for item in feedback),
        )

    async def resume_approved(
        self,
        state: RunState,
        action: AgentAction | None,
        *,
        task: str | None = None,
    ) -> LoopRunResult:
        recorder = _EventRecorder(state.run_id)
        if action is None or state.pending_action_id is None:
            feedback = ToolResult(
                action_id="approval",
                success=False,
                category=ResultCategory.APPROVAL_REJECTED,
                observation="missing pending action",
            )
            return LoopRunResult(state=state, events=recorder.events, feedback=feedback)

        action_id = state.pending_action_id
        try:
            self._approval_manager.consume(action_id)
        except ApprovalError as exc:
            feedback = ToolResult(
                action_id=action_id,
                success=False,
                category=ResultCategory.APPROVAL_REJECTED,
                observation=f"approval rejected: {exc}",
            )
            return LoopRunResult(state=state, events=recorder.events, feedback=feedback)

        running = transition_run_state(state, RunStatus.RUNNING)
        recorder.add(
            EventType.APPROVAL_DECIDED,
            {"action_id": action_id, "status": "approved"},
        )
        recorder.add(
            EventType.STATE_CHANGED,
            {"status": running.status.value, "step": running.step},
        )
        feedback = await self._execute_tool(
            action=action,
            action_id=action_id,
            state=running,
            recorder=recorder,
        )
        running = running.model_copy(
            update={"step": running.step + 1, "updated_at": datetime.now(timezone.utc)}
        )
        recorder.add(
            EventType.STATE_CHANGED,
            {"status": running.status.value, "step": running.step},
        )

        if feedback.category == ResultCategory.TOOL_ERROR:
            failed = transition_run_state(running, RunStatus.FAILED)
            recorder.add(
                EventType.RUN_FINISHED,
                {"status": failed.status.value, "step": failed.step},
            )
            return LoopRunResult(
                state=failed,
                events=recorder.events,
                feedback=feedback,
            )

        if task is None:
            return LoopRunResult(
                state=running,
                events=recorder.events,
                feedback=feedback,
            )

        messages = self._build_messages(task, [feedback])
        return await self._continue(
            state=running,
            messages=messages,
            recorder=recorder,
            started_at=datetime.now(timezone.utc),
            consecutive_failures=0 if feedback.success else 1,
        )

    async def _continue(
        self,
        *,
        state: RunState,
        messages: list[LLMMessage],
        recorder: _EventRecorder,
        started_at: datetime,
        consecutive_failures: int,
    ) -> LoopRunResult:
        last_feedback: ToolResult | None = None

        while True:
            budget_decision = self._budget.check(
                step=state.step,
                started_at=started_at,
                consecutive_failures=consecutive_failures,
            )
            if budget_decision.should_stop:
                last_feedback = ToolResult(
                    action_id="budget",
                    success=False,
                    category=ResultCategory.TIMEOUT,
                    observation=budget_decision.reason or "budget exhausted",
                )
                state = transition_run_state(state, RunStatus.BUDGET_EXHAUSTED)
                recorder.add(
                    EventType.FEEDBACK_BUILT,
                    self._feedback_payload(last_feedback),
                )
                recorder.add(
                    EventType.RUN_FINISHED,
                    {"status": state.status.value, "step": state.step},
                )
                return LoopRunResult(
                    state=state,
                    events=recorder.events,
                    feedback=last_feedback,
                )

            recorder.add(
                EventType.CONTEXT_BUILT,
                {"message_count": len(messages), "step": state.step},
            )
            request = LLMRequest(run_id=state.run_id, step=state.step, messages=messages)
            recorder.add(EventType.LLM_REQUESTED, {"step": state.step})
            try:
                response = await self._provider.complete(request)
            except Exception as exc:  # provider implementations are external ports
                last_feedback = ToolResult(
                    action_id="provider",
                    success=False,
                    category=ResultCategory.TOOL_ERROR,
                    observation=f"provider request failed: {type(exc).__name__}",
                )
                recorder.add(
                    EventType.FEEDBACK_BUILT,
                    self._feedback_payload(last_feedback),
                )
                state = transition_run_state(state, RunStatus.FAILED)
                recorder.add(
                    EventType.RUN_FINISHED,
                    {"status": state.status.value, "step": state.step},
                )
                return LoopRunResult(
                    state=state,
                    events=recorder.events,
                    feedback=last_feedback,
                )

            recorder.add(
                EventType.LLM_RESPONSE,
                {
                    "provider_name": response.provider_name,
                    "metadata": response.metadata,
                },
            )

            try:
                action = parse_action(response.content)
            except ActionParseError as exc:
                last_feedback = ToolResult(
                    action_id="parse",
                    success=False,
                    category=ResultCategory.PARSE_ERROR,
                    observation=f"invalid action: {exc}",
                    metadata={"raw": response.content},
                )
                recorder.add(
                    EventType.PARSE_FAILED,
                    self._feedback_payload(last_feedback),
                )
                state = self._advance_to_terminal(state, RunStatus.FAILED)
                recorder.add(
                    EventType.FEEDBACK_BUILT,
                    self._feedback_payload(last_feedback),
                )
                recorder.add(
                    EventType.RUN_FINISHED,
                    {"status": state.status.value, "step": state.step},
                )
                return LoopRunResult(
                    state=state,
                    events=recorder.events,
                    feedback=last_feedback,
                )

            recorder.add(
                EventType.ACTION_PARSED,
                {"type": action.type, "action": action.model_dump(mode="json")},
            )

            if self._policy_engine is not None:
                decision = self._policy_engine.evaluate(action)
                recorder.add(
                    EventType.POLICY_DECISION,
                    {
                        "status": decision.status.value,
                        "reason": decision.reason,
                        "metadata": decision.metadata,
                    },
                )
                if decision.status == DecisionStatus.DENY:
                    last_feedback = ToolResult(
                        action_id=self._action_id(state, action),
                        success=False,
                        category=ResultCategory.POLICY_DENIED,
                        observation=decision.reason,
                        metadata=decision.metadata,
                    )
                    state = self._advance_to_terminal(state, RunStatus.FAILED)
                    recorder.add(
                        EventType.FEEDBACK_BUILT,
                        self._feedback_payload(last_feedback),
                    )
                    recorder.add(
                        EventType.RUN_FINISHED,
                        {"status": state.status.value, "step": state.step},
                    )
                    return LoopRunResult(
                        state=state,
                        events=recorder.events,
                        feedback=last_feedback,
                    )
                if decision.status == DecisionStatus.REQUIRES_APPROVAL:
                    action_id = self._action_id(state, action)
                    self._approval_manager.request(action_id, reason=decision.reason)
                    state = transition_run_state(
                        state,
                        RunStatus.PAUSED_FOR_APPROVAL,
                        pending_action_id=action_id,
                    )
                    recorder.add(
                        EventType.APPROVAL_REQUESTED,
                        {
                            "action_id": action_id,
                            "reason": decision.reason,
                            "action": action.model_dump(mode="json"),
                        },
                    )
                    recorder.add(
                        EventType.RUN_FINISHED,
                        {"status": state.status.value, "step": state.step},
                    )
                    return LoopRunResult(
                        state=state,
                        events=recorder.events,
                        pending_action=action,
                    )

            if isinstance(action, FinishAction):
                target = (
                    RunStatus.COMPLETED
                    if action.status == "completed"
                    else RunStatus.FAILED
                )
                state = self._advance_to_terminal(state, target)
                recorder.add(
                    EventType.RUN_FINISHED,
                    {
                        "status": state.status.value,
                        "step": state.step,
                        "message": action.message,
                    },
                )
                return LoopRunResult(
                    state=state,
                    events=recorder.events,
                    feedback=last_feedback,
                    final_message=action.message,
                )

            action_id = self._action_id(state, action)
            last_feedback = await self._execute_tool(
                action=action,
                action_id=action_id,
                state=state,
                recorder=recorder,
            )
            state = state.model_copy(
                update={"step": state.step + 1, "updated_at": datetime.now(timezone.utc)}
            )
            recorder.add(
                EventType.STATE_CHANGED,
                {"status": state.status.value, "step": state.step},
            )

            if last_feedback.category == ResultCategory.TOOL_ERROR:
                state = transition_run_state(state, RunStatus.FAILED)
                recorder.add(
                    EventType.RUN_FINISHED,
                    {"status": state.status.value, "step": state.step},
                )
                return LoopRunResult(
                    state=state,
                    events=recorder.events,
                    feedback=last_feedback,
                )

            messages.append(LLMMessage(role="assistant", content=response.content))
            messages.append(self._feedback_builder.build_message(last_feedback))
            consecutive_failures = 0 if last_feedback.success else consecutive_failures + 1

    async def _execute_tool(
        self,
        *,
        action: AgentAction,
        action_id: str,
        state: RunState,
        recorder: _EventRecorder,
    ) -> ToolResult:
        recorder.add(
            EventType.TOOL_STARTED,
            {"action_id": action_id, "type": action.type, "step": state.step},
        )
        if self._tool_executor is None:
            feedback = ToolResult(
                action_id=action_id,
                success=False,
                category=ResultCategory.TOOL_ERROR,
                observation=f"no tool executor configured for action: {action.type}",
            )
        else:
            try:
                feedback = await self._tool_executor(action)
                if not isinstance(feedback, ToolResult):
                    raise TypeError("tool executor must return ToolResult")
            except Exception as exc:  # tool adapters must not crash the loop
                feedback = ToolResult(
                    action_id=action_id,
                    success=False,
                    category=ResultCategory.TOOL_ERROR,
                    observation=f"tool execution failed: {type(exc).__name__}",
                )
        recorder.add(EventType.TOOL_FINISHED, self._feedback_payload(feedback))
        recorder.add(EventType.FEEDBACK_BUILT, self._feedback_payload(feedback))
        return feedback

    def _build_messages(
        self,
        task: str,
        prior_feedback: list[ToolResult],
    ) -> list[LLMMessage]:
        messages = [
            LLMMessage(
                role="system",
                content="Return exactly one SafePatch JSON action.",
            ),
            LLMMessage(role="user", content=task),
        ]
        messages.extend(
            self._feedback_builder.build_message(result) for result in prior_feedback
        )
        return messages

    def _action_id(self, state: RunState, action: AgentAction) -> str:
        return f"{state.run_id}:step-{state.step}:{action.type}"

    def _advance_to_terminal(self, state: RunState, target: RunStatus) -> RunState:
        terminal = transition_run_state(state, target)
        return terminal.model_copy(
            update={"step": state.step + 1, "updated_at": datetime.now(timezone.utc)}
        )

    def _feedback_payload(self, feedback: ToolResult) -> dict[str, Any]:
        return {
            "action_id": feedback.action_id,
            "success": feedback.success,
            "category": feedback.category.value,
            "observation": feedback.observation,
            "metadata": feedback.metadata,
        }
