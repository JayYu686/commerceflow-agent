"""add durable workflow state

Revision ID: 202607160001
Revises: 202606070001
Create Date: 2026-07-16 00:01:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607160001"
down_revision: str | None = "202606070001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WORKFLOW_STATUS_CHECK = (
    "workflow_status IN ("
    "'legacy_manual', 'running', 'awaiting_approval', 'awaiting_execution', "
    "'completed', 'blocked', 'failed'"
    ")"
)

AUDIT_EVENTS = (
    "event_type IN ("
    "'action_plan_created', 'approval_requested', 'approval_approved', "
    "'approval_rejected', 'action_plan_not_executable', "
    "'tool_execution_succeeded', 'tool_execution_blocked', "
    "'tool_execution_idempotent_replay', 'workflow_started', "
    "'workflow_interrupted', 'workflow_resumed', 'workflow_completed', "
    "'workflow_blocked', 'workflow_failed'"
    ")"
)

AUDIT_EVENTS_OLD = (
    "event_type IN ("
    "'action_plan_created', 'approval_requested', 'approval_approved', "
    "'approval_rejected', 'action_plan_not_executable', "
    "'tool_execution_succeeded', 'tool_execution_blocked', "
    "'tool_execution_idempotent_replay'"
    ")"
)


def upgrade() -> None:
    with op.batch_alter_table("action_plans") as batch_op:
        batch_op.add_column(
            sa.Column(
                "workflow_status",
                sa.String(length=30),
                nullable=False,
                server_default="legacy_manual",
            )
        )
        batch_op.add_column(sa.Column("workflow_error_code", sa.String(length=80)))
        batch_op.add_column(sa.Column("trace_id", sa.String(length=32)))
        batch_op.create_unique_constraint("uq_action_plans_run_id", ["run_id"])
        batch_op.create_check_constraint("ck_action_plans_workflow_status", WORKFLOW_STATUS_CHECK)
        batch_op.create_index("ix_action_plans_trace_id", ["trace_id"])

    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.drop_constraint("ck_audit_logs_event_type", type_="check")
        batch_op.add_column(sa.Column("trace_id", sa.String(length=32)))
        batch_op.create_check_constraint("ck_audit_logs_event_type", AUDIT_EVENTS)
        batch_op.create_index("ix_audit_logs_trace_id", ["trace_id"])


def downgrade() -> None:
    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.drop_index("ix_audit_logs_trace_id")
        batch_op.drop_constraint("ck_audit_logs_event_type", type_="check")
        batch_op.create_check_constraint("ck_audit_logs_event_type", AUDIT_EVENTS_OLD)
        batch_op.drop_column("trace_id")

    with op.batch_alter_table("action_plans") as batch_op:
        batch_op.drop_index("ix_action_plans_trace_id")
        batch_op.drop_constraint("ck_action_plans_workflow_status", type_="check")
        batch_op.drop_constraint("uq_action_plans_run_id", type_="unique")
        batch_op.drop_column("trace_id")
        batch_op.drop_column("workflow_error_code")
        batch_op.drop_column("workflow_status")
