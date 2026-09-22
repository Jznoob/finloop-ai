from __future__ import annotations

import math

from app.db import Database


class BanditService:
    """Smoothed UCB-style creative preference ranking, updated only by reviews."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def select(self) -> tuple[str, dict[str, float]]:
        arms = self.database.get_bandit_arms()
        total = sum(arm["impressions"] for arm in arms) + 1
        scores: dict[str, float] = {}
        for arm in arms:
            posterior_mean = arm["alpha"] / (arm["alpha"] + arm["beta"])
            exploration = math.sqrt(2 * math.log(total + 1) / (arm["impressions"] + 1))
            scores[arm["arm"]] = round(posterior_mean + exploration * 0.2, 4)
        selected = max(scores, key=lambda key: (scores[key], key))
        return selected, scores

    def record(self, arm: str, converted: bool) -> None:
        self.database.update_bandit(arm, converted)
