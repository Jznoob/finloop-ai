from dataclasses import replace

import httpx

from app.core.runtime import AgentRuntime
from app.models import RunRequest
from app.services.comparison import compare_runs
from app.services.model_gateway import ModelGateway


async def test_saved_runs_expose_prompt_versions_and_strong_strategy_comparison(
    database, test_settings
):
    runtime = AgentRuntime(database, test_settings)
    left = await runtime.run(RunRequest(seed=42, variant="clarity"))
    right = await runtime.run(RunRequest(seed=42, variant="scenario"))

    assert left.evidence_passport["prompt_versions"] == {
        "strategy": "strategy-json-v1",
        "content": "content-json-v1",
    }
    result = compare_runs(left.model_dump(mode="json"), right.model_dump(mode="json"))
    assert result["quality"]["level"] == "strong"
    assert result["evidence"]["same"] is True
    assert next(row for row in result["dimensions"] if row["key"] == "variant") == {
        "key": "variant",
        "label": "实际策略",
        "left": "clarity",
        "right": "scenario",
        "changed": True,
    }
    assert result["content"]["changed"] is True
    assert result["funnel"][-1]["delta"] is not None


async def test_comparison_flags_evidence_drift_and_changed_inputs(database, test_settings):
    runtime = AgentRuntime(database, test_settings)
    left = await runtime.run(RunRequest(seed=8, variant="clarity"))
    with database.connect() as connection:
        connection.execute(
            "UPDATE documents SET content=content || ' 已修订' WHERE id='CMP-001'"
        )
    right = await runtime.run(RunRequest(seed=8, variant="evidence"))
    drift = compare_runs(left.model_dump(mode="json"), right.model_dump(mode="json"))
    assert drift["quality"]["level"] == "partial"
    assert [item["id"] for item in drift["evidence"]["version_changed"]] == ["CMP-001"]

    changed = await runtime.run(
        RunRequest(
            seed=9,
            variant="evidence",
            objective="解释另一项长期配置纪律",
            market_signal="市场成交活跃但分化明显",
        )
    )
    contextual = compare_runs(left.model_dump(mode="json"), changed.model_dump(mode="json"))
    assert contextual["quality"]["level"] == "contextual"
    assert "不能归因" in contextual["quality"]["detail"]


async def test_model_probe_distinguishes_local_remote_and_invalid_schema(
    test_settings, monkeypatch
):
    local = await ModelGateway(test_settings).probe()
    assert local["status"] == "local"
    assert local["remote_request_sent"] is False
    assert local["outcome"] == "local-template"

    responses = [
        {"choices": [{"message": {"content": '{"status":"ready","message":"ok"}'}}]},
        {"choices": [{"message": {"content": '{"status":""}'}}]},
    ]

    async def post(_self, url, **kwargs):
        return httpx.Response(
            200, json=responses.pop(0), request=httpx.Request("POST", url)
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    remote_settings = replace(
        test_settings, model_provider="openai-compatible", api_key="fake-test-key"
    )
    ready = await ModelGateway(remote_settings).probe()
    invalid = await ModelGateway(remote_settings).probe()
    assert ready["status"] == "ready"
    assert ready["remote_request_sent"] is True
    assert invalid["status"] == "invalid-schema"
    assert "fake-test-key" not in str(ready) + str(invalid)
