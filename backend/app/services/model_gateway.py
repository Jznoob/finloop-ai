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

    async def probe(self) -> dict[str, Any]:
        """Run one explicit, sanitized compatibility probe without persisting its output."""

        token = CALL_TRACE.set([])
        try:
            await self.generate_json(
                system=(
                    "你是模型连通性诊断器。只返回 JSON 对象，"
                    "字段必须为 status 和 message，不要输出其他内容。"
                ),
                user="返回 status=ready，message=finloop-probe。",
                fallback={"status": "ready", "message": "finloop-probe"},
            )
            trace = CALL_TRACE.get() or []
        finally:
            CALL_TRACE.reset(token)
        call = trace[0] if trace else {"outcome": "fallback:provider-error", "latency_ms": 0}
        outcome = str(call["outcome"])
        status = {
            "remote-success": "ready",
            "local-template": "local",
            "fallback:invalid-schema": "invalid-schema",
            "fallback:provider-error": "unavailable",
        }.get(outcome, "unavailable")
        message = {
            "ready": "远程接口连通，且结构化 JSON 响应通过校验。",
            "local": "当前为本地模板模式，没有向远程模型发送请求。",
            "invalid-schema": "接口已响应，但返回内容未通过 JSON 字段校验。",
            "unavailable": "远程调用失败，请检查地址、密钥、模型名与接口兼容性。",
        }[status]
        return {
            "status": status,
            "provider": self.provider_label,
            "key_configured": bool(self.settings.api_key),
            "remote_request_sent": status != "local",
            "outcome": outcome,
            "latency_ms": call.get("latency_ms", 0),
            "message": message,
            "cost_notice": "远程模式下，每次诊断会产生一次小型模型调用，可能产生费用。",
        }
