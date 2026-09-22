from __future__ import annotations

import math
import random
from uuid import uuid4

from pydantic import BaseModel, Field

from app.db import Database

VARIANTS = ("clarity", "evidence", "scenario")


class ExperimentRequest(BaseModel):
    run_id: str = Field(min_length=4, max_length=64)
    seed: int = Field(default=42, ge=0, le=2**31 - 1)
    sample_size: int = Field(default=1200, ge=200, le=5000)
    stress: float = Field(default=0.5, ge=0, le=1)
    fatigue: float = Field(default=0.2, ge=0, le=1)


def wilson(successes: int, n: int) -> list[float]:
    if not n:
        return [0.0, 1.0]
    z = 1.959963984540054
    p = successes / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return [round(max(0, center - half), 6), round(min(1, center + half), 6)]


def simulate(
    seed: int, n: int, variant: str, channel: str, stress: float = 0.5, fatigue: float = 0.2
) -> dict:
    """Common random numbers across alternatives; every conversion requires an open."""
    rng = random.Random(seed)
    outcomes, delivered, opened = [], 0, 0
    # These are explicit synthetic assumptions, not parameters learned from customers.
    appeal = {"clarity": 0.025 * (1 - stress), "evidence": 0.012, "scenario": 0.035 * stress}[
        variant
    ]
    open_probability = {"app": 0.44, "wechat": 0.55, "email": 0.39}[channel] * (1 - 0.4 * fatigue)
    response_probability = 0.045 + appeal - 0.015 * fatigue
    for _ in range(n):
        delivery_draw, open_draw, conversion_draw = rng.random(), rng.random(), rng.random()
        did_deliver = delivery_draw < 0.98
        did_open = did_deliver and open_draw < open_probability
        did_convert = did_open and conversion_draw < response_probability
        delivered += int(did_deliver)
        opened += int(did_open)
        outcomes.append(int(did_convert))
    converted = sum(outcomes)
    return {
        "variant": variant,
        "channel": channel,
        "audience_size": n,
        "delivered": delivered,
        "opened": opened,
        "converted": converted,
        "open_rate": opened / delivered if delivered else 0,
        "conversion_rate": converted / delivered if delivered else 0,
        "audience_conversion_rate": converted / n,
        "interval95": wilson(converted, n),
        "outcomes": outcomes,
    }


def compare(database: Database, request: ExperimentRequest) -> dict:
    source = database.get_run(request.run_id)
    if source is None or not source.get("execution"):
        raise ValueError("请选择有执行结果的运行作为实验基线")
    rows = [
        simulate(
            request.seed,
            request.sample_size,
            variant,
            source["segment"]["preferred_channel"],
            request.stress,
            request.fatigue,
        )
        for variant in VARIANTS
    ]
    baseline = rows[0]["outcomes"]
    for row in rows:
        deltas = [a - b for a, b in zip(row.pop("outcomes"), baseline, strict=True)]
        mean = sum(deltas) / len(deltas)
        variance = sum((delta - mean) ** 2 for delta in deltas) / (len(deltas) - 1)
        half = 1.96 * math.sqrt(variance / len(deltas))
        row["difference_vs_clarity"] = mean
        row["paired_interval95"] = [mean - half, mean + half]
        row["conclusion"] = (
            "仅基线"
            if row["variant"] == "clarity"
            else "在模拟假设下高于基线"
            if mean - half > 0
            else "在模拟假设下低于基线"
            if mean + half < 0
            else "差异证据不足"
        )
    report = {
        "id": f"exp_{uuid4().hex[:12]}",
        "request": request.model_dump(),
        "cohort_key": f"synthetic:{request.seed}:{request.sample_size}",
        "method": "common-random-numbers / paired normal interval / Wilson interval",
        "assumptions": {
            "delivery_probability": 0.98,
            "open_probability": {"app": 0.44, "wechat": 0.55, "email": 0.39},
            "response_base": 0.045,
            "stress": "压力只改变假设的创意响应概率，非真实市场预测",
            "fatigue": "疲劳同时降低打开概率和响应概率",
        },
        "notice": (
            "合成样本敏感性分析；区间只反映模拟抽样误差，不验证真实业务增益。"
            "配对区间为正态近似，差异样本少时不稳健。"
        ),
        "learning_writes": 0,
        "variants": rows,
    }
    database.save_report(report["id"], "experiment", report)
    return report
