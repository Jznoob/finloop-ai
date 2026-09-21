from app.services.context import ContextBuilder, ContextSection


def test_context_redacts_pii_and_respects_budget() -> None:
    builder = ContextBuilder(token_budget=90)
    prompt, trace = builder.build(
        [
            ContextSection(
                "required",
                "客户电话 13800138000，邮箱 user@example.com。必须保留合规结论。",
                priority=100,
                required=True,
            ),
            ContextSection("optional", "这是一段很长的可选上下文。" * 100, priority=10),
        ]
    )

    assert "13800138000" not in prompt
    assert "user@example.com" not in prompt
    assert "[PHONE_REDACTED]" in prompt
    assert trace.redactions == 2
    assert trace.estimated_tokens <= trace.budget
    assert "optional" in trace.dropped_sections
