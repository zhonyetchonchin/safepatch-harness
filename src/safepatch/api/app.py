from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ConfigDict
from starlette.staticfiles import StaticFiles

from safepatch.api.routes_approval import approval_router
from safepatch.api.routes_credentials import credentials_router
from safepatch.core.models import EventType, NonEmptyStr, RunStatus, StrictModel
from safepatch.policy.approval import ApprovalManager
from safepatch.security.redaction import redact_payload
from safepatch.security.vault import EncryptedVault
from safepatch.store.sqlite import RunRecord, SQLiteStore


class CreateRunRequest(StrictModel):
    model_config = ConfigDict(extra="forbid")

    task: NonEmptyStr
    scenario: NonEmptyStr | None = None


RunHandler = Callable[[str, str, str], RunRecord]


def create_app(
    *,
    store: SQLiteStore,
    approval_manager: ApprovalManager | None = None,
    credential_vault: EncryptedVault | None = None,
    demo_mode: bool = False,
    public_demo: bool = False,
    scenarios: Sequence[str] = (),
    run_handler: RunHandler | None = None,
    approval_handler=None,
) -> FastAPI:
    app = FastAPI(title="SafePatch Harness", version="0.2.0")
    app.state.store = store
    app.state.approval_manager = approval_manager or ApprovalManager()
    app.state.credential_vault = credential_vault
    app.state.approval_handler = approval_handler
    app.state.demo_mode = demo_mode
    app.state.public_demo = public_demo
    app.state.scenarios = tuple(scenarios)
    web_dir = Path(__file__).resolve().parent.parent / "web"
    app.mount("/static", StaticFiles(directory=web_dir), name="static")
    app.include_router(approval_router())
    app.include_router(credentials_router())

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; base-uri 'none'; "
            "frame-ancestors 'none'; form-action 'self'"
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        errors = exc.errors()
        if request.url.path.startswith("/credentials/"):
            errors = [
                {
                    "type": error.get("type"),
                    "loc": error.get("loc"),
                    "msg": error.get("msg"),
                }
                for error in errors
            ]
        return JSONResponse(status_code=422, content={"detail": redact_payload(errors)})

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/meta")
    def metadata():
        return {
            "name": "SafePatch Harness",
            "version": "0.2.0",
            "demo_mode": app.state.demo_mode,
            "public_demo": app.state.public_demo,
            "credentials_enabled": app.state.credential_vault is not None,
            "scenarios": list(app.state.scenarios),
        }

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(web_dir / "index.html")

    @app.get("/runs")
    def list_runs():
        return {"runs": [_run_response(record) for record in store.list_runs()]}

    @app.post("/runs", status_code=201)
    def create_run(request: CreateRunRequest):
        scenario = request.scenario
        if run_handler is not None:
            scenario = scenario or (app.state.scenarios[0] if app.state.scenarios else None)
            if scenario not in app.state.scenarios:
                raise HTTPException(status_code=422, detail="unknown demo scenario")
        run_id = str(uuid4())
        record = store.create_run(run_id=run_id, task=request.task, scenario=scenario)
        if run_handler is None:
            store.append_event(run_id, EventType.RUN_CREATED, {"task": request.task})
        else:
            record = run_handler(run_id, request.task, scenario)
        return _run_response(record)

    @app.get("/runs/{run_id}")
    def get_run(run_id: str):
        return _run_response(_get_run(store, run_id))

    @app.post("/runs/{run_id}/cancel")
    def cancel_run(run_id: str):
        record = _get_run(store, run_id)
        if record.status in {
            RunStatus.COMPLETED,
            RunStatus.FAILED,
            RunStatus.CANCELED,
            RunStatus.BUDGET_EXHAUSTED,
        }:
            raise HTTPException(status_code=409, detail="run is already terminal")
        record = store.update_run(run_id, status=RunStatus.CANCELED)
        store.append_event(
            run_id,
            EventType.STATE_CHANGED,
            {"status": record.status.value},
        )
        return _run_response(record)

    @app.get("/runs/{run_id}/events")
    def list_events(run_id: str):
        _get_run(store, run_id)
        events = store.list_events(run_id)
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


def _get_run(store: SQLiteStore, run_id: str) -> RunRecord:
    record = store.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="run not found")
    return record


def _run_response(record: RunRecord) -> dict[str, str | None]:
    return {
        "run_id": record.run_id,
        "task": record.task,
        "status": record.status.value,
        "scenario": record.scenario,
        "pending_action_id": record.pending_action_id,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }
