from __future__ import annotations

import asyncio
import logging
from uuid import uuid4

from app.core.runtime import AgentRuntime
from app.db import Database
from app.models import RunRequest
from app.services.context import ContextBuilder

logger = logging.getLogger(__name__)


class JobManager:
    """Single-process, bounded worker. Durable acceptance + explicit full-attempt retry."""

    def __init__(self, database: Database, runtime: AgentRuntime) -> None:
        self.database, self.runtime = database, runtime
        self.tasks: dict[str, asyncio.Task] = {}
        self.capacity = asyncio.Semaphore(2)

    def submit(self, request: RunRequest, key: str) -> dict:
        safe = request.model_copy(
            update={
                "objective": ContextBuilder.redact(request.objective)[0],
                "market_signal": ContextBuilder.redact(request.market_signal)[0],
            }
        )
        job = self.database.submit_job(f"job_{uuid4().hex[:12]}", key, safe.model_dump())
        if job["status"] == "queued":
            self.schedule(job["id"])
        return job

    def schedule(self, job_id: str) -> None:
        existing = self.tasks.get(job_id)
        if existing is None or existing.done():
            task = asyncio.create_task(self.work(job_id))
            self.tasks[job_id] = task

            def release(finished: asyncio.Task) -> None:
                if self.tasks.get(job_id) is finished:
                    self.tasks.pop(job_id, None)

            task.add_done_callback(release)

    async def work(self, job_id: str) -> None:
        async with self.capacity:
            run_id = f"run_{uuid4().hex[:12]}"
            if not self.database.claim_job(job_id, run_id):
                return
            job = self.database.get_job(job_id)
            try:
                async with asyncio.timeout(90):
                    result = await self.runtime.run(RunRequest(**job["request"]), run_id=run_id)
                self.database.finish_job(job_id, result.status)
            except asyncio.CancelledError:
                self.database.mark_run_failed(run_id)
                self.database.finish_job(job_id, "interrupted", "服务中断，可重新运行")
                raise
            except Exception:
                logger.exception("Job %s failed", job_id)
                self.database.mark_run_failed(run_id)
                self.database.finish_job(job_id, "failed", "运行失败，请检查服务日志后重试")

    def recover(self) -> None:
        self.database.recover_jobs()
        for job_id in self.database.queued_job_ids():
            self.schedule(job_id)

    async def shutdown(self) -> None:
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
