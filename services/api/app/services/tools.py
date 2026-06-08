from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import ActionPlan, ApprovalRequest, CouponRecord, RefundRecord, TicketRecord
from app.repositories.aftersales import get_action_plan_by_external_id
from app.repositories.tools import (
    get_coupon_by_action_plan_id,
    get_coupon_by_external_id,
    get_coupon_by_idempotency_key,
    get_refund_by_action_plan_id,
    get_refund_by_external_id,
    get_refund_by_idempotency_key,
    get_ticket_by_action_plan_id,
    get_ticket_by_external_id,
    get_ticket_by_idempotency_key,
)
from app.schemas.tools import (
    CouponIssueRequest,
    CouponRecordResponse,
    RefundApplyRequest,
    RefundRecordResponse,
    TicketCreateRequest,
    TicketRecordResponse,
    ToolExecutionResponse,
)
from app.services.aftersales import (
    ACTION_STATUS_APPROVED,
    ACTION_STATUS_PLANNED,
    APPROVAL_APPROVED,
    EXECUTION_NOT_EXECUTED,
    amount_to_string,
    append_audit_log,
    hash_json,
    normalize_idempotency_key,
)
from app.services.errors import ConflictError, NotFoundError

ACTION_TICKET_CREATE = "ticket_create"
EXECUTION_EXECUTED = "executed"
TOOL_REFUND_APPLY = "refund_apply"
TOOL_COUPON_ISSUE = "coupon_issue"
TOOL_TICKET_CREATE = "ticket_create"
REFUND_STATUS_SUCCEEDED = "succeeded"
COUPON_STATUS_ISSUED = "issued"
TICKET_STATUS_CREATED = "created"
COUPON_APPROVAL_THRESHOLD = Decimal("10.00")


def apply_refund(
    session: Session,
    request: RefundApplyRequest,
    *,
    idempotency_key: str,
    actor_id: str = "demo_tool_api",
) -> ToolExecutionResponse:
    normalized_key = normalize_idempotency_key(idempotency_key)
    request_hash = hash_json(request.model_dump(mode="json"))
    existing = get_refund_by_idempotency_key(session, normalized_key)
    if existing is not None:
        return handle_refund_replay_or_conflict(
            session,
            existing,
            request_hash,
            normalized_key,
            actor_id,
        )

    action_plan = get_action_plan_or_log_blocked(
        session,
        TOOL_REFUND_APPLY,
        request.action_plan_id,
        request.order_no,
        normalized_key,
        request_hash,
        actor_id,
    )
    existing_for_plan = get_refund_by_action_plan_id(session, action_plan.id)
    if existing_for_plan is not None:
        log_blocked_and_raise(
            session,
            tool_name=TOOL_REFUND_APPLY,
            action_plan=action_plan,
            approval_request=existing_for_plan.approval_request,
            order_no=request.order_no,
            amount=request.amount,
            currency=request.currency,
            idempotency_key=normalized_key,
            request_hash=request_hash,
            blocked_reason="duplicate_execution",
            existing_identifier=existing_for_plan.refund_id,
            actor_id=actor_id,
        )

    approval = action_plan.approval_request
    if approval is None or approval.approval_id != request.approval_id:
        log_blocked_and_raise(
            session,
            tool_name=TOOL_REFUND_APPLY,
            action_plan=action_plan,
            approval_request=approval,
            order_no=request.order_no,
            amount=request.amount,
            currency=request.currency,
            idempotency_key=normalized_key,
            request_hash=request_hash,
            blocked_reason="approval_mismatch",
            actor_id=actor_id,
        )
    validate_refund_action(action_plan, approval, request, normalized_key, request_hash, actor_id)

    now = datetime.now(UTC)
    record = RefundRecord(
        refund_id=str(uuid4()),
        action_plan=action_plan,
        approval_request=approval,
        order_no=request.order_no,
        amount=money(request.amount),
        currency=request.currency,
        reason=request.reason,
        status=REFUND_STATUS_SUCCEEDED,
        idempotency_key=normalized_key,
        request_hash=request_hash,
        tool_name=TOOL_REFUND_APPLY,
        created_at=now,
    )
    session.add(record)
    mark_action_plan_executed(action_plan, now)
    session.flush()
    append_tool_audit(
        session,
        event_type="tool_execution_succeeded",
        tool_name=TOOL_REFUND_APPLY,
        action_plan=action_plan,
        approval_request=approval,
        record_id=record.refund_id,
        order_no=request.order_no,
        amount=request.amount,
        currency=request.currency,
        idempotency_key=normalized_key,
        request_hash=request_hash,
        result_status=record.status,
        blocked_reason=None,
        actor_id=actor_id,
    )
    session.commit()
    session.refresh(record)
    session.refresh(action_plan)
    return refund_to_execution_response(record, idempotent_replay=False)


