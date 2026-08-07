from pathlib import Path

from fastapi.testclient import TestClient

from safepatch.runtime import create_demo_app


ROOT = Path(__file__).resolve().parents[2]


def test_demo_app_factory_serves_webui(tmp_path: Path):
    client = TestClient(create_demo_app(data_dir=tmp_path))

    health = client.get("/health")
    index = client.get("/")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert index.status_code == 200
    assert "SafePatch Harness" in index.text


def test_docker_assets_define_demo_webui_entrypoint():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert "python:3.12-slim" in dockerfile
    assert 'CMD ["python", "-m", "safepatch", "--demo"' in dockerfile
    assert "8000" in dockerfile
    for ignored in [".git", ".venv", ".env", "*.sqlite", "secrets"]:
        assert ignored in dockerignore
