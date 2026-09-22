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
    """Hard budget in estimator units, including section headers and separators."""

    def __init__(self, token_budget: int = 1800) -> None:
        if token_budget < 1:
            raise ValueError("Context budget must be positive")
        self.token_budget = token_budget

    @staticmethod
    def estimate_tokens(text: str) -> int:
        han = sum("\u4e00" <= char <= "\u9fff" for char in text)
        return han + (len(text) - han + 3) // 4

    @staticmethod
    def redact(text: str) -> tuple[str, int]:
        total = 0
        for pattern, replacement in (
            (IDENTITY, "[ID_REDACTED]"),
            (PHONE, "[PHONE_REDACTED]"),
            (EMAIL, "[EMAIL_REDACTED]"),
        ):
            text, count = pattern.subn(replacement, text)
            total += count
        return text, total

    def build(self, sections: list[ContextSection]) -> tuple[str, ContextTrace]:
        ordered = sorted(sections, key=lambda s: (not s.required, -s.priority))
        rendered: list[str] = []
        included, dropped = [], []
        redactions = 0
        for section in ordered:
            content, count = self.redact(section.content)
            redactions += count
            prefix = "\n\n".join(rendered)
            separator = "\n\n" if prefix else ""
            header = f"## {section.name}\n"
            cap = section.token_cap or self.token_budget

            def fits(
                value: str,
                header: str = header,
                cap: int = cap,
                prefix: str = prefix,
                separator: str = separator,
            ) -> bool:
                return (
                    self.estimate_tokens(header + value) <= cap
                    and self.estimate_tokens(prefix + separator + header + value)
                    <= self.token_budget
                )

            if not fits(content):
                if not section.required:
                    dropped.append(section.name)
                    continue
                low, high = 0, len(content)
                while low < high:
                    mid = (low + high + 1) // 2
                    if fits(content[:mid] + "…"):
                        low = mid
                    else:
                        high = mid - 1
                if low == 0:
                    dropped.append(section.name)
                    continue
                content = content[:low] + "…"
            rendered.append(header + content)
            included.append(section.name)
        prompt = "\n\n".join(rendered)
        return prompt, ContextTrace(
            budget=self.token_budget,
            estimated_tokens=self.estimate_tokens(prompt),
            included_sections=included,
            dropped_sections=dropped,
            redactions=redactions,
        )
