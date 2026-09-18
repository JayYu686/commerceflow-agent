from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from commerceflow.db import identifier, utcnow


class Base(DeclarativeBase):
    pass


class CommerceBase(DeclarativeBase):
    pass


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    owner: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), default="investigating")
    order_no: Mapped[str | None] = mapped_column(String(64))
    item_id: Mapped[str | None] = mapped_column(String(64))
    intent: Mapped[str | None] = mapped_column(String(40))
    generation: Mapped[int] = mapped_column(Integer, default=0)
    current_plan_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    target_reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CaseMessage(Base):
    __tablename__ = "case_messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    generation: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EvidenceSnapshot(Base):
    __tablename__ = "evidence_snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    generation: Mapped[int] = mapped_column(Integer)
    tool: Mapped[str] = mapped_column(String(60))
    arguments: Mapped[dict] = mapped_column(JSON)
    payload: Mapped[dict] = mapped_column(JSON)
    checksum: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PlanVersion(Base):
    __tablename__ = "plan_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    generation: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)
    checksum: Mapped[str] = mapped_column(String(64))
    requires_approval: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ApprovalDecision(Base):
    __tablename__ = "approval_decisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    plan_id: Mapped[str] = mapped_column(ForeignKey("plan_versions.id"), unique=True)
    plan_checksum: Mapped[str] = mapped_column(String(64))
    reviewer: Mapped[str] = mapped_column(String(40))
    approved: Mapped[bool] = mapped_column(Boolean)
    comment: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Execution(Base):
    __tablename__ = "executions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    plan_id: Mapped[str] = mapped_column(ForeignKey("plan_versions.id"), unique=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    plan_checksum: Mapped[str] = mapped_column(String(64))
    confirmed_by: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), default="queued")
    result: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    reference_id: Mapped[str] = mapped_column(String(36), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    owner_token: Mapped[str | None] = mapped_column(String(36))
    error: Mapped[str | None] = mapped_column(Text)


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    kind: Mapped[str] = mapped_column(String(60))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RequestRecord(Base):
    __tablename__ = "request_records"
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    checksum: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict] = mapped_column(JSON)


class LoginSession(Base):
    __tablename__ = "login_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    role: Mapped[str] = mapped_column(String(20))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Policy(Base):
    __table_args__ = (
        Index(
            "ix_policies_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
    __tablename__ = "policies"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    version: Mapped[str] = mapped_column(String(20))
    intent: Mapped[str] = mapped_column(String(40), index=True)
    active: Mapped[bool] = mapped_column(Boolean)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rules: Mapped[dict] = mapped_column(JSON)
    content: Mapped[str] = mapped_column(Text)
    checksum: Mapped[str] = mapped_column(String(64))
    embedding: Mapped[list | None] = mapped_column(Vector(512))
    embedding_model: Mapped[str | None] = mapped_column(String(200))


class BudgetAccount(Base):
    __tablename__ = "budget_accounts"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    committed_microyuan: Mapped[int] = mapped_column(BigInteger, default=0)


class ModelCall(Base):
    __tablename__ = "model_calls"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    case_id: Mapped[str | None] = mapped_column(String(36), index=True)
    provider: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(100))
    reserved_microyuan: Mapped[int] = mapped_column(BigInteger, default=0)
    actual_microyuan: Mapped[int | None] = mapped_column(BigInteger)
    usage: Mapped[dict | None] = mapped_column(JSON)
    pricing: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="reserved")
    elapsed_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Order(CommerceBase):
    __tablename__ = "orders"
    order_no: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30))
    paid_fen: Mapped[int] = mapped_column(Integer)
    refunded_fen: Mapped[int] = mapped_column(Integer, default=0)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    promised_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    tracking_no: Mapped[str | None] = mapped_column(String(64))
    carrier_events: Mapped[list] = mapped_column(JSON, default=list)


class OrderItem(CommerceBase):
    __tablename__ = "order_items"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_no: Mapped[str] = mapped_column(ForeignKey("orders.order_no"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(30))
    aftersales_type: Mapped[str] = mapped_column(String(30), default="standard")
    paid_fen: Mapped[int] = mapped_column(Integer)
    refunded_fen: Mapped[int] = mapped_column(Integer, default=0)


class BusinessResult(CommerceBase):
    __tablename__ = "business_results"
    execution_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    entitlement_key: Mapped[str] = mapped_column(String(160), unique=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    order_no: Mapped[str] = mapped_column(ForeignKey("orders.order_no"), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Ticket(CommerceBase):
    __tablename__ = "tickets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    execution_id: Mapped[str] = mapped_column(
        ForeignKey("business_results.execution_id"), unique=True
    )
    case_id: Mapped[str] = mapped_column(String(36))
    order_no: Mapped[str] = mapped_column(String(64))
    resolution: Mapped[str] = mapped_column(String(40))
