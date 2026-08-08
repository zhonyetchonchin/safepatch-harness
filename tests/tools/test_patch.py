from pathlib import Path

from safepatch.core.models import ResultCategory
from safepatch.tools.patch import PatchTool


def test_apply_patch_updates_file(tmp_path: Path):
    target = tmp_path / "src" / "app.py"
    target.parent.mkdir()
    target.write_text("line1\nold\nline3\n", encoding="utf-8")
    patch = """--- a/src/app.py
+++ b/src/app.py
@@ -1,3 +1,3 @@
 line1
-old
+new
 line3
"""

    result = PatchTool(tmp_path).apply_patch(patch)

    assert result.success is True
    assert result.category == ResultCategory.SUCCESS
    assert target.read_text(encoding="utf-8") == "line1\nnew\nline3\n"


def test_apply_patch_context_mismatch_does_not_modify_file(tmp_path: Path):
    target = tmp_path / "src" / "app.py"
    target.parent.mkdir()
    original = "line1\nactual\nline3\n"
    target.write_text(original, encoding="utf-8")
    patch = """--- a/src/app.py
+++ b/src/app.py
@@ -1,3 +1,3 @@
 line1
-old
+new
 line3
"""

    result = PatchTool(tmp_path).apply_patch(patch)

    assert result.success is False
    assert result.category == ResultCategory.PATCH_CONFLICT
    assert "context mismatch" in result.observation
    assert target.read_text(encoding="utf-8") == original


def test_apply_patch_rejects_path_escape(tmp_path: Path):
    outside = tmp_path.parent / "outside.py"
    outside.write_text("old\n", encoding="utf-8")
    patch = f"""--- a/{outside}
+++ b/{outside}
@@ -1 +1 @@
-old
+new
"""

    result = PatchTool(tmp_path).apply_patch(patch)

    assert result.success is False
    assert result.category == ResultCategory.POLICY_DENIED
    assert "outside workspace" in result.observation
    assert outside.read_text(encoding="utf-8") == "old\n"
