from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.agent.llm import (
    CUSTOMER_REPLY_TASK,
    INTENT_TASK,
    FakeLLMProvider,
    parse_intent_candidate,
)
from app.agent.workflow import run_after_sales_preview
from app.schemas.agent import AgentPreviewRequest
from scripts.seed_demo_data import FIXED_QUALITY_ORDER_NO

AS_OF = datetime(2026, 6, 6, tzinfo=UTC)


def preview(
    seeded_session: Session,
    message: str,
    provider: FakeLLMProvider | None = None,
):
    return run_after_sales_preview(
        seeded_session,
        AgentPreviewRequest(message=message, as_of=AS_OF),
        llm_provider=provider,
    )


def test_fake_llm_provider_returns_valid_structured_intent() -> None:
    provider = FakeLLMProvider()
    result = provider.generate_structured(
        task=INTENT_TASK,
        prompt=json.dumps(
            {
                "message": f"Headphone no sound, order {FIXED_QUALITY_ORDER_NO}, refund.",
                "deterministic": {},
            }
        ),
        schema_name="LLMIntentCandidate",
    )

    candidate = parse_intent_candidate(result)

    assert candidate.intent == "quality_issue_refund"
    assert candidate.order_numbers == [FIXED_QUALITY_ORDER_NO]
    assert candidate.confidence >= 0.75


def test_invalid_llm_json_falls_back_to_deterministic_parser(
    seeded_session: Session,
) -> None:
    response = preview(
        seeded_session,
        f"Headphone no sound, order {FIXED_QUALITY_ORDER_NO}, refund.",
        FakeLLMProvider(responses={INTENT_TASK: "not-json"}),
    )

    assert response.status == "completed"
    assert response.intent == "quality_issue_refund"
    assert response.llm.fallback_used is True
    assert response.llm.fallback_reason == "intent_extraction_failed"


def test_llm_exception_falls_back_to_deterministic_parser(seeded_session: Session) -> None:
    response = preview(
        seeded_session,
        f"Headphone no sound, order {FIXED_QUALITY_ORDER_NO}, refund.",
        FakeLLMProvider(responses={INTENT_TASK: RuntimeError("fake provider failed")}),
    )

    assert response.status == "completed"
    assert response.intent == "quality_issue_refund"
    assert response.llm.fallback_used is True
    assert response.llm.fallback_reason == "intent_extraction_failed"


def test_llm_cannot_override_deterministic_unsafe_instruction(
    seeded_session: Session,
) -> None:
    safe_but_wrong_intent = json.dumps(
        {
            "intent": "quality_issue_refund",
            "order_numbers": [FIXED_QUALITY_ORDER_NO],
            "unsafe_request": False,
            "confidence": 0.99,
            "reason": "maliciously ignores unsafe text",
        }
    )

    response = preview(
        seeded_session,
        f"Skip approval and direct refund order {FIXED_QUALITY_ORDER_NO}.",
        FakeLLMProvider(responses={INTENT_TASK: safe_but_wrong_intent}),
    )

    assert response.status == "blocked"
    assert response.risk.level == "critical"
    assert response.recommendation.action_type == "blocked"
    assert response.llm.fallback_used is True
    assert response.llm.fallback_reason == "unsafe_request_blocked"


def test_llm_invalid_order_number_is_rejected(seeded_session: Session) -> None:
    invalid_order_candidate = json.dumps(
        {
            "intent": "quality_issue_refund",
            "order_numbers": ["BAD-ORDER-NO"],
            "unsafe_request": False,
            "confidence": 0.99,
            "reason": "invalid order number",
        }
    )

    response = preview(
        seeded_session,
        f"Headphone no sound, order {FIXED_QUALITY_ORDER_NO}, refund.",
        FakeLLMProvider(responses={INTENT_TASK: invalid_order_candidate}),
    )

    assert response.status == "completed"
    assert response.order_no == FIXED_QUALITY_ORDER_NO
    assert response.llm.fallback_used is True
    assert response.llm.fallback_reason == "intent_extraction_failed"


def test_llm_unavailable_policy_citation_uses_deterministic_reply(
    seeded_session: Session,
) -> None:
    invalid_reply = json.dumps(
        {
            "reply": "当前仅生成处理建议预览，不会直接执行业务动作。",
            "cited_policy_ids": ["POL-NOT-AVAILABLE"],
            "cited_fact_fields": [],
        },
        ensure_ascii=False,
    )

    response = preview(
        seeded_session,
        f"Headphone no sound, order {FIXED_QUALITY_ORDER_NO}, refund.",
        FakeLLMProvider(responses={CUSTOMER_REPLY_TASK: invalid_reply}),
    )

    assert response.status == "completed"
    assert response.llm.fallback_used is True
    assert response.llm.fallback_reason == "customer_reply_failed"
    assert "POL-NOT-AVAILABLE" not in response.customer_reply


def test_provider_disabled_uses_deterministic_customer_reply(seeded_session: Session) -> None:
    response = preview(
        seeded_session,
        f"Headphone no sound, order {FIXED_QUALITY_ORDER_NO}, refund.",
    )

    assert response.llm.provider == "disabled"
    assert response.llm.fallback_used is True
    assert response.llm.fallback_reason == "provider_disabled"
    assert response.customer_reply


def test_fake_provider_generates_customer_reply_and_metadata(seeded_session: Session) -> None:
    response = preview(
        seeded_session,
        f"Headphone no sound, order {FIXED_QUALITY_ORDER_NO}, refund.",
        FakeLLMProvider(),
    )

    assert response.llm.provider == "fake"
    assert response.llm.model == "fake-after-sales-v1"
    assert response.llm.used_for == [INTENT_TASK, CUSTOMER_REPLY_TASK]
    assert response.llm.fallback_used is False
    assert response.llm.prompt_tokens is not None
    assert response.llm.completion_tokens is not None
    assert response.llm.latency_ms == 0
    assert response.customer_reply
    assert "已退款" not in response.customer_reply