def issue_coupon(
    session: Session,
    request: CouponIssueRequest,
    *,
    idempotency_key: str,
    actor_id: str = "demo_tool_api",
) -> ToolExecutionResponse:
    normalized_key = normalize_idempotency_key(idempotency_key)
    request_hash = hash_json(request.model_dump(mode="json"))
    existing = get_coupon_by_idempotency_key(session, normalized_key)
    if existing is not None:
        return handle_coupon_replay_or_conflict(
            session,
            existing,
            request_hash,
            normalized_key,
            actor_id,
        )

    action_plan = get_action_plan_or_log_blocked(
        session,
        TOOL_COUPON_ISSUE,
        request.action_plan_id,
        request.order_no,
        normalized_key,
        request_hash,
        actor_id,
    )
    existing_for_plan = get_coupon_by_action_plan_id(session, action_plan.id)
    if existing_for_plan is not None:
        log_blocked_and_raise(
            session,
            tool_name=TOOL_COUPON_ISSUE,
            action_plan=action_plan,
            approval_request=existing_for_plan.approval_request,
            order_no=request.order_no,
            amount=request.amount,
            currency=request.currency,
            idempotency_key=normalized_key,
            request_hash=request_hash,
            blocked_reason="duplicate_execution",
            existing_identifier=existing_for_plan.coupon_id,
            actor_id=actor_id,
        )

    approval = action_plan.approval_request
    validate_coupon_action(action_plan, approval, request, normalized_key, request_hash, actor_id)

    now = datetime.now(UTC)
    approved_coupon_approval = (
        approval if approval is not None and approval.status == APPROVAL_APPROVED else None
    )
    record = CouponRecord(
        coupon_id=str(uuid4()),
        action_plan=action_plan,
        approval_request=approved_coupon_approval,
        order_no=request.order_no,
        amount=money(request.amount),
        currency=request.currency,
        reason=request.reason,
        status=COUPON_STATUS_ISSUED,
        idempotency_key=normalized_key,
        request_hash=request_hash,
        tool_name=TOOL_COUPON_ISSUE,
        created_at=now,
    )
    session.add(record)
    mark_action_plan_executed(action_plan, now)
    session.flush()
    append_tool_audit(
        session,
        event_type="tool_execution_succeeded",
        tool_name=TOOL_COUPON_ISSUE,
        action_plan=action_plan,
        approval_request=record.approval_request,
        record_id=record.coupon_id,
        order_no=request.order_no,
        amount=request.amount,
        currency=request.currency,
        idempotency_key=normalized_key,
        request_hash=request_hash,
        result_status=record.status,
        blocked_reason=None,
        actor_id=actor_id,
    )
    session.commit()
    session.refresh(record)
    session.refresh(action_plan)
    return coupon_to_execution_response(record, idempotent_replay=False)


