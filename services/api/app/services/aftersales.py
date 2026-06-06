from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.agent.workflow import run_after_sales_preview
from app.models import ActionPlan, ApprovalRequest, AuditLog
from app.repositories.aftersales import (
    get_action_plan_by_business_dedupe_key,
    get_action_plan_by_external_id,
    get_action_plan_by_idempotency_key,
    get_approval_request_by_external_id,
    list_approval_requests,
)
from app.schemas.aftersales import (
    ActionPlanCreateResponse,
    ActionPlanResponse,
    ApprovalDecisionRequest,
    ApprovalRequestListResponse,
    ApprovalRequestResponse,
    ApprovalSummary,
)
from app.schemas.agent import AgentPreviewRequest, AgentPreviewResponse
from app.services.errors import ConflictError, NotFoundError

ACTION_STATUS_NOT_EXECUTABLE = "not_executable"
ACTION_STATUS_PLANNED = "planned"
ACTION_STATUS_PENDING_APPROVAL = "pending_approval"
ACTION_STATUS_APPROVED = "approved"
ACTION_STATUS_REJECTED = "rejected"

EXECUTION_NOT_EXECUTED = "not_executed"
EXECUTION_NOT_APPLICABLE = "not_applicable"

APPROVAL_PENDING = "pending"
APPROVAL_APPROVED = "approved"
APPROVAL_REJECTED = "rejected"

ACTION_REFUND_APPLY = "refund_apply"
ACTION_COUPON_ISSUE = "coupon_issue"
ACTION_MANUAL_REVIEW = "manual_review"
ACTION_BLOCKED = "blocked"
ACTION_REQUEST_MORE_INFO = "request_more_info"
ACTION_VERIFY_ORDER = "verify_order"
ACTION_NONE = "none"

PREVIEW_ACTION_REFUND_REVIEW = "refund_review"
PREVIEW_ACTION_DELAY_COMPENSATION_REVIEW = "delay_compensation_review"
PREVIEW_ACTION_ESCALATE_TO_HUMAN = "escalate_to_human"

SMALL_COMPENSATION_APPROVAL_THRESHOLD = Decimal("10.00")


def create_action_plan_from_preview(
    session: Session,
    request: AgentPreviewRequest,
    *,
    idempotency_key: str,
) -> ActionPlanCreateResponse:
    normalized_key = normalize_idempotency_key(idempotency_key)
    request_hash = hash_json(request.model_dump(mode="json"))
    existing_by_key = get_action_plan_by_idempotency_key(session, normalized_key)
    if existing_by_key is not None:
        if existing_by_key.request_hash == request_hash:
            return action_plan_to_create_response(existing_by_key)
        raise ConflictError(
            code="idempotency_key_reused",
            message="Idempotency-Key was already used for a different action plan request.",
            existing_identifier=existing_by_key.action_plan_id,
        )

    preview = run_after_sales_preview(session, request)
    mapped = map_preview_to_action(preview)
    policy_ids = [hit.policy_id for hit in preview.policy_evidence]
    business_dedupe_key = build_business_dedupe_key(
        preview=preview,
        action_type=mapped["action_type"],
        planned_tool_name=mapped["planned_tool_name"],
        proposed_amount=mapped["proposed_amount"],
        request_hash=request_hash,
        policy_ids=policy_ids,
    )
    existing_by_business = get_action_plan_by_business_dedupe_key(
        session,
        business_dedupe_key,
    )
    if existing_by_business is not None:
        raise ConflictError(
            code="duplicate_action_plan",
            message="An action plan for the same business request already exists.",
            existing_identifier=existing_by_business.action_plan_id,
        )

    now = datetime.now(UTC)
    action_plan = ActionPlan(
        action_plan_id=str(uuid4()),
        run_id=str(uuid4()),
        idempotency_key=normalized_key,
        business_dedupe_key=business_dedupe_key,
        order_no=preview.order_no,
        intent=preview.intent or "unknown",
        planned_tool_name=mapped["planned_tool_name"],
        action_type=mapped["action_type"],
        status=mapped["status"],
        execution_status=mapped["execution_status"],
        risk_level=preview.risk.level,
        requires_approval=mapped["requires_approval"],
        proposed_amount=mapped["proposed_amount"],
        currency=preview.recommendation.currency,
        summary=preview.recommendation.summary,
        reasons_json=list(preview.recommendation.reasons),
        next_steps_json=list(preview.recommendation.next_steps),
        fact_evidence_json=[item.model_dump(mode="json") for item in preview.fact_evidence],
        policy_evidence_json=[item.model_dump(mode="json") for item in preview.policy_evidence],
        llm_json=preview.llm.model_dump(mode="json"),
        request_message=request.message,
        request_hash=request_hash,
        created_at=now,
        updated_at=now,
    )
    session.add(action_plan)
    session.flush()

    append_audit_log(
        session,
        event_type="action_plan_created",
        actor_type="agent",
        action_plan=action_plan,
        approval_request=None,
        order_no=action_plan.order_no,
        idempotency_key=normalized_key,
        payload=audit_payload(action_plan, policy_ids),
    )
    if action_plan.status == ACTION_STATUS_NOT_EXECUTABLE:
        append_audit_log(
            session,
            event_type="action_plan_not_executable",
            actor_type="agent",
            action_plan=action_plan,
            approval_request=None,
            order_no=action_plan.order_no,
            idempotency_key=normalized_key,
            payload=audit_payload(action_plan, policy_ids),
        )

    if action_plan.status == ACTION_STATUS_PENDING_APPROVAL:
        approval = ApprovalRequest(
            approval_id=str(uuid4()),
            action_plan=action_plan,
            status=APPROVAL_PENDING,
            risk_level=action_plan.risk_level,
            requested_action_type=action_plan.action_type,
            proposed_amount=action_plan.proposed_amount,
            currency=action_plan.currency,
            policy_ids_json=policy_ids,
            requester="agent",
            requested_at=now,
            updated_at=now,
        )
        session.add(approval)
        session.flush()
        append_audit_log(
            session,
            event_type="approval_requested",
            actor_type="agent",
            action_plan=action_plan,
            approval_request=approval,
            order_no=action_plan.order_no,
            idempotency_key=normalized_key,
            payload=audit_payload(action_plan, policy_ids, approval),
        )

    session.commit()
    session.refresh(action_plan)
    return action_plan_to_create_response(action_plan)


