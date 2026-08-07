from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

from safepatch.core.models import NonEmptyStr, StrictModel


class VaultError(ValueError):
    pass


class CredentialStatus(StrictModel):
    provider: NonEmptyStr
    has_key: bool
    updated_at: datetime | None = None


class EncryptedVault:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def set_key(self, provider: str, api_key: str, *, password: str) -> None:
        data = self._load()
        salt = os.urandom(16)
        nonce = os.urandom(12)
        key = _derive_key(password, salt)
        ciphertext = AESGCM(key).encrypt(nonce, api_key.encode("utf-8"), None)
        data[provider] = {
            "salt": _b64(salt),
            "nonce": _b64(nonce),
            "ciphertext": _b64(ciphertext),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save(data)

    def get_key(self, provider: str, *, password: str) -> str:
        record = self._load().get(provider)
        if record is None:
            raise VaultError("credential not found")
        try:
            salt = _unb64(record["salt"])
            nonce = _unb64(record["nonce"])
            ciphertext = _unb64(record["ciphertext"])
            key = _derive_key(password, salt)
            plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
        except (KeyError, InvalidTag, ValueError) as exc:
            raise VaultError("could not decrypt credential") from exc
        return plaintext.decode("utf-8")

    def status(self, provider: str) -> CredentialStatus:
        record = self._load().get(provider)
        if record is None:
            return CredentialStatus(provider=provider, has_key=False)
        return CredentialStatus(
            provider=provider,
            has_key=True,
            updated_at=record.get("updated_at"),
        )

    def delete_key(self, provider: str) -> None:
        data = self._load()
        data.pop(provider, None)
        self._save(data)

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self._path.exists():
            return {}
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _save(self, data: dict[str, dict[str, Any]]) -> None:
        self._path.write_text(
            json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8",
        )


def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = Argon2id(
        length=32,
        salt=salt,
        iterations=3,
        lanes=4,
        memory_cost=64 * 1024,
    )
    return kdf.derive(password.encode("utf-8"))


def _b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.b64decode(value.encode("ascii"))
