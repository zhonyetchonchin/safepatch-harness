from __future__ import annotations

import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

from safepatch.core.models import ResultCategory, ToolResult


class CheckTool:
    def __init__(
        self,
        workspace_root: str | Path,
        *,
        allowed_checks: Mapping[str, Sequence[str]],
        timeout_seconds: float = 30.0,
    ) -> None:
        self._root = Path(workspace_root).resolve()
        self._allowed_checks = {
            name: [str(part) for part in command]
            for name, command in allowed_checks.items()
        }
        self._timeout_seconds = timeout_seconds

    def run_check(self, name: str) -> ToolResult:
        command = self._allowed_checks.get(name)
        if command is None:
            return ToolResult(
                action_id="run_check",
                success=False,
                category=ResultCategory.POLICY_DENIED,
                observation=f"check is not allowlisted: {name}",
            )
        try:
            completed = subprocess.run(
                command,
                cwd=self._root,
                capture_output=True,
                text=True,
                shell=False,
                timeout=self._timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return ToolResult(
                action_id="run_check",
                success=False,
                category=ResultCategory.TIMEOUT,
                observation=f"check timed out: {name}",
                metadata={
                    "stdout": exc.stdout or "",
                    "stderr": exc.stderr or "",
                },
            )
        except OSError as exc:
            return ToolResult(
                action_id="run_check",
                success=False,
                category=ResultCategory.TOOL_ERROR,
                observation=f"failed to start check: {exc}",
            )

        success = completed.returncode == 0
        return ToolResult(
            action_id="run_check",
            success=success,
            category=ResultCategory.SUCCESS
            if success
            else ResultCategory.CHECK_FAILED,
            observation="check passed" if success else "check failed",
            metadata={
                "name": name,
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            },
        )
