from pathlib import Path

from safepatch.core.models import EventType
from safepatch.store.sqlite import SQLiteStore


def test_event_sequence_increments_per_run(tmp_path: Path):
    store = SQLiteStore(tmp_path / "state.sqlite")

    first = store.append_event("run-1", EventType.RUN_CREATED, {"task": "x"})
    second = store.append_event("run-1", EventType.CONTEXT_BUILT, {"count": 2})
    other = store.append_event("run-2", EventType.RUN_CREATED, {"task": "y"})

    assert first.sequence == 1
    assert second.sequence == 2
    assert other.sequence == 1
    assert [event.sequence for event in store.list_events("run-1")] == [1, 2]


def test_memory_can_be_retrieved_by_tag(tmp_path: Path):
    store = SQLiteStore(tmp_path / "state.sqlite")
    store.add_memory(
        project_id="project-1",
        kind="project_convention",
        content="Use pytest.",
        tags=["tests", "python"],
    )
    store.add_memory(
        project_id="project-1",
        kind="user_decision",
        content="Avoid deploy.",
        tags=["safety"],
    )

    memories = store.find_memories(project_id="project-1", tags=["tests"])

    assert len(memories) == 1
    assert memories[0].content == "Use pytest."
    assert memories[0].tags == ["tests", "python"]
