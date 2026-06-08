"""create mock business result tables

Revision ID: 202606070001
Revises: 202606060002
Create Date: 2026-06-07 00:01:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "202606070001"
down_revision: str | None = "202606060002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTION_PLAN_EXECUTION_STATUS_CHECK = (
    "execution_status IN ("
    "'not_executed', "
    "'not_applicable', "
    "'executed', "
    "'execution_failed'"
    ")"
)

ACTION_PLAN_EXECUTION_STATUS_CHECK_OLD = (
    "execution_status IN ('not_executed', 'not_applicable')"
)

AUDIT_LOG_EVENT_TYPE_CHECK = (
    "event_type IN ("
    "'action_plan_created', "
    "'approval_requested', "
    "'approval_approved', "
    "'approval_rejected', "
    "'action_plan_not_executable', "
    "'tool_execution_succeeded', "
    "'tool_execution_blocked', "
    "'tool_execution_idempotent_replay'"
    ")"
)

AUDIT_LOG_EVENT_TYPE_CHECK_OLD = (
    "event_type IN ("
    "'action_plan_created', "
    "'approval_requested', "
    "'approval_approved', "
    "'approval_rejected', "
    "'action_plan_not_executable'"
    ")"
)


def upgrade() -> None:
    with op.batch_alter_table("action_plans") as batch_op:
        batch_op.drop_constraint("ck_action_plans_execution_status", type_="check")
        batch_op.create_check_constraint(
            "ck_action_plans_execution_status",
            ACTION_PLAN_EXECUTION_STATUS_CHECK,
        )

    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.drop_constraint("ck_audit_logs_event_type", type_="check")
        batch_op.create_check_constraint(
            "ck_audit_logs_event_type",
            AUDIT_LOG_EVENT_TYPE_CHECK,
        )

    op.create_table(
        "refund_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("refund_id", sa.String(length=36), nullable=False),
        sa.Column("action_plan_id", sa.Integer(), nullable=False),
        sa.Column("approval_request_id", sa.Integer(), nullable=False),
        sa.Column("order_no", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("tool_name", sa.String(length=60), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('succeeded')", name="ck_refund_records_status"),
        sa.CheckConstraint("tool_name = 'refund_apply'", name="ck_refund_records_tool_name"),
        sa.ForeignKeyConstraint(["action_plan_id"], ["action_plans.id"]),
        sa.ForeignKeyConstraint(["approval_request_id"], ["approval_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("action_plan_id", name="uq_refund_records_action_plan_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_refund_records_idempotency_key"),
        sa.UniqueConstraint("refund_id", name="uq_refund_records_refund_id"),
    )
    op.create_index("ix_refund_records_action_plan_id", "refund_records", ["action_plan_id"])
    op.create_index(
        "ix_refund_records_approval_request_id",
        "refund_records",
        ["approval_request_id"],
    )
    op.create_index("ix_refund_records_order_no", "refund_records", ["order_no"])

    op.create_table(
        "coupon_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("coupon_id", sa.String(length=36), nullable=False),
        sa.Column("action_plan_id", sa.Integer(), nullable=False),
        sa.Column("approval_request_id", sa.Integer(), nullable=True),
        sa.Column("order_no", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("tool_name", sa.String(length=60), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('issued')", name="ck_coupon_records_status"),
        sa.CheckConstraint("tool_name = 'coupon_issue'", name="ck_coupon_records_tool_name"),
        sa.ForeignKeyConstraint(["action_plan_id"], ["action_plans.id"]),
        sa.ForeignKeyConstraint(["approval_request_id"], ["approval_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("action_plan_id", name="uq_coupon_records_action_plan_id"),
        sa.UniqueConstraint("coupon_id", name="uq_coupon_records_coupon_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_coupon_records_idempotency_key"),
    )
    op.create_index("ix_coupon_records_action_plan_id", "coupon_records", ["action_plan_id"])
    op.create_index(
        "ix_coupon_records_approval_request_id",
        "coupon_records",
        ["approval_request_id"],
    )
    op.create_index("ix_coupon_records_order_no", "coupon_records", ["order_no"])

    op.create_table(
        "ticket_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.String(length=36), nullable=False),
        sa.Column("action_plan_id", sa.Integer(), nullable=False),
        sa.Column("order_no", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("tool_name", sa.String(length=60), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('created')", name="ck_ticket_records_status"),
        sa.CheckConstraint("tool_name = 'ticket_create'", name="ck_ticket_records_tool_name"),
        sa.ForeignKeyConstraint(["action_plan_id"], ["action_plans.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("action_plan_id", name="uq_ticket_records_action_plan_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_ticket_records_idempotency_key"),
        sa.UniqueConstraint("ticket_id", name="uq_ticket_records_ticket_id"),
    )
    op.create_index("ix_ticket_records_action_plan_id", "ticket_records", ["action_plan_id"])
    op.create_index("ix_ticket_records_order_no", "ticket_records", ["order_no"])


def downgrade() -> None:
    op.drop_index("ix_ticket_records_order_no", table_name="ticket_records")
    op.drop_index("ix_ticket_records_action_plan_id", table_name="ticket_records")
    op.drop_table("ticket_records")

    op.drop_index("ix_coupon_records_order_no", table_name="coupon_records")
    op.drop_index("ix_coupon_records_approval_request_id", table_name="coupon_records")
    op.drop_index("ix_coupon_records_action_plan_id", table_name="coupon_records")
    op.drop_table("coupon_records")

    op.drop_index("ix_refund_records_order_no", table_name="refund_records")
    op.drop_index("ix_refund_records_approval_request_id", table_name="refund_records")
    op.drop_index("ix_refund_records_action_plan_id", table_name="refund_records")
    op.drop_table("refund_records")

    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.drop_constraint("ck_audit_logs_event_type", type_="check")
        batch_op.create_check_constraint(
            "ck_audit_logs_event_type",
            AUDIT_LOG_EVENT_TYPE_CHECK_OLD,
        )

    with op.batch_alter_table("action_plans") as batch_op:
        batch_op.drop_constraint("ck_action_plans_execution_status", type_="check")
        batch_op.create_check_constraint(
            "ck_action_plans_execution_status",
            ACTION_PLAN_EXECUTION_STATUS_CHECK_OLD,
        )
