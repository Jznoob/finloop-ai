from app.agents.compliance import ComplianceAgent
from app.catalog import PRODUCTS, SEGMENTS
from app.models import Citation


def citations() -> list[Citation]:
    return [
        Citation(document_id="CMP-001", title="合规", source="CMP-001", excerpt="风险", score=1),
        Citation(document_id="SUT-002", title="适当性", source="SUT-002", excerpt="适当", score=1),
    ]


def test_guard_rewrites_prohibited_claims() -> None:
    result = ComplianceAgent().review(
        "这是一款稳赚且零风险的产品。",
        SEGMENTS["steady-planner"],
        PRODUCTS["DEMO-FI-01"],
        citations(),
    )

    assert result.status == "revised"
    assert "稳赚" not in result.final_copy
    assert "零风险" not in result.final_copy
    assert "风险提示" in result.final_copy


def test_guard_blocks_risk_level_mismatch() -> None:
    result = ComplianceAgent().review(
        "风险提示：可能面临权益市场波动、模型失效和跟踪偏离。",
        SEGMENTS["steady-planner"],
        PRODUCTS["DEMO-EQ-02"],
        citations(),
    )

    assert result.status == "blocked"
    assert any("风险等级" in violation for violation in result.violations)
