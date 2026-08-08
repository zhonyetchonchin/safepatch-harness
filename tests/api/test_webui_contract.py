from pathlib import Path

from fastapi.testclient import TestClient

from safepatch.api.app import create_app
from safepatch.security.vault import EncryptedVault
from safepatch.store.sqlite import SQLiteStore


def test_webui_exposes_workbench_regions_and_api_bindings(tmp_path: Path):
    store = SQLiteStore(tmp_path / "state.sqlite")
    vault = EncryptedVault(tmp_path / "vault.json")
    client = TestClient(create_app(store=store, credential_vault=vault))

    index = client.get("/")
    script = client.get("/static/app.js")
    styles = client.get("/static/styles.css")

    assert index.status_code == 200
    html = index.text
    for element_id in [
        "run-form",
        "run-list",
        "timeline",
        "approval-form",
        "credential-form",
        "check-results",
        "diff-view",
    ]:
        assert f'id="{element_id}"' in html

    assert script.status_code == 200
    assert 'fetch("/runs"' in script.text
    assert 'fetch(`/runs/${state.selectedRunId}/events`)' in script.text
    assert 'fetch(`/approvals/${actionId}/approve`' in script.text
    assert 'fetch("/credentials/openai/status")' in script.text
    assert styles.status_code == 200
    assert ".timeline" in styles.text


def test_run_list_api_contract_for_webui(tmp_path: Path):
    store = SQLiteStore(tmp_path / "state.sqlite")
    client = TestClient(create_app(store=store))
    first = client.post("/runs", json={"task": "fix tests"}).json()
    second = client.post("/runs", json={"task": "update docs"}).json()

    response = client.get("/runs")

    assert response.status_code == 200
    runs = response.json()["runs"]
    assert [run["run_id"] for run in runs] == [first["run_id"], second["run_id"]]
    assert [run["task"] for run in runs] == ["fix tests", "update docs"]
