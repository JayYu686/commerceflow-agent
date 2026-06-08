from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.schemas.tools import (
    CouponIssueRequest,
    CouponRecordResponse,
    RefundApplyRequest,
    RefundRecordResponse,
    TicketCreateRequest,
    TicketRecordResponse,
    ToolExecutionResponse,
)
from app.services.tools import (
    apply_refund,
    create_ticket,
    get_coupon_response,
    get_refund_response,
    get_ticket_response,
    issue_coupon,
)

router = APIRouter(prefix="/api", tags=["tools"])


@router.post("/tools/refund-apply", response_model=ToolExecutionResponse)
def refund_apply(
    request: RefundApplyRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    session: Session = Depends(get_session),
) -> ToolExecutionResponse:
    return apply_refund(session, request, idempotency_key=idempotency_key)


@router.post("/tools/coupon-issue", response_model=ToolExecutionResponse)
def coupon_issue(
    request: CouponIssueRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    session: Session = Depends(get_session),
) -> ToolExecutionResponse:
    return issue_coupon(session, request, idempotency_key=idempotency_key)


@router.post("/tools/ticket-create", response_model=ToolExecutionResponse)
def ticket_create(
    request: TicketCreateRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    session: Session = Depends(get_session),
) -> ToolExecutionResponse:
    return create_ticket(session, request, idempotency_key=idempotency_key)


@router.get("/refunds/{refund_id}", response_model=RefundRecordResponse)
def read_refund(
    refund_id: str,
    session: Session = Depends(get_session),
) -> RefundRecordResponse:
    return get_refund_response(session, refund_id)


@router.get("/coupons/{coupon_id}", response_model=CouponRecordResponse)
def read_coupon(
    coupon_id: str,
    session: Session = Depends(get_session),
) -> CouponRecordResponse:
    return get_coupon_response(session, coupon_id)


@router.get("/tickets/{ticket_id}", response_model=TicketRecordResponse)
def read_ticket(
    ticket_id: str,
    session: Session = Depends(get_session),
) -> TicketRecordResponse:
    return get_ticket_response(session, ticket_id)
