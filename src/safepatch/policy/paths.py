from __future__ import annotations

from pathlib import Path


class PathPolicyError(ValueError):
    pass


class PathPolicy:
    def __init__(self, workspace_root: str | Path) -> None:
        self._root = Path(workspace_root).resolve()

    def resolve(self, path: str | Path) -> Path:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self._root / candidate
        resolved = candidate.resolve()
        try:
            resolved.relative_to(self._root)
        except ValueError as exc:
            raise PathPolicyError("path is outside workspace") from exc
        return resolved
