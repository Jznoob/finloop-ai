import pytest

from app.config import Settings
from app.core.runtime import AgentRuntime
from app.db import Database
from app.models import RunRequest


async def test_runtime_completes_auditable_loop(
    database: Database, test_settings: Settings
) -> None:
    runtime = AgentRuntime(database, test_settings)
    result = await runtime.run(
        RunRequest(
            segment_id="steady-planner",
            objective="向稳健客群解释市场波动与配置纪律",
            market_signal="权益市场波动放大，回撤咨询增加",
        )
    )

    assert result.status == "completed"
    assert result.compliance.status == "approved"
    assert result.selected_product is not None
    assert result.selected_product.risk_level <= result.segment.risk_level
    assert result.execution is not None
    assert result.execution.mode == "simulation"
    assert len(result.events) >= 14
    assert len(result.citations) >= 2
    assert {memory.kind for memory in result.memory_updates} == {
        "episodic",
        "semantic",
        "procedural",
    }
    stored = database.get_run(result.run_id)
    assert stored is not None
    assert stored["run_id"] == result.run_id


@pytest.mark.parametrize(
    "objective,signal,scenario,expected",
    [
        ("向沉默客户提供阅读邀请", "打开率下降，可能出现疲劳", "reengagement", "暂停接收"),
        ("开展多资产教育", "股债相关性变化与海外波动", "multiasset", "相关性"),
        ("解释市场波动", "市场回撤增大", "volatility", "波动应对清单"),
        ("介绍持有期限", "用户希望了解产品基本结构", "education", "投资教育阅读清单"),
    ],
)
async def test_scenario_changes_insight_strategy_and_copy(
    database, test_settings, objective, signal, scenario, expected
):
    result = await AgentRuntime(database, test_settings).run(
        RunRequest(objective=objective, market_signal=signal, variant="clarity")
    )
    assert result.status == "completed"
    artifacts = {artifact.agent: artifact for artifact in result.artifacts}
    for agent in ("insight-agent", "strategy-agent", "content-agent"):
        assert artifacts[agent].data["scenario"] == scenario
    assert expected in result.compliance.final_copy
    assert "[PRD-DEMO]" in result.compliance.final_copy
    assert all(artifact.confidence is None for artifact in result.artifacts)


async def test_selected_strategy_reaches_model_content_request(
    database, test_settings, monkeypatch
):
    runtime = AgentRuntime(database, test_settings)
    prompts = []

    async def generate(system, user, fallback):
        prompts.append(user)
        return fallback

    monkeypatch.setattr(runtime.model_gateway, "generate_json", generate)
    await runtime.run(RunRequest(variant="evidence", objective="重新激活沉默客群"))
    assert len(prompts) == 2
    assert "固定策略：evidence" in prompts[0]
    assert "指定创意策略：evidence" in prompts[1]
    assert "暂停接收" in prompts[1]
    assert "策略角度：用制度依据和情景证据建立信任" in prompts[1]
