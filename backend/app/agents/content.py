from __future__ import annotations

from app.models import AgentArtifact, Citation, Product, RunRequest, Segment
from app.services.model_gateway import ModelGateway


class ContentAgent:
    name = "content-agent"

    def __init__(self, model_gateway: ModelGateway) -> None:
        self.model_gateway = model_gateway

    async def run(
        self,
        request: RunRequest,
        segment: Segment,
        product: Product,
        variant: str,
        citations: list[Citation],
        context: str,
    ) -> AgentArtifact:
        source_tags = " ".join(f"[{citation.document_id}]" for citation in citations[:3])
        openings = {
            "clarity": f"市场波动变大时，先把问题拆清楚，比追逐短期方向更重要。{source_tags}",
            "evidence": f"近期波动值得关注，但单一信号不足以推导确定结论。{source_tags}",
            "scenario": f"如果波动延续、回落或横盘，不同情景需要不同的仓位纪律。{source_tags}",
        }
        fallback_copy = (
            f"【{segment.name}的波动应对清单】\n"
            f"{openings[variant]}\n\n"
            f"结合你对{segment.concerns[0]}的关注，可以先检查资金使用期限和可承受回撤，"
            f"再了解 R{product.risk_level} 的「{product.name}」如何通过"
            f"{'、'.join(product.highlights[:2])}服务于组合目标。\n\n"
            f"建议行动：阅读 3 分钟情景说明，完成风险承受能力复核后再决定是否进一步了解。\n\n"
            f"风险提示：本内容仅用于投资者教育，不构成投资建议或收益承诺。"
            f"产品可能面临{'、'.join(product.risks)}，净值会发生波动。"
        )
        generated = await self.model_gateway.generate_json(
            system=(
                "你是审慎的金融内容智能体。只返回 JSON 对象 {copy, rationale}。"
                "不得使用保本、稳赚、零风险、确定上涨或内幕消息等表达。"
            ),
            user=f"客群：{segment.name}\n产品：{product.model_dump_json()}\n上下文：\n{context}",
            fallback={"copy": fallback_copy, "rationale": "教育优先、弱销售、风险前置"},
        )
        copy = str(generated.get("copy") or fallback_copy)
        return AgentArtifact(
            agent=self.name,
            title="渠道内容草案",
            summary=copy,
            data={
                "copy": copy,
                "channel": segment.preferred_channel,
                "variant": variant,
                "rationale": generated.get("rationale", "教育优先、弱销售、风险前置"),
                "character_count": len(copy),
            },
            citations=citations[:3],
            confidence=0.85,
        )
