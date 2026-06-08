from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.models.aftersales import ActionPlan, ApprovalRequest


class RefundRecord(Base):
    __tablename__ = "refund_records"
    __table_args__ = (
        CheckConstraint("status IN ('succeeded')", name="ck_refund_records_status"),
        CheckConstraint("tool_name = 'refund_apply'", name="ck_refund_records_tool_name"),
        UniqueConstraint("refund_id", name="uq_refund_records_refund_id"),
        UniqueConstraint("idempotency_key", name="uq_refund_records_idempotency_key"),
        UniqueConstraint("action_plan_id", name="uq_refund_records_action_plan_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    refund_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action_plan_id: Mapped[int] = mapped_column(
        ForeignKey("action_plans.id"),
        nullable=False,
        index=True,
    )
    approval_request_id: Mapped[int] = mapped_column(
        ForeignKey("approval_requests.id"),
        nullable=False,
        index=True,
    )
    order_no: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(60), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    action_plan: Mapped[ActionPlan] = relationship()
    approval_request: Mapped[ApprovalRequest] = relationship()


class CouponRecord(Base):
    __tablename__ = "coupon_records"
    __table_args__ = (
        CheckConstraint("status IN ('issued')", name="ck_coupon_records_status"),
        CheckConstraint("tool_name = 'coupon_issue'", name="ck_coupon_records_tool_name"),
        UniqueConstraint("coupon_id", name="uq_coupon_records_coupon_id"),
        UniqueConstraint("idempotency_key", name="uq_coupon_records_idempotency_key"),
        UniqueConstraint("action_plan_id", name="uq_coupon_records_action_plan_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coupon_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action_plan_id: Mapped[int] = mapped_column(
        ForeignKey("action_plans.id"),
        nullable=False,
        index=True,
    )
    approval_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("approval_requests.id"),
        nullable=True,
        index=True,
    )
    order_no: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(60), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    action_plan: Mapped[ActionPlan] = relationship()
    approval_request: Mapped[ApprovalRequest | None] = relationship()


class TicketRecord(Base):
    __tablename__ = "ticket_records"
    __table_args__ = (
        CheckConstraint("status IN ('created')", name="ck_ticket_records_status"),
        CheckConstraint("tool_name = 'ticket_create'", name="ck_ticket_records_tool_name"),
        UniqueConstraint("ticket_id", name="uq_ticket_records_ticket_id"),
        UniqueConstraint("idempotency_key", name="uq_ticket_records_idempotency_key"),
        UniqueConstraint("action_plan_id", name="uq_ticket_records_action_plan_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action_plan_id: Mapped[int] = mapped_column(
        ForeignKey("action_plans.id"),
        nullable=False,
        index=True,
    )
    order_no: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(60), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    action_plan: Mapped[ActionPlan] = relationship()
