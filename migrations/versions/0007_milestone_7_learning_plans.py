"""Milestone 7: Personalized 14-Day Learning Plans — add 11 new tables.

Revision ID: 0007
Revises: 0006
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # student_profile_analyses
    # ------------------------------------------------------------------
    op.create_table(
        "student_profile_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
        sa.Column("raw_profile", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("observed_skills", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("inferred_skills", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("unknown_areas", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("learning_style", sa.String(80)),
        sa.Column("risk_factors", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("strengths", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("ai_model", sa.String(80)),
        sa.Column("confidence", sa.Float),
        sa.Column("generated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    op.create_index("ix_student_profile_analyses_student_id", "student_profile_analyses", ["student_id"])
    op.create_index("ix_student_profile_analyses_organization_id", "student_profile_analyses", ["organization_id"])
    op.create_index("ix_student_profile_analyses_status", "student_profile_analyses", ["status"])

    # ------------------------------------------------------------------
    # skill_assessments
    # ------------------------------------------------------------------
    op.create_table(
        "skill_assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("profile_analysis_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("student_profile_analyses.id")),
        sa.Column("dimension", sa.String(80), nullable=False),
        sa.Column("score", sa.Integer, nullable=False),
        sa.Column("evidence_sources", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("confidence", sa.String(40), nullable=False, server_default="unknown"),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.UniqueConstraint("student_id", "dimension", name="uq_skill_assessments_student_dim"),
    )
    op.create_index("ix_skill_assessments_student_id", "skill_assessments", ["student_id"])
    op.create_index("ix_skill_assessments_organization_id", "skill_assessments", ["organization_id"])
    op.create_index("ix_skill_assessments_dimension", "skill_assessments", ["dimension"])

    # ------------------------------------------------------------------
    # learning_plans
    # ------------------------------------------------------------------
    op.create_table(
        "learning_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("batches.id"), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="draft"),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("total_days", sa.Integer, nullable=False, server_default="14"),
        sa.Column("ai_model", sa.String(80)),
        sa.Column("generation_prompt_hash", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    op.create_index("ix_learning_plans_student_id", "learning_plans", ["student_id"])
    op.create_index("ix_learning_plans_organization_id", "learning_plans", ["organization_id"])
    op.create_index("ix_learning_plans_batch_id", "learning_plans", ["batch_id"])
    op.create_index("ix_learning_plans_status", "learning_plans", ["status"])

    # ------------------------------------------------------------------
    # learning_plan_days
    # ------------------------------------------------------------------
    op.create_table(
        "learning_plan_days",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("learning_plans.id"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("day_number", sa.Integer, nullable=False),
        sa.Column("scheduled_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="locked"),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("daily_tasks.id")),
        sa.Column("target_skills", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("unlock_condition", postgresql.JSONB),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("score", sa.Integer),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.UniqueConstraint("plan_id", "day_number", name="uq_plan_days_plan_day"),
    )
    op.create_index("ix_learning_plan_days_plan_id", "learning_plan_days", ["plan_id"])
    op.create_index("ix_learning_plan_days_student_id", "learning_plan_days", ["student_id"])
    op.create_index("ix_learning_plan_days_scheduled_date", "learning_plan_days", ["scheduled_date"])
    op.create_index("ix_learning_plan_days_status", "learning_plan_days", ["status"])
    op.create_index("ix_learning_plan_days_task_id", "learning_plan_days", ["task_id"])

    # ------------------------------------------------------------------
    # task_dependencies
    # ------------------------------------------------------------------
    op.create_table(
        "task_dependencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("daily_tasks.id"), nullable=False),
        sa.Column("depends_on_task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("daily_tasks.id"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("dependency_type", sa.String(40), nullable=False, server_default="prerequisite"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.UniqueConstraint("task_id", "depends_on_task_id", name="uq_task_deps_pair"),
    )
    op.create_index("ix_task_dependencies_task_id", "task_dependencies", ["task_id"])
    op.create_index("ix_task_dependencies_depends_on_task_id", "task_dependencies", ["depends_on_task_id"])

    # ------------------------------------------------------------------
    # submission_evidences
    # ------------------------------------------------------------------
    op.create_table(
        "submission_evidences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("submissions.id"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("evidence_type", sa.String(80), nullable=False),
        sa.Column("url", sa.String(500)),
        sa.Column("content", sa.Text),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("collected_by", sa.String(40), nullable=False, server_default="student"),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quality_score", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    op.create_index("ix_submission_evidences_submission_id", "submission_evidences", ["submission_id"])
    op.create_index("ix_submission_evidences_organization_id", "submission_evidences", ["organization_id"])
    op.create_index("ix_submission_evidences_evidence_type", "submission_evidences", ["evidence_type"])

    # ------------------------------------------------------------------
    # verification_results
    # ------------------------------------------------------------------
    op.create_table(
        "verification_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("submissions.id"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("plan_day_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("learning_plan_days.id")),
        sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
        sa.Column("overall_score", sa.Integer),
        sa.Column("verdict", sa.String(80)),
        sa.Column("ai_model", sa.String(80)),
        sa.Column("verification_prompt_version", sa.String(80)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text),
        sa.Column("escalate_to_mentor", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("escalation_reason", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    op.create_index("ix_verification_results_submission_id", "verification_results", ["submission_id"])
    op.create_index("ix_verification_results_organization_id", "verification_results", ["organization_id"])
    op.create_index("ix_verification_results_plan_day_id", "verification_results", ["plan_day_id"])
    op.create_index("ix_verification_results_status", "verification_results", ["status"])

    # ------------------------------------------------------------------
    # verification_evidences
    # ------------------------------------------------------------------
    op.create_table(
        "verification_evidences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("verification_result_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("verification_results.id"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("evidence_type", sa.String(80), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("content", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("quality", sa.String(40), nullable=False, server_default="moderate"),
        sa.Column("weight", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    op.create_index("ix_verification_evidences_verification_result_id", "verification_evidences", ["verification_result_id"])

    # ------------------------------------------------------------------
    # student_progress
    # ------------------------------------------------------------------
    op.create_table(
        "student_progress",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("learning_plans.id")),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("day_number", sa.Integer),
        sa.Column("days_completed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("days_remaining", sa.Integer, nullable=False, server_default="14"),
        sa.Column("current_streak", sa.Integer, nullable=False, server_default="0"),
        sa.Column("longest_streak", sa.Integer, nullable=False, server_default="0"),
        sa.Column("average_score", sa.Float),
        sa.Column("skill_velocity", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("completed_task_ids", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.UniqueConstraint("student_id", "snapshot_date", name="uq_student_progress_date"),
    )
    op.create_index("ix_student_progress_student_id", "student_progress", ["student_id"])
    op.create_index("ix_student_progress_organization_id", "student_progress", ["organization_id"])
    op.create_index("ix_student_progress_snapshot_date", "student_progress", ["snapshot_date"])
    op.create_index("ix_student_progress_plan_id", "student_progress", ["plan_id"])

    # ------------------------------------------------------------------
    # daily_automation_runs
    # ------------------------------------------------------------------
    op.create_table(
        "daily_automation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("batches.id")),
        sa.Column("run_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
        sa.Column("students_processed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tasks_generated", sa.Integer, nullable=False, server_default="0"),
        sa.Column("verifications_triggered", sa.Integer, nullable=False, server_default="0"),
        sa.Column("plans_adapted", sa.Integer, nullable=False, server_default="0"),
        sa.Column("errors", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    op.create_index("ix_daily_automation_runs_organization_id", "daily_automation_runs", ["organization_id"])
    op.create_index("ix_daily_automation_runs_batch_id", "daily_automation_runs", ["batch_id"])
    op.create_index("ix_daily_automation_runs_run_date", "daily_automation_runs", ["run_date"])
    op.create_index("ix_daily_automation_runs_status", "daily_automation_runs", ["status"])

    # ------------------------------------------------------------------
    # ai_interaction_logs
    # ------------------------------------------------------------------
    op.create_table(
        "ai_interaction_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id")),
        sa.Column("interaction_type", sa.String(80), nullable=False),
        sa.Column("ai_model", sa.String(80), nullable=False),
        sa.Column("prompt_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("success", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("error_message", sa.Text),
        sa.Column("request_hash", sa.String(64)),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ai_interaction_logs_organization_id", "ai_interaction_logs", ["organization_id"])
    op.create_index("ix_ai_interaction_logs_student_id", "ai_interaction_logs", ["student_id"])
    op.create_index("ix_ai_interaction_logs_interaction_type", "ai_interaction_logs", ["interaction_type"])
    op.create_index("ix_ai_interaction_logs_created_at", "ai_interaction_logs", ["created_at"])
    op.create_index("ix_ai_interaction_logs_request_hash", "ai_interaction_logs", ["request_hash"])


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table("ai_interaction_logs")
    op.drop_table("daily_automation_runs")
    op.drop_table("student_progress")
    op.drop_table("verification_evidences")
    op.drop_table("verification_results")
    op.drop_table("submission_evidences")
    op.drop_table("task_dependencies")
    op.drop_table("learning_plan_days")
    op.drop_table("learning_plans")
    op.drop_table("skill_assessments")
    op.drop_table("student_profile_analyses")
