from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import Settings, settings


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
        if self.settings.model_provider == "deterministic" or not self.settings.api_key:
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
            return generated if isinstance(generated, dict) else fallback
        except (httpx.HTTPError, KeyError, json.JSONDecodeError, TypeError):
            return fallback
