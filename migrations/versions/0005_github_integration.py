"""Milestone 4: GitHub integration — connections, webhook events, commits, commit files.

Also extends repositories with new columns and adds state column to submissions.

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # github_connections
    # ------------------------------------------------------------------
    op.create_table(
        "github_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("github_user_login", sa.String(80), nullable=False),
        sa.Column("github_user_id", sa.Integer, nullable=False),
        sa.Column("access_token", sa.String(500), nullable=False),
        sa.Column("token_scope", sa.String(200), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("organization_id", name="uq_github_connections_org"),
    )
    op.create_index("ix_github_connections_organization_id", "github_connections", ["organization_id"])

    # ------------------------------------------------------------------
    # webhook_events
    # ------------------------------------------------------------------
    op.create_table(
        "webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("delivery_id", sa.String(120), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("repository_full_name", sa.String(300), nullable=False, server_default=""),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True)),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("delivery_id", name="uq_webhook_events_delivery_id"),
    )
    op.create_index("ix_webhook_events_delivery_id", "webhook_events", ["delivery_id"])
    op.create_index("ix_webhook_events_event_type", "webhook_events", ["event_type"])
    op.create_index("ix_webhook_events_status", "webhook_events", ["status"])

    # ------------------------------------------------------------------
    # commits
    # ------------------------------------------------------------------
    op.create_table(
        "commits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sha", sa.String(80), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("author_name", sa.String(200), nullable=False),
        sa.Column("author_email", sa.String(254), nullable=False),
        sa.Column("author_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("committer_name", sa.String(200), nullable=False),
        sa.Column("committer_email", sa.String(254), nullable=False),
        sa.Column("committer_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("branch", sa.String(200), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("parent_shas", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("additions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("deletions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("diff_truncated", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.UniqueConstraint("repository_id", "sha", name="uq_commits_repo_sha"),
    )
    op.create_index("ix_commits_repository_id", "commits", ["repository_id"])
    op.create_index("ix_commits_organization_id", "commits", ["organization_id"])
    op.create_index("ix_commits_sha", "commits", ["sha"])

    # ------------------------------------------------------------------
    # commit_files
    # ------------------------------------------------------------------
    op.create_table(
        "commit_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("commit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("path", sa.String(800), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("additions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("deletions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("changes", sa.Integer, nullable=False, server_default="0"),
        sa.Column("patch", sa.Text),
        sa.Column("patch_truncated", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["commit_id"], ["commits.id"]),
    )
    op.create_index("ix_commit_files_commit_id", "commit_files", ["commit_id"])

    # ------------------------------------------------------------------
    # Extend repositories with new columns
    # ------------------------------------------------------------------
    op.add_column("repositories", sa.Column("owner", sa.String(80)))
    op.add_column("repositories", sa.Column("name", sa.String(160)))
    op.add_column("repositories", sa.Column("full_name", sa.String(300)))
    op.add_column("repositories", sa.Column("external_repository_id", sa.Integer))
    op.add_column("repositories", sa.Column("private", sa.Boolean, server_default="false"))
    op.add_column("repositories", sa.Column("html_url", sa.String(500)))
    op.add_column("repositories", sa.Column("clone_url", sa.String(500)))
    op.add_column("repositories", sa.Column("last_synced_at", sa.DateTime(timezone=True)))
    op.create_index("ix_repositories_full_name", "repositories", ["full_name"])

    # ------------------------------------------------------------------
    # Add state column to submissions
    # ------------------------------------------------------------------
    op.add_column("submissions", sa.Column("state", sa.String(40)))
    op.create_index("ix_submissions_state", "submissions", ["state"])


def downgrade() -> None:
    op.drop_index("ix_submissions_state", "submissions")
    op.drop_column("submissions", "state")

    op.drop_index("ix_repositories_full_name", "repositories")
    op.drop_column("repositories", "last_synced_at")
    op.drop_column("repositories", "clone_url")
    op.drop_column("repositories", "html_url")
    op.drop_column("repositories", "private")
    op.drop_column("repositories", "external_repository_id")
    op.drop_column("repositories", "full_name")
    op.drop_column("repositories", "name")
    op.drop_column("repositories", "owner")

    op.drop_table("commit_files")
    op.drop_table("commits")
    op.drop_table("webhook_events")
    op.drop_table("github_connections")
