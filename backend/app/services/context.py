from __future__ import annotations

import re
from dataclasses import dataclass

from app.models import ContextTrace

PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
IDENTITY = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")


@dataclass(slots=True)
class ContextSection:
    name: str
    content: str
    priority: int
    required: bool = False
    token_cap: int | None = None


class ContextBuilder:
    """Budget-aware context packing with deterministic PII minimization."""

    def __init__(self, token_budget: int = 1800) -> None:
        self.token_budget = token_budget

    @staticmethod
    def estimate_tokens(text: str) -> int:
        han_count = sum("\u4e00" <= char <= "\u9fff" for char in text)
        other_count = len(text) - han_count
        return max(1, han_count + other_count // 4)

    @staticmethod
    def redact(text: str) -> tuple[str, int]:
        redactions = 0
        for pattern, replacement in (
            (PHONE, "[PHONE_REDACTED]"),
            (EMAIL, "[EMAIL_REDACTED]"),
            (IDENTITY, "[ID_REDACTED]"),
        ):
            text, count = pattern.subn(replacement, text)
            redactions += count
        return text, redactions

    def build(self, sections: list[ContextSection]) -> tuple[str, ContextTrace]:
        ordered = sorted(sections, key=lambda section: (not section.required, -section.priority))
        remaining = self.token_budget
        included: list[str] = []
        dropped: list[str] = []
        rendered: list[str] = []
        redaction_count = 0

        for section in ordered:
            content, section_redactions = self.redact(section.content)
            redaction_count += section_redactions
            cap = min(section.token_cap or remaining, remaining)
            cost = self.estimate_tokens(content)
            if cost > cap:
                if section.required and cap > 30:
                    ratio = cap / cost
                    content = content[: max(80, int(len(content) * ratio))] + "…"
                    cost = self.estimate_tokens(content)
                else:
                    dropped.append(section.name)
                    continue
            if cost > remaining:
                dropped.append(section.name)
                continue
            rendered.append(f"## {section.name}\n{content}")
            included.append(section.name)
            remaining -= cost

        prompt = "\n\n".join(rendered)
        trace = ContextTrace(
            budget=self.token_budget,
            estimated_tokens=self.estimate_tokens(prompt),
            included_sections=included,
            dropped_sections=dropped,
            redactions=redaction_count,
        )
        return prompt, trace
