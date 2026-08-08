from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.staticfiles import StaticFiles

from safepatch.api.routes_approval import approval_router
from safepatch.api.routes_credentials import credentials_router
from safepatch.core.models import EventType
from safepatch.policy.approval import ApprovalManager
from safepatch.security.vault import EncryptedVault
from safepatch.store.sqlite import SQLiteStore


class CreateRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: str = Field(min_length=1)


@dataclass
class RunRecord:
    run_id: str
    task: str
    status: str


def create_app(
    *,
    store: SQLiteStore,
    approval_manager: ApprovalManager | None = None,
    credential_vault: EncryptedVault | None = None,
) -> FastAPI:
    app = FastAPI(title="SafePatch Harness")
    app.state.store = store
    app.state.runs: dict[str, RunRecord] = {}
    app.state.approval_manager = approval_manager or ApprovalManager()
    app.state.credential_vault = credential_vault
    web_dir = Path(__file__).resolve().parent.parent / "web"
    app.mount("/static", StaticFiles(directory=web_dir), name="static")
    app.include_router(approval_router())
    app.include_router(credentials_router())

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(web_dir / "index.html")

    @app.get("/runs")
    def list_runs():
        return {
            "runs": [_run_response(record) for record in app.state.runs.values()]
        }

    @app.post("/runs", status_code=201)
    def create_run(request: CreateRunRequest):
        run_id = str(uuid4())
        record = RunRecord(run_id=run_id, task=request.task, status="created")
        app.state.runs[run_id] = record
        app.state.store.append_event(
            run_id,
            EventType.RUN_CREATED,
            {"task": request.task},
        )
        return _run_response(record)

    @app.get("/runs/{run_id}")
    def get_run(run_id: str):
        return _run_response(_get_run(app, run_id))

    @app.post("/runs/{run_id}/cancel")
    def cancel_run(run_id: str):
        record = _get_run(app, run_id)
        record.status = "canceled"
        app.state.store.append_event(
            run_id,
            EventType.STATE_CHANGED,
            {"status": record.status},
        )
        return _run_response(record)

    @app.get("/runs/{run_id}/events")
    def list_events(run_id: str):
        _get_run(app, run_id)
        events = app.state.store.list_events(run_id)
        return {
            "events": [
                {
                    "id": event.id,
                    "sequence": event.sequence,
                    "type": event.type.value,
                    "payload": event.payload,
                    "created_at": event.created_at.isoformat(),
                }
                for event in events
            ]
        }

    return app


def _get_run(app: FastAPI, run_id: str) -> RunRecord:
    try:
        return app.state.runs[run_id]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc


def _run_response(record: RunRecord) -> dict[str, str]:
    return {
        "run_id": record.run_id,
        "task": record.task,
        "status": record.status,
    }
