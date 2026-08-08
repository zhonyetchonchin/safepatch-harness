# SafePatch Harness

SafePatch Harness is a local-first coding-agent harness for controlled software
repair experiments. It combines a strict action schema, deterministic mock LLM
providers, policy gates, human approval, encrypted credential storage, a small
FastAPI backend, and a static WebUI workbench.

Live demo WebUI: https://safepatch-harness.onrender.com (Render, free tier,
demo mode).

The project is designed for AI4SE Project A: it demonstrates how a coding agent
can inspect files, propose patches, run allowlisted checks, receive feedback,
and stop before unsafe actions.

## Installation

Use Python 3.12 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
```

On Linux/macOS, replace the Python path with the active virtual environment's
`python` binary.

## Run the demo WebUI

Start the local demo server:

```powershell
.\.venv\Scripts\python.exe -m safepatch --demo --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. The WebUI provides:

- run creation, listing, cancellation, and event timeline;
- approval and rejection controls for pending action IDs;
- OpenAI credential status, set/update, and clear controls;
- check-result and diff preview panels.

The short command form is also supported:

```powershell
python -m safepatch --demo
```

## Credential setup

Credentials are stored through `EncryptedVault` using Argon2id-derived
AES-GCM encryption. The API key is submitted with a local master password and
the status endpoint only returns provider, `has_key`, and update time.

The credential status response does not echo the API key or password.
There is intentionally no plaintext read endpoint.

## Directory structure

```text
src/safepatch/core/       action schemas, provider port, loop, budget, feedback
src/safepatch/tools/      safe file, patch, and check tools
src/safepatch/policy/     policy engine, path boundary, approval state machine
src/safepatch/store/      SQLite event and memory store
src/safepatch/security/   encrypted vault and redaction
src/safepatch/api/        FastAPI app and route modules
src/safepatch/web/        static WebUI workbench
src/safepatch/demo/       deterministic mechanism scenarios
tests/                    unit and contract tests
```

## Safety boundaries

SafePatch uses these boundaries by default:

- paths are resolved inside the configured workspace;
- sensitive paths such as `.env` are denied;
- dangerous check names such as `rm -rf`, `git push`, `curl`, and `wget` are
  denied;
- only allowlisted check names can run;
- protected dependency files require approval;
- approvals are one-time consumable state;
- events and stored payloads redact OpenAI-style `sk-...` secrets.

This is a demo harness, not a general remote execution service. Public
deployment should use demo mode only.

## Docker and CI

Build the container:

```powershell
docker build -t safepatch .
```

Run the demo WebUI:

```powershell
docker run --rm -p 8000:8000 safepatch
```

## Public deployment

The container runs in demo mode on `0.0.0.0`, so it can be deployed as a
public WebUI. The demo mode only serves the workbench UI and its local API;
it never opens arbitrary user repositories or executes unrestricted commands.

Render (free tier) example using `render.yaml` in this repository:

1. Push the repository to GitHub.
2. Create a Render web service with runtime `Docker`.
3. Set env var `SAFEPATCH_DATA_DIR=/data/safepatch` and health check path
   `/health`.

The server honors the platform-provided `PORT` environment variable as a
fallback (Render / Fly.io / Railway all inject `PORT`).

The repository includes `.gitlab-ci.yml` with a `unit-test` job that installs
`.[dev]` and runs:

```powershell
python -m pytest -q
```

It also includes a Docker build job for GitLab runners with Docker-in-Docker.

## Mechanism demo

Run deterministic mock scenarios:

```powershell
python -m safepatch.demo
```

The demo reports three mechanisms:

- dangerous action block: policy denies a dangerous check before any tool runs;
- failure feedback recovery: a mock provider changes action after seeing failed
  check feedback;
- HITL pause: a protected patch pauses with a pending approval and no tool
  execution.