def get_action_plan_response(session: Session, action_plan_id: str) -> ActionPlanResponse:
    action_plan = get_action_plan_by_external_id(session, action_plan_id)
    if action_plan is None:
        raise NotFoundError("action_plan", action_plan_id)
    return action_plan_to_response(action_plan)


def list_approval_request_responses(
    session: Session,
    *,
    status: str,
    limit: int,
) -> ApprovalRequestListResponse:
    if status not in {APPROVAL_PENDING, APPROVAL_APPROVED, APPROVAL_REJECTED}:
        raise ConflictError(
            code="invalid_approval_status",
            message="Approval status filter is invalid.",
        )
    if limit < 1 or limit > 100:
        raise ConflictError(
            code="invalid_limit",
            message="Approval request limit must be between 1 and 100.",
        )
    approvals = list_approval_requests(session, status=status, limit=limit)
    return ApprovalRequestListResponse(
        approvals=[approval_request_to_response(approval) for approval in approvals]
    )


def get_approval_request_response(session: Session, approval_id: str) -> ApprovalRequestResponse:
    approval = get_approval_request_by_external_id(session, approval_id)
    if approval is None:
        raise NotFoundError("approval", approval_id)
    return approval_request_to_response(approval)


def decide_approval(
    session: Session,
    approval_id: str,
    request: ApprovalDecisionRequest,
    *,
    idempotency_key: str,
) -> ApprovalRequestResponse:
    normalized_key = normalize_idempotency_key(idempotency_key)
    approval = get_approval_request_by_external_id(session, approval_id)
    if approval is None:
        raise NotFoundError("approval", approval_id)

    decision_hash = hash_json(request.model_dump(mode="json"))
    if approval.decision_idempotency_key == normalized_key:
        if approval.decision_request_hash == decision_hash:
            return approval_request_to_response(approval)
        raise ConflictError(
            code="idempotency_key_reused",
            message="Idempotency-Key was already used for a different approval decision.",
            existing_identifier=approval.approval_id,
        )

    if approval.status != APPROVAL_PENDING:
        raise ConflictError(
            code="approval_already_decided",
            message="Approval request has already been decided.",
            existing_identifier=approval.approval_id,
        )

    new_status = APPROVAL_APPROVED if request.decision == "approve" else APPROVAL_REJECTED
    approval.status = new_status
    approval.reviewer = request.reviewer
    approval.decision_comment = request.comment
    approval.decision_idempotency_key = normalized_key
    approval.decision_request_hash = decision_hash
    approval.decided_at = datetime.now(UTC)
    approval.updated_at = datetime.now(UTC)

    action_plan = approval.action_plan
    action_plan.status = (
        ACTION_STATUS_APPROVED if new_status == APPROVAL_APPROVED else ACTION_STATUS_REJECTED
    )
    action_plan.execution_status = EXECUTION_NOT_EXECUTED
    action_plan.updated_at = datetime.now(UTC)

    policy_ids = [str(policy_id) for policy_id in approval.policy_ids_json]
    append_audit_log(
        session,
        event_type="approval_approved" if new_status == APPROVAL_APPROVED else "approval_rejected",
        actor_type="reviewer",
        actor_id=request.reviewer,
        action_plan=action_plan,
        approval_request=approval,
        order_no=action_plan.order_no,
        idempotency_key=normalized_key,
        payload=audit_payload(action_plan, policy_ids, approval, request),
    )
    session.commit()
    session.refresh(approval)
    session.refresh(action_plan)
    return approval_request_to_response(approval)


