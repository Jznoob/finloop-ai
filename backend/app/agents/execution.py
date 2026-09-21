from __future__ import annotations

import hashlib

from app.models import ExecutionResult, Segment


class ExecutionAgent:
    name = "execution-agent"

    def run(self, run_id: str, segment: Segment, variant: str) -> ExecutionResult:
        audience = {"steady-planner": 1240, "growth-explorer": 980, "pro-allocator": 360}.get(
            segment.id, 500
        )
        digest = int(hashlib.sha256(f"{run_id}:{variant}".encode()).hexdigest()[:8], 16)
        delivery_rate = 0.972 + (digest % 12) / 1000
        open_base = {"app": 0.42, "wechat": 0.56, "email": 0.38}[segment.preferred_channel]
        variant_lift = {"clarity": 0.024, "evidence": 0.018, "scenario": 0.031}[variant]
        open_rate = min(0.78, open_base + variant_lift + (digest % 17) / 1000)
        conversion_rate = 0.018 + variant_lift / 3 + (digest % 9) / 1000
        delivered = int(audience * delivery_rate)
        opened = int(delivered * open_rate)
        converted = int(delivered * conversion_rate)
        return ExecutionResult(
            variant=variant,
            channel=segment.preferred_channel,
            audience_size=audience,
            delivered=delivered,
            opened=opened,
            converted=converted,
            open_rate=round(open_rate, 4),
            conversion_rate=round(conversion_rate, 4),
            idempotency_key=f"exec_{hashlib.sha1(run_id.encode()).hexdigest()[:16]}",
        )
