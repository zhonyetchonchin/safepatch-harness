from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_final_delivery_docs_exist_and_record_limitations():
    reflection = (ROOT / "REFLECTION.md").read_text(encoding="utf-8")
    process = (ROOT / "SPEC_PROCESS.md").read_text(encoding="utf-8")

    assert "# REFLECTION" in reflection
    assert "学生本人" in reflection
    assert "最终交付检查" in process
    assert "88 passed, 1 skipped" in process
    assert "Docker Desktop daemon 未运行" in process
    assert "writing-plans" in process
