from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = "FinLoop AI"
    environment: str = os.getenv("FINLOOP_ENV", "development")
    model_provider: str = os.getenv("FINLOOP_MODEL_PROVIDER", "deterministic")
    model_name: str = os.getenv("FINLOOP_MODEL_NAME", "gpt-5-mini")
    api_key: str = os.getenv("FINLOOP_API_KEY", "")
    base_url: str = os.getenv("FINLOOP_BASE_URL", "https://api.openai.com/v1")
    database_path: Path = Path(
        os.getenv("FINLOOP_DATABASE_PATH", str(PROJECT_ROOT / "data" / "finloop.db"))
    ).resolve()
    knowledge_path: Path = PROJECT_ROOT / "data" / "knowledge"
    eval_path: Path = PROJECT_ROOT / "evals" / "cases.json"
    frontend_dist: Path = PROJECT_ROOT / "frontend" / "dist"
    cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv("FINLOOP_CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    )
    context_token_budget: int = int(os.getenv("FINLOOP_CONTEXT_TOKEN_BUDGET", "1800"))


settings = Settings()
