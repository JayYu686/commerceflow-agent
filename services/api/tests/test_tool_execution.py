from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    ActionPlan,
    ApprovalRequest,
    AuditLog,
    CouponRecord,
    Order,
    PolicyChunk,
    PolicyDocument,
    RefundRecord,
    Shipment,
    TicketRecord,
)
from scripts.seed_demo_data import FIXED_DELAYED_ORDER_NO, FIXED_QUALITY_ORDER_NO

QUALITY_MESSAGE = (
    f"Earbuds left speaker has no sound, order {FIXED_QUALITY_ORDER_NO}, I want a refund."
)
DELAY_MESSAGE = (
    f"Order {FIXED_DELAYED_ORDER_NO} logistics has no movement, request delay compensation."
)


def test_approved_refund_tool_creates_record_and_read_api(
    client: TestClient,
    seeded_session: Session,
) -> None:
    plan = create_quality_plan_and_approve(client)
    before_audits = count_rows(seeded_session, AuditLog)

    response = refund_apply(client, plan, "refund-tool-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_name"] == "refund_apply"
    assert payload["status"] == "succeeded"
    assert payload["execution_status"] == "executed"
    assert payload["idempotent_replay"] is False
    assert count_rows(seeded_session, RefundRecord) == 1
    assert count_rows(seeded_session, AuditLog) == before_audits + 1

    read_response = client.get(f"/api/refunds/{payload['record_id']}")
    assert read_response.status_code == 200
    refund = read_response.json()
    assert refund["refund_id"] == payload["record_id"]
    assert refund["amount"] == "299.00"
    assert refund["status"] == "succeeded"

    action_result = client.get(f"/api/action-plans/{plan['action_plan_id']}/result")
    assert action_result.status_code == 200
    result_payload = action_result.json()
    assert result_payload["result_type"] == "refund"
    assert result_payload["result"]["refund_id"] == payload["record_id"]


