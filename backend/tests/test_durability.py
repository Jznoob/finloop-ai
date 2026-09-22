import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.core.jobs import JobManager
from app.core.runtime import AgentRuntime
from app.models import RunRequest


def test_concurrent_submissions_accept_exactly_one_job(database):
    request = RunRequest().model_dump()
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs = list(
            pool.map(lambda i: database.submit_job(f"job_{i}", "same-request", request), range(16))
        )
    assert len({job["id"] for job in jobs}) == 1
    assert len(database.list_jobs()) == 1
    with pytest.raises(ValueError, match="不同输入"):
        database.submit_job("other", "same-request", {**request, "seed": 100})
    job = jobs[0]
    assert database.claim_job(job["id"], "attempt1")
    assert not database.claim_job(job["id"], "attempt2")
    assert not database.retry_job(job["id"])


async def test_failed_job_retries_original_input_without_learning(
    database, test_settings, monkeypatch
):
    runtime = AgentRuntime(database, test_settings)
    manager = JobManager(database, runtime)
    original = runtime.strategy_agent.run

    async def fail(*args, **kwargs):
        raise RuntimeError("injected failure after retrieval")

    monkeypatch.setattr(runtime.strategy_agent, "run", fail)
    weights = database.get_bandit_arms()
    job = manager.submit(RunRequest(objective="请联系13812345678提供投资教育"), "retry-original")
    await asyncio.gather(*manager.tasks.values())
    failed = database.get_job(job["id"])
    assert failed["status"] == "failed"
    assert failed["attempts"] == 1
    assert "13812345678" not in str(failed)
    assert database.memory_inventory() == []
    assert database.get_bandit_arms() == weights
    assert database.list_runs() == []
    previous_run = failed["run_id"]
    assert database.list_events(previous_run)
    assert database.get_run(previous_run)["status"] == "failed"

    monkeypatch.setattr(runtime.strategy_agent, "run", original)
    assert database.retry_job(job["id"])
    manager.schedule(job["id"])
    await asyncio.gather(*manager.tasks.values())
    finished = database.get_job(job["id"])
    assert finished["status"] == "completed"
    assert finished["attempts"] == 2
    assert finished["run_id"] != previous_run
    assert finished["request"] == failed["request"]
    attempts = database.job_attempts(job["id"])
    assert [attempt["attempt"] for attempt in attempts] == [2, 1]
    assert [attempt["status"] for attempt in attempts] == ["completed", "failed"]
    assert len(database.list_runs()) == 1
    assert database.get_bandit_arms() == weights
    assert (
        manager.submit(RunRequest(objective="请联系13812345678提供投资教育"), "retry-original")[
            "id"
        ]
        == job["id"]
    )
    await manager.shutdown()


async def test_cancel_and_recover_jobs(database, test_settings, monkeypatch):
    runtime = AgentRuntime(database, test_settings)
    entered = asyncio.Event()

    async def stalled(*args, **kwargs):
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(runtime.strategy_agent, "run", stalled)
    manager = JobManager(database, runtime)
    job = manager.submit(RunRequest(), "cancel-request")
    await asyncio.wait_for(entered.wait(), timeout=3)
    await manager.shutdown()
    assert database.get_job(job["id"])["status"] == "interrupted"
    assert database.memory_inventory() == []

    queued = database.submit_job("crashed", "crashed-request", RunRequest().model_dump())
    database.claim_job(queued["id"], "crashed-run")
    database.create_run("crashed-run", "original", "steady-planner", "signal", "2026-01-01")
    database.recover_jobs()
    assert database.get_job("crashed")["status"] == "interrupted"
    assert database.get_run("crashed-run")["status"] == "failed"


async def test_recovery_keeps_committed_results(database, test_settings):
    database.submit_job("accepted", "committed-request", RunRequest().model_dump())
    database.claim_job("accepted", "committed-run")
    await AgentRuntime(database, test_settings).run(RunRequest(), run_id="committed-run")
    # Simulate a crash between committing a result and marking its job completed.
    database.recover_jobs()
    assert database.get_job("accepted")["status"] == "completed"
    assert database.get_job("accepted")["error"] is None
    assert not database.retry_job("accepted")


def test_recovery_does_not_use_history_page_limit(database):
    for i in range(105):
        database.submit_job(f"queued-{i}", f"queued-key-{i}", {})
    assert len(database.list_jobs()) == 100
    assert len(database.queued_job_ids()) == 105


async def test_result_and_memory_transaction_rolls_back_together(database, test_settings):
    result = await AgentRuntime(database, test_settings).run(RunRequest())
    before = database.memory_inventory()
    payload = result.model_dump(mode="json")
    payload["memory_updates"][0]["id"] = "must-not-commit"
    del payload["compliance"]
    with pytest.raises(KeyError):
        database.save_final_memories(result.run_id, payload)
    assert database.memory_inventory() == before


async def test_concurrent_reviews_update_weights_once(database, test_settings):
    result = await AgentRuntime(database, test_settings).run(RunRequest(variant="clarity"))

    def review(_):
        try:
            database.save_feedback(result.run_id, True, 5, "联系person@example.com")
            return "saved"
        except ValueError:
            return "duplicate"

    with ThreadPoolExecutor(max_workers=6) as pool:
        outcomes = list(pool.map(review, range(12)))
    assert outcomes.count("saved") == 1
    arm = next(arm for arm in database.get_bandit_arms() if arm["arm"] == "clarity")
    assert (arm["alpha"], arm["beta"], arm["impressions"]) == (2, 1, 1)
    assert "person@example.com" not in str(database.review_for(result.run_id))
    assert database.dashboard_metrics()["feedback_count"] == 1
