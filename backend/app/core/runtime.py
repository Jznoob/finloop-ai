from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

from app.agents import (
    ComplianceAgent,
    ContentAgent,
    ExecutionAgent,
    FeedbackAgent,
    InsightAgent,
    StrategyAgent,
)
from app.catalog import get_segment
from app.config import Settings, settings
from app.db import Database
from app.models import (
    AgentArtifact,
    PipelineEvent,
    RunRequest,
    RunResult,
)
from app.services.bandit import BanditService
from app.services.context import ContextBuilder, ContextSection
from app.services.memory import MemoryService
from app.services.model_gateway import CALL_TRACE, ModelGateway
from app.services.retrieval import HybridRetriever


class AgentRuntime:
    """Coordinates specialist agents as a typed, auditable workflow graph."""

    def __init__(self, database: Database, app_settings: Settings | None = None) -> None:
        self.settings = app_settings or settings
        self.database = database
        self.retriever = HybridRetriever(database)
        self.memory = MemoryService(database)
        self.bandit = BanditService(database)
        self.model_gateway = ModelGateway(self.settings)
        self.context_builder = ContextBuilder(self.settings.context_token_budget)
        self.insight_agent = InsightAgent()
        self.strategy_agent = StrategyAgent(self.bandit, self.model_gateway)
        self.content_agent = ContentAgent(self.model_gateway)
        self.compliance_agent = ComplianceAgent()
        self.execution_agent = ExecutionAgent()
        self.feedback_agent = FeedbackAgent(self.memory, self.bandit)

    async def run(self, request: RunRequest, run_id: str | None = None) -> RunResult:
        CALL_TRACE.set([])
        run_id = run_id or f"run_{uuid4().hex[:12]}"
        # Redact before persistence, retrieval, tracing or model calls, not just prompt packing.
        request = request.model_copy(
            update={
                "objective": self.context_builder.redact(request.objective)[0],
                "market_signal": self.context_builder.redact(request.market_signal)[0],
            }
        )
        created_at = datetime.now(UTC)
        segment = get_segment(request.segment_id)
        events: list[PipelineEvent] = []
        artifacts: list[AgentArtifact] = []
        self.database.create_run(
            run_id,
            request.objective,
            segment.id,
            request.market_signal,
            created_at.isoformat(),
        )

        def emit(
            agent: str,
            stage: str,
            status: str,
            message: str,
            payload: dict | None = None,
        ) -> None:
            event = PipelineEvent(
                sequence=len(events) + 1,
                run_id=run_id,
                agent=agent,
                stage=stage,
                status=status,
                message=message,
                payload=payload or {},
            )
            events.append(event)
            self.database.append_event(event.model_dump(mode="json"))

        emit(
            "orchestrator",
            "ingest",
            "completed",
            "任务已标准化，客户字段已最小化。",
            {"segment": segment.name, "dry_run": request.dry_run},
        )
        recalled = self.memory.recall(segment.id, f"{request.objective} {request.market_signal}")

        emit("insight-agent", "insight", "started", "分析市场信号与客群意图。")
        emit("knowledge-agent", "retrieve", "started", "检索制度、产品与运营知识。")
        insight_task = self.insight_agent.run(request, segment)
        retrieval_task = asyncio.to_thread(
            self.retriever.evidence_snapshot,
            f"{request.objective} {request.market_signal}",
        )
        insight, evidence = await asyncio.gather(insight_task, retrieval_task)
        citations, sources = evidence
        artifacts.append(insight)
        emit(
            "insight-agent",
            "insight",
            "completed",
            insight.summary,
            {"method": "keyword-rules", "calibrated_confidence": False},
        )
        knowledge_artifact = AgentArtifact(
            agent="knowledge-agent",
            title="可追溯知识证据",
            summary=f"查询检索与制度固定载入共 {len(citations)} 条依据，已保存原文快照。",
            data={"retrieval_strategy": "paragraph BM25 + explicit policy pins"},
            citations=citations,
        )
        artifacts.append(knowledge_artifact)
        emit(
            "knowledge-agent",
            "retrieve",
            "completed",
            knowledge_artifact.summary,
            {"document_ids": [citation.document_id for citation in citations]},
        )

        knowledge_text = "\n".join(
            f"[{citation.document_id}] {citation.title}: {citation.excerpt}"
            for citation in citations
        )
        memory_text = (
            "\n".join(
                f"[{memory.kind} | origin={memory.metadata.get('origin', 'legacy-unverified')}] "
                f"{memory.content}"
                for memory in recalled
            )
            or "暂无历史记忆，这是该客群的首次运行。"
        )
        context, context_trace = self.context_builder.build(
            [
                ContextSection(
                    "任务约束",
                    f"目标：{request.objective}\n市场信号：{request.market_signal}\n仅作演示，不执行真实触达。",
                    priority=100,
                    required=True,
                    token_cap=350,
                ),
                ContextSection(
                    "客群画像",
                    segment.model_dump_json(),
                    priority=95,
                    required=True,
                    token_cap=280,
                ),
                ContextSection(
                    "知识证据",
                    knowledge_text,
                    priority=90,
                    required=True,
                    token_cap=750,
                ),
                ContextSection(
                    "长期记忆",
                    memory_text,
                    priority=70,
                    token_cap=350,
                ),
                ContextSection(
                    "洞察结果",
                    insight.model_dump_json(),
                    priority=80,
                    token_cap=320,
                ),
            ]
        )

        emit("strategy-agent", "decide", "started", "执行适当性过滤并选择下一最佳行动。")
        strategy, product, variant = await self.strategy_agent.run(
            request, segment, insight, citations, context
        )
        artifacts.append(strategy)
        emit(
            "strategy-agent",
            "decide",
            "completed",
            strategy.summary,
            {"product_id": product.id, "variant": variant},
        )

        emit("content-agent", "compose", "started", "生成带知识引用的渠道内容。")
        content = await self.content_agent.run(
            request, segment, product, variant, citations, context, decision=strategy
        )
        artifacts.append(content)
        emit(
            "content-agent",
            "compose",
            "completed",
            "内容草案已生成，进入独立合规闸门。",
            {"character_count": content.data["character_count"]},
        )

        emit("compliance-agent", "guard", "started", "检查禁用词、适当性、风险披露与依据。")
        compliance = self.compliance_agent.review(content.data["copy"], segment, product, citations)
        emit(
            "compliance-agent",
            "guard",
            "blocked"
            if compliance.status == "blocked"
            else ("revised" if compliance.status == "revised" else "completed"),
            {
                "approved": "四类合规检查全部通过。",
                "revised": "发现可修复风险，已自动改写后通过。",
                "blocked": "适当性或证据检查未通过，阻止执行。",
            }[compliance.status],
            {"score": compliance.score, "violations": compliance.violations},
        )

        execution = None
        memory_updates = []
        if compliance.status != "blocked":
            emit("execution-agent", "execute", "started", "创建幂等执行任务。")
            execution = self.execution_agent.run(run_id, segment, variant, seed=request.seed)
            emit(
                "execution-agent",
                "execute",
                "completed",
                f"仿真触达 {execution.delivered} 人，未连接任何真实渠道。",
                execution.model_dump(),
            )
            emit("feedback-agent", "learn", "started", "归因反馈并更新策略记忆。")
            memory_updates = self.feedback_agent.run(run_id, segment, product, execution)
            emit(
                "feedback-agent",
                "learn",
                "completed",
                "已记录模拟情景与去重记忆；策略权重等待人工复核。",
                {"memory_ids": [memory.id for memory in memory_updates]},
            )

        final_status = "blocked" if compliance.status == "blocked" else "completed"
        emit(
            "orchestrator",
            "complete",
            "blocked" if final_status == "blocked" else "completed",
            "本次闭环已结束，完整轨迹可用于审计与复盘。",
        )
        completed_at = datetime.now(UTC)
        result = RunResult(
            run_id=run_id,
            status=final_status,
            created_at=created_at,
            completed_at=completed_at,
            request=request,
            segment=segment,
            selected_product=product,
            artifacts=artifacts,
            events=events,
            citations=citations,
            compliance=compliance,
            execution=execution,
            context_trace=context_trace,
            memory_updates=memory_updates,
            model_provider=self.model_gateway.provider_label,
            model_calls=CALL_TRACE.get() or [],
            evidence_passport={
                "version": "3.0",
                "policy_version": "demo-policy-2",
                "retrieval": "paragraph-bm25-v2",
                "simulator": "paired-cohort-v1",
                "prompt_versions": {
                    "strategy": self.strategy_agent.prompt_version,
                    "content": self.content_agent.prompt_version,
                },
                "seed": request.seed,
                "context_sha256": hashlib.sha256(context.encode()).hexdigest(),
                "input_sha256": hashlib.sha256(
                    json.dumps(request.model_dump(), sort_keys=True).encode()
                ).hexdigest(),
                "sources": sources,
                "memory_ids": [m.id for m in recalled],
                "boundaries": "引用来源与版本可核验；不等于逐句事实蕴含验证。",
            },
        )
        self.database.save_final_memories(run_id, result.model_dump(mode="json"))
        return result
