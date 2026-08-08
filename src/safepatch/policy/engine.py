from __future__ import annotations

from enum import Enum
from pathlib import PurePosixPath
from typing import Any

from pydantic import Field

from safepatch.core.models import (
    AgentAction,
    ApplyPatchAction,
    ListFilesAction,
    ReadFileAction,
    RunCheckAction,
    SearchTextAction,
    StrictModel,
)


class DecisionStatus(str, Enum):
    ALLOW = "allow"
    REQUIRES_APPROVAL = "requires_approval"
    DENY = "deny"


class PolicyDecision(StrictModel):
    status: DecisionStatus
    reason: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyEngine:
    def __init__(
        self,
        *,
        allowed_checks: set[str] | None = None,
        protected_paths: set[str] | None = None,
        sensitive_paths: set[str] | None = None,
    ) -> None:
        self._allowed_checks = allowed_checks or set()
        self._protected_paths = protected_paths or {
            "requirements.txt",
            "pyproject.toml",
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
        }
        self._sensitive_paths = sensitive_paths or {".env"}

    def evaluate(self, action: AgentAction) -> PolicyDecision:
        if isinstance(action, RunCheckAction):
            return self._evaluate_run_check(action)
        if isinstance(action, (ReadFileAction, ListFilesAction, SearchTextAction)):
            return self._evaluate_read_like(action)
        if isinstance(action, ApplyPatchAction):
            return self._evaluate_patch(action)
        return PolicyDecision(status=DecisionStatus.ALLOW, reason="allowed")

    def _evaluate_run_check(self, action: RunCheckAction) -> PolicyDecision:
        if _looks_dangerous(action.name):
            return PolicyDecision(
                status=DecisionStatus.DENY,
                reason=f"dangerous command denied: {action.name}",
            )
        if action.name not in self._allowed_checks:
            return PolicyDecision(
                status=DecisionStatus.DENY,
                reason=f"check is not allowlisted: {action.name}",
            )
        return PolicyDecision(status=DecisionStatus.ALLOW, reason="allowed")

    def _evaluate_read_like(
        self,
        action: ReadFileAction | ListFilesAction | SearchTextAction,
    ) -> PolicyDecision:
        path = getattr(action, "path", None) or getattr(action, "glob", None)
        if path is not None and self._is_sensitive(str(path)):
            return PolicyDecision(
                status=DecisionStatus.DENY,
                reason=f"sensitive path denied: {path}",
            )
        return PolicyDecision(status=DecisionStatus.ALLOW, reason="allowed")

    def _evaluate_patch(self, action: ApplyPatchAction) -> PolicyDecision:
        for path in _extract_patch_paths(action.patch):
            if self._is_sensitive(path):
                return PolicyDecision(
                    status=DecisionStatus.DENY,
                    reason=f"sensitive path denied: {path}",
                )
            if path in self._protected_paths:
                return PolicyDecision(
                    status=DecisionStatus.REQUIRES_APPROVAL,
                    reason=f"protected path requires approval: {path}",
                    metadata={"path": path},
                )
        return PolicyDecision(status=DecisionStatus.ALLOW, reason="allowed")

    def _is_sensitive(self, path: str) -> bool:
        parts = PurePosixPath(path.replace("\\", "/")).parts
        return any(part in self._sensitive_paths for part in parts)


def _looks_dangerous(value: str) -> bool:
    lowered = value.lower()
    dangerous_tokens = [
        "rm -rf",
        "del /s",
        "format",
        "git push",
        "curl ",
        "wget ",
    ]
    return any(token in lowered for token in dangerous_tokens)


def _extract_patch_paths(patch_text: str) -> list[str]:
    paths: list[str] = []
    for line in patch_text.splitlines():
        if not line.startswith("+++ "):
            continue
        path = line[4:].strip()
        if path.startswith("b/") or path.startswith("a/"):
            path = path[2:]
        paths.append(path.replace("\\", "/"))
    return paths
