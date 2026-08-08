from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI

from safepatch.api.app import create_app
from safepatch.demo.workbench import DEMO_SCENARIOS, DemoWorkbench
from safepatch.policy.approval import ApprovalManager
from safepatch.security.vault import EncryptedVault
from safepatch.store.sqlite import SQLiteStore


def create_demo_app(
    data_dir: str | Path | None = None,
    *,
    public_demo: bool | None = None,
) -> FastAPI:
    root = _data_dir(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    store = SQLiteStore(root / "state.sqlite")
    if public_demo is None:
        public_demo = _env_flag("SAFEPATCH_PUBLIC_DEMO", default=False)
    approvals = ApprovalManager()
    workbench = DemoWorkbench(store, approvals)
    vault = None if public_demo else EncryptedVault(root / "vault.json")
    return create_app(
        store=store,
        approval_manager=approvals,
        credential_vault=vault,
        demo_mode=True,
        public_demo=public_demo,
        scenarios=DEMO_SCENARIOS,
        run_handler=workbench.start,
        approval_handler=workbench,
    )


def _data_dir(data_dir: str | Path | None) -> Path:
    if data_dir is not None:
        return Path(data_dir)
    configured = os.environ.get("SAFEPATCH_DATA_DIR")
    if configured:
        return Path(configured)
    return Path(".safepatch")


def _env_flag(name: str, *, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
