from pathlib import Path

from fastapi.testclient import TestClient

from safepatch.api.app import create_app
from safepatch.store.sqlite import SQLiteStore


def test_create_get_cancel_run_and_list_events(tmp_path: Path):
    store = SQLiteStore(tmp_path / "state.sqlite")
    client = TestClient(create_app(store=store))

    created = client.post("/runs", json={"task": "fix tests"})

    assert created.status_code == 201
    run_id = created.json()["run_id"]
    assert created.json()["status"] == "created"

    fetched = client.get(f"/runs/{run_id}")
    assert fetched.status_code == 200
    assert fetched.json()["task"] == "fix tests"

    canceled = client.post(f"/runs/{run_id}/cancel")
    assert canceled.status_code == 200
    assert canceled.json()["status"] == "canceled"

    events = client.get(f"/runs/{run_id}/events")
    assert events.status_code == 200
    assert [event["type"] for event in events.json()["events"]] == [
        "run_created",
        "state_changed",
    ]
