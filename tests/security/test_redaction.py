from pathlib import Path

from safepatch.core.models import EventType
from safepatch.security.redaction import REDACTED, redact_payload, redact_text
from safepatch.store.sqlite import SQLiteStore


def test_redact_text_removes_api_key_like_values():
    text = "provider returned sk-fakeSecret12345 in output"

    assert redact_text(text) == f"provider returned {REDACTED} in output"


def test_redact_payload_recurses_through_dicts_and_lists():
    payload = {
        "message": "token sk-fakeSecret12345",
        "nested": [{"stderr": "bad sk-anotherSecret999"}],
    }

    redacted = redact_payload(payload)

    assert redacted == {
        "message": f"token {REDACTED}",
        "nested": [{"stderr": f"bad {REDACTED}"}],
    }


def test_sqlite_events_are_redacted_before_persist(tmp_path: Path):
    store = SQLiteStore(tmp_path / "state.sqlite")
    store.append_event(
        "run-1",
        EventType.TOOL_FINISHED,
        {"stdout": "leaked sk-fakeSecret12345"},
    )

    [event] = store.list_events("run-1")

    assert event.payload == {"stdout": f"leaked {REDACTED}"}
