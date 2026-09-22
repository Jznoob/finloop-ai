from __future__ import annotations

import json
import time
from contextvars import ContextVar
from typing import Any

import httpx

from app.config import Settings, settings

CALL_TRACE: ContextVar[list[dict] | None] = ContextVar("model_trace", default=None)


class ModelGateway:
    """Optional OpenAI-compatible gateway with a deterministic offline fallback."""

    def __init__(self, app_settings: Settings | None = None) -> None:
        self.settings = app_settings or settings

    @property
    def provider_label(self) -> str:
        if self.settings.model_provider == "deterministic" or not self.settings.api_key:
            return "deterministic/local"
        return f"openai-compatible/{self.settings.model_name}"

    async def generate_json(
        self,
        system: str,
        user: str,
        fallback: dict[str, Any],
    ) -> dict[str, Any]:
        trace = CALL_TRACE.get()
        started = time.perf_counter()

        def record(outcome: str) -> None:
            if trace is not None:
                trace.append(
                    {
                        "outcome": outcome,
                        "configured_provider": self.provider_label,
                        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                    }
                )

        if self.settings.model_provider == "deterministic" or not self.settings.api_key:
            record("local-template")
            return fallback
        payload = {
            "model": self.settings.model_name,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        headers = {"Authorization": f"Bearer {self.settings.api_key}"}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.settings.base_url.rstrip('/')}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            generated = json.loads(content)
            if not isinstance(generated, dict) or any(
                not isinstance(generated.get(key), str)
                or not generated[key].strip()
                or len(generated[key]) > 6000
                for key in fallback
            ):
                record("fallback:invalid-schema")
                return fallback
            record("remote-success")
            return generated
        except (httpx.HTTPError, KeyError, json.JSONDecodeError, TypeError, IndexError):
            record("fallback:provider-error")
            return fallback
