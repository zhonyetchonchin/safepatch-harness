from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator

from safepatch.core.models import StrictModel


class SafePatchConfig(StrictModel):
    workspace_root: Path
    allowed_checks: dict[str, list[str]] = Field(default_factory=dict)
    denied_paths: set[str] = Field(default_factory=lambda: {".env"})
    protected_paths: set[str] = Field(
        default_factory=lambda: {
            "requirements.txt",
            "pyproject.toml",
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
        }
    )
    diff_line_budget: int = Field(default=200, ge=1)
    max_steps: int = Field(default=20, ge=1)
    max_seconds: int = Field(default=600, ge=1)
    max_consecutive_failures: int = Field(default=3, ge=1)
    provider_name: str = "mock"
    demo_mode: bool = True

    @field_validator("workspace_root")
    @classmethod
    def _workspace_root_must_be_absolute(cls, value: Path) -> Path:
        return value.resolve()

    @field_validator("allowed_checks", mode="before")
    @classmethod
    def _allowed_checks_must_be_argv(
        cls,
        value: Any,
    ) -> dict[str, list[str]]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("allowed_checks must be a mapping")
        normalized: dict[str, list[str]] = {}
        for name, command in value.items():
            if not isinstance(command, list):
                raise ValueError("allowed check command must be a list")
            normalized[str(name)] = [str(part) for part in command]
        return normalized

    def is_check_allowed(self, name: str) -> bool:
        return name in self.allowed_checks


def load_config(
    path: str | Path,
    *,
    workspace_root: str | Path | None = None,
) -> SafePatchConfig:
    config_path = Path(path)
    root = Path(workspace_root) if workspace_root is not None else config_path.parent
    if not config_path.exists():
        return SafePatchConfig(workspace_root=root)

    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("config file must contain a mapping")
    data.setdefault("workspace_root", root)
    return SafePatchConfig(**data)
