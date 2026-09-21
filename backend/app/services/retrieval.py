from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from typing import Any

from app.db import Database
from app.models import Citation

LATIN_PATTERN = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]+")
HAN_PATTERN = re.compile(r"[\u4e00-\u9fff]+")
STOP_WORDS = {
    "的",
    "了",
    "和",
    "与",
    "及",
    "或",
    "是",
    "在",
    "为",
    "对",
    "不得",
    "客户",
    "进行",
}


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    tokens = LATIN_PATTERN.findall(lowered)
    for sequence in HAN_PATTERN.findall(lowered):
        tokens.extend(char for char in sequence if char not in STOP_WORDS)
        tokens.extend(sequence[index : index + 2] for index in range(len(sequence) - 1))
    return [token for token in tokens if token and token not in STOP_WORDS]


def _hashed_vector(tokens: list[str], dimensions: int = 256) -> dict[int, float]:
    vector: Counter[int] = Counter()
    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        raw = int.from_bytes(digest, "big")
        index = raw % dimensions
        sign = 1 if raw & 1 else -1
        vector[index] += sign * (1 + math.log1p(len(token)))
    norm = math.sqrt(sum(value * value for value in vector.values())) or 1.0
    return {index: value / norm for index, value in vector.items()}


def _cosine(left: dict[int, float], right: dict[int, float]) -> float:
    return max(0.0, sum(value * right.get(index, 0) for index, value in left.items()))


class HybridRetriever:
    """Small, dependency-free hybrid retriever suited to an auditable demo corpus."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def search(self, query: str, limit: int = 4) -> list[Citation]:
        documents = self.database.list_documents()
        if not documents:
            return []
        query_tokens = tokenize(query)
        query_counts = Counter(query_tokens)
        doc_tokens = [
            tokenize(f"{doc['title']} {doc['category']} {doc['content']}")
            for doc in documents
        ]
        document_frequency: Counter[str] = Counter()
        for tokens in doc_tokens:
            document_frequency.update(set(tokens))
        average_length = sum(len(tokens) for tokens in doc_tokens) / len(doc_tokens)
        query_vector = _hashed_vector(query_tokens)

        scored: list[tuple[float, dict[str, Any]]] = []
        for document, tokens in zip(documents, doc_tokens, strict=True):
            counts = Counter(tokens)
            sparse = 0.0
            for token, query_frequency in query_counts.items():
                frequency = counts[token]
                if not frequency:
                    continue
                inverse_frequency = math.log(
                    1 + (len(documents) - document_frequency[token] + 0.5)
                    / (document_frequency[token] + 0.5)
                )
                denominator = frequency + 1.2 * (
                    0.25 + 0.75 * len(tokens) / max(average_length, 1)
                )
                sparse += inverse_frequency * (frequency * 2.2 / denominator) * query_frequency
            semantic = _cosine(query_vector, _hashed_vector(tokens))
            category_boost = 0.0
            if (
                any(word in query for word in ("合规", "风险", "适当", "营销"))
                and document["category"] in {"compliance", "suitability"}
            ):
                category_boost = 0.18
            raw_score = sparse + semantic * 1.8 + category_boost
            scored.append((raw_score, document))

        scored.sort(key=lambda item: item[0], reverse=True)
        top_score = scored[0][0] or 1.0
        results: list[Citation] = []
        for score, document in scored[:limit]:
            results.append(
                Citation(
                    document_id=document["id"],
                    title=document["title"],
                    source=document["source"],
                    excerpt=self._excerpt(document["content"], query_tokens),
                    score=round(min(1.0, max(0.05, score / top_score)), 3),
                )
            )
        return results

    @staticmethod
    def _excerpt(content: str, query_tokens: list[str], length: int = 150) -> str:
        compact = " ".join(content.split())
        positions = [compact.lower().find(token) for token in query_tokens if len(token) > 1]
        positions = [position for position in positions if position >= 0]
        center = min(positions) if positions else 0
        start = max(0, center - 35)
        end = min(len(compact), start + length)
        prefix = "…" if start else ""
        suffix = "…" if end < len(compact) else ""
        return f"{prefix}{compact[start:end]}{suffix}"
