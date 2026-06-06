"""create policy rag tables

Revision ID: 202606060001
Revises: 202606050001
Create Date: 2026-06-06 00:01:00.000000
"""

from collections.abc import Sequence

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa

revision: str = "202606060001"
down_revision: str | None = "202606050001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "policy_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("policy_id", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("version", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("aftersales_type", sa.String(length=30), nullable=False),
        sa.Column("intent", sa.String(length=60), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_path", sa.String(length=260), nullable=False),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "aftersales_type IN ('all', 'standard', 'special', 'perishable', 'final_sale')",
            name="ck_policy_documents_aftersales_type",
        ),
        sa.CheckConstraint(
            "category IN ('all', 'electronics', 'apparel', 'appliance', 'fresh', 'home')",
            name="ck_policy_documents_category",
        ),
        sa.CheckConstraint(
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
        sa.CheckConstraint(
            "status IN ('active', 'deprecated', 'draft')",
            name="ck_policy_documents_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("policy_id", name="uq_policy_documents_policy_id"),
    )
    op.create_index("ix_policy_documents_aftersales_type", "policy_documents", ["aftersales_type"])
    op.create_index("ix_policy_documents_category", "policy_documents", ["category"])
    op.create_index("ix_policy_documents_intent", "policy_documents", ["intent"])

    op.create_table(
        "policy_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("chunk_id", sa.String(length=120), nullable=False),
        sa.Column("section", sa.String(length=120), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("embedding_model", sa.String(length=80), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["policy_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chunk_id", name="uq_policy_chunks_chunk_id"),
        sa.UniqueConstraint("document_id", "sequence", name="uq_policy_chunks_document_sequence"),
    )
    op.create_index("ix_policy_chunks_document_id", "policy_chunks", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_policy_chunks_document_id", table_name="policy_chunks")
    op.drop_table("policy_chunks")
    op.drop_index("ix_policy_documents_intent", table_name="policy_documents")
    op.drop_index("ix_policy_documents_category", table_name="policy_documents")
    op.drop_index("ix_policy_documents_aftersales_type", table_name="policy_documents")
    op.drop_table("policy_documents")
