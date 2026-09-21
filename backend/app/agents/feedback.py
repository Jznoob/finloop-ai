from __future__ import annotations

from app.models import ExecutionResult, MemoryItem, Product, Segment
from app.services.bandit import BanditService
from app.services.memory import MemoryService


class FeedbackAgent:
    name = "feedback-agent"

    def __init__(self, memory: MemoryService, bandit: BanditService) -> None:
        self.memory = memory
        self.bandit = bandit

    def run(
        self,
        run_id: str,
        segment: Segment,
        product: Product,
        execution: ExecutionResult,
    ) -> list[MemoryItem]:
        converted = execution.conversion_rate >= 0.025
        self.bandit.record(execution.variant, converted)
        episodic = self.memory.remember(
            namespace=segment.id,
            kind="episodic",
            content=(
                f"运行 {run_id} 使用 {execution.variant} 版本触达 {segment.name}，"
                f"打开率 {execution.open_rate:.1%}，转化率 {execution.conversion_rate:.1%}。"
            ),
            importance=0.78,
            metadata={"run_id": run_id, "variant": execution.variant},
        )
        semantic = self.memory.remember(
            namespace=segment.id,
            kind="semantic",
            content=(
                f"{segment.name}对{segment.concerns[0]}敏感；{product.category}内容应优先解释"
                f"{product.risks[0]}并强调持有期限。"
            ),
            importance=0.68,
            metadata={"product_id": product.id},
        )
        procedural = self.memory.remember(
            namespace="global",
            kind="procedural",
            content="生成金融营销内容时，先做适当性匹配，再生成内容，最后执行合规闸门。",
            importance=0.95,
            metadata={"source": "feedback-loop", "run_id": run_id},
        )
        return [episodic, semantic, procedural]
