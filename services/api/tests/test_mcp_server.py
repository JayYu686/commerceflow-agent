from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.server.fastmcp.exceptions import ToolError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.mcp_server.server import create_mcp_server
from app.mcp_server.tools import (
    execute_coupon_issue,
    execute_refund_apply,
    execute_ticket_create,
)
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
from scripts.ingest_policies import ingest_policies
from scripts.seed_demo_data import FIXED_DELAYED_ORDER_NO, FIXED_QUALITY_ORDER_NO, seed_session


def test_mcp_server_registers_three_tools_with_input_and_output_schemas() -> None:
    server = create_mcp_server()
    tools = {tool.name: tool for tool in server._tool_manager.list_tools()}

    assert set(tools) == {"refund_apply", "coupon_issue", "ticket_create"}
    for tool_name, required_fields in {
        "refund_apply": {
            "action_plan_id",
            "approval_id",
            "order_no",
            "amount",
            "currency",
            "reason",
            "idempotency_key",
        },
        "coupon_issue": {
            "action_plan_id",
            "approval_id",
            "order_no",
            "amount",
            "currency",
            "reason",
            "idempotency_key",
        },
        "ticket_create": {"action_plan_id", "order_no", "category", "summary", "idempotency_key"},
    }.items():
        input_properties = tools[tool_name].parameters["properties"]
        assert required_fields <= set(input_properties)
        assert tools[tool_name].output_schema is not None
        assert "mock" in tools[tool_name].description.lower()
        assert "idempotency" in tools[tool_name].description.lower()


def test_approved_refund_mcp_handler_creates_record_and_audit(seeded_session: Session) -> None:
    payload = create_approved_refund_payload(seeded_session)
    before_audits = count_rows(seeded_session, AuditLog)

    result = execute_refund_apply(
        **payload,
        idempotency_key="mcp-refund-success",
        session=seeded_session,
    )

    assert result.ok is True
    assert result.tool_name == "refund_apply"
    assert result.status == "succeeded"
    assert result.execution_status == "executed"
    assert result.idempotent_replay is False
    assert count_rows(seeded_session, RefundRecord) == 1
    assert count_rows(seeded_session, AuditLog) == before_audits + 1


def test_refund_without_approval_mcp_handler_is_blocked(seeded_session: Session) -> None:
    action_plan = create_direct_action_plan(
        seeded_session,
        planned_tool_name="refund_apply",
        action_type="refund_apply",
        status="approved",
        order_no=FIXED_QUALITY_ORDER_NO,
        amount=Decimal("299.00"),
        policy_evidence=True,
    )

    with pytest.raises(ToolError) as exc_info:
        execute_refund_apply(
            action_plan_id=action_plan.action_plan_id,
            approval_id=str(uuid4()),
            order_no=FIXED_QUALITY_ORDER_NO,
            amount=Decimal("299.00"),
            currency="CNY",
            reason="Quality issue refund.",
            idempotency_key="mcp-refund-no-approval",
            session=seeded_session,
        )

    assert "approval_mismatch" in str(exc_info.value)
    assert count_rows(seeded_session, RefundRecord) == 0


def test_planned_low_value_coupon_mcp_handler_executes(seeded_session: Session) -> None:
    action_plan = create_direct_action_plan(
        seeded_session,
        planned_tool_name="coupon_issue",
        action_type="coupon_issue",
        status="planned",
        order_no=FIXED_DELAYED_ORDER_NO,
        amount=Decimal("10.00"),
        policy_evidence=True,
    )

    result = execute_coupon_issue(
        action_plan_id=action_plan.action_plan_id,
        approval_id=None,
        order_no=FIXED_DELAYED_ORDER_NO,
        amount=Decimal("10.00"),
        currency="CNY",
        reason="Delay compensation.",
        idempotency_key="mcp-coupon-low",
        session=seeded_session,
    )

    assert result.ok is True
    assert result.tool_name == "coupon_issue"
    assert result.status == "issued"
    assert count_rows(seeded_session, CouponRecord) == 1


