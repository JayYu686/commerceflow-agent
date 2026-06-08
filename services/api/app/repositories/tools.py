from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import CouponRecord, RefundRecord, TicketRecord


def get_refund_by_idempotency_key(
    session: Session,
    idempotency_key: str,
) -> RefundRecord | None:
    return session.scalar(
        select(RefundRecord)
        .where(RefundRecord.idempotency_key == idempotency_key)
        .options(
            selectinload(RefundRecord.action_plan),
            selectinload(RefundRecord.approval_request),
        )
    )


def get_coupon_by_idempotency_key(
    session: Session,
    idempotency_key: str,
) -> CouponRecord | None:
    return session.scalar(
        select(CouponRecord)
        .where(CouponRecord.idempotency_key == idempotency_key)
        .options(
            selectinload(CouponRecord.action_plan),
            selectinload(CouponRecord.approval_request),
        )
    )


def get_ticket_by_idempotency_key(
    session: Session,
    idempotency_key: str,
) -> TicketRecord | None:
    return session.scalar(
        select(TicketRecord)
        .where(TicketRecord.idempotency_key == idempotency_key)
        .options(selectinload(TicketRecord.action_plan))
    )


def get_refund_by_action_plan_id(
    session: Session,
    action_plan_id: int,
) -> RefundRecord | None:
    return session.scalar(
        select(RefundRecord)
        .where(RefundRecord.action_plan_id == action_plan_id)
        .options(
            selectinload(RefundRecord.action_plan),
            selectinload(RefundRecord.approval_request),
        )
    )


def get_coupon_by_action_plan_id(
    session: Session,
    action_plan_id: int,
) -> CouponRecord | None:
    return session.scalar(
        select(CouponRecord)
        .where(CouponRecord.action_plan_id == action_plan_id)
        .options(
            selectinload(CouponRecord.action_plan),
            selectinload(CouponRecord.approval_request),
        )
    )


def get_ticket_by_action_plan_id(
    session: Session,
    action_plan_id: int,
) -> TicketRecord | None:
    return session.scalar(
        select(TicketRecord)
        .where(TicketRecord.action_plan_id == action_plan_id)
        .options(selectinload(TicketRecord.action_plan))
    )


def get_refund_by_external_id(
    session: Session,
    refund_id: str,
) -> RefundRecord | None:
    return session.scalar(
        select(RefundRecord)
        .where(RefundRecord.refund_id == refund_id)
        .options(
            selectinload(RefundRecord.action_plan),
            selectinload(RefundRecord.approval_request),
        )
    )


def get_coupon_by_external_id(
    session: Session,
    coupon_id: str,
) -> CouponRecord | None:
    return session.scalar(
        select(CouponRecord)
        .where(CouponRecord.coupon_id == coupon_id)
        .options(
            selectinload(CouponRecord.action_plan),
            selectinload(CouponRecord.approval_request),
        )
    )


def get_ticket_by_external_id(
    session: Session,
    ticket_id: str,
) -> TicketRecord | None:
    return session.scalar(
        select(TicketRecord)
        .where(TicketRecord.ticket_id == ticket_id)
        .options(selectinload(TicketRecord.action_plan))
    )