def create_ticket(
    session: Session,
    request: TicketCreateRequest,
    *,
    idempotency_key: str,
    actor_id: str = "demo_tool_api",
) -> ToolExecutionResponse:
    normalized_key = normalize_idempotency_key(idempotency_key)
    request_hash = hash_json(request.model_dump(mode="json"))
    existing = get_ticket_by_idempotency_key(session, normalized_key)
    if existing is not None:
        return handle_ticket_replay_or_conflict(
            session,
            existing,
            request_hash,
            normalized_key,
            actor_id,
        )

    action_plan = get_action_plan_or_log_blocked(
        session,
        TOOL_TICKET_CREATE,
        request.action_plan_id,
        request.order_no,
        normalized_key,
        request_hash,
        actor_id,
    )
    existing_for_plan = get_ticket_by_action_plan_id(session, action_plan.id)
    if existing_for_plan is not None:
        log_blocked_and_raise(
            session,
            tool_name=TOOL_TICKET_CREATE,
            action_plan=action_plan,
            approval_request=None,
            order_no=request.order_no,
            amount=None,
            currency=None,
            idempotency_key=normalized_key,
            request_hash=request_hash,
            blocked_reason="duplicate_execution",
            existing_identifier=existing_for_plan.ticket_id,
            actor_id=actor_id,
        )

    validate_ticket_action(action_plan, request, normalized_key, request_hash, actor_id)

    now = datetime.now(UTC)
    record = TicketRecord(
        ticket_id=str(uuid4()),
        action_plan=action_plan,
        order_no=request.order_no,
        category=request.category,
        summary=request.summary,
        status=TICKET_STATUS_CREATED,
        idempotency_key=normalized_key,
        request_hash=request_hash,
        tool_name=TOOL_TICKET_CREATE,
        created_at=now,
    )
    session.add(record)
    mark_action_plan_executed(action_plan, now)
    session.flush()
    append_tool_audit(
        session,
        event_type="tool_execution_succeeded",
        tool_name=TOOL_TICKET_CREATE,
        action_plan=action_plan,
        approval_request=None,
        record_id=record.ticket_id,
        order_no=request.order_no,
        amount=None,
        currency=None,
        idempotency_key=normalized_key,
        request_hash=request_hash,
        result_status=record.status,
        blocked_reason=None,
        actor_id=actor_id,
    )
    session.commit()
    session.refresh(record)
    session.refresh(action_plan)
    return ticket_to_execution_response(record, idempotent_replay=False)


def get_refund_response(session: Session, refund_id: str) -> RefundRecordResponse:
    record = get_refund_by_external_id(session, refund_id)
    if record is None:
        raise NotFoundError("refund", refund_id)
    return refund_to_response(record)


def get_coupon_response(session: Session, coupon_id: str) -> CouponRecordResponse:
    record = get_coupon_by_external_id(session, coupon_id)
    if record is None:
        raise NotFoundError("coupon", coupon_id)
    return coupon_to_response(record)


def get_ticket_response(session: Session, ticket_id: str) -> TicketRecordResponse:
    record = get_ticket_by_external_id(session, ticket_id)
    if record is None:
        raise NotFoundError("ticket", ticket_id)
    return ticket_to_response(record)


def handle_refund_replay_or_conflict(
    session: Session,
    record: RefundRecord,
    request_hash: str,
    idempotency_key: str,
    actor_id: str,
) -> ToolExecutionResponse:
    if record.request_hash != request_hash:
        log_blocked_and_raise(
            session,
            tool_name=TOOL_REFUND_APPLY,
            action_plan=record.action_plan,
            approval_request=record.approval_request,
            order_no=record.order_no,
            amount=record.amount,
            currency=record.currency,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            blocked_reason="idempotency_key_reused",
            existing_identifier=record.refund_id,
            actor_id=actor_id,
        )
    log_replay(session, TOOL_REFUND_APPLY, record, record.refund_id, actor_id)
    return refund_to_execution_response(record, idempotent_replay=True)


