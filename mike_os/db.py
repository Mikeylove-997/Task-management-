from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

STATUSES = {"inbox", "active", "backlog", "completed"}

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('inbox','active','backlog','completed')),
    project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    target_date TEXT,
    completed_at TEXT,
    next_action TEXT,
    notes TEXT,
    priority INTEGER,
    last_worked_at TEXT,
    is_accomplishment INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS task_events (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    source TEXT NOT NULL,
    details_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_target_date ON tasks(target_date);
CREATE INDEX IF NOT EXISTS idx_tasks_completed_at ON tasks(completed_at);
CREATE INDEX IF NOT EXISTS idx_events_task_time ON task_events(task_id, occurred_at);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class TaskStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            connection.execute("PRAGMA journal_mode=WAL")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    @staticmethod
    def _task(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["is_accomplishment"] = bool(result["is_accomplishment"])
        result["metadata"] = json.loads(result.pop("metadata_json") or "{}")
        return result

    def _event(self, connection: sqlite3.Connection, task_id: str, event_type: str,
               source: str, details: dict[str, Any]) -> None:
        connection.execute(
            "INSERT INTO task_events VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), task_id, event_type, now_iso(), source,
             json.dumps(details, separators=(",", ":"))),
        )

    def _project_id(self, connection: sqlite3.Connection, name: str | None) -> str | None:
        if not name or not name.strip():
            return None
        name = name.strip()
        row = connection.execute("SELECT id FROM projects WHERE name=? COLLATE NOCASE", (name,)).fetchone()
        if row:
            return row["id"]
        project_id = str(uuid.uuid4())
        connection.execute("INSERT INTO projects VALUES (?, ?, ?)", (project_id, name, now_iso()))
        return project_id

    def create(self, data: dict[str, Any], source: str = "manual") -> dict[str, Any]:
        title = str(data.get("title", "")).strip()
        status = str(data.get("status", "inbox")).lower()
        if not title:
            raise ValueError("A task title is required.")
        if status not in STATUSES:
            raise ValueError("Invalid task status.")
        timestamp = now_iso()
        task_id = str(uuid.uuid4())
        completed_at = data.get("completed_at") or (timestamp if status == "completed" else None)
        with self.connect() as connection:
            project_id = self._project_id(connection, data.get("project"))
            connection.execute(
                """INSERT INTO tasks
                (id,title,status,project_id,created_at,updated_at,target_date,completed_at,
                 next_action,notes,priority,last_worked_at,is_accomplishment,metadata_json,version)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                (task_id, title, status, project_id, timestamp, timestamp, data.get("target_date"),
                 completed_at, data.get("next_action"), data.get("notes"), data.get("priority"),
                 data.get("last_worked_at"), int(bool(data.get("is_accomplishment"))),
                 json.dumps(data.get("metadata", {}))),
            )
            self._event(connection, task_id, "created", source, {"status": status, "title": title})
        return self.get(task_id)

    def get(self, task_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT t.*, p.name project FROM tasks t
                   LEFT JOIN projects p ON p.id=t.project_id WHERE t.id=?""", (task_id,)
            ).fetchone()
        if not row:
            raise KeyError("Task not found.")
        return self._task(row)

    def list(self, status: str | None = None, query: str | None = None,
             project: str | None = None) -> list[dict[str, Any]]:
        clauses, args = [], []
        if status and status != "all":
            if status not in STATUSES:
                raise ValueError("Invalid task status.")
            clauses.append("t.status=?")
            args.append(status)
        if query:
            clauses.append("(t.title LIKE ? OR t.notes LIKE ? OR t.next_action LIKE ? OR p.name LIKE ?)")
            pattern = f"%{query.strip()}%"
            args.extend([pattern] * 4)
        if project:
            clauses.append("p.name=? COLLATE NOCASE")
            args.append(project)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        order = "ORDER BY CASE t.status WHEN 'active' THEN 0 WHEN 'inbox' THEN 1 WHEN 'backlog' THEN 2 ELSE 3 END, COALESCE(t.target_date,'9999-12-31'), t.updated_at DESC"
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT t.*, p.name project FROM tasks t LEFT JOIN projects p ON p.id=t.project_id{where} {order}", args
            ).fetchall()
        return [self._task(row) for row in rows]

    def update(self, task_id: str, data: dict[str, Any], source: str = "manual") -> dict[str, Any]:
        current = self.get(task_id)
        allowed = {"title", "status", "target_date", "next_action", "notes", "priority",
                   "last_worked_at", "is_accomplishment", "project"}
        changes = {key: value for key, value in data.items() if key in allowed}
        if "title" in changes and not str(changes["title"]).strip():
            raise ValueError("A task title is required.")
        if "status" in changes and changes["status"] not in STATUSES:
            raise ValueError("Invalid task status.")
        if not changes:
            return current
        timestamp = now_iso()
        with self.connect() as connection:
            project_id = self._project_id(connection, changes.pop("project")) if "project" in changes else current["project_id"]
            if changes.get("status") == "completed" and current["status"] != "completed":
                changes["completed_at"] = data.get("completed_at") or timestamp
            elif "status" in changes and changes["status"] != "completed" and current["status"] == "completed":
                changes["completed_at"] = None
            changes["project_id"] = project_id
            changes["updated_at"] = timestamp
            changes["version"] = current["version"] + 1
            if "is_accomplishment" in changes:
                changes["is_accomplishment"] = int(bool(changes["is_accomplishment"]))
            assignments = ",".join(f"{key}=?" for key in changes)
            connection.execute(f"UPDATE tasks SET {assignments} WHERE id=?", [*changes.values(), task_id])
            before_after = {key: {"before": current.get(key), "after": value} for key, value in changes.items() if current.get(key) != value and key not in {"updated_at", "version"}}
            event_type = "completed" if changes.get("status") == "completed" else "updated"
            self._event(connection, task_id, event_type, source, before_after)
        return self.get(task_id)

    def history(self, task_id: str) -> list[dict[str, Any]]:
        self.get(task_id)
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM task_events WHERE task_id=? ORDER BY occurred_at DESC", (task_id,)
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["details"] = json.loads(item.pop("details_json"))
            result.append(item)
        return result

    def export(self) -> dict[str, Any]:
        with self.connect() as connection:
            projects = [dict(row) for row in connection.execute("SELECT * FROM projects ORDER BY name")]
            events = [dict(row) for row in connection.execute("SELECT * FROM task_events ORDER BY occurred_at")]
        return {"format": "mike-os-backup", "version": 1, "exported_at": now_iso(),
                "tasks": self.list(), "projects": projects, "task_events": events}

