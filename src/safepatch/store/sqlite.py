from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from pydantic import Field

from safepatch.core.models import Event, EventType, NonEmptyStr, StrictModel
from safepatch.security.redaction import redact_payload


class MemoryRecord(StrictModel):
    id: int
    project_id: NonEmptyStr
    kind: NonEmptyStr
    content: NonEmptyStr
    tags: list[NonEmptyStr] = Field(default_factory=list)


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
