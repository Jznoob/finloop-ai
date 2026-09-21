from __future__ import annotations

from app.catalog import PRODUCTS
from app.models import AgentArtifact, Citation, Product, RunRequest, Segment
from app.services.bandit import BanditService
from app.services.model_gateway import ModelGateway


class StrategyAgent:
    name = "strategy-agent"

    def __init__(self, bandit: BanditService, model_gateway: ModelGateway) -> None:
        self.bandit = bandit
        self.model_gateway = model_gateway

    async def run(
        self,
        request: RunRequest,
        segment: Segment,
        insight: AgentArtifact,
        citations: list[Citation],
        context: str,
    ) -> tuple[AgentArtifact, Product, str]:
        eligible = [
            product
            for product in PRODUCTS.values()
            if product.risk_level <= segment.risk_level
        ]
        category_preference = {
            "steady-planner": "固收+",
            "growth-explorer": "权益量化",
            "pro-allocator": "多资产",
        }.get(segment.id)
        product = next(
            (candidate for candidate in eligible if candidate.category == category_preference),
            max(eligible, key=lambda candidate: candidate.risk_level),
        )
        variant, bandit_scores = self.bandit.select()
        fallback = {
            "angle": {
                "clarity": "把复杂波动拆成可理解、可行动的三步",
                "evidence": "用制度依据和情景证据建立信任",
                "scenario": "用压力情景帮助客户校准预期",
            }[variant],
            "reason": f"{product.name}的 R{product.risk_level} 不高于客群 C{segment.risk_level}",
            "north_star_metric": "教育内容完成率",
        }
        generated = await self.model_gateway.generate_json(
            system="你是金融机构营销策略智能体。只输出 JSON，不承诺收益，严格遵守适当性。",
            user=f"根据以下已脱敏上下文给出 angle、reason、north_star_metric：\n{context}",
            fallback=fallback,
        )
        data = {
            "objective": request.objective,
            "product_id": product.id,
            "product_name": product.name,
            "product_risk": product.risk_level,
            "segment_risk": segment.risk_level,
            "creative_variant": variant,
            "bandit_scores": bandit_scores,
            "angle": generated.get("angle", fallback["angle"]),
            "reason": generated.get("reason", fallback["reason"]),
            "north_star_metric": generated.get(
                "north_star_metric", fallback["north_star_metric"]
            ),
            "guardrails": ["风险等级不倒挂", "不使用收益承诺", "所有关键结论可追溯"],
        }
        return (
            AgentArtifact(
                agent=self.name,
                title="下一最佳行动",
                summary=f"选择 {product.name} 的教育型触达，创意策略为 {variant}。",
                data=data,
                citations=citations[:3],
                confidence=0.88,
            ),
            product,
            variant,
        )
