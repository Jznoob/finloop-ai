from __future__ import annotations

import asyncio

from app.models import AgentArtifact, RunRequest, Segment
from app.services.scenarios import SCENARIOS, classify_scenario


class InsightAgent:
    name = "insight-agent"

    async def run(self, request: RunRequest, segment: Segment) -> AgentArtifact:
        await asyncio.sleep(0)
        scenario = classify_scenario(request)
        if "波动" in request.market_signal or "回撤" in request.market_signal:
            climate = "risk-off"
        elif "活跃" in request.market_signal or "回升" in request.market_signal:
            climate = "selective-risk-on"
        else:
            climate = "neutral"
        intent = SCENARIOS[scenario]["intent"]
        return AgentArtifact(
            agent=self.name,
            title="客群与市场洞察",
            summary=f"{segment.name}当前更需要“{intent}”。",
            data={
                "market_climate": climate,
                "scenario": scenario,
                "method": "explicit keyword rules; not a calibrated probability",
                "jobs_to_be_done": intent,
                "concerns": segment.concerns,
                "risk_ceiling": segment.risk_level,
                "decision_hypothesis": f"围绕{segment.concerns[0]}组织内容，可降低决策焦虑。",
            },
        )
