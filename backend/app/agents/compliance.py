from __future__ import annotations

import re

from app.models import Citation, ComplianceResult, Product, Segment


class ComplianceAgent:
    name = "compliance-agent"
    replacements = {
        "保本": "本金可能发生损失",
        "稳赚": "存在收益与损失的可能",
        "零风险": "风险相对可控但不等于无风险",
        "确定上涨": "存在上涨或下跌的多种情景",
        "内部消息": "公开信息",
    }

    def review(
        self,
        copy: str,
        segment: Segment,
        product: Product,
        citations: list[Citation],
    ) -> ComplianceResult:
        checks: list[dict] = []
        violations: list[str] = []
        revised = copy
        matched_terms = [term for term in self.replacements if term in copy]
        checks.append(
            {
                "rule": "CMP-001 / 禁止收益承诺与内幕暗示",
                "passed": not matched_terms,
                "detail": (
                    "未发现禁用词" if not matched_terms else f"命中：{', '.join(matched_terms)}"
                ),
            }
        )
        for term in matched_terms:
            violations.append(f"禁用表达：{term}")
            revised = revised.replace(term, self.replacements[term])

        suitable = product.risk_level <= segment.risk_level
        checks.append(
            {
                "rule": "SUT-002 / 产品适当性",
                "passed": suitable,
                "detail": f"产品 R{product.risk_level} / 客群 C{segment.risk_level}",
            }
        )
        if not suitable:
            violations.append("产品风险等级高于客群风险承受等级")

        has_risk = "风险提示" in revised and all(risk in revised for risk in product.risks)
        checks.append(
            {
                "rule": "CMP-001 / 风险披露",
                "passed": has_risk,
                "detail": "风险提示与产品主要风险已披露" if has_risk else "风险披露不完整",
            }
        )
        if not has_risk:
            violations.append("缺少完整风险披露")
            revised += (
                f"\n\n风险提示：本内容不构成投资建议或收益承诺；"
                f"产品可能面临{'、'.join(product.risks)}，请审慎决策。"
            )

        known_ids = {citation.document_id for citation in citations}
        anchors = set(re.findall(r"\[([A-Z][A-Z0-9-]+)\]", copy))
        has_sources = {"CMP-001", "SUT-002"} <= known_ids
        fabricated = anchors - known_ids
        if fabricated:
            violations.append(f"无法核验的引用：{', '.join(sorted(fabricated))}")
            has_sources = False
        checks.append(
            {
                "rule": "AUD-001 / 决策可追溯",
                "passed": has_sources,
                "detail": f"去重后 {len(known_ids)} 条依据；强制检查 CMP-001 与 SUT-002",
            }
        )
        if not has_sources:
            violations.append("知识依据不足")

        if not suitable or not has_sources:
            status = "blocked"
        elif violations:
            status = "revised"
        else:
            status = "approved"
        score = max(0, 100 - len(violations) * 16 - (35 if not suitable else 0))
        return ComplianceResult(
            status=status,
            score=score,
            violations=violations,
            checks=checks,
            final_copy=revised,
        )
