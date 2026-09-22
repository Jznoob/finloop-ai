from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class Segment(BaseModel):
    id: str
    name: str
    description: str
    risk_level: int = Field(ge=1, le=5)
    preferred_channel: Literal["app", "wechat", "email"]
    concerns: list[str]


class Product(BaseModel):
    id: str
    name: str
    risk_level: int = Field(ge=1, le=5)
    category: str
    horizon: str
    highlights: list[str]
    risks: list[str]


class Citation(BaseModel):
    document_id: str
    title: str
    source: str
    excerpt: str
    score: float = Field(ge=0, le=1)
    content_hash: str = ""
    effective_date: str = ""
    retrieval_reason: str = "query"


class MemoryItem(BaseModel):
    id: str
    namespace: str
    kind: Literal["episodic", "semantic", "procedural"]
    content: str
    importance: float = Field(ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class ContextTrace(BaseModel):
    budget: int
    estimated_tokens: int
    included_sections: list[str]
    dropped_sections: list[str]
    redactions: int = 0


class AgentArtifact(BaseModel):
    agent: str
    title: str
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)
    citations: list[Citation] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)


class PipelineEvent(BaseModel):
    sequence: int
    run_id: str
    timestamp: datetime = Field(default_factory=utc_now)
    agent: str
    stage: Literal[
        "ingest",
        "insight",
        "retrieve",
        "decide",
        "compose",
        "guard",
        "execute",
        "learn",
        "complete",
    ]
    status: Literal["started", "completed", "revised", "blocked"]
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)


class RunRequest(BaseModel):
    segment_id: str = "steady-planner"
    objective: str = Field(
        default="在市场波动加剧时，为稳健客户提供有依据的资产配置教育",
        min_length=4,
        max_length=300,
    )
    market_signal: str = Field(
        default="权益市场近五日波动显著放大，客户对回撤的咨询增加",
        min_length=4,
        max_length=500,
    )
    dry_run: Literal[True] = True
    seed: int = Field(default=42, ge=0, le=2**31 - 1)
    variant: Literal["auto", "clarity", "evidence", "scenario"] = "auto"


class ComplianceResult(BaseModel):
    status: Literal["approved", "revised", "blocked"]
    score: int = Field(ge=0, le=100)
    violations: list[str]
    checks: list[dict[str, Any]]
    final_copy: str


class ExecutionResult(BaseModel):
    mode: Literal["simulation", "live"] = "simulation"
    variant: str
    channel: str
    audience_size: int
    delivered: int
    opened: int
    converted: int
    open_rate: float
    conversion_rate: float
    idempotency_key: str


class RunResult(BaseModel):
    run_id: str
    status: Literal["completed", "blocked", "failed"]
    created_at: datetime
    completed_at: datetime
    request: RunRequest
    segment: Segment
    selected_product: Product | None
    artifacts: list[AgentArtifact]
    events: list[PipelineEvent]
    citations: list[Citation]
    compliance: ComplianceResult
    execution: ExecutionResult | None
    context_trace: ContextTrace
    memory_updates: list[MemoryItem]
    model_provider: str
    evidence_passport: dict[str, Any] = Field(default_factory=dict)
    model_calls: list[dict[str, Any]] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    run_id: str
    converted: bool
    rating: int = Field(default=4, ge=1, le=5)
    note: str = Field(default="", max_length=500)


class KnowledgeSearchResult(BaseModel):
    query: str
    results: list[Citation]
    strategy: str = "paragraph BM25 + document max-pooling (no embeddings)"


class EvaluationCaseResult(BaseModel):
    case_id: str
    passed: bool
    compliance_ok: bool
    citation_recall: float
    suitability_ok: bool
    latency_ms: float
    notes: list[str]


class EvaluationReport(BaseModel):
    total: int
    passed: int
    pass_rate: float
    average_citation_recall: float
    average_latency_ms: float
    cases: list[EvaluationCaseResult]
