from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_readme_covers_required_delivery_sections():
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    for heading in [
        "# SafePatch Harness",
        "## Installation",
        "## Run the demo WebUI",
        "## Credential setup",
        "## Directory structure",
        "## Safety boundaries",
        "## Docker and CI",
        "## Mechanism demo",
    ]:
        assert heading in text

    for command in [
        "python -m safepatch --demo",
        "python -m safepatch.demo",
        "docker build -t safepatch .",
        "python -m pytest -q",
    ]:
        assert command in text

    assert "API key" in text
    assert "does not echo" in text
