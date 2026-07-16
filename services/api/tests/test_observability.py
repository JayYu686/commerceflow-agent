from app.observability import safe_trace_attributes


def test_trace_attributes_use_an_explicit_safe_allowlist() -> None:
    filtered = safe_trace_attributes(
        {
            "workflow.run_id": "run-1",
            "agent.intent": "quality_issue_refund",
            "llm.provider": "disabled",
            "raw_message": "private user message",
            "prompt": "private prompt",
            "api_key": "secret",
            "database_url": "postgresql://secret",
            "none_value": None,
        }
    )

    assert filtered == {
        "workflow.run_id": "run-1",
        "agent.intent": "quality_issue_refund",
        "llm.provider": "disabled",
    }
