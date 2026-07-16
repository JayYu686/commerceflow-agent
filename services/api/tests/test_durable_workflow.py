from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent.mcp_client import MCPToolCallError
from app.api.approvals import get_mcp_tool_client
from app.mcp_server.tools import execute_coupon_issue, execute_refund_apply
from app.models import ActionPlan, AuditLog, CouponRecord, RefundRecord

QUALITY_MESSAGE = (
    "The left speaker of my earbuds has no sound. "
    "Order CF202605180023. I want a refund for a quality issue."
)
DELAY_MESSAGE = (
    "Order CF202605200071 has had no logistics update for seven days. I want delay compensation."
)
AS_OF = "2026-06-09T00:00:00Z"


class InternalMCPTestClient:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.calls: list[tuple[str, dict[str, object]]] = []

    def call_tool(self, tool_name: str, arguments: dict[str, object]) -> dict[str, object]:
        self.calls.append((tool_name, arguments))
        if tool_name == "refund_apply":
            result = execute_refund_apply(
                action_plan_id=str(arguments["action_plan_id"]),
                approval_id=str(arguments["approval_id"]),
                order_no=str(arguments["order_no"]),
                amount=Decimal(str(arguments["amount"])),
                currency=str(arguments["currency"]),
                reason=str(arguments["reason"]),
                idempotency_key=str(arguments["idempotency_key"]),
                session=self.session,
            )
        elif tool_name == "coupon_issue":
            approval_id = arguments.get("approval_id")
            result = execute_coupon_issue(
                action_plan_id=str(arguments["action_plan_id"]),
                approval_id=str(approval_id) if approval_id is not None else None,
                order_no=str(arguments["order_no"]),
                amount=Decimal(str(arguments["amount"])),
                currency=str(arguments["currency"]),
                reason=str(arguments["reason"]),
                idempotency_key=str(arguments["idempotency_key"]),
                session=self.session,
            )
        else:
            raise AssertionError(f"unexpected tool: {tool_name}")
        return result.model_dump(mode="json")


class FailingMCPTestClient:
    def call_tool(self, tool_name: str, arguments: dict[str, object]) -> dict[str, object]:
        raise MCPToolCallError("mcp_transport_failed", "test transport failure")


def test_refund_workflow_interrupts_resumes_and_executes_once(
    client: TestClient,
    seeded_session: Session,
) -> None:
    created = create_action_plan(client, QUALITY_MESSAGE, "durable-refund-plan")
    action_plan_id = created["action_plan_id"]
    approval_id = created["approval_id"]

    assert created["workflow_status"] == "awaiting_approval"
    assert created["execution_status"] == "not_executed"
    assert count_rows(seeded_session, RefundRecord) == 0

    decision = client.post(
        f"/api/approvals/{approval_id}/decision",
        headers={"Idempotency-Key": "durable-refund-approval"},
        json={"decision": "approve", "reviewer": "workflow_reviewer"},
    )
    assert decision.status_code == 200
    detail = client.get(f"/api/action-plans/{action_plan_id}").json()
    assert detail["workflow_status"] == "awaiting_execution"
    assert detail["execution_status"] == "not_executed"
    assert count_rows(seeded_session, RefundRecord) == 0

    mcp_client = InternalMCPTestClient(seeded_session)
    client.app.dependency_overrides[get_mcp_tool_client] = lambda: mcp_client
    try:
        executed = client.post(
            f"/api/action-plans/{action_plan_id}/execute",
            headers={"Idempotency-Key": "durable-refund-execution"},
            json={"confirm": True},
        )
        replay = client.post(
            f"/api/action-plans/{action_plan_id}/execute",
            headers={"Idempotency-Key": "durable-refund-execution"},
            json={"confirm": True},
        )
    finally:
        client.app.dependency_overrides.pop(get_mcp_tool_client, None)

    assert executed.status_code == 200
    assert executed.json()["workflow_status"] == "completed"
    assert executed.json()["result_type"] == "refund"
    assert executed.json()["idempotent_replay"] is False
    assert replay.status_code == 200
    assert replay.json()["record_id"] == executed.json()["record_id"]
    assert replay.json()["idempotent_replay"] is True
    assert [call[0] for call in mcp_client.calls] == ["refund_apply"]
    assert count_rows(seeded_session, RefundRecord) == 1


