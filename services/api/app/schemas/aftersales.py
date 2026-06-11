from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

DecisionValue = Literal["approve", "reject"]
ExecutionStatus = Literal["not_executed", "not_applicable", "executed", "execution_failed"]
ActionPlanStatus = Literal["not_executable", "planned", "pending_approval", "approved", "rejected"]
ActionPlanResultType = Literal["refund", "coupon", "ticket"]


class ApprovalSummary(BaseModel):
    approval_id: str
    status: str
    risk_level: str
    requested_action_type: str
    proposed_amount: str | None
    currency: str | None
    requested_at: datetime
    decided_at: datetime | None


class ActionPlanResponse(BaseModel):
    action_plan_id: str
    run_id: str
    request_message: str
    order_no: str | None
    intent: str
    planned_tool_name: str | None
    action_type: str
    status: str
    execution_status: ExecutionStatus
    risk_level: str
    requires_approval: bool
    proposed_amount: str | None
    currency: str | None
    summary: str
    reasons: list[str]
    next_steps: list[str]
    fact_evidence: list[dict]
    policy_evidence: list[dict]
    llm: dict
    approval: ApprovalSummary | None
    created_at: datetime
    updated_at: datetime


class ActionPlanCreateResponse(BaseModel):
    action_plan_id: str
    run_id: str
    order_no: str | None
    intent: str
    planned_tool_name: str | None
    action_type: str
    status: str
    execution_status: ExecutionStatus
    risk_level: str
    requires_approval: bool
    approval_id: str | None
    proposed_amount: str | None
    currency: str | None
    summary: str
    created_at: datetime


class ActionPlanListItem(BaseModel):
    action_plan_id: str
    order_no: str | None
    intent: str
    planned_tool_name: str | None
    action_type: str
    status: str
    execution_status: ExecutionStatus
    risk_level: str
    requires_approval: bool
    approval_id: str | None
    proposed_amount: str | None
    currency: str | None
    summary: str
    created_at: datetime
    updated_at: datetime


class ActionPlanListResponse(BaseModel):
    action_plans: list[ActionPlanListItem]


class AuditLogResponse(BaseModel):
    event_id: str
    event_type: str
    actor_type: str
    actor_id: str | None
    action_plan_id: str | None
    approval_id: str | None
    order_no: str | None
    idempotency_key: str | None
    payload: dict
    created_at: datetime


class AuditLogListResponse(BaseModel):
    events: list[AuditLogResponse]


class ActionPlanResultResponse(BaseModel):
    action_plan_id: str
    result_type: ActionPlanResultType | None
    result: dict | None


class ApprovalRequestResponse(BaseModel):
    approval_id: str
    action_plan_id: str
    status: str
    risk_level: str
    requested_action_type: str
    proposed_amount: str | None
    currency: str | None
    policy_ids: list[str]
    requester: str
    reviewer: str | None
    decision_comment: str | None
    requested_at: datetime
    decided_at: datetime | None
    updated_at: datetime
    action_plan: ActionPlanCreateResponse


class ApprovalRequestListResponse(BaseModel):
    approvals: list[ApprovalRequestResponse]


class ApprovalDecisionRequest(BaseModel):
    decision: DecisionValue
    reviewer: str = Field(min_length=1, max_length=120)
    comment: str | None = Field(default=None, max_length=1000)

    @field_validator("reviewer", "comment")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be empty")
        return stripped
