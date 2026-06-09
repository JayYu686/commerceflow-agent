from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import Field, ValidationError
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.mcp_server.results import (
    McpToolSuccess,
    map_known_error,
    raise_mcp_tool_error,
    sanitized_unexpected_error,
    success_from_service_result,
)
from app.schemas.tools import (
    CouponIssueRequest,
    RefundApplyRequest,
    TicketCreateRequest,
    ToolExecutionResponse,
    ToolName,
)
from app.services.tools import apply_refund, create_ticket, issue_coupon

MCP_ACTOR_ID = "mcp_stdio"

ShortText = Annotated[str, Field(min_length=1)]
OrderNo = Annotated[str, Field(min_length=1, max_length=32)]
Currency = Annotated[str, Field(min_length=3, max_length=3)]
Reason = Annotated[str, Field(min_length=1, max_length=1000)]
TicketCategory = Annotated[str, Field(min_length=1, max_length=80)]
TicketSummary = Annotated[str, Field(min_length=1, max_length=1000)]
PositiveAmount = Annotated[Decimal, Field(gt=Decimal("0.00"))]

REFUND_APPLY_DESCRIPTION = """
Apply a local mock refund record for a persisted CommerceFlow action plan.
This tool has local mock write side effects: it can write refund_records, update the
matching action_plans.execution_status, and append audit_logs only. It never calls a
real payment system and never modifies original order, logistics, or policy records.
It requires a persisted action plan, an approved approval request, matching order,
amount, currency, applicable policy evidence, execution_status=not_executed, and an
idempotency key. All approval, action match, amount, order, policy evidence,
duplicate execution, idempotency, and audit rules are enforced by the internal tool
execution service, not by this MCP wrapper.
""".strip()

COUPON_ISSUE_DESCRIPTION = """
Issue a local mock coupon record for a persisted CommerceFlow action plan.
This tool has local mock write side effects: it can write coupon_records, update the
matching action_plans.execution_status, and append audit_logs only. It never calls a
real coupon system and never modifies original order, logistics, or policy records.
It requires a persisted action plan, matching order, amount, currency, applicable
policy evidence, execution_status=not_executed, and an idempotency key. High-value
coupons require approved approval according to the internal service threshold. This
MCP wrapper does not reimplement the CNY 10 approval threshold or any business rule.
""".strip()

TICKET_CREATE_DESCRIPTION = """
Create a local mock ticket record for a persisted CommerceFlow action plan.
This tool has local mock write side effects: it can write ticket_records, update the
matching action_plans.execution_status, and append audit_logs only. It never calls a
real customer support ticketing system and never modifies original order, logistics,
or policy records. It requires a persisted planned or approved action plan,
execution_status=not_executed, matching order, and an idempotency key. All action
state, duplicate execution, idempotency, and audit rules are enforced by the
internal tool execution service, not by this MCP wrapper.
""".strip()


def register_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        name="refund_apply",
        description=REFUND_APPLY_DESCRIPTION,
        structured_output=True,
    )
    def refund_apply_tool(
        action_plan_id: ShortText,
        approval_id: ShortText,
        order_no: OrderNo,
        amount: PositiveAmount,
        currency: Currency,
        reason: Reason,
        idempotency_key: ShortText,
    ) -> McpToolSuccess:
        return execute_refund_apply(
            action_plan_id=action_plan_id,
            approval_id=approval_id,
            order_no=order_no,
            amount=amount,
            currency=currency,
            reason=reason,
            idempotency_key=idempotency_key,
        )

    @mcp.tool(
        name="coupon_issue",
        description=COUPON_ISSUE_DESCRIPTION,
        structured_output=True,
    )
    def coupon_issue_tool(
        action_plan_id: ShortText,
        approval_id: str | None,
        order_no: OrderNo,
        amount: PositiveAmount,
        currency: Currency,
        reason: Reason,
        idempotency_key: ShortText,
    ) -> McpToolSuccess:
        return execute_coupon_issue(
            action_plan_id=action_plan_id,
            approval_id=approval_id,
            order_no=order_no,
            amount=amount,
            currency=currency,
            reason=reason,
            idempotency_key=idempotency_key,
        )

    @mcp.tool(
        name="ticket_create",
        description=TICKET_CREATE_DESCRIPTION,
        structured_output=True,
    )
    def ticket_create_tool(
        action_plan_id: ShortText,
        order_no: OrderNo,
        category: TicketCategory,
        summary: TicketSummary,
        idempotency_key: ShortText,
    ) -> McpToolSuccess:
        return execute_ticket_create(
            action_plan_id=action_plan_id,
            order_no=order_no,
            category=category,
            summary=summary,
            idempotency_key=idempotency_key,
        )


