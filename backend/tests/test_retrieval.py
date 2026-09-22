from app.db import Database
from app.services.retrieval import HybridRetriever


def test_compliance_query_returns_traceable_sources(database: Database) -> None:
    results = HybridRetriever(database).search("低风险客户 产品适当性 保本承诺 风险提示")

    assert len(results) <= 3
    assert results[0].score >= results[-1].score
    assert {result.document_id for result in results} >= {"CMP-001", "SUT-002"}
    assert all(result.source and result.excerpt for result in results)
