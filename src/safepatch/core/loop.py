from __future__ import annotations

from collections.abc import Awaitable, Callable
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


ToolExecutor = Callable[[AgentAction], Awaitable[ToolResult]]


class LoopRunResult(StrictModel):
    state: RunState
    events: list[Event] = Field(default_factory=list)
    feedback: ToolResult | None = None
    final_message: str | None = None
    pending_action: AgentAction | None = None


class _EventRecorder:
    def __init__(self, run_id: str) -> None:
        self._run_id = run_id
        self._sequence = 0
        self.events: list[Event] = []

    def add(self, event_type: EventType, payload: dict[str, Any] | None = None) -> None:
        self._sequence += 1
        self.events.append(
            Event(
                run_id=self._run_id,
                sequence=self._sequence,
                type=event_type,
                payload=payload or {},
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

        budget_decision = self._budget.check(step=state.step)
        if budget_decision.should_stop:
            feedback = ToolResult(
                action_id="budget",
                success=False,
                category=ResultCategory.TIMEOUT,
                observation=budget_decision.reason or "budget exhausted",
            )
            state = transition_run_state(state, RunStatus.BUDGET_EXHAUSTED)
            recorder.add(
                EventType.FEEDBACK_BUILT,
                {"category": feedback.category.value},
            )
            recorder.add(
                EventType.RUN_FINISHED,
                {"status": state.status.value, "step": state.step},
            )
            return LoopRunResult(
                state=state,
                events=recorder.events,
                feedback=feedback,
            )

        messages = self._build_messages(task, prior_feedback or [])
        recorder.add(EventType.CONTEXT_BUILT, {"message_count": len(messages)})
        request = LLMRequest(run_id=run_id, step=state.step, messages=messages)
        recorder.add(EventType.LLM_REQUESTED, {"step": state.step})
        response = await self._provider.complete(request)
        recorder.add(
            EventType.LLM_RESPONSE,
            {"provider_name": response.provider_name, "metadata": response.metadata},
        )

        try:
            action = parse_action(response.content)
        except ActionParseError as exc:
            feedback = ToolResult(
                action_id="parse",
                success=False,
                category=ResultCategory.PARSE_ERROR,
                observation=f"invalid action: {exc}",
                metadata={"raw": response.content},
            )
            recorder.add(
                EventType.PARSE_FAILED,
                {"category": feedback.category.value, "observation": feedback.observation},
            )
            state = transition_run_state(state, RunStatus.FAILED)
            state = state.model_copy(update={"step": state.step + 1})
            recorder.add(
                EventType.FEEDBACK_BUILT,
                {"category": feedback.category.value},
            )
            recorder.add(
                EventType.RUN_FINISHED,
                {"status": state.status.value, "step": state.step},
            )
            return LoopRunResult(
                state=state,
                events=recorder.events,
                feedback=feedback,
            )

        recorder.add(EventType.ACTION_PARSED, {"type": action.type})
        if self._policy_engine is not None:
            decision = self._policy_engine.evaluate(action)
            recorder.add(
                EventType.POLICY_DECISION,
                {"status": decision.status.value, "reason": decision.reason},
            )
            if decision.status == DecisionStatus.DENY:
                feedback = ToolResult(
                    action_id=self._action_id(state, action),
                    success=False,
                    category=ResultCategory.POLICY_DENIED,
                    observation=decision.reason,
                    metadata=decision.metadata,
                )
                state = transition_run_state(state, RunStatus.FAILED)
                state = state.model_copy(update={"step": state.step + 1})
                recorder.add(
                    EventType.FEEDBACK_BUILT,
                    {"category": feedback.category.value},
                )
                recorder.add(
                    EventType.RUN_FINISHED,
                    {"status": state.status.value, "step": state.step},
                )
                return LoopRunResult(
                    state=state,
                    events=recorder.events,
                    feedback=feedback,
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
                    {"action_id": action_id, "reason": decision.reason},
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
            state = transition_run_state(state, target)
            state = state.model_copy(update={"step": state.step + 1})
            recorder.add(
                EventType.RUN_FINISHED,
                {"status": state.status.value, "step": state.step},
            )
            return LoopRunResult(
                state=state,
                events=recorder.events,
                final_message=action.message,
            )

        if self._tool_executor is None:
            feedback = ToolResult(
                action_id=action.type,
                success=False,
                category=ResultCategory.TOOL_ERROR,
                observation=f"no tool executor configured for action: {action.type}",
            )
        else:
            feedback = await self._tool_executor(action)
        state = transition_run_state(state, RunStatus.FAILED)
        state = state.model_copy(update={"step": state.step + 1})
        recorder.add(EventType.FEEDBACK_BUILT, {"category": feedback.category.value})
        recorder.add(EventType.RUN_FINISHED, {"status": state.status.value})
        return LoopRunResult(state=state, events=recorder.events, feedback=feedback)

    async def resume_approved(
        self,
        state: RunState,
        action: AgentAction | None,
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

        try:
            self._approval_manager.consume(state.pending_action_id)
        except ApprovalError as exc:
            feedback = ToolResult(
                action_id=state.pending_action_id,
                success=False,
                category=ResultCategory.APPROVAL_REJECTED,
                observation=f"approval rejected: {exc}",
            )
            return LoopRunResult(state=state, events=recorder.events, feedback=feedback)

        running = transition_run_state(state, RunStatus.RUNNING)
        recorder.add(
            EventType.APPROVAL_DECIDED,
            {"action_id": state.pending_action_id, "status": "approved"},
        )
        if self._tool_executor is None:
            feedback = ToolResult(
                action_id=state.pending_action_id,
                success=False,
                category=ResultCategory.TOOL_ERROR,
                observation=f"no tool executor configured for action: {action.type}",
            )
        else:
            feedback = await self._tool_executor(action)
        recorder.add(EventType.TOOL_FINISHED, {"category": feedback.category.value})
        return LoopRunResult(state=running, events=recorder.events, feedback=feedback)

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
            self._feedback_builder.build_message(result)
            for result in prior_feedback
        )
        return messages

    def _action_id(self, state: RunState, action: AgentAction) -> str:
        return f"step-{state.step}:{action.type}"
