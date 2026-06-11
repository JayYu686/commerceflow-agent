from typing import Literal

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.schemas.aftersales import (
    ActionPlanListResponse,
    ActionPlanResponse,
    ActionPlanResultResponse,
    ApprovalDecisionRequest,
    ApprovalRequestListResponse,
    ApprovalRequestResponse,
    AuditLogListResponse,
)
from app.services.aftersales import (
    decide_approval,
    get_action_plan_response,
    get_action_plan_result_response,
    get_approval_request_response,
    list_action_plan_audit_log_responses,
    list_action_plan_responses,
    list_approval_request_responses,
)

router = APIRouter(prefix="/api", tags=["approvals"])


@router.get("/action-plans", response_model=ActionPlanListResponse)
def list_action_plan_requests(
    status: Literal["not_executable", "planned", "pending_approval", "approved", "rejected"]
    | None = None,
    execution_status: Literal[
        "not_executed",
        "not_applicable",
        "executed",
        "execution_failed",
    ]
    | None = None,
    order_no: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=50, ge=1, le=100),
    session: Session = Depends(get_session),
) -> ActionPlanListResponse:
    return list_action_plan_responses(
        session,
        status=status,
        execution_status=execution_status,
        order_no=order_no,
        limit=limit,
    )


@router.get("/action-plans/{action_plan_id}", response_model=ActionPlanResponse)
def read_action_plan(
    action_plan_id: str,
    session: Session = Depends(get_session),
) -> ActionPlanResponse:
    return get_action_plan_response(session, action_plan_id)


@router.get("/action-plans/{action_plan_id}/audit-logs", response_model=AuditLogListResponse)
def list_action_plan_audit_logs(
    action_plan_id: str,
    session: Session = Depends(get_session),
) -> AuditLogListResponse:
    return list_action_plan_audit_log_responses(session, action_plan_id)


@router.get("/action-plans/{action_plan_id}/result", response_model=ActionPlanResultResponse)
def read_action_plan_result(
    action_plan_id: str,
    session: Session = Depends(get_session),
) -> ActionPlanResultResponse:
    return get_action_plan_result_response(session, action_plan_id)


@router.get("/approvals", response_model=ApprovalRequestListResponse)
def list_approvals(
    status: Literal["pending", "approved", "rejected"] = "pending",
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> ApprovalRequestListResponse:
    return list_approval_request_responses(session, status=status, limit=limit)


@router.get("/approvals/{approval_id}", response_model=ApprovalRequestResponse)
def read_approval_request(
    approval_id: str,
    session: Session = Depends(get_session),
) -> ApprovalRequestResponse:
    return get_approval_request_response(session, approval_id)


@router.post("/approvals/{approval_id}/decision", response_model=ApprovalRequestResponse)
def decide_approval_request(
    approval_id: str,
    request: ApprovalDecisionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    session: Session = Depends(get_session),
) -> ApprovalRequestResponse:
    return decide_approval(
        session,
        approval_id,
        request,
        idempotency_key=idempotency_key,
    )
