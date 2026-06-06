from typing import Literal

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.schemas.aftersales import (
    ActionPlanResponse,
    ApprovalDecisionRequest,
    ApprovalRequestListResponse,
    ApprovalRequestResponse,
)
from app.services.aftersales import (
    decide_approval,
    get_action_plan_response,
    get_approval_request_response,
    list_approval_request_responses,
)

router = APIRouter(prefix="/api", tags=["approvals"])


@router.get("/action-plans/{action_plan_id}", response_model=ActionPlanResponse)
def read_action_plan(
    action_plan_id: str,
    session: Session = Depends(get_session),
) -> ActionPlanResponse:
    return get_action_plan_response(session, action_plan_id)


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