def test_high_value_coupon_without_approval_mcp_handler_is_blocked(
    seeded_session: Session,
) -> None:
    action_plan = create_direct_action_plan(
        seeded_session,
        planned_tool_name="coupon_issue",
        action_type="coupon_issue",
        status="planned",
        order_no=FIXED_DELAYED_ORDER_NO,
        amount=Decimal("10.01"),
        policy_evidence=True,
    )

    with pytest.raises(ToolError) as exc_info:
        execute_coupon_issue(
            action_plan_id=action_plan.action_plan_id,
            approval_id=None,
            order_no=FIXED_DELAYED_ORDER_NO,
            amount=Decimal("10.01"),
            currency="CNY",
            reason="Delay compensation.",
            idempotency_key="mcp-coupon-high-blocked",
            session=seeded_session,
        )

    assert "approval_required" in str(exc_info.value)
    assert count_rows(seeded_session, CouponRecord) == 0


def test_planned_ticket_mcp_handler_executes(seeded_session: Session) -> None:
    action_plan = create_direct_action_plan(
        seeded_session,
        planned_tool_name="ticket_create",
        action_type="manual_review",
        status="planned",
        order_no=FIXED_QUALITY_ORDER_NO,
        amount=None,
        policy_evidence=False,
    )

    result = execute_ticket_create(
        action_plan_id=action_plan.action_plan_id,
        order_no=FIXED_QUALITY_ORDER_NO,
        category="quality_issue",
        summary="Create follow-up ticket for evidence review.",
        idempotency_key="mcp-ticket-planned",
        session=seeded_session,
    )

    assert result.ok is True
    assert result.tool_name == "ticket_create"
    assert result.status == "created"
    assert count_rows(seeded_session, TicketRecord) == 1


def test_mcp_handler_idempotency_replay_and_conflicts(seeded_session: Session) -> None:
    payload = create_approved_refund_payload(seeded_session)
    first = execute_refund_apply(
        **payload,
        idempotency_key="mcp-refund-replay",
        session=seeded_session,
    )
    replay = execute_refund_apply(
        **payload,
        idempotency_key="mcp-refund-replay",
        session=seeded_session,
    )

    assert replay.idempotent_replay is True
    assert replay.record_id == first.record_id

    with pytest.raises(ToolError) as reused_key:
        execute_refund_apply(
            **{**payload, "amount": Decimal("1.00")},
            idempotency_key="mcp-refund-replay",
            session=seeded_session,
        )
    assert "idempotency_key_reused" in str(reused_key.value)

    duplicate_payload = create_approved_refund_payload(seeded_session)
    execute_refund_apply(
        **duplicate_payload,
        idempotency_key="mcp-refund-duplicate-first",
        session=seeded_session,
    )
    with pytest.raises(ToolError) as duplicate:
        execute_refund_apply(
            **duplicate_payload,
            idempotency_key="mcp-refund-duplicate-second",
            session=seeded_session,
        )
    assert "duplicate_execution" in str(duplicate.value)


def test_mcp_handler_validation_error_is_safely_mapped(seeded_session: Session) -> None:
    with pytest.raises(ToolError) as exc_info:
        execute_ticket_create(
            action_plan_id=" ",
            order_no=FIXED_QUALITY_ORDER_NO,
            category="quality_issue",
            summary="Create ticket.",
            idempotency_key="mcp-validation-error",
            session=seeded_session,
        )

    message = str(exc_info.value)
    assert "validation_error" in message
    assert "Traceback" not in message
    assert "DATABASE_URL" not in message


