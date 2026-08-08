from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI

from safepatch.api.app import create_app
from safepatch.security.vault import EncryptedVault
from safepatch.store.sqlite import SQLiteStore


def create_demo_app(data_dir: str | Path | None = None) -> FastAPI:
    root = _data_dir(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    store = SQLiteStore(root / "state.sqlite")
    vault = EncryptedVault(root / "vault.json")
    return create_app(store=store, credential_vault=vault)


def _data_dir(data_dir: str | Path | None) -> Path:
    if data_dir is not None:
        return Path(data_dir)
    configured = os.environ.get("SAFEPATCH_DATA_DIR")
    if configured:
        return Path(configured)
    return Path(".safepatch")
