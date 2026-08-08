"""Milestone 5: AI Evaluation Engine — add detailed evaluation columns.

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Create ai_evaluations table (new rich evaluations separate from
    # the legacy evaluations table for backward compatibility)
    # ------------------------------------------------------------------
    op.create_table(
        "ai_evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("state", sa.String(40), nullable=False, server_default="pending"),
        sa.Column("result", postgresql.JSONB),
        sa.Column("provider", sa.String(80), nullable=False, server_default=""),
        sa.Column("model", sa.String(80), nullable=False, server_default=""),
        sa.Column("prompt_version", sa.String(80), nullable=False, server_default=""),
        sa.Column("context_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("input_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text),
        # Mentor review
        sa.Column("mentor_decision", sa.String(40)),
        sa.Column("mentor_feedback", sa.Text),
        sa.Column("mentor_id", postgresql.UUID(as_uuid=True)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("mentor_override_score", sa.Float),
        # Standard timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["daily_tasks.id"]),
    )
    op.create_index("ix_ai_evaluations_submission_id", "ai_evaluations", ["submission_id"])
    op.create_index("ix_ai_evaluations_organization_id", "ai_evaluations", ["organization_id"])
    op.create_index("ix_ai_evaluations_state", "ai_evaluations", ["state"])
    op.create_index("ix_ai_evaluations_context_hash", "ai_evaluations", ["context_hash"])


def downgrade() -> None:
    op.drop_index("ix_ai_evaluations_context_hash", "ai_evaluations")
    op.drop_index("ix_ai_evaluations_state", "ai_evaluations")
    op.drop_index("ix_ai_evaluations_organization_id", "ai_evaluations")
    op.drop_index("ix_ai_evaluations_submission_id", "ai_evaluations")
    op.drop_table("ai_evaluations")
