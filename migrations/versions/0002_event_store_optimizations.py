"""event store optimizations

Revision ID: 0002_event_store_optimizations
Revises: 0001_initial_backend_architecture
Create Date: 2026-08-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_event_store_optimizations"
down_revision = "0001_initial_backend_architecture"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Composite index for time-ordered event queries per aggregate (the hot path for event sourcing)
    op.create_index(
        "ix_system_events_aggregate_type_event_type_occurred_at",
        "system_events",
        ["aggregate_type", "event_type", "occurred_at"],
    )

    # GIN index enables fast JSONB containment queries on event payload (e.g. payload @> '{"student_id": "..."}')
    op.create_index(
        "ix_system_events_payload_gin",
        "system_events",
        ["payload"],
        postgresql_using="gin",
    )

    # GIN index on submission evidence for future evidence-based queries
    op.create_index(
        "ix_evaluations_evidence_gin",
        "evaluations",
        ["evidence"],
        postgresql_using="gin",
    )

    # Partial index: only unevaluated submissions — used by the evaluation worker to pick up work
    op.create_index(
        "ix_submissions_status_received",
        "submissions",
        ["status"],
        postgresql_where=sa.text("status = 'received'"),
    )

    # Partial index: mentor review queue — only submissions pending mentor attention
    op.create_index(
        "ix_submissions_status_mentor_review_pending",
        "submissions",
        ["status"],
        postgresql_where=sa.text("status = 'mentor_review_pending'"),
    )

    # Composite index for daily task lookups by student + due date
    op.create_index(
        "ix_daily_tasks_student_id_due_on",
        "daily_tasks",
        ["student_id", "due_on"],
    )


def downgrade() -> None:
    op.drop_index("ix_daily_tasks_student_id_due_on", "daily_tasks")
    op.drop_index("ix_submissions_status_mentor_review_pending", "submissions")
    op.drop_index("ix_submissions_status_received", "submissions")
    op.drop_index("ix_evaluations_evidence_gin", "evaluations")
    op.drop_index("ix_system_events_payload_gin", "system_events")
    op.drop_index("ix_system_events_aggregate_type_event_type_occurred_at", "system_events")
