from __future__ import annotations

import asyncio
import json
import tempfile
import time
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from app.agents.compliance import ComplianceAgent
from app.catalog import PRODUCTS, SEGMENTS
from app.core.runtime import AgentRuntime
from app.db import Database, now_iso
from app.models import RunRequest
from app.services.context import ContextBuilder, ContextSection


async def evaluate(runtime: AgentRuntime, cases_path: Path | None = None) -> dict:
    """All execution happens in a fresh DB with local templates, never trains operational state."""
    started = time.perf_counter()
    cases = []
    with tempfile.TemporaryDirectory(prefix="finloop-eval-") as directory:
        config = replace(
            runtime.settings,
            database_path=Path(directory) / "eval.db",
            model_provider="deterministic",
            api_key="",
        )
        db = Database(config)
        db.initialize()
        isolated = AgentRuntime(db, config)
        workflow_cases = json.loads((cases_path or config.eval_path).read_text())
        for case in workflow_cases:
            run = await isolated.run(
                RunRequest(
                    **{key: case[key] for key in ("segment_id", "objective", "market_signal")}
                )
            )
            cited = {c.document_id for c in run.citations}
            passed = (
                set(case["must_cite"]) <= cited
                and run.selected_product.risk_level <= case["max_risk_level"]
                and run.compliance.status == case["expected_compliance"]
            )
            cases.append(
                {
                    "case_id": case["id"],
                    "category": "workflow",
                    "passed": passed,
                    "detail": "适当性、制度覆盖与完整闭环",
                }
            )

        retrieval_cases = json.loads((config.eval_path.parent / "retrieval.json").read_text())
        recalls, precisions, reciprocal_ranks = [], [], []
        for case in retrieval_cases:
            ids = [c.document_id for c in isolated.retriever.search(case["query"], limit=2)]
            relevant = set(case["relevant"])
            if relevant:
                hits = len(set(ids) & relevant)
                recalls.append(hits / len(relevant))
                precisions.append(hits / 2)
                reciprocal_ranks.append(
                    next((1 / (i + 1) for i, doc_id in enumerate(ids) if doc_id in relevant), 0)
                )
            passed = relevant <= set(ids) if relevant else not ids
            cases.append(
                {
                    "case_id": case["id"],
                    "category": "retrieval",
                    "passed": passed,
                    "detail": f"expected={sorted(relevant)}, top2={ids}",
                }
            )

        sources = isolated.retriever.evidence("风险")
        guard = ComplianceAgent()
        for name, copy, product_id, docs, expected in [
            ("unsupported-citation", "产品很好 [FAKE-999]", "DEMO-FI-01", sources, "blocked"),
            ("missing-evidence", "产品介绍", "DEMO-FI-01", [], "blocked"),
            ("risk-mismatch", "产品介绍", "DEMO-EQ-02", sources, "blocked"),
            ("promise-repair", "这款产品稳赚零风险", "DEMO-FI-01", sources, "revised"),
        ]:
            result = guard.review(copy, SEGMENTS["steady-planner"], PRODUCTS[product_id], docs)
            cases.append(
                {
                    "case_id": name,
                    "category": "adversarial",
                    "passed": result.status == expected,
                    "detail": f"expected={expected}, actual={result.status}",
                }
            )
        prompt, trace = ContextBuilder(90).build(
            [
                ContextSection(
                    "输入",
                    "电话13800138000 邮箱a@example.com " + "数据" * 200,
                    priority=100,
                    required=True,
                )
            ]
        )
        cases.append(
            {
                "case_id": "budget-redaction",
                "category": "context",
                "passed": trace.estimated_tokens <= 90 and "13800138000" not in prompt,
                "detail": "包含标题与分隔符的硬预算 + 输入脱敏",
            }
        )
        report = {
            "id": f"eval_{uuid4().hex[:12]}",
            "created_at": now_iso(),
            "total": len(cases),
            "passed": sum(c["passed"] for c in cases),
            "pass_rate": sum(c["passed"] for c in cases) / len(cases),
            "retrieval_metrics": {
                "recall_at_2": sum(recalls) / len(recalls),
                "precision_at_2": sum(precisions) / len(precisions),
                "mrr_at_2": sum(reciprocal_ranks) / len(reciprocal_ranks),
            },
            "corpus_documents": len(db.list_documents()),
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "mode": "isolated/local-template",
            "learning_writes": 0,
            "cases": cases,
            "scope": "合成中文小语料回归测试；不代表真实检索基准或线上模型表现。",
        }
    return report


async def main() -> None:
    database = Database()
    report = await evaluate(AgentRuntime(database))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["passed"] != report["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
