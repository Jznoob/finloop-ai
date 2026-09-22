from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from datetime import date

from app.db import Database
from app.models import Citation


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9][a-z0-9_-]+", text.lower())
    for phrase in re.findall(r"[\u4e00-\u9fff]+", text):
        tokens.extend(phrase[i : i + 2] for i in range(len(phrase) - 1))
    return tokens


def document_hash(document: dict) -> str:
    value = "\n".join(
        str(document[key])
        for key in ("id", "title", "category", "source", "effective_date", "content")
    )
    return hashlib.sha256(value.encode()).hexdigest()


class HybridRetriever:
    """Paragraph BM25 baseline; no claimed semantic embeddings or probability scores."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def search(
        self, query: str, limit: int = 3, *, documents: list[dict] | None = None
    ) -> list[Citation]:
        query_terms = set(tokenize(query))
        if not query_terms:
            return []
        paragraphs = []
        for doc in documents if documents is not None else self.database.list_documents():
            if doc["effective_date"] > date.today().isoformat():
                continue
            for paragraph in doc["content"].split("\n\n"):
                terms = tokenize(f"{doc['title']} {paragraph}")
                paragraphs.append((doc, paragraph, terms))
        if not paragraphs:
            return []
        frequencies: Counter = Counter()
        for _, _, terms in paragraphs:
            frequencies.update(set(terms))
        avg_len = sum(len(p[2]) for p in paragraphs) / len(paragraphs)
        best: dict[str, tuple[float, dict, str]] = {}
        for doc, paragraph, terms in paragraphs:
            counts = Counter(terms)
            overlap = query_terms & counts.keys()
            if not overlap:
                continue
            score = 0.0
            for term in overlap:
                tf = counts[term]
                idf = math.log(
                    1 + (len(paragraphs) - frequencies[term] + 0.5) / (frequencies[term] + 0.5)
                )
                score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * len(terms) / avg_len))
            if score > best.get(doc["id"], (0, {}, ""))[0]:
                best[doc["id"]] = (score, doc, paragraph)
        ranked = sorted(best.values(), key=lambda row: (-row[0], row[1]["id"]))[:limit]
        return [
            self._citation(doc, paragraph, score / (score + 8)) for score, doc, paragraph in ranked
        ]

    @staticmethod
    def _citation(doc: dict, paragraph: str, score: float, reason: str = "query") -> Citation:
        return Citation(
            document_id=doc["id"],
            title=doc["title"],
            source=doc["source"],
            excerpt=paragraph,
            score=round(score, 4),
            content_hash=document_hash(doc),
            effective_date=doc["effective_date"],
            retrieval_reason=reason,
        )

    def evidence(self, query: str) -> list[Citation]:
        return self.evidence_snapshot(query)[0]

    def evidence_snapshot(self, query: str) -> tuple[list[Citation], list[dict]]:
        """Mandatory policy pins are recorded separately from query retrieval."""
        documents = self.database.list_documents()
        citations = {c.document_id: c for c in self.search(query, limit=2, documents=documents)}
        for doc in documents:
            if (
                doc["id"] in {"CMP-001", "SUT-002", "PRD-DEMO"}
                and doc["effective_date"] <= date.today().isoformat()
            ):
                citations[doc["id"]] = self._citation(doc, doc["content"], 1.0, "mandatory-policy")
        sources = [
            {**doc, "content_hash": document_hash(doc)}
            for doc in documents
            if doc["id"] in citations
        ]
        return list(citations.values()), sources