def handle_coupon_replay_or_conflict(
    session: Session,
    record: CouponRecord,
    request_hash: str,
    idempotency_key: str,
    actor_id: str,
) -> ToolExecutionResponse:
    if record.request_hash != request_hash:
        log_blocked_and_raise(
            session,
            tool_name=TOOL_COUPON_ISSUE,
            action_plan=record.action_plan,
            approval_request=record.approval_request,
            order_no=record.order_no,
            amount=record.amount,
            currency=record.currency,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            blocked_reason="idempotency_key_reused",
            existing_identifier=record.coupon_id,
            actor_id=actor_id,
        )
    log_replay(session, TOOL_COUPON_ISSUE, record, record.coupon_id, actor_id)
    return coupon_to_execution_response(record, idempotent_replay=True)


def handle_ticket_replay_or_conflict(
    session: Session,
    record: TicketRecord,
    request_hash: str,
    idempotency_key: str,
    actor_id: str,
) -> ToolExecutionResponse:
    if record.request_hash != request_hash:
        log_blocked_and_raise(
            session,
            tool_name=TOOL_TICKET_CREATE,
            action_plan=record.action_plan,
            approval_request=None,
            order_no=record.order_no,
            amount=None,
            currency=None,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            blocked_reason="idempotency_key_reused",
            existing_identifier=record.ticket_id,
            actor_id=actor_id,
        )
    log_replay(session, TOOL_TICKET_CREATE, record, record.ticket_id, actor_id)
    return ticket_to_execution_response(record, idempotent_replay=True)


def get_action_plan_or_log_blocked(
    session: Session,
    tool_name: str,
    action_plan_id: str,
    order_no: str,
    idempotency_key: str,
    request_hash: str,
    actor_id: str,
) -> ActionPlan:
    action_plan = get_action_plan_by_external_id(session, action_plan_id)
    if action_plan is None:
        append_tool_audit(
            session,
            event_type="tool_execution_blocked",
            tool_name=tool_name,
            action_plan=None,
            approval_request=None,
            record_id=None,
            order_no=order_no,
            amount=None,
            currency=None,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            result_status=None,
            blocked_reason="action_plan_not_found",
            actor_id=actor_id,
        )
        session.commit()
        raise NotFoundError("action_plan", action_plan_id)
    return action_plan


def validate_refund_action(
    action_plan: ActionPlan,
    approval: ApprovalRequest,
    request: RefundApplyRequest,
    idempotency_key: str,
    request_hash: str,
    actor_id: str,
) -> None:
    validate_common_action(
        action_plan,
        tool_name=TOOL_REFUND_APPLY,
        request_order_no=request.order_no,
        request_amount=request.amount,
        request_currency=request.currency,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        actor_id=actor_id,
        approval_request=approval,
        require_policy_evidence=True,
    )
    if action_plan.status != ACTION_STATUS_APPROVED:
        log_blocked_and_raise(
            session_from(action_plan),
            tool_name=TOOL_REFUND_APPLY,
            action_plan=action_plan,
            approval_request=approval,
            order_no=request.order_no,
            amount=request.amount,
            currency=request.currency,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            blocked_reason="approval_required",
            actor_id=actor_id,
        )
    if approval.status != APPROVAL_APPROVED:
        log_blocked_and_raise(
            session_from(action_plan),
            tool_name=TOOL_REFUND_APPLY,
            action_plan=action_plan,
            approval_request=approval,
            order_no=request.order_no,
            amount=request.amount,
            currency=request.currency,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            blocked_reason="approval_not_approved",
            actor_id=actor_id,
        )


