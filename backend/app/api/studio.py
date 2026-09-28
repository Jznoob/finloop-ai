from __future__ import annotations

import asyncio
import json
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.catalog import SEGMENTS
from app.core.jobs import JobManager
from app.core.runtime import AgentRuntime
from app.db import Database
from app.models import RunRequest
from app.services.comparison import compare_runs
from app.services.experiments import ExperimentRequest, compare
from app.services.retrieval import document_hash


class MemoryState(BaseModel):
    active: bool


def studio_router(database: Database, runtime: AgentRuntime, jobs: JobManager) -> APIRouter:
    router = APIRouter()

    @router.post("/jobs", status_code=202)
    async def submit(request: RunRequest, idempotency_key: str | None = Header(default=None)):
        if request.segment_id not in SEGMENTS:
            raise HTTPException(422, "未知客群")
        if idempotency_key and not 8 <= len(idempotency_key) <= 128:
            raise HTTPException(422, "幂等键长度须为 8–128")
        try:
            return jobs.submit(request, idempotency_key or uuid4().hex)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    @router.get("/jobs")
    async def history():
        return database.list_jobs()

    @router.get("/jobs/{job_id}")
    async def job_status(job_id: str):
        job = database.get_job(job_id)
        if job is None:
            raise HTTPException(404, "任务不存在")
        job["events"] = database.list_events(job["run_id"]) if job["run_id"] else []
        job["history"] = [
            {**attempt, "events": database.list_events(attempt["run_id"])}
            for attempt in database.job_attempts(job_id)
        ]
        return job

    @router.post("/jobs/{job_id}/retry", status_code=202)
    async def retry(job_id: str):
        if not database.get_job(job_id):
            raise HTTPException(404, "任务不存在")
        if not database.retry_job(job_id):
            raise HTTPException(409, "只有失败或中断任务允许重试")
        jobs.schedule(job_id)
        return database.get_job(job_id)

    @router.get("/knowledge")
    async def knowledge():
        return [{**doc, "content_hash": document_hash(doc)} for doc in database.list_documents()]

    @router.get("/memories")
    async def memories():
        return database.memory_inventory()

    @router.patch("/memories/{memory_id}")
    async def memory_state(memory_id: str, state: MemoryState):
        try:
            database.set_memory_active(memory_id, state.active)
        except KeyError as error:
            raise HTTPException(404, "记忆不存在") from error
        return {"id": memory_id, "active": state.active}

    @router.get("/experiments")
    async def experiments():
        return database.reports("experiment")

    @router.post("/experiments")
    async def experiment(request: ExperimentRequest):
        try:
            return await asyncio.to_thread(compare, database, request)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @router.get("/evals/reports")
    async def evaluation_reports():
        return database.reports("evaluation")

    @router.get("/runs/{run_id}/review")
    async def review(run_id: str):
        return database.review_for(run_id)

    @router.get("/runs/{run_id}/export")
    async def export(run_id: str):
        result = database.get_run(run_id)
        if not result:
            raise HTTPException(404, "运行不存在")
        return Response(
            json.dumps(result, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{result.get("run_id", "run")}.json"'
            },
        )

    @router.get("/runs/{run_id}/evidence")
    async def evidence(run_id: str):
        result = database.get_run(run_id)
        if not result:
            raise HTTPException(404, "运行不存在")
        current = {d["id"]: document_hash(d) for d in database.list_documents()}
        passport = result.get("evidence_passport", {})
        return {
            **passport,
            "verification": [
                {
                    "id": source["id"],
                    "snapshot_integrity": document_hash(source) == source["content_hash"],
                    "current_matches": current.get(source["id"]) == source["content_hash"],
                }
                for source in passport.get("sources", [])
            ],
        }

    @router.get("/configuration")
    async def configuration():
        return {
            "provider": runtime.model_gateway.provider_label,
            "key_configured": bool(runtime.settings.api_key),
            "context_budget": runtime.settings.context_token_budget,
            "execution": "simulation-only",
            "runtime": "single-process / max 2 concurrent jobs",
            "retry": "原始输入重跑；旧尝试事件保留，不是节点级断点续跑",
            "retrieval": "中文二元词 + 段落 BM25；无 embedding 模型",
            "learning": "人工复核权重；模拟转化不参与策略学习",
            "token_estimator": (
                "上下文装箱的字符近似预算；不含系统提示与节点元数据，"
                "并非完整请求 token 数"
            ),
        }

    @router.post("/model/probe")
    async def model_probe():
        return await runtime.model_gateway.probe()

    @router.get("/runs/compare")
    async def run_comparison(left: str, right: str):
        if left == right:
            raise HTTPException(422, "请选择两条不同的运行")
        left_run, right_run = database.get_run(left), database.get_run(right)
        if left_run is None or right_run is None:
            raise HTTPException(404, "对比运行不存在")
        if not left_run.get("result_json", True) or not right_run.get("result_json", True):
            raise HTTPException(409, "只有已保存完整结果的运行可以比较")
        return compare_runs(left_run, right_run)

    return router
