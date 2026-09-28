from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import build_router
from app.config import settings
from app.core.jobs import JobManager
from app.core.runtime import AgentRuntime
from app.db import Database

database = Database()
runtime = AgentRuntime(database)
jobs = JobManager(database, runtime)


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.initialize()
    jobs.recover()
    yield
    await jobs.shutdown()


app = FastAPI(
    title="FinLoop AI API",
    description="Auditable multi-agent growth intelligence for financial services.",
    version="0.3.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(build_router(database, runtime, jobs))


if settings.frontend_dist.exists():
    assets = settings.frontend_dist / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "接口不存在")
        frontend_root = settings.frontend_dist.resolve()
        requested = (frontend_root / path).resolve()
        if path and requested.is_relative_to(frontend_root) and requested.is_file():
            return FileResponse(requested)
        return FileResponse(frontend_root / "index.html")
