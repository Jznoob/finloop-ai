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
