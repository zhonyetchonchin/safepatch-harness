from pathlib import Path

from safepatch.config import SafePatchConfig, load_config


def test_missing_config_uses_safe_defaults(tmp_path: Path):
    config = load_config(tmp_path / "missing.yml", workspace_root=tmp_path)

    assert config.workspace_root == tmp_path.resolve()
    assert config.allowed_checks == {}
    assert config.is_check_allowed("unit-test") is False
    assert ".env" in config.denied_paths


def test_load_config_reads_allowed_checks(tmp_path: Path):
    config_file = tmp_path / "safepatch.yml"
    config_file.write_text(
        """
allowed_checks:
  unit-test:
    - python
    - -m
    - pytest
protected_paths:
  - pyproject.toml
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_file, workspace_root=tmp_path)

    assert config.allowed_checks == {"unit-test": ["python", "-m", "pytest"]}
    assert config.is_check_allowed("unit-test") is True
    assert config.protected_paths == {"pyproject.toml"}


def test_config_rejects_string_shell_command(tmp_path: Path):
    config_file = tmp_path / "safepatch.yml"
    config_file.write_text(
        "allowed_checks:\n  unit-test: python -m pytest\n",
        encoding="utf-8",
    )

    try:
        load_config(config_file, workspace_root=tmp_path)
    except ValueError as exc:
        assert "allowed check command must be a list" in str(exc)
    else:
        raise AssertionError("expected config validation failure")


def test_config_model_forbids_unknown_fields(tmp_path: Path):
    try:
        SafePatchConfig(workspace_root=tmp_path, unknown=True)
    except ValueError as exc:
        assert "Extra inputs are not permitted" in str(exc)
    else:
        raise AssertionError("expected config validation failure")
