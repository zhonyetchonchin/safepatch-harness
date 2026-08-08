from pathlib import Path

from safepatch.core.models import EventType, RunStatus
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


def test_runs_persist_across_store_instances(tmp_path: Path):
    database = tmp_path / "state.sqlite"
    first = SQLiteStore(database)
    created = first.create_run(
        run_id="run-persisted",
        task="repair the tests",
        scenario="feedback_recovery",
    )

    first.update_run(
        created.run_id,
        status=RunStatus.PAUSED_FOR_APPROVAL,
        pending_action_id="run-persisted:step-2:apply_patch",
    )
    second = SQLiteStore(database)

    loaded = second.get_run("run-persisted")
    assert loaded is not None
    assert loaded.task == "repair the tests"
    assert loaded.scenario == "feedback_recovery"
    assert loaded.status == RunStatus.PAUSED_FOR_APPROVAL
    assert loaded.pending_action_id == "run-persisted:step-2:apply_patch"
    assert [run.run_id for run in second.list_runs()] == ["run-persisted"]