def test_mcp_handler_unexpected_error_is_sanitized(
    seeded_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_with_internal_details(*args, **kwargs):
        raise RuntimeError("secret DATABASE_URL postgresql://x C:\\internal\\path traceback")

    monkeypatch.setattr("app.mcp_server.tools.apply_refund", fail_with_internal_details)

    with pytest.raises(ToolError) as exc_info:
        execute_refund_apply(
            action_plan_id=str(uuid4()),
            approval_id=str(uuid4()),
            order_no=FIXED_QUALITY_ORDER_NO,
            amount=Decimal("299.00"),
            currency="CNY",
            reason="Quality issue refund.",
            idempotency_key="mcp-unexpected-error",
            session=seeded_session,
        )

    message = str(exc_info.value)
    assert "tool_execution_failed" in message
    assert "DATABASE_URL" not in message
    assert "postgresql://" not in message
    assert "C:\\internal" not in message
    assert "traceback" not in message


def test_mcp_tool_execution_does_not_mutate_protected_tables(seeded_session: Session) -> None:
    payload = create_approved_refund_payload(seeded_session)
    before_counts = protected_table_counts(seeded_session)
    before_status = order_aftersales_status(seeded_session, FIXED_QUALITY_ORDER_NO)

    result = execute_refund_apply(
        **payload,
        idempotency_key="mcp-mutation-safe-refund",
        session=seeded_session,
    )

    assert result.status == "succeeded"
    assert protected_table_counts(seeded_session) == before_counts
    assert order_aftersales_status(seeded_session, FIXED_QUALITY_ORDER_NO) == before_status


def test_mcp_wrapper_does_not_import_result_orm_or_agent_auto_call() -> None:
    source = Path("app/mcp_server/tools.py").read_text(encoding="utf-8")
    forbidden_model_names = ("RefundRecord", "CouponRecord", "TicketRecord", "ActionPlan")
    assert all(name not in source for name in forbidden_model_names)
    assert "LangGraph" not in source
    assert "interrupt" not in source
    assert "resume" not in source


@pytest.mark.anyio
async def test_mcp_stdio_protocol_lists_tools_and_calls_success_and_blocked(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "mcp_protocol.sqlite"
    database_url = f"sqlite+pysqlite:///{db_path.as_posix()}"
    success_payload, blocked_payload = prepare_protocol_database(database_url)
    api_dir = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    env["APP_ENV"] = "test"

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp_server.server"],
        cwd=api_dir,
        env=env,
    )
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as client_session:
            await client_session.initialize()
            tools_result = await client_session.list_tools()
            tools = {tool.name: tool for tool in tools_result.tools}

            assert set(tools) == {"refund_apply", "coupon_issue", "ticket_create"}
            assert "idempotency_key" in tools["coupon_issue"].inputSchema["properties"]
            assert "amount" in tools["coupon_issue"].inputSchema["properties"]

            success = await client_session.call_tool("coupon_issue", success_payload)
            assert success.isError is False
            assert success.structuredContent is not None
            assert success.structuredContent["ok"] is True
            assert success.structuredContent["tool_name"] == "coupon_issue"
            assert success.structuredContent["status"] == "issued"

            blocked = await client_session.call_tool("refund_apply", blocked_payload)
            assert blocked.isError is True
            assert any("approval_mismatch" in block.text for block in blocked.content)


def prepare_protocol_database(database_url: str) -> tuple[dict, dict]:
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with SessionLocal() as session:
        seed_session(session, reset=True)
        ingest_policies(session, reset=True)
        coupon_plan = create_direct_action_plan(
            session,
            planned_tool_name="coupon_issue",
            action_type="coupon_issue",
            status="planned",
            order_no=FIXED_DELAYED_ORDER_NO,
            amount=Decimal("10.00"),
            policy_evidence=True,
        )
        refund_plan = create_direct_action_plan(
            session,
            planned_tool_name="refund_apply",
            action_type="refund_apply",
            status="approved",
            order_no=FIXED_QUALITY_ORDER_NO,
            amount=Decimal("299.00"),
            policy_evidence=True,
        )
        success_payload = {
            "action_plan_id": coupon_plan.action_plan_id,
            "approval_id": None,
            "order_no": FIXED_DELAYED_ORDER_NO,
            "amount": "10.00",
            "currency": "CNY",
            "reason": "Delay compensation.",
            "idempotency_key": "mcp-protocol-coupon-success",
        }
        blocked_payload = {
            "action_plan_id": refund_plan.action_plan_id,
            "approval_id": str(uuid4()),
            "order_no": FIXED_QUALITY_ORDER_NO,
            "amount": "299.00",
            "currency": "CNY",
            "reason": "Quality issue refund.",
            "idempotency_key": "mcp-protocol-refund-blocked",
        }
    engine.dispose()
    return success_payload, blocked_payload


def create_approved_refund_payload(session: Session) -> dict:
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
        "amount": Decimal("299.00"),
        "currency": "CNY",
        "reason": "Quality issue refund.",
    }


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
        summary="Direct MCP test action plan.",
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
