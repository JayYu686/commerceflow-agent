from typing import Literal

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.agent.mcp_client import StdioMCPToolClient
from app.agent.workflow import execute_action_plan_workflow, resume_after_approval
from app.db.session import get_session
from app.repositories.aftersales import get_approval_request_by_external_id
from app.schemas.aftersales import (
    ActionPlanExecuteRequest,
    ActionPlanExecuteResponse,
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


def get_mcp_tool_client() -> StdioMCPToolClient:
    return StdioMCPToolClient()


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
    existing = get_approval_request_by_external_id(session, approval_id)
    should_resume = existing is not None and existing.status == "pending"
    response = decide_approval(
        session,
        approval_id,
        request,
        idempotency_key=idempotency_key,
    )
    if should_resume:
        resume_after_approval(session, response.action_plan_id)
    return response


@router.post(
    "/action-plans/{action_plan_id}/execute",
    response_model=ActionPlanExecuteResponse,
)
def execute_action_plan(
    action_plan_id: str,
    _request: ActionPlanExecuteRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    session: Session = Depends(get_session),
    mcp_client: StdioMCPToolClient = Depends(get_mcp_tool_client),
) -> ActionPlanExecuteResponse:
    return execute_action_plan_workflow(
        session,
        action_plan_id,
        idempotency_key=idempotency_key,
        mcp_client=mcp_client,
    )