def validate_coupon_action(
    action_plan: ActionPlan,
    approval: ApprovalRequest | None,
    request: CouponIssueRequest,
    idempotency_key: str,
    request_hash: str,
    actor_id: str,
) -> None:
    validate_common_action(
        action_plan,
        tool_name=TOOL_COUPON_ISSUE,
        request_order_no=request.order_no,
        request_amount=request.amount,
        request_currency=request.currency,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        actor_id=actor_id,
        approval_request=approval,
        require_policy_evidence=True,
    )
    if money(request.amount) > COUPON_APPROVAL_THRESHOLD:
        if approval is None or request.approval_id is None:
            log_blocked_and_raise(
                session_from(action_plan),
                tool_name=TOOL_COUPON_ISSUE,
                action_plan=action_plan,
                approval_request=approval,
                order_no=request.order_no,
                amount=request.amount,
                currency=request.currency,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                blocked_reason="approval_required",
                actor_id=actor_id,
            )
        if approval.approval_id != request.approval_id or approval.status != APPROVAL_APPROVED:
            log_blocked_and_raise(
                session_from(action_plan),
                tool_name=TOOL_COUPON_ISSUE,
                action_plan=action_plan,
                approval_request=approval,
                order_no=request.order_no,
                amount=request.amount,
                currency=request.currency,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                blocked_reason="approval_not_approved",
                actor_id=actor_id,
            )
        if action_plan.status != ACTION_STATUS_APPROVED:
            log_blocked_and_raise(
                session_from(action_plan),
                tool_name=TOOL_COUPON_ISSUE,
                action_plan=action_plan,
                approval_request=approval,
                order_no=request.order_no,
                amount=request.amount,
                currency=request.currency,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                blocked_reason="approval_required",
                actor_id=actor_id,
            )
    elif action_plan.status != ACTION_STATUS_PLANNED:
        log_blocked_and_raise(
            session_from(action_plan),
            tool_name=TOOL_COUPON_ISSUE,
            action_plan=action_plan,
            approval_request=approval,
            order_no=request.order_no,
            amount=request.amount,
            currency=request.currency,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            blocked_reason="action_plan_not_planned",
            actor_id=actor_id,
        )


def validate_ticket_action(
    action_plan: ActionPlan,
    request: TicketCreateRequest,
    idempotency_key: str,
    request_hash: str,
    actor_id: str,
) -> None:
    validate_common_action(
        action_plan,
        tool_name=TOOL_TICKET_CREATE,
        request_order_no=request.order_no,
        request_amount=None,
        request_currency=None,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        actor_id=actor_id,
        approval_request=action_plan.approval_request,
        require_policy_evidence=False,
    )
    if action_plan.status not in {ACTION_STATUS_PLANNED, ACTION_STATUS_APPROVED}:
        log_blocked_and_raise(
            session_from(action_plan),
            tool_name=TOOL_TICKET_CREATE,
            action_plan=action_plan,
            approval_request=action_plan.approval_request,
            order_no=request.order_no,
            amount=None,
            currency=None,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            blocked_reason="action_plan_not_executable",
            actor_id=actor_id,
        )


