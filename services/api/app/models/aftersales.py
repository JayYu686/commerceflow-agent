from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
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


class ActionPlan(Base):
    __tablename__ = "action_plans"
    __table_args__ = (
        CheckConstraint(
            "action_type IN ("
            "'refund_apply', "
            "'coupon_issue', "
            "'manual_review', "
            "'blocked', "
            "'request_more_info', "
            "'verify_order', "
            "'none'"
            ")",
            name="ck_action_plans_action_type",
        ),
        CheckConstraint(
            "status IN ('not_executable', 'planned', 'pending_approval', 'approved', 'rejected')",
            name="ck_action_plans_status",
        ),
        CheckConstraint(
            "execution_status IN ('not_executed', 'not_applicable')",
            name="ck_action_plans_execution_status",
        ),
        CheckConstraint(
            "risk_level IN ('low', 'medium', 'high', 'critical')",
            name="ck_action_plans_risk_level",
        ),
        UniqueConstraint("action_plan_id", name="uq_action_plans_action_plan_id"),
        UniqueConstraint("idempotency_key", name="uq_action_plans_idempotency_key"),
        UniqueConstraint("business_dedupe_key", name="uq_action_plans_business_dedupe_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action_plan_id: Mapped[str] = mapped_column(String(36), nullable=False)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    business_dedupe_key: Mapped[str] = mapped_column(String(160), nullable=False)
    order_no: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    intent: Mapped[str] = mapped_column(String(60), nullable=False)
    planned_tool_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    action_type: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    execution_status: Mapped[str] = mapped_column(String(30), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False)
    proposed_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    reasons_json: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    next_steps_json: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    fact_evidence_json: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    policy_evidence_json: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    llm_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    request_message: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    approval_request: Mapped["ApprovalRequest | None"] = relationship(
        back_populates="action_plan",
        cascade="all, delete-orphan",
        uselist=False,
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="action_plan")


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name="ck_approval_requests_status",
        ),
        CheckConstraint(
            "risk_level IN ('low', 'medium', 'high', 'critical')",
            name="ck_approval_requests_risk_level",
        ),
        UniqueConstraint("approval_id", name="uq_approval_requests_approval_id"),
        UniqueConstraint("action_plan_id", name="uq_approval_requests_action_plan_id"),
        UniqueConstraint(
            "decision_idempotency_key",
            name="uq_approval_requests_decision_idempotency_key",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    approval_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action_plan_id: Mapped[int] = mapped_column(
        ForeignKey("action_plans.id"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    requested_action_type: Mapped[str] = mapped_column(String(60), nullable=False)
    proposed_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    policy_ids_json: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    requester: Mapped[str] = mapped_column(String(80), nullable=False, default="agent")
    reviewer: Mapped[str | None] = mapped_column(String(120), nullable=True)
    decision_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_idempotency_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    decision_request_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    action_plan: Mapped[ActionPlan] = relationship(back_populates="approval_request")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="approval_request")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ("
            "'action_plan_created', "
            "'approval_requested', "
            "'approval_approved', "
            "'approval_rejected', "
            "'action_plan_not_executable'"
            ")",
            name="ck_audit_logs_event_type",
        ),
        CheckConstraint(
            "actor_type IN ('system', 'agent', 'reviewer')",
            name="ck_audit_logs_actor_type",
        ),
        UniqueConstraint("event_id", name="uq_audit_logs_event_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    action_plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("action_plans.id"),
        nullable=True,
        index=True,
    )
    approval_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("approval_requests.id"),
        nullable=True,
        index=True,
    )
    order_no: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    action_plan: Mapped[ActionPlan | None] = relationship(back_populates="audit_logs")
    approval_request: Mapped[ApprovalRequest | None] = relationship(back_populates="audit_logs")
