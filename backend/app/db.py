from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import Settings, settings

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    source TEXT NOT NULL,
    effective_date TEXT NOT NULL,
    content TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    objective TEXT NOT NULL,
    segment_id TEXT NOT NULL,
    market_signal TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    result_json TEXT,
    compliance_status TEXT,
    variant TEXT,
    conversion_rate REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    agent TEXT NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(run_id, sequence)
);

CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    importance REAL NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_accessed TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memory_namespace ON memories(namespace, kind);

CREATE TABLE IF NOT EXISTS bandit_arms (
    arm TEXT PRIMARY KEY,
    alpha REAL NOT NULL DEFAULT 1,
    beta REAL NOT NULL DEFAULT 1,
    impressions INTEGER NOT NULL DEFAULT 0,
    conversions INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    converted INTEGER NOT NULL,
    rating INTEGER NOT NULL,
    note TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class Database:
    def __init__(self, app_settings: Settings | None = None) -> None:
        self.settings = app_settings or settings
        self.path = self.settings.database_path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            for arm in ("clarity", "evidence", "scenario"):
                connection.execute(
                    """INSERT OR IGNORE INTO bandit_arms
                    (arm, alpha, beta, impressions, conversions, updated_at)
                    VALUES (?, 1, 1, 0, 0, ?)""",
                    (arm, now_iso()),
                )
        self._seed_documents(self.settings.knowledge_path)

    def _seed_documents(self, directory: Path) -> None:
        for file_path in sorted(directory.glob("*.md")):
            metadata, content = self._parse_markdown(file_path)
            document_id = metadata.get("source", file_path.stem).split("/")[-1].strip()
            with self.connect() as connection:
                connection.execute(
                    """INSERT INTO documents
                    (id, title, category, source, effective_date, content, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                      title=excluded.title, category=excluded.category,
                      source=excluded.source, effective_date=excluded.effective_date,
                      content=excluded.content, updated_at=excluded.updated_at""",
                    (
                        document_id,
                        metadata.get("title", file_path.stem),
                        metadata.get("category", "general"),
                        metadata.get("source", file_path.name),
                        metadata.get("effective_date", ""),
                        content,
                        now_iso(),
                    ),
                )

    @staticmethod
    def _parse_markdown(path: Path) -> tuple[dict[str, str], str]:
        raw = path.read_text(encoding="utf-8")
        if not raw.startswith("---"):
            return {}, raw.strip()
        _, header, body = raw.split("---", 2)
        metadata: dict[str, str] = {}
        for line in header.strip().splitlines():
            key, _, value = line.partition(":")
            metadata[key.strip()] = value.strip()
        return metadata, body.strip()

    def list_documents(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM documents ORDER BY id").fetchall()
        return [dict(row) for row in rows]

    def create_run(
        self, run_id: str, objective: str, segment_id: str, market_signal: str, created_at: str
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO runs
                (id, objective, segment_id, market_signal, status, created_at)
                VALUES (?, ?, ?, ?, 'running', ?)""",
                (run_id, objective, segment_id, market_signal, created_at),
            )

    def complete_run(self, run_id: str, result: dict[str, Any]) -> None:
        execution = result.get("execution") or {}
        with self.connect() as connection:
            connection.execute(
                """UPDATE runs SET status=?, completed_at=?, result_json=?,
                compliance_status=?, variant=?, conversion_rate=? WHERE id=?""",
                (
                    result["status"],
                    result["completed_at"],
                    json.dumps(result, ensure_ascii=False),
                    result["compliance"]["status"],
                    execution.get("variant"),
                    execution.get("conversion_rate", 0),
                    run_id,
                ),
            )

    def append_event(self, event: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO events
                (run_id, sequence, timestamp, agent, stage, status, message, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event["run_id"],
                    event["sequence"],
                    event["timestamp"],
                    event["agent"],
                    event["stage"],
                    event["status"],
                    event["message"],
                    json.dumps(event.get("payload", {}), ensure_ascii=False),
                ),
            )

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            return None
        record = dict(row)
        if record.get("result_json"):
            return json.loads(record["result_json"])
        return record

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        results = []
        for row in rows:
            record = dict(row)
            if record.get("result_json"):
                results.append(json.loads(record["result_json"]))
            else:
                results.append(record)
        return results

    def list_events(self, run_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM events WHERE run_id=? ORDER BY sequence", (run_id,)
            ).fetchall()
        return [
            {
                "sequence": row["sequence"],
                "run_id": row["run_id"],
                "timestamp": row["timestamp"],
                "agent": row["agent"],
                "stage": row["stage"],
                "status": row["status"],
                "message": row["message"],
                "payload": json.loads(row["payload_json"]),
            }
            for row in rows
        ]

    def put_memory(self, memory: dict[str, Any]) -> None:
        created_at = memory["created_at"]
        if hasattr(created_at, "isoformat"):
            created_at = created_at.isoformat()
        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO memories
                (id, namespace, kind, content, importance, metadata_json, created_at, last_accessed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    memory["id"],
                    memory["namespace"],
                    memory["kind"],
                    memory["content"],
                    memory["importance"],
                    json.dumps(memory.get("metadata", {}), ensure_ascii=False),
                    created_at,
                    now_iso(),
                ),
            )

    def list_memories(self, namespace: str, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT * FROM memories WHERE namespace IN (?, 'global')
                ORDER BY importance DESC, created_at DESC LIMIT ?""",
                (namespace, limit),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "namespace": row["namespace"],
                "kind": row["kind"],
                "content": row["content"],
                "importance": row["importance"],
                "metadata": json.loads(row["metadata_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def get_bandit_arms(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM bandit_arms ORDER BY arm").fetchall()
        return [dict(row) for row in rows]

    def update_bandit(self, arm: str, converted: bool) -> None:
        with self.connect() as connection:
            connection.execute(
                """UPDATE bandit_arms SET alpha=alpha+?, beta=beta+?,
                impressions=impressions+1, conversions=conversions+?, updated_at=? WHERE arm=?""",
                (int(converted), int(not converted), int(converted), now_iso(), arm),
            )

    def save_feedback(self, run_id: str, converted: bool, rating: int, note: str) -> None:
        run = self.get_run(run_id)
        if run is None:
            raise KeyError(run_id)
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO feedback (run_id, converted, rating, note, created_at)
                VALUES (?, ?, ?, ?, ?)""",
                (run_id, int(converted), rating, note, now_iso()),
            )
        execution = run.get("execution") or {}
        if execution.get("variant"):
            self.update_bandit(execution["variant"], converted)

    def dashboard_metrics(self) -> dict[str, Any]:
        with self.connect() as connection:
            run_stats = connection.execute(
                """SELECT COUNT(*) AS total,
                SUM(CASE WHEN compliance_status IN ('approved','revised')
                    THEN 1 ELSE 0 END) AS safe,
                AVG(conversion_rate) AS avg_conversion
                FROM runs WHERE status IN ('completed','blocked')"""
            ).fetchone()
            feedback = connection.execute(
                "SELECT COUNT(*) AS total, AVG(rating) AS rating FROM feedback"
            ).fetchone()
            memory_count = connection.execute(
                "SELECT COUNT(*) AS total FROM memories"
            ).fetchone()[0]
        total = int(run_stats["total"] or 0)
        safe = int(run_stats["safe"] or 0)
        return {
            "total_runs": total,
            "compliance_rate": round(safe / total, 4) if total else 1.0,
            "average_conversion_rate": round(float(run_stats["avg_conversion"] or 0), 4),
            "feedback_count": int(feedback["total"] or 0),
            "average_rating": round(float(feedback["rating"] or 0), 2),
            "memory_count": memory_count,
            "bandit_arms": self.get_bandit_arms(),
        }
