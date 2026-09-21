from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import build_router
from app.config import Settings
from app.core.runtime import AgentRuntime
from app.db import Database


def test_api_run_and_dashboard(database: Database, test_settings: Settings) -> None:
    app = FastAPI()
    app.include_router(build_router(database, AgentRuntime(database, test_settings)))

    with TestClient(app) as client:
        response = client.post(
            "/api/runs",
            json={
                "segment_id": "growth-explorer",
                "objective": "解释长期投资纪律",
                "market_signal": "宽基指数成交活跃度回升但仍有不确定性",
            },
        )
        assert response.status_code == 200
        run = response.json()
        assert run["status"] == "completed"

        dashboard = client.get("/api/dashboard")
        assert dashboard.status_code == 200
        assert dashboard.json()["metrics"]["total_runs"] == 1
        assert len(dashboard.json()["pipeline"]) == 7
