from __future__ import annotations

from pathlib import Path

from safepatch.core.models import ResultCategory, ToolResult


DEFAULT_DENIED_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__"}
DEFAULT_SENSITIVE_NAMES = {".env"}
DEFAULT_SENSITIVE_SUFFIXES = {".key", ".pem"}


class FileTools:
    def __init__(self, workspace_root: str | Path) -> None:
        self._root = Path(workspace_root).resolve()

    def read_file(self, path: str, *, max_bytes: int = 200_000) -> ToolResult:
        resolved = self._resolve_user_path(path)
        if resolved is None:
            return self._denied("read_file", "outside workspace")
        if self._is_sensitive(resolved):
            return self._denied("read_file", "sensitive path denied")
        if not resolved.is_file():
            return self._error("read_file", "file not found")
        if resolved.stat().st_size > max_bytes:
            return self._error("read_file", "file too large")
        try:
            content = resolved.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return self._error("read_file", "file is not valid utf-8")
        return ToolResult(
            action_id="read_file",
            success=True,
            category=ResultCategory.SUCCESS,
            observation=content,
            metadata={"path": self._relative(resolved)},
        )

    def list_files(self, glob: str = "**/*", *, limit: int = 100) -> ToolResult:
        paths: list[str] = []
        for candidate in sorted(self._root.glob(glob)):
            if len(paths) >= limit:
                break
            if not candidate.is_file():
                continue
            resolved = candidate.resolve()
            if not self._is_inside_root(resolved):
                continue
            if self._is_denied_by_default(resolved) or self._is_sensitive(resolved):
                continue
            paths.append(self._relative(resolved))
        return ToolResult(
            action_id="list_files",
            success=True,
            category=ResultCategory.SUCCESS,
            observation=f"{len(paths)} file(s)",
            metadata={"paths": paths},
        )

    def search_text(
        self,
        query: str,
        *,
        glob: str = "**/*",
        limit: int = 50,
    ) -> ToolResult:
        matches: list[dict[str, object]] = []
        for file_path in self.list_files(glob, limit=10_000).metadata["paths"]:
            if len(matches) >= limit:
                break
            resolved = (self._root / str(file_path)).resolve()
            try:
                lines = resolved.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for line_number, line in enumerate(lines, start=1):
                if query in line:
                    matches.append(
                        {
                            "path": str(file_path),
                            "line": line_number,
                            "text": line,
                        }
                    )
                    if len(matches) >= limit:
                        break
        return ToolResult(
            action_id="search_text",
            success=True,
            category=ResultCategory.SUCCESS,
            observation=f"{len(matches)} match(es)",
            metadata={"matches": matches},
        )

    def _resolve_user_path(self, path: str) -> Path | None:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self._root / candidate
        resolved = candidate.resolve()
        if not self._is_inside_root(resolved):
            return None
        return resolved

    def _is_inside_root(self, path: Path) -> bool:
        try:
            path.relative_to(self._root)
        except ValueError:
            return False
        return True

    def _is_denied_by_default(self, path: Path) -> bool:
        relative_parts = path.relative_to(self._root).parts
        return any(part in DEFAULT_DENIED_DIRS for part in relative_parts)

    def _is_sensitive(self, path: Path) -> bool:
        relative_parts = path.relative_to(self._root).parts
        if any(part in DEFAULT_SENSITIVE_NAMES for part in relative_parts):
            return True
        return path.suffix.lower() in DEFAULT_SENSITIVE_SUFFIXES

    def _relative(self, path: Path) -> str:
        return path.relative_to(self._root).as_posix()

    def _denied(self, action_id: str, observation: str) -> ToolResult:
        return ToolResult(
            action_id=action_id,
            success=False,
            category=ResultCategory.POLICY_DENIED,
            observation=observation,
        )

    def _error(self, action_id: str, observation: str) -> ToolResult:
        return ToolResult(
            action_id=action_id,
            success=False,
            category=ResultCategory.TOOL_ERROR,
            observation=observation,
        )
