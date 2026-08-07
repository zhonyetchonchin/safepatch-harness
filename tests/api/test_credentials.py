from pathlib import Path

from fastapi.testclient import TestClient

from safepatch.api.app import create_app
from safepatch.security.vault import EncryptedVault
from safepatch.store.sqlite import SQLiteStore


def test_set_status_update_and_delete_credential_without_echoing_key(tmp_path: Path):
    store = SQLiteStore(tmp_path / "state.sqlite")
    vault = EncryptedVault(tmp_path / "vault.json")
    client = TestClient(create_app(store=store, credential_vault=vault))

    created = client.put(
        "/credentials/openai",
        json={"api_key": "sk-test-secret-value", "password": "correct horse"},
    )
    status = client.get("/credentials/openai/status")
    updated = client.put(
        "/credentials/openai",
        json={"api_key": "sk-new-secret-value", "password": "correct horse"},
    )
    stored_key = vault.get_key("openai", password="correct horse")
    deleted = client.delete("/credentials/openai")

    assert created.status_code == 200
    assert created.json()["has_key"] is True
    assert status.status_code == 200
    assert status.json()["provider"] == "openai"
    assert status.json()["has_key"] is True
    assert updated.status_code == 200
    assert stored_key == "sk-new-secret-value"
    assert deleted.status_code == 200
    assert deleted.json()["has_key"] is False

    response_text = "\n".join(
        [created.text, status.text, updated.text, deleted.text]
    )
    assert "sk-test-secret-value" not in response_text
    assert "sk-new-secret-value" not in response_text
    assert "correct horse" not in response_text