def validate_common_action(
    action_plan: ActionPlan,
    *,
    tool_name: str,
    request_order_no: str,
    request_amount: Decimal | None,
    request_currency: str | None,
    idempotency_key: str,
    request_hash: str,
    actor_id: str,
    approval_request: ApprovalRequest | None,
    require_policy_evidence: bool,
) -> None:
    if action_plan.planned_tool_name != tool_name:
        log_blocked_and_raise(
            session_from(action_plan),
            tool_name=tool_name,
            action_plan=action_plan,
            approval_request=approval_request,
            order_no=request_order_no,
            amount=request_amount,
            currency=request_currency,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            blocked_reason="tool_action_mismatch",
            actor_id=actor_id,
        )
    if action_plan.execution_status != EXECUTION_NOT_EXECUTED:
        log_blocked_and_raise(
            session_from(action_plan),
            tool_name=tool_name,
            action_plan=action_plan,
            approval_request=approval_request,
            order_no=request_order_no,
            amount=request_amount,
            currency=request_currency,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            blocked_reason="action_plan_already_executed",
            actor_id=actor_id,
        )
    if action_plan.order_no != request_order_no:
        log_blocked_and_raise(
            session_from(action_plan),
            tool_name=tool_name,
            action_plan=action_plan,
            approval_request=approval_request,
            order_no=request_order_no,
            amount=request_amount,
            currency=request_currency,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            blocked_reason="order_mismatch",
            actor_id=actor_id,
        )
    if request_amount is not None and money(action_plan.proposed_amount) != money(request_amount):
        log_blocked_and_raise(
            session_from(action_plan),
            tool_name=tool_name,
            action_plan=action_plan,
            approval_request=approval_request,
            order_no=request_order_no,
            amount=request_amount,
            currency=request_currency,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            blocked_reason="amount_mismatch",
            actor_id=actor_id,
        )
    if request_currency is not None and action_plan.currency != request_currency:
        log_blocked_and_raise(
            session_from(action_plan),
            tool_name=tool_name,
            action_plan=action_plan,
            approval_request=approval_request,
            order_no=request_order_no,
            amount=request_amount,
            currency=request_currency,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            blocked_reason="currency_mismatch",
            actor_id=actor_id,
        )
    if require_policy_evidence and not action_plan.policy_evidence_json:
        log_blocked_and_raise(
            session_from(action_plan),
            tool_name=tool_name,
            action_plan=action_plan,
            approval_request=approval_request,
            order_no=request_order_no,
            amount=request_amount,
            currency=request_currency,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            blocked_reason="missing_policy_evidence",
            actor_id=actor_id,
        )


def log_blocked_and_raise(
    session: Session,
    *,
    tool_name: str,
    action_plan: ActionPlan,
    approval_request: ApprovalRequest | None,
    order_no: str | None,
    amount: Decimal | None,
    currency: str | None,
    idempotency_key: str,
    request_hash: str,
    blocked_reason: str,
    actor_id: str,
    existing_identifier: str | None = None,
) -> None:
    append_tool_audit(
        session,
        event_type="tool_execution_blocked",
        tool_name=tool_name,
        action_plan=action_plan,
        approval_request=approval_request,
        record_id=None,
        order_no=order_no,
        amount=amount,
        currency=currency,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        result_status=None,
        blocked_reason=blocked_reason,
        actor_id=actor_id,
    )
    session.commit()
    raise ConflictError(
        code=blocked_reason,
        message=f"{tool_name} blocked: {blocked_reason}.",
        existing_identifier=existing_identifier or action_plan.action_plan_id,
    )


def log_replay(
    session: Session,
    tool_name: str,
    record: RefundRecord | CouponRecord | TicketRecord,
    record_id: str,
    actor_id: str,
) -> None:
    approval_request = getattr(record, "approval_request", None)
    append_tool_audit(
        session,
        event_type="tool_execution_idempotent_replay",
        tool_name=tool_name,
        action_plan=record.action_plan,
        approval_request=approval_request,
        record_id=record_id,
        order_no=record.order_no,
        amount=getattr(record, "amount", None),
        currency=getattr(record, "currency", None),
        idempotency_key=record.idempotency_key,
        request_hash=record.request_hash,
        result_status=record.status,
        blocked_reason=None,
        actor_id=actor_id,
    )
    session.commit()


def append_tool_audit(
    session: Session,
    *,
    event_type: str,
    tool_name: str,
    action_plan: ActionPlan | None,
    approval_request: ApprovalRequest | None,
    record_id: str | None,
    order_no: str | None,
    amount: Decimal | None,
    currency: str | None,
    idempotency_key: str,
    request_hash: str,
    result_status: str | None,
    blocked_reason: str | None,
    actor_id: str,
) -> None:
    payload = {
        "tool_name": tool_name,
        "action_plan_id": action_plan.action_plan_id if action_plan is not None else None,
        "approval_id": approval_request.approval_id if approval_request is not None else None,
        "record_id": record_id,
        "order_no": order_no,
        "amount": amount_to_string(amount),
        "currency": currency,
        "idempotency_key": idempotency_key,
        "request_hash": request_hash,
        "result_status": result_status,
        "blocked_reason": blocked_reason,
    }
    append_audit_log(
        session,
        event_type=event_type,
        actor_type="system",
        actor_id=actor_id,
        action_plan=action_plan,
        approval_request=approval_request,
        order_no=order_no,
        idempotency_key=idempotency_key,
        payload=payload,
    )


