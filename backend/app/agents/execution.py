from __future__ import annotations

import hashlib

from app.models import ExecutionResult, Segment
from app.services.experiments import simulate


class ExecutionAgent:
    name = "execution-agent"

    def run(self, run_id: str, segment: Segment, variant: str, seed: int = 42) -> ExecutionResult:
        audience = {"steady-planner": 1240, "growth-explorer": 980, "pro-allocator": 360}[
            segment.id
        ]
        sampled = simulate(seed, audience, variant, segment.preferred_channel)
        return ExecutionResult(
            **{
                key: sampled[key]
                for key in (
                    "variant",
                    "channel",
                    "audience_size",
                    "delivered",
                    "opened",
                    "converted",
                    "open_rate",
                    "conversion_rate",
                )
            },
            idempotency_key=f"exec_{hashlib.sha256(run_id.encode()).hexdigest()[:16]}",
        )
