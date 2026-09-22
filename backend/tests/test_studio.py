import json
from dataclasses import replace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import build_router
from app.core.runtime import AgentRuntime
from app.evals import evaluate
from app.models import RunRequest
from app.services.context import ContextBuilder, ContextSection
from app.services.experiments import ExperimentRequest, compare, simulate, wilson
from app.services.model_gateway import CALL_TRACE, ModelGateway
from app.services.retrieval import HybridRetriever, document_hash


async def test_experiments_and_evaluations_never_teach(database, test_settings):
    runtime = AgentRuntime(database, test_settings)
    result = await runtime.run(RunRequest(variant="clarity"))
    before = (database.list_runs(), database.memory_inventory(), database.get_bandit_arms())
    request = ExperimentRequest(run_id=result.run_id, seed=100, sample_size=1000)
    first, second = compare(database, request), compare(database, request)
    assert first["variants"] == second["variants"]
    assert first["cohort_key"] == second["cohort_key"]
    assert len({row["delivered"] for row in first["variants"]}) == 1
    assert len({row["opened"] for row in first["variants"]}) == 1
    for row in first["variants"]:
        assert 0 <= row["converted"] <= row["opened"] <= row["delivered"] <= 1000
        assert row["interval95"][0] <= row["audience_conversion_rate"] <= row["interval95"][1]
    report = await evaluate(runtime)
    assert report["passed"] == report["total"] == 18
    assert (database.list_runs(), database.memory_inventory(), database.get_bandit_arms()) == before


@pytest.mark.parametrize("seed", [0, 42, 2147483647])
def test_simulation_nested_counts_reproducible(seed):
    first = simulate(seed, 500, "scenario", "app")
    assert first == simulate(seed, 500, "scenario", "app")
    assert first["converted"] == sum(first["outcomes"])
    assert first["conversion_rate"] == first["converted"] / first["delivered"]
    assert wilson(0, 200)[0] == 0
    assert wilson(200, 200)[1] == 1
    assert wilson(0, 0) == [0, 1]


async def test_memory_deduplication_disable_and_reenable(database, test_settings):
    runtime = AgentRuntime(database, test_settings)
    await runtime.run(RunRequest())
    before = database.memory_inventory()
    policy = next(memory for memory in before if memory["kind"] == "procedural")
    database.set_memory_active(policy["id"], False)
    # Upsert must not delete a row referenced by memory_flags or reactivate it.
    database.put_memory(policy)
    await runtime.run(RunRequest())
    after = database.memory_inventory()
    assert sum(memory["kind"] == "procedural" for memory in after) == 1
    assert sum(memory["kind"] == "semantic" for memory in after) == 1
    assert policy["id"] not in {memory["id"] for memory in database.list_memories("steady-planner")}
    database.set_memory_active(policy["id"], True)
    assert policy["id"] in {memory["id"] for memory in database.list_memories("steady-planner")}


async def test_legacy_duplicates_preserved_but_not_recalled_twice(database, test_settings):
    runtime = AgentRuntime(database, test_settings)
    result = await runtime.run(RunRequest())
    policy = next(memory for memory in result.memory_updates if memory.kind == "procedural")
    for index in range(3):
        database.put_memory({**policy.model_dump(), "id": f"legacy-policy-{index}"})
    grouped = next(row for row in database.memory_inventory() if row["kind"] == "procedural")
    assert grouped["duplicate_count"] == 4
    assert (
        len([row for row in database.list_memories("global") if row["kind"] == "procedural"]) == 1
    )
    database.set_memory_active(grouped["id"], False)
    await runtime.run(RunRequest())
    assert database.list_memories("global") == []
    database.set_memory_active(policy.id, True)
    assert len(database.list_memories("global")) == 1
    with database.connect() as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM memories WHERE kind='procedural'").fetchone()[
                0
            ]
            == 4
        )


