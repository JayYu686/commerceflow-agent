"""create action plan approval audit tables

Revision ID: 202606060002
Revises: 202606060001
Create Date: 2026-06-06 00:02:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "202606060002"
down_revision: str | None = "202606060001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "action_plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("action_plan_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("business_dedupe_key", sa.String(length=160), nullable=False),
        sa.Column("order_no", sa.String(length=32), nullable=True),
        sa.Column("intent", sa.String(length=60), nullable=False),
        sa.Column("planned_tool_name", sa.String(length=80), nullable=True),
        sa.Column("action_type", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("execution_status", sa.String(length=30), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("requires_approval", sa.Boolean(), nullable=False),
        sa.Column("proposed_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("reasons_json", sa.JSON(), nullable=False),
        sa.Column("next_steps_json", sa.JSON(), nullable=False),
        sa.Column("fact_evidence_json", sa.JSON(), nullable=False),
        sa.Column("policy_evidence_json", sa.JSON(), nullable=False),
        sa.Column("llm_json", sa.JSON(), nullable=False),
        sa.Column("request_message", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
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
        sa.CheckConstraint(
            "execution_status IN ('not_executed', 'not_applicable')",
            name="ck_action_plans_execution_status",
        ),
        sa.CheckConstraint(
            "risk_level IN ('low', 'medium', 'high', 'critical')",
            name="ck_action_plans_risk_level",
        ),
        sa.CheckConstraint(
            "status IN ('not_executable', 'planned', 'pending_approval', 'approved', 'rejected')",
            name="ck_action_plans_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("action_plan_id", name="uq_action_plans_action_plan_id"),
        sa.UniqueConstraint("business_dedupe_key", name="uq_action_plans_business_dedupe_key"),
        sa.UniqueConstraint("idempotency_key", name="uq_action_plans_idempotency_key"),
    )
    op.create_index("ix_action_plans_order_no", "action_plans", ["order_no"])

    op.create_table(
        "approval_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("approval_id", sa.String(length=36), nullable=False),
        sa.Column("action_plan_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("requested_action_type", sa.String(length=60), nullable=False),
        sa.Column("proposed_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("policy_ids_json", sa.JSON(), nullable=False),
        sa.Column("requester", sa.String(length=80), nullable=False),
        sa.Column("reviewer", sa.String(length=120), nullable=True),
        sa.Column("decision_comment", sa.Text(), nullable=True),
        sa.Column("decision_idempotency_key", sa.String(length=160), nullable=True),
        sa.Column("decision_request_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "risk_level IN ('low', 'medium', 'high', 'critical')",
            name="ck_approval_requests_risk_level",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name="ck_approval_requests_status",
        ),
        sa.ForeignKeyConstraint(["action_plan_id"], ["action_plans.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("action_plan_id", name="uq_approval_requests_action_plan_id"),
        sa.UniqueConstraint("approval_id", name="uq_approval_requests_approval_id"),
        sa.UniqueConstraint(
            "decision_idempotency_key",
            name="uq_approval_requests_decision_idempotency_key",
        ),
    )
    op.create_index("ix_approval_requests_action_plan_id", "approval_requests", ["action_plan_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("actor_type", sa.String(length=30), nullable=False),
        sa.Column("actor_id", sa.String(length=120), nullable=True),
        sa.Column("action_plan_id", sa.Integer(), nullable=True),
        sa.Column("approval_request_id", sa.Integer(), nullable=True),
        sa.Column("order_no", sa.String(length=32), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "actor_type IN ('system', 'agent', 'reviewer')",
            name="ck_audit_logs_actor_type",
        ),
        sa.CheckConstraint(
            "event_type IN ("
            "'action_plan_created', "
            "'approval_requested', "
            "'approval_approved', "
            "'approval_rejected', "
            "'action_plan_not_executable'"
            ")",
            name="ck_audit_logs_event_type",
        ),
        sa.ForeignKeyConstraint(["action_plan_id"], ["action_plans.id"]),
        sa.ForeignKeyConstraint(["approval_request_id"], ["approval_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_audit_logs_event_id"),
    )
    op.create_index("ix_audit_logs_action_plan_id", "audit_logs", ["action_plan_id"])
    op.create_index("ix_audit_logs_approval_request_id", "audit_logs", ["approval_request_id"])
    op.create_index("ix_audit_logs_order_no", "audit_logs", ["order_no"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_order_no", table_name="audit_logs")
    op.drop_index("ix_audit_logs_approval_request_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action_plan_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_approval_requests_action_plan_id", table_name="approval_requests")
    op.drop_table("approval_requests")
    op.drop_index("ix_action_plans_order_no", table_name="action_plans")
    op.drop_table("action_plans")