def append_audit_log(
    session: Session,
    *,
    event_type: str,
    actor_type: str,
    action_plan: ActionPlan | None,
    approval_request: ApprovalRequest | None,
    order_no: str | None,
    idempotency_key: str | None,
    payload: dict,
    actor_id: str | None = None,
) -> AuditLog:
    audit_log = AuditLog(
        event_id=str(uuid4()),
        event_type=event_type,
        actor_type=actor_type,
        actor_id=actor_id,
        action_plan=action_plan,
        approval_request=approval_request,
        order_no=order_no,
        idempotency_key=idempotency_key,
        payload_json=payload,
        created_at=datetime.now(UTC),
    )
    session.add(audit_log)
    return audit_log


def map_preview_to_action(preview: AgentPreviewResponse) -> dict:
    preview_action = preview.recommendation.action_type
    proposed_amount = parse_decimal(preview.recommendation.proposed_amount)

    if preview_action == PREVIEW_ACTION_REFUND_REVIEW:
        return {
            "planned_tool_name": ACTION_REFUND_APPLY,
            "action_type": ACTION_REFUND_APPLY,
            "status": ACTION_STATUS_PENDING_APPROVAL,
            "execution_status": EXECUTION_NOT_EXECUTED,
            "requires_approval": True,
            "proposed_amount": proposed_amount,
        }

    if preview_action == PREVIEW_ACTION_DELAY_COMPENSATION_REVIEW:
        requires_approval = (
            proposed_amount is not None and proposed_amount > SMALL_COMPENSATION_APPROVAL_THRESHOLD
        )
        return {
            "planned_tool_name": ACTION_COUPON_ISSUE,
            "action_type": ACTION_COUPON_ISSUE,
            "status": ACTION_STATUS_PENDING_APPROVAL
            if requires_approval
            else ACTION_STATUS_PLANNED,
            "execution_status": EXECUTION_NOT_EXECUTED,
            "requires_approval": requires_approval,
            "proposed_amount": proposed_amount,
        }

    if preview_action == "blocked":
        action_type = ACTION_BLOCKED
    elif preview_action == "request_more_info":
        action_type = ACTION_REQUEST_MORE_INFO
    elif preview_action == "verify_order":
        action_type = ACTION_VERIFY_ORDER
    elif preview_action == PREVIEW_ACTION_ESCALATE_TO_HUMAN:
        action_type = ACTION_MANUAL_REVIEW
    else:
        action_type = ACTION_NONE

    return {
        "planned_tool_name": None,
        "action_type": action_type,
        "status": ACTION_STATUS_NOT_EXECUTABLE,
        "execution_status": EXECUTION_NOT_APPLICABLE,
        "requires_approval": False,
        "proposed_amount": proposed_amount,
    }


def build_business_dedupe_key(
    *,
    preview: AgentPreviewResponse,
    action_type: str,
    planned_tool_name: str | None,
    proposed_amount: Decimal | None,
    request_hash: str,
    policy_ids: list[str],
) -> str:
    if preview.order_no is None:
        parts = [request_hash, action_type, preview.status]
    else:
        policy_hash = hash_json(policy_ids)[:16]
        parts = [
            preview.order_no,
            preview.intent or "unknown",
            planned_tool_name or action_type,
            amount_to_string(proposed_amount) or "",
            preview.recommendation.currency or "",
            policy_hash,
        ]
    return hash_json(parts)