async def test_evidence_snapshot_survives_mid_run_document_changes(
    database, test_settings, monkeypatch
):
    runtime = AgentRuntime(database, test_settings)
    original = runtime.strategy_agent.run

    async def update_source(*args, **kwargs):
        with database.connect() as connection:
            connection.execute(
                "UPDATE documents SET content=content || ' new revision' WHERE id='CMP-001'"
            )
        return await original(*args, **kwargs)

    monkeypatch.setattr(runtime.strategy_agent, "run", update_source)
    result = await runtime.run(RunRequest())
    snapshot = next(
        source for source in result.evidence_passport["sources"] if source["id"] == "CMP-001"
    )
    cite = next(cite for cite in result.citations if cite.document_id == "CMP-001")
    assert document_hash(snapshot) == snapshot["content_hash"] == cite.content_hash
    assert "new revision" not in snapshot["content"]
    app = FastAPI()
    app.include_router(build_router(database, runtime))
    with TestClient(app) as client:
        evidence = client.get(f"/api/runs/{result.run_id}/evidence").json()
        check = next(row for row in evidence["verification"] if row["id"] == "CMP-001")
        assert check == {"id": "CMP-001", "snapshot_integrity": True, "current_matches": False}
        assert client.post("/api/runs", json={"dry_run": False}).status_code == 422
        assert client.post("/api/jobs", json={"segment_id": "unknown"}).status_code == 422
        assert (
            client.post("/api/jobs", json={}, headers={"Idempotency-Key": "short"}).status_code
            == 422
        )
        assert client.get("/api/configuration").json()["key_configured"] is False


@pytest.mark.parametrize("budget", [1, 7, 30, 90, 400, 1800])
def test_budget_includes_headers_and_separators(budget):
    builder = ContextBuilder(budget)
    context, trace = builder.build(
        [
            ContextSection("必选材料", "客户13812345678 " + "中文Evidence " * 200, 100, True),
            ContextSection("长标题也占预算" * 30, "other" * 200, 99, True),
            ContextSection("可选材料", "context" * 100, 50),
        ]
    )
    assert trace.estimated_tokens == builder.estimate_tokens(context) <= budget
    assert "13812345678" not in context
    assert trace.redactions == 1


async def test_pii_redacted_before_persistence_and_tracing(database, test_settings):
    result = await AgentRuntime(database, test_settings).run(
        RunRequest(
            objective="联系13812345678或hello@example.com开展教育",
            market_signal="客户证件11010519491231002X需保护",
        )
    )
    saved = json.dumps(database.get_run(result.run_id), ensure_ascii=False)
    for value in ("13812345678", "hello@example.com", "11010519491231002X"):
        assert value not in saved
        assert value not in str(database.list_events(result.run_id))
        assert value not in str(database.memory_inventory())


def test_future_documents_and_unrelated_queries_excluded(database):
    with database.connect() as connection:
        connection.execute("UPDATE documents SET effective_date='2999-01-01' WHERE id='CMP-001'")
    retriever = HybridRetriever(database)
    assert retriever.search("火星火山烘焙菠萝") == []
    assert "CMP-001" not in {cite.document_id for cite in retriever.evidence("营销合规")}


@pytest.mark.parametrize(
    "response, outcome",
    [
        ({"choices": []}, "fallback:provider-error"),
        ({"choices": [{"message": {"content": '{"answer": ""}'}}]}, "fallback:invalid-schema"),
        ({"choices": [{"message": {"content": '{"answer": "valid"}'}}]}, "remote-success"),
    ],
)
async def test_model_fallback_is_observable(test_settings, monkeypatch, response, outcome):
    async def post(_self, url, **kwargs):
        return httpx.Response(200, json=response, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    gateway = ModelGateway(
        replace(test_settings, model_provider="compatible", api_key="fake-test-key")
    )
    token = CALL_TRACE.set([])
    try:
        result = await gateway.generate_json("system", "user", {"answer": "fallback"})
        assert result["answer"] == ("valid" if outcome == "remote-success" else "fallback")
        assert CALL_TRACE.get()[0]["outcome"] == outcome
        assert "fake-test-key" not in str(CALL_TRACE.get())
    finally:
        CALL_TRACE.reset(token)
