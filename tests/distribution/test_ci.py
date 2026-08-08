from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def test_gitlab_ci_defines_unit_test_job():
    ci = yaml.safe_load((ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8"))

    assert "unit-test" in ci
    job = ci["unit-test"]
    assert job["image"] == "python:3.12-slim"
    assert job["stage"] == "test"
    script = "\n".join(job["script"])
    assert "python -m pip install -e \".[dev]\"" in script
    assert "python -m pytest -q" in script
