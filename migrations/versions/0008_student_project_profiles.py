"""Add student project profiles for autonomous workflow.

Revision ID: 0008
Revises: 0007
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_project_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("github_repository", sa.String(500), nullable=False),
        sa.Column("deployed_url", sa.String(500)),
        sa.Column("project_title", sa.String(160), nullable=False),
        sa.Column("project_description", sa.Text, nullable=False, server_default=""),
        sa.Column("tech_stack", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("languages", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("frameworks", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("database", sa.String(120)),
        sa.Column("architecture_summary", sa.Text),
        sa.Column("current_strengths", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("current_weaknesses", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("skill_gaps", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("current_level", sa.String(40), nullable=False, server_default="unknown"),
        sa.Column("mentor_notes", sa.Text),
        sa.Column("analysis_version", sa.String(80), nullable=False, server_default="project-profile.v1"),
        sa.Column("last_analyzed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.UniqueConstraint("student_id", name="uq_student_project_profiles_student_id"),
    )
    op.create_index("ix_student_project_profiles_student_id", "student_project_profiles", ["student_id"])
    op.create_index("ix_student_project_profiles_organization_id", "student_project_profiles", ["organization_id"])
    op.create_index("ix_student_project_profiles_project_id", "student_project_profiles", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_student_project_profiles_project_id", table_name="student_project_profiles")
    op.drop_index("ix_student_project_profiles_organization_id", table_name="student_project_profiles")
    op.drop_index("ix_student_project_profiles_student_id", table_name="student_project_profiles")
    op.drop_table("student_project_profiles")