def execute_refund_apply(
    *,
    action_plan_id: str,
    approval_id: str,
    order_no: str,
    amount: Decimal,
    currency: str,
    reason: str,
    idempotency_key: str,
    session: Session | None = None,
) -> McpToolSuccess:
    return _run_tool(
        tool_name="refund_apply",
        idempotency_key=idempotency_key,
        session=session,
        operation=lambda active_session: apply_refund(
            active_session,
            RefundApplyRequest(
                action_plan_id=action_plan_id,
                approval_id=approval_id,
                order_no=order_no,
                amount=amount,
                currency=currency,
                reason=reason,
            ),
            idempotency_key=idempotency_key,
            actor_id=MCP_ACTOR_ID,
        ),
    )


def execute_coupon_issue(
    *,
    action_plan_id: str,
    approval_id: str | None,
    order_no: str,
    amount: Decimal,
    currency: str,
    reason: str,
    idempotency_key: str,
    session: Session | None = None,
) -> McpToolSuccess:
    return _run_tool(
        tool_name="coupon_issue",
        idempotency_key=idempotency_key,
        session=session,
        operation=lambda active_session: issue_coupon(
            active_session,
            CouponIssueRequest(
                action_plan_id=action_plan_id,
                approval_id=approval_id,
                order_no=order_no,
                amount=amount,
                currency=currency,
                reason=reason,
            ),
            idempotency_key=idempotency_key,
            actor_id=MCP_ACTOR_ID,
        ),
    )


def execute_ticket_create(
    *,
    action_plan_id: str,
    order_no: str,
    category: str,
    summary: str,
    idempotency_key: str,
    session: Session | None = None,
) -> McpToolSuccess:
    return _run_tool(
        tool_name="ticket_create",
        idempotency_key=idempotency_key,
        session=session,
        operation=lambda active_session: create_ticket(
            active_session,
            TicketCreateRequest(
                action_plan_id=action_plan_id,
                order_no=order_no,
                category=category,
                summary=summary,
            ),
            idempotency_key=idempotency_key,
            actor_id=MCP_ACTOR_ID,
        ),
    )


def _run_tool(
    *,
    tool_name: ToolName,
    idempotency_key: str | None,
    session: Session | None,
    operation: Callable[[Session], ToolExecutionResponse],
) -> McpToolSuccess:
    owns_session = session is None
    active_session = session or SessionLocal()
    try:
        result = operation(active_session)
        return success_from_service_result(result)
    except ValidationError as error:
        active_session.rollback()
        raise_mcp_tool_error(
            tool_name=tool_name,
            code="validation_error",
            message="Tool input validation failed.",
            idempotency_key=idempotency_key,
            details={"reason": error.errors()[0]["type"] if error.errors() else "validation_error"},
        )
    except ToolError:
        active_session.rollback()
        raise
    except Exception as error:
        active_session.rollback()
        map_known_error(error, tool_name=tool_name, idempotency_key=idempotency_key)
        raise sanitized_unexpected_error(
            tool_name=tool_name,
            idempotency_key=idempotency_key,
        ) from error
    finally:
        if owns_session:
            active_session.close()
