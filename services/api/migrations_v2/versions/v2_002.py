"""Index the native 512-dimensional policy vectors in the independent agent database."""

from alembic import context, op

revision = "v2_002"
down_revision = "v2_001"
branch_labels = None
depends_on = None


def upgrade():
    if context.get_x_argument(as_dictionary=True).get("database") != "commerce":
        op.execute(
            "CREATE INDEX ix_policies_embedding ON policies USING hnsw (embedding vector_cosine_ops)"
        )


def downgrade():
    raise RuntimeError("Automatic destructive v2 downgrades are not supported")
