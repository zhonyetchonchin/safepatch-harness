import os
from pathlib import Path

import pytest

from safepatch.policy.paths import PathPolicy, PathPolicyError


def test_resolve_workspace_path_allows_inside_file(tmp_path: Path):
    target = tmp_path / "src" / "app.py"
    target.parent.mkdir()
    target.write_text("", encoding="utf-8")

    resolved = PathPolicy(tmp_path).resolve("src/app.py")

    assert resolved == target.resolve()


def test_resolve_workspace_path_rejects_parent_escape(tmp_path: Path):
    policy = PathPolicy(tmp_path)

    with pytest.raises(PathPolicyError) as exc_info:
        policy.resolve("../outside.txt")

    assert str(exc_info.value) == "path is outside workspace"


def test_resolve_workspace_path_rejects_absolute_escape(tmp_path: Path):
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("", encoding="utf-8")

    with pytest.raises(PathPolicyError) as exc_info:
        PathPolicy(tmp_path).resolve(str(outside))

    assert str(exc_info.value) == "path is outside workspace"


def test_resolve_workspace_path_rejects_symlink_escape(tmp_path: Path):
    outside_dir = tmp_path.parent / "outside"
    outside_dir.mkdir()
    outside_file = outside_dir / "secret.txt"
    outside_file.write_text("secret", encoding="utf-8")
    link = tmp_path / "link"
    try:
        os.symlink(outside_dir, link, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    with pytest.raises(PathPolicyError) as exc_info:
        PathPolicy(tmp_path).resolve("link/secret.txt")

    assert str(exc_info.value) == "path is outside workspace"
