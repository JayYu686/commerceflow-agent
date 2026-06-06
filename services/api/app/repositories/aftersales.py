from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import ActionPlan, ApprovalRequest, AuditLog


def get_action_plan_by_idempotency_key(
    session: Session,
    idempotency_key: str,
) -> ActionPlan | None:
    statement = (
        select(ActionPlan)
        .where(ActionPlan.idempotency_key == idempotency_key)
        .options(selectinload(ActionPlan.approval_request))
    )
    return session.scalar(statement)


def get_action_plan_by_business_dedupe_key(
    session: Session,
    business_dedupe_key: str,
) -> ActionPlan | None:
    statement = (
        select(ActionPlan)
        .where(ActionPlan.business_dedupe_key == business_dedupe_key)
        .options(selectinload(ActionPlan.approval_request))
    )
    return session.scalar(statement)


def get_action_plan_by_external_id(
    session: Session,
    action_plan_id: str,
) -> ActionPlan | None:
    statement = (
        select(ActionPlan)
        .where(ActionPlan.action_plan_id == action_plan_id)
        .options(selectinload(ActionPlan.approval_request))
    )
    return session.scalar(statement)


def get_approval_request_by_external_id(
    session: Session,
    approval_id: str,
) -> ApprovalRequest | None:
    statement = (
        select(ApprovalRequest)
        .where(ApprovalRequest.approval_id == approval_id)
        .options(selectinload(ApprovalRequest.action_plan))
    )
    return session.scalar(statement)


def list_approval_requests(
    session: Session,
    *,
    status: str,
    limit: int,
) -> list[ApprovalRequest]:
    statement = (
        select(ApprovalRequest)
        .where(ApprovalRequest.status == status)
        .order_by(ApprovalRequest.requested_at.desc(), ApprovalRequest.id.desc())
        .limit(limit)
        .options(selectinload(ApprovalRequest.action_plan))
    )
    return list(session.scalars(statement))


def count_action_plans(session: Session) -> int:
    return len(session.scalars(select(ActionPlan.id)).all())


def count_approval_requests(session: Session) -> int:
    return len(session.scalars(select(ApprovalRequest.id)).all())


def count_audit_logs(session: Session) -> int:
    return len(session.scalars(select(AuditLog.id)).all())
