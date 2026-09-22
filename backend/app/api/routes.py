from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.api.studio import studio_router
from app.catalog import SEGMENTS
from app.core.jobs import JobManager
from app.core.runtime import AgentRuntime
from app.db import Database
from app.evals import evaluate
from app.models import (
    FeedbackRequest,
    KnowledgeSearchResult,
    RunRequest,
    RunResult,
)
from app.services.retrieval import HybridRetriever


def build_router(
    database: Database,
    runtime: AgentRuntime,
    jobs: JobManager | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api")
    router.include_router(studio_router(database, runtime, jobs or JobManager(database, runtime)))
    retriever = HybridRetriever(database)

    @router.get("/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "service": "finloop-ai",
            "mode": runtime.model_gateway.provider_label,
            "database": "ready",
        }

    @router.get("/dashboard")
    async def dashboard() -> dict:
        return {
            "metrics": database.dashboard_metrics(),
            "segments": [segment.model_dump() for segment in SEGMENTS.values()],
            "recent_runs": database.list_runs(limit=8),
            "pipeline": [
                {"id": "insight", "name": "洞察", "agent": "Insight Agent"},
                {"id": "retrieve", "name": "知识", "agent": "Knowledge Agent"},
                {"id": "decide", "name": "决策", "agent": "Strategy Agent"},
                {"id": "compose", "name": "内容", "agent": "Content Agent"},
                {"id": "guard", "name": "合规", "agent": "Compliance Agent"},
                {"id": "execute", "name": "执行", "agent": "Execution Agent"},
                {"id": "learn", "name": "反馈", "agent": "Feedback Agent"},
            ],
        }

    @router.post("/runs", response_model=RunResult)
    async def create_run(request: RunRequest) -> RunResult:
        if request.segment_id not in SEGMENTS:
            raise HTTPException(status_code=422, detail="未知客群")
        return await runtime.run(request)

    @router.get("/runs")
    async def list_runs(limit: int = Query(default=20, ge=1, le=100)) -> list[dict]:
        return database.list_runs(limit=limit)

    @router.get("/runs/{run_id}")
    async def get_run(run_id: str) -> dict:
        run = database.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="运行记录不存在")
        return run

    @router.get("/runs/{run_id}/events")
    async def get_events(run_id: str) -> list[dict]:
        if database.get_run(run_id) is None:
            raise HTTPException(status_code=404, detail="运行记录不存在")
        return database.list_events(run_id)

    @router.get("/knowledge/search", response_model=KnowledgeSearchResult)
    async def search_knowledge(
        q: str = Query(min_length=2, max_length=300),
    ) -> KnowledgeSearchResult:
        return KnowledgeSearchResult(query=q, results=retriever.search(q))

    @router.post("/feedback")
    async def save_feedback(feedback: FeedbackRequest) -> dict:
        try:
            database.save_feedback(
                feedback.run_id, feedback.converted, feedback.rating, feedback.note
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="运行记录不存在") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {"saved": True, "run_id": feedback.run_id}

    @router.post("/evals/run")
    async def run_evaluations() -> dict:
        report = await evaluate(runtime)
        database.save_report(report["id"], "evaluation", report)
        return report

    @router.get("/architecture")
    async def architecture() -> dict:
        return {
            "pattern": "event-driven typed workflow",
            "memory": ["episodic", "semantic", "procedural"],
            "retrieval": "paragraph BM25 + explicit policy pins",
            "safety": [
                "PII redaction",
                "suitability gate",
                "citation gate",
                "idempotent execution",
            ],
            "execution": "simulation-only by default",
        }

    return router