def test_low_value_coupon_waits_for_confirmation_without_approval(
    client: TestClient,
    seeded_session: Session,
) -> None:
    created = create_action_plan(client, DELAY_MESSAGE, "durable-coupon-plan")
    action_plan_id = created["action_plan_id"]

    assert created["workflow_status"] == "awaiting_execution"
    assert created["approval_id"] is None
    assert count_rows(seeded_session, CouponRecord) == 0

    mcp_client = InternalMCPTestClient(seeded_session)
    client.app.dependency_overrides[get_mcp_tool_client] = lambda: mcp_client
    try:
        response = client.post(
            f"/api/action-plans/{action_plan_id}/execute",
            headers={"Idempotency-Key": "durable-coupon-execution"},
            json={"confirm": True},
        )
    finally:
        client.app.dependency_overrides.pop(get_mcp_tool_client, None)

    assert response.status_code == 200
    assert response.json()["tool_name"] == "coupon_issue"
    assert count_rows(seeded_session, CouponRecord) == 1


def test_mcp_failure_keeps_workflow_retryable_and_business_state_unchanged(
    client: TestClient,
    seeded_session: Session,
) -> None:
    created = create_action_plan(client, DELAY_MESSAGE, "durable-retry-plan")
    action_plan_id = created["action_plan_id"]
    client.app.dependency_overrides[get_mcp_tool_client] = lambda: FailingMCPTestClient()
    try:
        failed = client.post(
            f"/api/action-plans/{action_plan_id}/execute",
            headers={"Idempotency-Key": "durable-retry-execution"},
            json={"confirm": True},
        )
    finally:
        client.app.dependency_overrides.pop(get_mcp_tool_client, None)

    assert failed.status_code == 409
    action_plan = seeded_session.scalar(
        select(ActionPlan).where(ActionPlan.action_plan_id == action_plan_id)
    )
    assert action_plan is not None
    seeded_session.refresh(action_plan)
    assert action_plan.workflow_status == "awaiting_execution"
    assert action_plan.workflow_error_code == "mcp_transport_failed"
    assert action_plan.execution_status == "not_executed"
    assert count_rows(seeded_session, CouponRecord) == 0


def test_rejected_approval_cannot_reach_execution(
    client: TestClient,
    seeded_session: Session,
) -> None:
    created = create_action_plan(client, QUALITY_MESSAGE, "durable-reject-plan")
    action_plan_id = created["action_plan_id"]
    decision = client.post(
        f"/api/approvals/{created['approval_id']}/decision",
        headers={"Idempotency-Key": "durable-reject-approval"},
        json={"decision": "reject", "reviewer": "workflow_reviewer"},
    )

    assert decision.status_code == 200
    blocked = client.post(
        f"/api/action-plans/{action_plan_id}/execute",
        headers={"Idempotency-Key": "durable-reject-execution"},
        json={"confirm": True},
    )
    assert blocked.status_code == 409
    assert count_rows(seeded_session, RefundRecord) == 0


def test_workflow_audit_events_share_action_plan_run(
    client: TestClient,
    seeded_session: Session,
) -> None:
    created = create_action_plan(client, DELAY_MESSAGE, "durable-audit-plan")
    events = client.get(f"/api/action-plans/{created['action_plan_id']}/audit-logs").json()[
        "events"
    ]

    assert [event["event_type"] for event in events][-2:] == [
        "workflow_started",
        "workflow_interrupted",
    ]
    assert all(event["action_plan_id"] == created["action_plan_id"] for event in events)
    assert count_rows(seeded_session, AuditLog) >= 3


def create_action_plan(client: TestClient, message: str, key: str) -> dict:
    response = client.post(
        "/api/agent/after-sales/action-plans",
        headers={"Idempotency-Key": key},
        json={"message": message, "as_of": AS_OF},
    )
    assert response.status_code == 200, response.text
    return response.json()


def count_rows(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0