def mark_action_plan_executed(action_plan: ActionPlan, now: datetime) -> None:
    action_plan.execution_status = EXECUTION_EXECUTED
    action_plan.updated_at = now


def money(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(value).quantize(Decimal("0.01"))


def session_from(action_plan: ActionPlan) -> Session:
    session = Session.object_session(action_plan)
    if session is None:
        raise RuntimeError("action plan is not attached to a session")
    return session


def refund_to_execution_response(
    record: RefundRecord,
    *,
    idempotent_replay: bool,
) -> ToolExecutionResponse:
    return ToolExecutionResponse(
        tool_name=TOOL_REFUND_APPLY,
        status=record.status,
        record_id=record.refund_id,
        action_plan_id=record.action_plan.action_plan_id,
        order_no=record.order_no,
        execution_status=EXECUTION_EXECUTED,
        idempotent_replay=idempotent_replay,
        created_at=record.created_at,
    )


def coupon_to_execution_response(
    record: CouponRecord,
    *,
    idempotent_replay: bool,
) -> ToolExecutionResponse:
    return ToolExecutionResponse(
        tool_name=TOOL_COUPON_ISSUE,
        status=record.status,
        record_id=record.coupon_id,
        action_plan_id=record.action_plan.action_plan_id,
        order_no=record.order_no,
        execution_status=EXECUTION_EXECUTED,
        idempotent_replay=idempotent_replay,
        created_at=record.created_at,
    )


def ticket_to_execution_response(
    record: TicketRecord,
    *,
    idempotent_replay: bool,
) -> ToolExecutionResponse:
    return ToolExecutionResponse(
        tool_name=TOOL_TICKET_CREATE,
        status=record.status,
        record_id=record.ticket_id,
        action_plan_id=record.action_plan.action_plan_id,
        order_no=record.order_no,
        execution_status=EXECUTION_EXECUTED,
        idempotent_replay=idempotent_replay,
        created_at=record.created_at,
    )


def refund_to_response(record: RefundRecord) -> RefundRecordResponse:
    return RefundRecordResponse(
        refund_id=record.refund_id,
        action_plan_id=record.action_plan.action_plan_id,
        approval_id=record.approval_request.approval_id,
        order_no=record.order_no,
        amount=amount_to_string(record.amount) or "0.00",
        currency=record.currency,
        reason=record.reason,
        status=record.status,
        tool_name=record.tool_name,
        created_at=record.created_at,
    )


def coupon_to_response(record: CouponRecord) -> CouponRecordResponse:
    return CouponRecordResponse(
        coupon_id=record.coupon_id,
        action_plan_id=record.action_plan.action_plan_id,
        approval_id=record.approval_request.approval_id
        if record.approval_request is not None
        else None,
        order_no=record.order_no,
        amount=amount_to_string(record.amount) or "0.00",
        currency=record.currency,
        reason=record.reason,
        status=record.status,
        tool_name=record.tool_name,
        created_at=record.created_at,
    )


def ticket_to_response(record: TicketRecord) -> TicketRecordResponse:
    return TicketRecordResponse(
        ticket_id=record.ticket_id,
        action_plan_id=record.action_plan.action_plan_id,
        order_no=record.order_no,
        category=record.category,
        summary=record.summary,
        status=record.status,
        tool_name=record.tool_name,
        created_at=record.created_at,
    )