def test_refund_without_approval_is_blocked_and_audited(
    client: TestClient,
    seeded_session: Session,
) -> None:
    action_plan = create_direct_action_plan(
        seeded_session,
        planned_tool_name="refund_apply",
        action_type="refund_apply",
        status="approved",
        order_no=FIXED_QUALITY_ORDER_NO,
        amount=Decimal("299.00"),
        policy_evidence=True,
    )
    before_audits = count_rows(seeded_session, AuditLog)

    response = refund_apply(
        client,
        {
            "action_plan_id": action_plan.action_plan_id,
            "approval_id": str(uuid4()),
            "order_no": FIXED_QUALITY_ORDER_NO,
            "amount": "299.00",
            "currency": "CNY",
            "reason": "Quality issue refund.",
        },
        "refund-no-approval",
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "approval_mismatch"
    assert count_rows(seeded_session, RefundRecord) == 0
    assert count_rows(seeded_session, AuditLog) == before_audits + 1


def test_refund_pending_approval_is_blocked(client: TestClient) -> None:
    plan = create_quality_action_plan(client, "refund-pending-plan")

    response = refund_apply(client, plan, "refund-pending-tool")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "approval_required"


def test_refund_rejected_approval_is_blocked(client: TestClient) -> None:
    plan = create_quality_action_plan(client, "refund-rejected-plan")
    approval_id = plan["approval_id"]
    reject = decide_approval(client, approval_id, "reject", "reject-before-refund")
    assert reject.status_code == 200

    response = refund_apply(client, plan, "refund-rejected-tool")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "approval_required"


def test_refund_argument_mismatches_are_blocked(
    client: TestClient,
    seeded_session: Session,
) -> None:
    amount_plan = create_approved_refund_payload_from_direct_plan(seeded_session)
    amount_response = refund_apply(
        client,
        {**amount_plan, "amount": "1.00"},
        "refund-wrong-amount",
    )
    assert amount_response.status_code == 409
    assert amount_response.json()["detail"]["code"] == "amount_mismatch"

    order_plan = create_approved_refund_payload_from_direct_plan(seeded_session)
    order_response = refund_apply(
        client,
        {**order_plan, "order_no": FIXED_DELAYED_ORDER_NO},
        "refund-wrong-order",
    )
    assert order_response.status_code == 409
    assert order_response.json()["detail"]["code"] == "order_mismatch"


def test_refund_action_mismatch_is_blocked(
    client: TestClient,
    seeded_session: Session,
) -> None:
    action_plan = create_direct_action_plan(
        seeded_session,
        planned_tool_name="coupon_issue",
        action_type="coupon_issue",
        status="approved",
        order_no=FIXED_QUALITY_ORDER_NO,
        amount=Decimal("299.00"),
        policy_evidence=True,
    )
    approval = create_direct_approval(seeded_session, action_plan, status="approved")

    response = refund_apply(
        client,
        {
            "action_plan_id": action_plan.action_plan_id,
            "approval_id": approval.approval_id,
            "order_no": FIXED_QUALITY_ORDER_NO,
            "amount": "299.00",
            "currency": "CNY",
            "reason": "Quality issue refund.",
        },
        "refund-action-mismatch",
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "tool_action_mismatch"


def test_refund_duplicate_execution_is_blocked(client: TestClient) -> None:
    plan = create_quality_plan_and_approve(client)
    first = refund_apply(client, plan, "refund-duplicate-first")
    second = refund_apply(client, plan, "refund-duplicate-second")

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "duplicate_execution"


def test_refund_same_idempotency_replay_returns_same_result_and_audits(
    client: TestClient,
    seeded_session: Session,
) -> None:
    plan = create_quality_plan_and_approve(client)
    first = refund_apply(client, plan, "refund-replay-key")
    before_replay_audits = count_rows(seeded_session, AuditLog)
    second = refund_apply(client, plan, "refund-replay-key")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["record_id"] == first.json()["record_id"]
    assert second.json()["idempotent_replay"] is True
    assert count_rows(seeded_session, AuditLog) == before_replay_audits + 1


def test_coupon_cny_10_planned_action_executes(
    client: TestClient,
    seeded_session: Session,
) -> None:
    plan = create_delay_coupon_plan(client)

    response = coupon_issue(client, plan, "coupon-small-tool")

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_name"] == "coupon_issue"
    assert payload["status"] == "issued"
    assert count_rows(seeded_session, CouponRecord) == 1

    read_response = client.get(f"/api/coupons/{payload['record_id']}")
    assert read_response.status_code == 200
    assert read_response.json()["amount"] == "10.00"

    action_result = client.get(f"/api/action-plans/{plan['action_plan_id']}/result")
    assert action_result.status_code == 200
    assert action_result.json()["result_type"] == "coupon"


def test_coupon_above_threshold_requires_approval_then_executes(
    client: TestClient,
    seeded_session: Session,
) -> None:
    planned = create_direct_action_plan(
        seeded_session,
        planned_tool_name="coupon_issue",
        action_type="coupon_issue",
        status="planned",
        order_no=FIXED_DELAYED_ORDER_NO,
        amount=Decimal("10.01"),
        policy_evidence=True,
    )
    blocked = coupon_issue(
        client,
        {
            "action_plan_id": planned.action_plan_id,
            "approval_id": None,
            "order_no": FIXED_DELAYED_ORDER_NO,
            "amount": "10.01",
            "currency": "CNY",
            "reason": "Delay compensation.",
        },
        "coupon-high-blocked",
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "approval_required"

    approved = create_direct_action_plan(
        seeded_session,
        planned_tool_name="coupon_issue",
        action_type="coupon_issue",
        status="approved",
        order_no=FIXED_DELAYED_ORDER_NO,
        amount=Decimal("10.01"),
        policy_evidence=True,
    )
    approval = create_direct_approval(seeded_session, approved, status="approved")
    executed = coupon_issue(
        client,
        {
            "action_plan_id": approved.action_plan_id,
            "approval_id": approval.approval_id,
            "order_no": FIXED_DELAYED_ORDER_NO,
            "amount": "10.01",
            "currency": "CNY",
            "reason": "Delay compensation.",
        },
        "coupon-high-approved",
    )
    assert executed.status_code == 200
    assert executed.json()["status"] == "issued"


def test_ticket_planned_action_executes_and_read_api(
    client: TestClient,
    seeded_session: Session,
) -> None:
    action_plan = create_direct_action_plan(
        seeded_session,
        planned_tool_name="ticket_create",
        action_type="manual_review",
        status="planned",
        order_no=FIXED_QUALITY_ORDER_NO,
        amount=None,
        policy_evidence=False,
    )

    response = ticket_create(
        client,
        {
            "action_plan_id": action_plan.action_plan_id,
            "order_no": FIXED_QUALITY_ORDER_NO,
            "category": "quality_issue",
            "summary": "Create follow-up ticket for evidence review.",
        },
        "ticket-planned-tool",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_name"] == "ticket_create"
    assert payload["status"] == "created"
    assert count_rows(seeded_session, TicketRecord) == 1

    read_response = client.get(f"/api/tickets/{payload['record_id']}")
    assert read_response.status_code == 200
    assert read_response.json()["category"] == "quality_issue"

    action_result = client.get(f"/api/action-plans/{action_plan.action_plan_id}/result")
    assert action_result.status_code == 200
    assert action_result.json()["result_type"] == "ticket"


def test_not_executable_action_plan_blocks_tool_execution(client: TestClient) -> None:
    response = client.post(
        "/api/agent/after-sales/action-plans",
        headers={"Idempotency-Key": "not-executable-plan"},
        json={
            "message": "Fresh fruit spoiled, order CF202605100004, I want a refund.",
            "as_of": "2026-06-06T00:00:00Z",
        },
    )
    assert response.status_code == 200
    plan = response.json()

    execute = ticket_create(
        client,
        {
            "action_plan_id": plan["action_plan_id"],
            "order_no": plan["order_no"],
            "category": "manual_review",
            "summary": "Try to create ticket from not executable plan.",
        },
        "ticket-not-executable",
    )

    assert execute.status_code == 409
    assert execute.json()["detail"]["code"] == "tool_action_mismatch"


def test_tool_api_404_and_result_404(client: TestClient) -> None:
    missing_action = refund_apply(
        client,
        {
            "action_plan_id": str(uuid4()),
            "approval_id": str(uuid4()),
            "order_no": FIXED_QUALITY_ORDER_NO,
            "amount": "299.00",
            "currency": "CNY",
            "reason": "Quality issue refund.",
        },
        "missing-action-plan",
    )
    missing_result = client.get(f"/api/refunds/{uuid4()}")

    assert missing_action.status_code == 404
    assert missing_result.status_code == 404


def test_tool_execution_does_not_mutate_protected_business_tables(
    client: TestClient,
    seeded_session: Session,
) -> None:
    plan = create_quality_plan_and_approve(client)
    before_counts = protected_table_counts(seeded_session)
    before_status = order_aftersales_status(seeded_session, FIXED_QUALITY_ORDER_NO)

    response = refund_apply(client, plan, "mutation-safe-refund")

    assert response.status_code == 200
    assert protected_table_counts(seeded_session) == before_counts
    assert order_aftersales_status(seeded_session, FIXED_QUALITY_ORDER_NO) == before_status


def test_tool_routes_do_not_expose_mcp_or_arbitrary_sql(client: TestClient) -> None:
    paths = {getattr(route, "path", "") for route in client.app.routes}
    forbidden_fragments = ("mcp", "sql")

    forbidden_paths = [
        path for path in paths if any(fragment in path.lower() for fragment in forbidden_fragments)
    ]
    assert forbidden_paths == []
    assert not any(path.startswith("/api/agent") and "/tools/" in path for path in paths)


def create_quality_action_plan(
    client: TestClient,
    idempotency_key: str,
) -> dict:
    response = client.post(
        "/api/agent/after-sales/action-plans",
        headers={"Idempotency-Key": idempotency_key},
        json={"message": QUALITY_MESSAGE, "as_of": "2026-06-06T00:00:00Z"},
    )
    assert response.status_code == 200
    payload = response.json()
    return {
        "action_plan_id": payload["action_plan_id"],
        "approval_id": payload["approval_id"],
        "order_no": payload["order_no"],
        "amount": payload["proposed_amount"],
        "currency": payload["currency"],
        "reason": "Quality issue refund.",
    }


def create_quality_plan_and_approve(
    client: TestClient,
    *,
    idempotency_suffix: str = "default",
) -> dict:
    plan = create_quality_action_plan(client, f"quality-plan-{idempotency_suffix}")
    decision = decide_approval(
        client,
        plan["approval_id"],
        "approve",
        f"quality-approval-{idempotency_suffix}",
    )
    assert decision.status_code == 200
    return plan


def create_approved_refund_payload_from_direct_plan(session: Session) -> dict:
    action_plan = create_direct_action_plan(
        session,
        planned_tool_name="refund_apply",
        action_type="refund_apply",
        status="approved",
        order_no=FIXED_QUALITY_ORDER_NO,
        amount=Decimal("299.00"),
        policy_evidence=True,
    )
    approval = create_direct_approval(session, action_plan, status="approved")
    return {
        "action_plan_id": action_plan.action_plan_id,
        "approval_id": approval.approval_id,
        "order_no": FIXED_QUALITY_ORDER_NO,
        "amount": "299.00",
        "currency": "CNY",
        "reason": "Quality issue refund.",
    }


def create_delay_coupon_plan(client: TestClient) -> dict:
    response = client.post(
        "/api/agent/after-sales/action-plans",
        headers={"Idempotency-Key": "delay-coupon-plan"},
        json={"message": DELAY_MESSAGE, "as_of": "2026-06-06T00:00:00Z"},
    )
    assert response.status_code == 200
    payload = response.json()
    return {
        "action_plan_id": payload["action_plan_id"],
        "approval_id": None,
        "order_no": payload["order_no"],
        "amount": payload["proposed_amount"],
        "currency": payload["currency"],
        "reason": "Delay compensation.",
    }


def decide_approval(
    client: TestClient,
    approval_id: str,
    decision: str,
    idempotency_key: str,
):
    return client.post(
        f"/api/approvals/{approval_id}/decision",
        headers={"Idempotency-Key": idempotency_key},
        json={
            "decision": decision,
            "reviewer": "demo_reviewer",
            "comment": "Evidence and policy match the proposed action.",
        },
    )


def refund_apply(client: TestClient, payload: dict, idempotency_key: str):
    return client.post(
        "/api/tools/refund-apply",
        headers={"Idempotency-Key": idempotency_key},
        json=payload,
    )


def coupon_issue(client: TestClient, payload: dict, idempotency_key: str):
    return client.post(
        "/api/tools/coupon-issue",
        headers={"Idempotency-Key": idempotency_key},
        json=payload,
    )


def ticket_create(client: TestClient, payload: dict, idempotency_key: str):
    return client.post(
        "/api/tools/ticket-create",
        headers={"Idempotency-Key": idempotency_key},
        json=payload,
    )


def create_direct_action_plan(
    session: Session,
    *,
    planned_tool_name: str,
    action_type: str,
    status: str,
    order_no: str,
    amount: Decimal | None,
    policy_evidence: bool,
) -> ActionPlan:
    now = datetime.now(UTC)
    action_plan = ActionPlan(
        action_plan_id=str(uuid4()),
        run_id=str(uuid4()),
        idempotency_key=str(uuid4()),
        business_dedupe_key=str(uuid4()),
        order_no=order_no,
        intent="quality_issue_refund",
        planned_tool_name=planned_tool_name,
        action_type=action_type,
        status=status,
        execution_status="not_executed",
        risk_level="high" if action_type == "refund_apply" else "medium",
        requires_approval=status == "approved",
        proposed_amount=amount,
        currency="CNY" if amount is not None else None,
        summary="Direct test action plan.",
        reasons_json=["test setup"],
        next_steps_json=["test execution"],
        fact_evidence_json=[{"source": "test"}],
        policy_evidence_json=[{"policy_id": "POL-QUALITY-ELECTRONICS-V2"}]
        if policy_evidence
        else [],
        llm_json={"provider": "disabled"},
        request_message="test",
        request_hash=str(uuid4()).replace("-", ""),
        created_at=now,
        updated_at=now,
    )
    session.add(action_plan)
    session.commit()
    session.refresh(action_plan)
    return action_plan


def create_direct_approval(
    session: Session,
    action_plan: ActionPlan,
    *,
    status: str,
) -> ApprovalRequest:
    now = datetime.now(UTC)
    approval = ApprovalRequest(
        approval_id=str(uuid4()),
        action_plan=action_plan,
        status=status,
        risk_level=action_plan.risk_level,
        requested_action_type=action_plan.action_type,
        proposed_amount=action_plan.proposed_amount,
        currency=action_plan.currency,
        policy_ids_json=["POL-QUALITY-ELECTRONICS-V2"],
        requester="agent",
        reviewer="demo_reviewer" if status == "approved" else None,
        decision_comment="approved" if status == "approved" else None,
        requested_at=now,
        decided_at=now if status == "approved" else None,
        updated_at=now,
    )
    session.add(approval)
    session.commit()
    session.refresh(approval)
    return approval


def count_rows(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def protected_table_counts(session: Session) -> dict[str, int]:
    return {
        "orders": count_rows(session, Order),
        "shipments": count_rows(session, Shipment),
        "policy_documents": count_rows(session, PolicyDocument),
        "policy_chunks": count_rows(session, PolicyChunk),
    }


def order_aftersales_status(session: Session, order_no: str) -> str | None:
    return session.scalar(select(Order.aftersales_status).where(Order.order_no == order_no))
