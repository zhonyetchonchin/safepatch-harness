from pathlib import Path

import pytest

from safepatch.security.vault import EncryptedVault, VaultError


def test_vault_set_status_and_get_key(tmp_path: Path):
    vault = EncryptedVault(tmp_path / "vault.json")

    vault.set_key("openai", "test-secret-value", password="correct horse")
    status = vault.status("openai")

    assert status.provider == "openai"
    assert status.has_key is True
    assert "test-secret-value" not in status.model_dump_json()
    assert vault.get_key("openai", password="correct horse") == "test-secret-value"


def test_vault_file_does_not_contain_plaintext(tmp_path: Path):
    path = tmp_path / "vault.json"
    vault = EncryptedVault(path)

    vault.set_key("openai", "test-secret-value", password="correct horse")

    assert "test-secret-value" not in path.read_text(encoding="utf-8")


def test_wrong_password_cannot_decrypt(tmp_path: Path):
    vault = EncryptedVault(tmp_path / "vault.json")
    vault.set_key("openai", "test-secret-value", password="correct horse")

    with pytest.raises(VaultError):
        vault.get_key("openai", password="wrong")


def test_vault_update_and_delete(tmp_path: Path):
    vault = EncryptedVault(tmp_path / "vault.json")
    vault.set_key("openai", "old-secret", password="correct horse")
    vault.set_key("openai", "new-secret", password="correct horse")

    assert vault.get_key("openai", password="correct horse") == "new-secret"

    vault.delete_key("openai")

    assert vault.status("openai").has_key is False
