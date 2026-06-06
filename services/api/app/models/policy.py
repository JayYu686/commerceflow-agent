from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.services.embeddings import EMBEDDING_DIMENSION, EMBEDDING_MODEL


class PolicyDocument(Base):
    __tablename__ = "policy_documents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'deprecated', 'draft')",
            name="ck_policy_documents_status",
        ),
        CheckConstraint(
            "category IN ('all', 'electronics', 'apparel', 'appliance', 'fresh', 'home')",
            name="ck_policy_documents_category",
        ),
        CheckConstraint(
            "aftersales_type IN ('all', 'standard', 'special', 'perishable', 'final_sale')",
            name="ck_policy_documents_aftersales_type",
        ),
        CheckConstraint(
            "intent IN ("
            "'quality_issue_refund', "
            "'logistics_delay_compensation', "
            "'perishable_after_sales', "
            "'size_exchange', "
            "'warranty_service', "
            "'damaged_item_refund', "
            "'final_sale_exclusion'"
            ")",
            name="ck_policy_documents_intent",
        ),
        UniqueConstraint("policy_id", name="uq_policy_documents_policy_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_id: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    aftersales_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    intent: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_path: Mapped[str] = mapped_column(String(260), nullable=False)
    source_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
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

    chunks: Mapped[list["PolicyChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="PolicyChunk.sequence",
    )


class PolicyChunk(Base):
    __tablename__ = "policy_chunks"
    __table_args__ = (
        UniqueConstraint("chunk_id", name="uq_policy_chunks_chunk_id"),
        UniqueConstraint("document_id", "sequence", name="uq_policy_chunks_document_sequence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("policy_documents.id"),
        nullable=False,
        index=True,
    )
    chunk_id: Mapped[str] = mapped_column(String(120), nullable=False)
    section: Mapped[str] = mapped_column(String(120), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSION), nullable=False)
    embedding_model: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default=EMBEDDING_MODEL,
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    document: Mapped[PolicyDocument] = relationship(back_populates="chunks")
