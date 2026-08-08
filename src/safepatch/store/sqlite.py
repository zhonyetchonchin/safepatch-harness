from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator

from safepatch.core.models import (
    Event,
    EventType,
    NonEmptyStr,
    RunStatus,
    StrictModel,
)
from safepatch.security.redaction import redact_payload


class MemoryRecord(StrictModel):
    id: int
    project_id: NonEmptyStr
    kind: NonEmptyStr
    content: NonEmptyStr
    tags: list[NonEmptyStr] = Field(default_factory=list)


class RunRecord(StrictModel):
    run_id: NonEmptyStr
    task: NonEmptyStr
    status: RunStatus
    scenario: NonEmptyStr | None = None
    pending_action_id: NonEmptyStr | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _pending_action_matches_status(self) -> RunRecord:
        if self.status == RunStatus.PAUSED_FOR_APPROVAL:
            if self.pending_action_id is None:
                raise ValueError("pending action is required for paused run")
        elif self.pending_action_id is not None:
            raise ValueError("pending action is only valid for paused run")
        return self


class SQLiteStore:
    def __init__(self, database_path: str | Path) -> None:
        self._path = Path(database_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def append_event(
        self,
        run_id: str,
        event_type: EventType,
        payload: dict[str, Any] | None = None,
    ) -> Event:
        with self._connect() as connection:
            sequence = self._next_sequence(connection, run_id)
            event = Event(
                run_id=run_id,
                sequence=sequence,
                type=event_type,
                payload=redact_payload(payload or {}),
            )
            connection.execute(
                """
                INSERT INTO events(id, run_id, sequence, type, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.run_id,
                    event.sequence,
                    event.type.value,
                    json.dumps(event.payload, ensure_ascii=False, sort_keys=True),
                    event.created_at.isoformat(),
                ),
            )
            return event

    def create_run(
        self,
        *,
        run_id: str,
        task: str,
        scenario: str | None = None,
    ) -> RunRecord:
        now = datetime.now(timezone.utc)
        record = RunRecord(
            run_id=run_id,
            task=task,
            status=RunStatus.CREATED,
            scenario=scenario,
            created_at=now,
            updated_at=now,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO runs(
                    run_id, task, status, scenario, pending_action_id,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.run_id,
                    record.task,
                    record.status.value,
                    record.scenario,
                    record.pending_action_id,
                    record.created_at.isoformat(),
                    record.updated_at.isoformat(),
                ),
            )
        return record

    def get_run(self, run_id: str) -> RunRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT run_id, task, status, scenario, pending_action_id,
                       created_at, updated_at
                FROM runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
        return self._run_from_row(row) if row is not None else None

    def list_runs(self) -> list[RunRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT run_id, task, status, scenario, pending_action_id,
                       created_at, updated_at
                FROM runs
                ORDER BY created_at ASC, run_id ASC
                """
            ).fetchall()
        return [self._run_from_row(row) for row in rows]

    def update_run(
        self,
        run_id: str,
        *,
        status: RunStatus,
        pending_action_id: str | None = None,
    ) -> RunRecord:
        current = self.get_run(run_id)
        if current is None:
            raise KeyError(run_id)
        record = RunRecord(
            run_id=current.run_id,
            task=current.task,
            status=RunStatus(status),
            scenario=current.scenario,
            pending_action_id=pending_action_id,
            created_at=current.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE runs
                SET status = ?, pending_action_id = ?, updated_at = ?
                WHERE run_id = ?
                """,
                (
                    record.status.value,
                    record.pending_action_id,
                    record.updated_at.isoformat(),
                    record.run_id,
                ),
            )
        return record

    def list_events(self, run_id: str) -> list[Event]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, run_id, sequence, type, payload_json, created_at
                FROM events
                WHERE run_id = ?
                ORDER BY sequence ASC
                """,
                (run_id,),
            ).fetchall()
        return [
            Event(
                id=row["id"],
                run_id=row["run_id"],
                sequence=row["sequence"],
                type=EventType(row["type"]),
                payload=json.loads(row["payload_json"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def add_memory(
        self,
        *,
        project_id: str,
        kind: str,
        content: str,
        tags: list[str],
    ) -> MemoryRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO memories(project_id, kind, content, tags_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    project_id,
                    kind,
                    content,
                    json.dumps(tags, ensure_ascii=False),
                ),
            )
            memory_id = int(cursor.lastrowid)
        return MemoryRecord(
            id=memory_id,
            project_id=project_id,
            kind=kind,
            content=content,
            tags=tags,
        )

    def find_memories(
        self,
        *,
        project_id: str,
        tags: list[str],
    ) -> list[MemoryRecord]:
        requested = set(tags)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, project_id, kind, content, tags_json
                FROM memories
                WHERE project_id = ?
                ORDER BY id ASC
                """,
                (project_id,),
            ).fetchall()
        memories: list[MemoryRecord] = []
        for row in rows:
            row_tags = json.loads(row["tags_json"])
            if requested and not requested.issubset(set(row_tags)):
                continue
            memories.append(
                MemoryRecord(
                    id=row["id"],
                    project_id=row["project_id"],
                    kind=row["kind"],
                    content=row["content"],
                    tags=row_tags,
                )
            )
        return memories

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    task TEXT NOT NULL,
                    status TEXT NOT NULL,
                    scenario TEXT,
                    pending_action_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(run_id, sequence)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags_json TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        return connection

    def _next_sequence(self, connection: sqlite3.Connection, run_id: str) -> int:
        row = connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 AS next_sequence FROM events WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        return int(row["next_sequence"])

    def _run_from_row(self, row: sqlite3.Row) -> RunRecord:
        return RunRecord(
            run_id=row["run_id"],
            task=row["task"],
            status=RunStatus(row["status"]),
            scenario=row["scenario"],
            pending_action_id=row["pending_action_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
