from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Order, PolicyChunk, PolicyDocument, Shipment
from scripts.seed_demo_data import FIXED_DELAYED_ORDER_NO, FIXED_QUALITY_ORDER_NO


def test_agent_preview_api_returns_quality_refund_preview(client: TestClient) -> None:
    response = client.post(
        "/api/agent/after-sales/preview",
        json={
            "message": (
                f"Earbuds left speaker has no sound, order {FIXED_QUALITY_ORDER_NO}, "
                "I want a refund."
            ),
            "as_of": "2026-06-06T00:00:00Z",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["recommendation"]["action_type"] == "refund_review"
    assert payload["recommendation"]["action_status"] == "preview_only"
    assert payload["risk"]["level"] == "high"
    assert payload["risk"]["requires_approval"] is True
    assert payload["policy_evidence"][0]["policy_id"] == "POL-QUALITY-ELECTRONICS-V2"
    assert payload["customer_reply"]
    assert payload["llm"]["provider"] == "disabled"
    assert payload["llm"]["fallback_used"] is True
    assert payload["llm"]["fallback_reason"] == "provider_disabled"


def test_agent_preview_api_rejects_invalid_request(client: TestClient) -> None:
    response = client.post(
        "/api/agent/after-sales/preview",
        json={"message": " ", "as_of": "2026-06-06T00:00:00Z"},
    )

    assert response.status_code == 422


def test_agent_preview_api_regresses_existing_read_only_endpoints(client: TestClient) -> None:
    health_response = client.get("/health")
    order_response = client.get(f"/api/orders/{FIXED_QUALITY_ORDER_NO}")
    logistics_response = client.get(f"/api/orders/{FIXED_DELAYED_ORDER_NO}/logistics")
    policy_response = client.get(
        "/api/policies/search",
        params={
            "query": "earbuds no sound return refund",
            "intent": "quality_issue_refund",
            "category": "electronics",
            "aftersales_type": "standard",
            "limit": 5,
        },
    )

    assert health_response.status_code == 200
    assert order_response.status_code == 200
    assert logistics_response.status_code == 200
    assert policy_response.status_code == 200
    assert policy_response.json()["hits"][0]["policy_id"] == "POL-QUALITY-ELECTRONICS-V2"


def test_agent_preview_routes_do_not_expose_phase_4_capabilities(client: TestClient) -> None:
    forbidden_fragments = ("refund", "coupon", "ticket", "approval", "mcp")
    paths = {getattr(route, "path", "") for route in client.app.routes}

    forbidden_paths = [
        path
        for path in paths
        if path != "/api/agent/after-sales/preview"
        and any(fragment in path.lower() for fragment in forbidden_fragments)
    ]
    assert forbidden_paths == []


def test_agent_preview_does_not_mutate_existing_tables(
    client: TestClient,
    seeded_session: Session,
) -> None:
    before_counts = table_counts(seeded_session)
    before_aftersales_status = order_aftersales_status(
        seeded_session,
        FIXED_DELAYED_ORDER_NO,
    )

    response = client.post(
        "/api/agent/after-sales/preview",
        json={
            "message": (
                f"Order {FIXED_DELAYED_ORDER_NO} logistics has no movement, "
                "request delay compensation."
            ),
            "as_of": datetime(2026, 6, 6, tzinfo=UTC).isoformat(),
        },
    )

    assert response.status_code == 200
    assert table_counts(seeded_session) == before_counts
    assert (
        order_aftersales_status(seeded_session, FIXED_DELAYED_ORDER_NO) == before_aftersales_status
    )


def table_counts(session: Session) -> dict[str, int]:
    return {
        "orders": session.scalar(select(func.count()).select_from(Order)),
        "shipments": session.scalar(select(func.count()).select_from(Shipment)),
        "policy_documents": session.scalar(select(func.count()).select_from(PolicyDocument)),
        "policy_chunks": session.scalar(select(func.count()).select_from(PolicyChunk)),
    }


def order_aftersales_status(session: Session, order_no: str) -> str | None:
    return session.scalar(select(Order.aftersales_status).where(Order.order_no == order_no))