def audit_payload(
    action_plan: ActionPlan,
    policy_ids: list[str],
    approval: ApprovalRequest | None = None,
    decision: ApprovalDecisionRequest | None = None,
) -> dict:
    payload = {
        "action_plan_id": action_plan.action_plan_id,
        "approval_id": approval.approval_id if approval is not None else None,
        "order_no": action_plan.order_no,
        "action_type": action_plan.action_type,
        "status": action_plan.status,
        "execution_status": action_plan.execution_status,
        "risk_level": action_plan.risk_level,
        "requires_approval": action_plan.requires_approval,
        "proposed_amount": amount_to_string(action_plan.proposed_amount),
        "currency": action_plan.currency,
        "policy_ids": policy_ids,
        "idempotency_key": action_plan.idempotency_key,
        "request_hash": action_plan.request_hash,
    }
    if decision is not None:
        payload["decision"] = decision.decision
        payload["reviewer"] = decision.reviewer
        payload["decision_comment"] = decision.comment
    return payload


def action_plan_to_create_response(action_plan: ActionPlan) -> ActionPlanCreateResponse:
    approval = action_plan.approval_request
    return ActionPlanCreateResponse(
        action_plan_id=action_plan.action_plan_id,
        run_id=action_plan.run_id,
        order_no=action_plan.order_no,
        intent=action_plan.intent,
        planned_tool_name=action_plan.planned_tool_name,
        action_type=action_plan.action_type,
        status=action_plan.status,
        execution_status=action_plan.execution_status,
        risk_level=action_plan.risk_level,
        requires_approval=action_plan.requires_approval,
        approval_id=approval.approval_id if approval is not None else None,
        proposed_amount=amount_to_string(action_plan.proposed_amount),
        currency=action_plan.currency,
        summary=action_plan.summary,
        created_at=action_plan.created_at,
    )


def action_plan_to_response(action_plan: ActionPlan) -> ActionPlanResponse:
    return ActionPlanResponse(
        action_plan_id=action_plan.action_plan_id,
        run_id=action_plan.run_id,
        order_no=action_plan.order_no,
        intent=action_plan.intent,
        planned_tool_name=action_plan.planned_tool_name,
        action_type=action_plan.action_type,
        status=action_plan.status,
        execution_status=action_plan.execution_status,
        risk_level=action_plan.risk_level,
        requires_approval=action_plan.requires_approval,
        proposed_amount=amount_to_string(action_plan.proposed_amount),
        currency=action_plan.currency,
        summary=action_plan.summary,
        reasons=list(action_plan.reasons_json),
        next_steps=list(action_plan.next_steps_json),
        fact_evidence=list(action_plan.fact_evidence_json),
        policy_evidence=list(action_plan.policy_evidence_json),
        llm=dict(action_plan.llm_json),
        approval=approval_to_summary(action_plan.approval_request),
        created_at=action_plan.created_at,
        updated_at=action_plan.updated_at,
    )


def approval_request_to_response(approval: ApprovalRequest) -> ApprovalRequestResponse:
    return ApprovalRequestResponse(
        approval_id=approval.approval_id,
        action_plan_id=approval.action_plan.action_plan_id,
        status=approval.status,
        risk_level=approval.risk_level,
        requested_action_type=approval.requested_action_type,
        proposed_amount=amount_to_string(approval.proposed_amount),
        currency=approval.currency,
        policy_ids=[str(policy_id) for policy_id in approval.policy_ids_json],
        requester=approval.requester,
        reviewer=approval.reviewer,
        decision_comment=approval.decision_comment,
        requested_at=approval.requested_at,
        decided_at=approval.decided_at,
        updated_at=approval.updated_at,
        action_plan=action_plan_to_create_response(approval.action_plan),
    )


def approval_to_summary(approval: ApprovalRequest | None) -> ApprovalSummary | None:
    if approval is None:
        return None
    return ApprovalSummary(
        approval_id=approval.approval_id,
        status=approval.status,
        risk_level=approval.risk_level,
        requested_action_type=approval.requested_action_type,
        proposed_amount=amount_to_string(approval.proposed_amount),
        currency=approval.currency,
        requested_at=approval.requested_at,
        decided_at=approval.decided_at,
    )


def normalize_idempotency_key(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ConflictError(
            code="missing_idempotency_key",
            message="Idempotency-Key must not be empty.",
        )
    return stripped


def hash_json(value) -> str:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def parse_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(value)


def amount_to_string(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return f"{value:.2f}"
