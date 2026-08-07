import sys
from pathlib import Path

from safepatch.core.models import ResultCategory
from safepatch.tools.checks import CheckTool


def test_run_check_rejects_non_allowlisted_command(tmp_path: Path):
    tool = CheckTool(tmp_path, allowed_checks={})

    result = tool.run_check("unit-test")

    assert result.success is False
    assert result.category == ResultCategory.POLICY_DENIED
    assert result.observation == "check is not allowlisted: unit-test"


def test_run_check_success_captures_output(tmp_path: Path):
    tool = CheckTool(
        tmp_path,
        allowed_checks={
            "hello": [sys.executable, "-c", "print('hello')"],
        },
    )

    result = tool.run_check("hello")

    assert result.success is True
    assert result.category == ResultCategory.SUCCESS
    assert result.metadata["returncode"] == 0
    assert result.metadata["stdout"] == "hello\n"


def test_run_check_failure_reports_check_failed(tmp_path: Path):
    tool = CheckTool(
        tmp_path,
        allowed_checks={
            "fail": [sys.executable, "-c", "import sys; print('bad'); sys.exit(2)"],
        },
    )

    result = tool.run_check("fail")

    assert result.success is False
    assert result.category == ResultCategory.CHECK_FAILED
    assert result.metadata["returncode"] == 2
    assert result.metadata["stdout"] == "bad\n"


def test_run_check_timeout(tmp_path: Path):
    tool = CheckTool(
        tmp_path,
        allowed_checks={
            "slow": [
                sys.executable,
                "-c",
                "import time; time.sleep(2)",
            ],
        },
        timeout_seconds=0.1,
    )

    result = tool.run_check("slow")

    assert result.success is False
    assert result.category == ResultCategory.TIMEOUT
    assert "timed out" in result.observation
