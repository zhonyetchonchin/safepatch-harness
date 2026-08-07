from pathlib import Path

from fastapi.testclient import TestClient

from safepatch.api.app import create_app
from safepatch.store.sqlite import SQLiteStore


def test_health_endpoint_and_static_webui_shell(tmp_path: Path):
    store = SQLiteStore(tmp_path / "state.sqlite")
    client = TestClient(create_app(store=store))

    health = client.get("/health")
    index = client.get("/")
    css = client.get("/static/styles.css")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert index.status_code == 200
    assert "SafePatch Harness" in index.text
    assert css.status_code == 200
