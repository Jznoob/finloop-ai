from __future__ import annotations

import math
from datetime import UTC, datetime
from uuid import uuid4

from app.db import Database
from app.models import MemoryItem
from app.services.retrieval import tokenize


class MemoryService:
    """Three-layer memory with relevance, importance and freshness ranking."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def remember(
        self,
        namespace: str,
        kind: str,
        content: str,
        importance: float,
        metadata: dict | None = None,
    ) -> MemoryItem:
        memory = MemoryItem(
            id=f"mem_{uuid4().hex[:12]}",
            namespace=namespace,
            kind=kind,
            content=content,
            importance=importance,
            metadata=metadata or {},
        )
        self.database.put_memory(memory.model_dump())
        return memory

    def recall(self, namespace: str, query: str, limit: int = 5) -> list[MemoryItem]:
        candidates = self.database.list_memories(namespace, limit=40)
        query_tokens = set(tokenize(query))
        now = datetime.now(UTC)
        ranked: list[tuple[float, dict]] = []
        for candidate in candidates:
            candidate_tokens = set(tokenize(candidate["content"]))
            overlap = len(query_tokens & candidate_tokens) / max(
                1, len(query_tokens | candidate_tokens)
            )
            created = datetime.fromisoformat(candidate["created_at"])
            age_days = max(0.0, (now - created).total_seconds() / 86_400)
            freshness = math.exp(-age_days / 45)
            kind_boost = {"procedural": 0.1, "semantic": 0.06, "episodic": 0.0}.get(
                candidate["kind"], 0
            )
            score = overlap * 0.55 + candidate["importance"] * 0.3 + freshness * 0.15 + kind_boost
            ranked.append((score, candidate))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [MemoryItem.model_validate(candidate) for _, candidate in ranked[:limit]]
