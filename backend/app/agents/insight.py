from __future__ import annotations

import asyncio
import hashlib

from app.models import AgentArtifact, RunRequest, Segment


class InsightAgent:
    name = "insight-agent"

    async def run(self, request: RunRequest, segment: Segment) -> AgentArtifact:
        await asyncio.sleep(0)
        signal_strength = 65 + int(
            hashlib.sha256(request.market_signal.encode("utf-8")).hexdigest()[:2], 16
        ) % 25
        if "波动" in request.market_signal or "回撤" in request.market_signal:
            climate = "risk-off"
            intent = "先解释波动，再给出与承受能力匹配的行动框架"
        elif "活跃" in request.market_signal or "回升" in request.market_signal:
            climate = "selective-risk-on"
            intent = "用纪律和情景边界承接增长兴趣"
        else:
            climate = "neutral"
            intent = "提供中性、可验证的配置教育"
        return AgentArtifact(
            agent=self.name,
            title="客群与市场洞察",
            summary=f"{segment.name}当前更需要“{intent}”。",
            data={
                "market_climate": climate,
                "signal_strength": signal_strength,
                "jobs_to_be_done": intent,
                "concerns": segment.concerns,
                "risk_ceiling": segment.risk_level,
                "decision_hypothesis": f"围绕{segment.concerns[0]}组织内容，可降低决策焦虑。",
            },
            confidence=round(signal_strength / 100, 2),
        )
