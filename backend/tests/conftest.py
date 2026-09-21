from __future__ import annotations

from pathlib import Path

import pytest

from app.config import PROJECT_ROOT, Settings
from app.db import Database


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        model_provider="deterministic",
        model_name="test-model",
        api_key="",
        base_url="http://unused.local/v1",
        database_path=tmp_path / "test.db",
        knowledge_path=PROJECT_ROOT / "data" / "knowledge",
        eval_path=PROJECT_ROOT / "evals" / "cases.json",
        frontend_dist=PROJECT_ROOT / "frontend" / "dist",
        cors_origins=("http://testserver",),
        context_token_budget=1800,
    )


@pytest.fixture
def database(test_settings: Settings) -> Database:
    instance = Database(test_settings)
    instance.initialize()
    return instance
