"""Add daily task assignments.

Revision ID: 0009
Revises: 0008
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("batches.id"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("daily_tasks.id"), nullable=False),
        sa.Column("assigned_on", sa.Date, nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="assigned"),
        sa.Column("why_this_task", sa.Text, nullable=False),
        sa.Column("instructions", sa.Text, nullable=False),
        sa.Column("expected_deliverables", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("verification_strategy", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("difficulty", sa.String(40), nullable=False, server_default="medium"),
        sa.Column("estimated_minutes", sa.Integer, nullable=False, server_default="60"),
        sa.Column("skills_tested", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("mentor_review_required", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.UniqueConstraint("student_id", "assigned_on", name="uq_task_assignments_student_day"),
    )
    op.create_index("ix_task_assignments_organization_id", "task_assignments", ["organization_id"])
    op.create_index("ix_task_assignments_batch_id", "task_assignments", ["batch_id"])
    op.create_index("ix_task_assignments_student_id", "task_assignments", ["student_id"])
    op.create_index("ix_task_assignments_task_id", "task_assignments", ["task_id"])
    op.create_index("ix_task_assignments_assigned_on", "task_assignments", ["assigned_on"])


def downgrade() -> None:
    op.drop_index("ix_task_assignments_assigned_on", table_name="task_assignments")
    op.drop_index("ix_task_assignments_task_id", table_name="task_assignments")
    op.drop_index("ix_task_assignments_student_id", table_name="task_assignments")
    op.drop_index("ix_task_assignments_batch_id", table_name="task_assignments")
    op.drop_index("ix_task_assignments_organization_id", table_name="task_assignments")
    op.drop_table("task_assignments")
