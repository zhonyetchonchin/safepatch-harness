from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from safepatch.security.vault import CredentialStatus, EncryptedVault, VaultError


class SetCredentialRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_key: str = Field(min_length=1)
    password: str = Field(min_length=1)


def credentials_router() -> APIRouter:
    router = APIRouter(prefix="/credentials", tags=["credentials"])

    @router.get("/{provider}/status")
    def status(provider: str, request: Request):
        vault = _credential_vault(request)
        return _status_response(vault.status(provider))

    @router.put("/{provider}")
    def set_credential(
        provider: str,
        body: SetCredentialRequest,
        request: Request,
    ):
        vault = _credential_vault(request)
        try:
            vault.set_key(provider, body.api_key, password=body.password)
            return _status_response(vault.status(provider))
        except VaultError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.delete("/{provider}")
    def delete_credential(provider: str, request: Request):
        vault = _credential_vault(request)
        vault.delete_key(provider)
        return _status_response(vault.status(provider))

    return router


def _credential_vault(request: Request) -> EncryptedVault:
    vault = request.app.state.credential_vault
    if vault is None:
        raise HTTPException(status_code=503, detail="credential vault not configured")
    return vault


def _status_response(status: CredentialStatus) -> dict[str, str | bool | None]:
    return {
        "provider": status.provider,
        "has_key": status.has_key,
        "updated_at": status.updated_at.isoformat()
        if status.updated_at is not None
        else None,
    }
