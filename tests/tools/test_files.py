from pathlib import Path

from safepatch.core.models import ResultCategory
from safepatch.tools.files import FileTools


def test_read_file_inside_workspace(tmp_path: Path):
    target = tmp_path / "src" / "app.py"
    target.parent.mkdir()
    target.write_text("print('ok')\n", encoding="utf-8")

    result = FileTools(tmp_path).read_file("src/app.py")

    assert result.success is True
    assert result.category == ResultCategory.SUCCESS
    assert result.metadata["path"] == "src/app.py"
    assert result.observation == "print('ok')"


def test_read_file_rejects_parent_escape(tmp_path: Path):
    result = FileTools(tmp_path).read_file("../outside.txt")

    assert result.success is False
    assert result.category == ResultCategory.POLICY_DENIED
    assert "outside workspace" in result.observation


def test_read_file_rejects_absolute_escape(tmp_path: Path):
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret", encoding="utf-8")

    result = FileTools(tmp_path).read_file(str(outside))

    assert result.success is False
    assert result.category == ResultCategory.POLICY_DENIED
    assert "outside workspace" in result.observation


def test_read_file_rejects_sensitive_paths(tmp_path: Path):
    secret = tmp_path / ".env"
    secret.write_text("API_KEY=secret", encoding="utf-8")

    result = FileTools(tmp_path).read_file(".env")

    assert result.success is False
    assert result.category == ResultCategory.POLICY_DENIED
    assert "sensitive path" in result.observation


def test_list_files_ignores_denied_directories(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("", encoding="utf-8")

    result = FileTools(tmp_path).list_files("**/*")

    assert result.success is True
    assert result.metadata["paths"] == ["src/app.py"]


def test_search_text_returns_matching_lines(tmp_path: Path):
    target = tmp_path / "src" / "app.py"
    target.parent.mkdir()
    target.write_text("alpha\nneedle here\n", encoding="utf-8")

    result = FileTools(tmp_path).search_text("needle", glob="**/*.py")

    assert result.success is True
    assert result.metadata["matches"] == [
        {"path": "src/app.py", "line": 2, "text": "needle here"}
    ]
