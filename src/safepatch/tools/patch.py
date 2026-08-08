from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from safepatch.core.models import ResultCategory, ToolResult


_HUNK_RE = re.compile(r"^@@ -(?P<old_start>\d+)(?:,\d+)? \+(?P<new_start>\d+)(?:,\d+)? @@")


@dataclass(frozen=True)
class _Hunk:
    old_start: int
    lines: list[str]


@dataclass(frozen=True)
class _FilePatch:
    path: str
    hunks: list[_Hunk]


class PatchTool:
    def __init__(self, workspace_root: str | Path) -> None:
        self._root = Path(workspace_root).resolve()

    def apply_patch(self, patch_text: str) -> ToolResult:
        try:
            patches = self._parse(patch_text)
            planned_writes: list[tuple[Path, str]] = []
            for file_patch in patches:
                target = self._resolve_patch_path(file_patch.path)
                if target is None:
                    return self._denied("outside workspace")
                if not target.is_file():
                    return self._conflict(f"file not found: {file_patch.path}")
                original = target.read_text(encoding="utf-8")
                updated = self._apply_to_text(original, file_patch)
                planned_writes.append((target, updated))
        except _PatchConflict as exc:
            return self._conflict(str(exc))
        except UnicodeDecodeError:
            return self._conflict("file is not valid utf-8")

        for path, content in planned_writes:
            path.write_text(content, encoding="utf-8")

        return ToolResult(
            action_id="apply_patch",
            success=True,
            category=ResultCategory.SUCCESS,
            observation=f"applied patch to {len(planned_writes)} file(s)",
            metadata={"files": [self._relative(path) for path, _ in planned_writes]},
        )

    def _parse(self, patch_text: str) -> list[_FilePatch]:
        lines = patch_text.splitlines()
        patches: list[_FilePatch] = []
        index = 0
        while index < len(lines):
            if not lines[index].startswith("--- "):
                index += 1
                continue
            if index + 1 >= len(lines) or not lines[index + 1].startswith("+++ "):
                raise _PatchConflict("missing target file header")
            path = self._strip_diff_prefix(lines[index + 1][4:].strip())
            index += 2
            hunks: list[_Hunk] = []
            while index < len(lines) and not lines[index].startswith("--- "):
                match = _HUNK_RE.match(lines[index])
                if match is None:
                    index += 1
                    continue
                old_start = int(match.group("old_start"))
                index += 1
                hunk_lines: list[str] = []
                while index < len(lines):
                    line = lines[index]
                    if line.startswith("@@ ") or line.startswith("--- "):
                        break
                    if not line or line[0] not in {" ", "+", "-", "\\"}:
                        raise _PatchConflict("invalid hunk line")
                    if line.startswith("\\"):
                        index += 1
                        continue
                    hunk_lines.append(line)
                    index += 1
                hunks.append(_Hunk(old_start=old_start, lines=hunk_lines))
            if not hunks:
                raise _PatchConflict("patch has no hunks")
            patches.append(_FilePatch(path=path, hunks=hunks))
        if not patches:
            raise _PatchConflict("patch has no files")
        return patches

    def _apply_to_text(self, original: str, file_patch: _FilePatch) -> str:
        original_lines = original.splitlines(keepends=True)
        output: list[str] = []
        cursor = 0

        for hunk in file_patch.hunks:
            hunk_start = hunk.old_start - 1
            if hunk_start < cursor:
                raise _PatchConflict("overlapping hunks")
            output.extend(original_lines[cursor:hunk_start])
            cursor = hunk_start
            for hunk_line in hunk.lines:
                marker = hunk_line[0]
                content = hunk_line[1:] + "\n"
                if marker == " ":
                    if cursor >= len(original_lines) or original_lines[cursor] != content:
                        raise _PatchConflict("context mismatch")
                    output.append(original_lines[cursor])
                    cursor += 1
                elif marker == "-":
                    if cursor >= len(original_lines) or original_lines[cursor] != content:
                        raise _PatchConflict("context mismatch")
                    cursor += 1
                elif marker == "+":
                    output.append(content)
        output.extend(original_lines[cursor:])
        return "".join(output)

    def _resolve_patch_path(self, path: str) -> Path | None:
        candidate = Path(path)
        if candidate.is_absolute():
            return None
        resolved = (self._root / candidate).resolve()
        try:
            resolved.relative_to(self._root)
        except ValueError:
            return None
        return resolved

    def _strip_diff_prefix(self, path: str) -> str:
        if path.startswith("b/") or path.startswith("a/"):
            return path[2:]
        return path

    def _relative(self, path: Path) -> str:
        return path.relative_to(self._root).as_posix()

    def _denied(self, observation: str) -> ToolResult:
        return ToolResult(
            action_id="apply_patch",
            success=False,
            category=ResultCategory.POLICY_DENIED,
            observation=observation,
        )

    def _conflict(self, observation: str) -> ToolResult:
        return ToolResult(
            action_id="apply_patch",
            success=False,
            category=ResultCategory.PATCH_CONFLICT,
            observation=observation,
        )


class _PatchConflict(ValueError):
    pass
