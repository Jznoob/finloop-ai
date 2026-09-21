from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from app.config import settings
from app.core.runtime import AgentRuntime
from app.db import Database
from app.models import EvaluationCaseResult, EvaluationReport, RunRequest


async def evaluate(
    runtime: AgentRuntime,
    cases_path: Path | None = None,
) -> EvaluationReport:
    cases = json.loads((cases_path or settings.eval_path).read_text(encoding="utf-8"))
    results: list[EvaluationCaseResult] = []
    for case in cases:
        started = time.perf_counter()
        run = await runtime.run(
            RunRequest(
                segment_id=case["segment_id"],
                objective=case["objective"],
                market_signal=case["market_signal"],
            )
        )
        latency_ms = (time.perf_counter() - started) * 1000
        cited = {citation.document_id for citation in run.citations}
        expected = set(case["must_cite"])
        citation_recall = len(cited & expected) / max(1, len(expected))
        suitability_ok = bool(
            run.selected_product
            and run.selected_product.risk_level <= case["max_risk_level"]
        )
        compliance_ok = run.compliance.status == case["expected_compliance"]
        passed = citation_recall >= 0.5 and suitability_ok and compliance_ok
        notes = []
        if citation_recall < 1:
            notes.append(f"缺少依据：{', '.join(sorted(expected - cited))}")
        if not suitability_ok:
            notes.append("产品风险等级超出评测上限")
        if not compliance_ok:
            notes.append(f"合规状态为 {run.compliance.status}")
        results.append(
            EvaluationCaseResult(
                case_id=case["id"],
                passed=passed,
                compliance_ok=compliance_ok,
                citation_recall=round(citation_recall, 3),
                suitability_ok=suitability_ok,
                latency_ms=round(latency_ms, 2),
                notes=notes,
            )
        )
    passed_count = sum(result.passed for result in results)
    return EvaluationReport(
        total=len(results),
        passed=passed_count,
        pass_rate=round(passed_count / max(1, len(results)), 3),
        average_citation_recall=round(
            sum(result.citation_recall for result in results) / max(1, len(results)), 3
        ),
        average_latency_ms=round(
            sum(result.latency_ms for result in results) / max(1, len(results)), 2
        ),
        cases=results,
    )


async def main() -> None:
    database = Database()
    database.initialize()
    report = await evaluate(AgentRuntime(database))
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
