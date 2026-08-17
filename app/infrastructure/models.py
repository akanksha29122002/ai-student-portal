from datetime import UTC, date, datetime
from uuid import uuid4

from app.shared.exceptions import InfrastructureException

try:
    from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
    from sqlalchemy.dialects.postgresql import JSONB, UUID
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
except ModuleNotFoundError as exc:
    raise InfrastructureException("SQLAlchemy is required for database models.") from exc


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class OrganizationModel(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)


class ProgramModel(Base, TimestampMixin):
    __tablename__ = "programs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    track: Mapped[str] = mapped_column(String(40), nullable=False, default="track_a")


class BatchModel(Base, TimestampMixin):
    __tablename__ = "batches"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)


class MentorModel(Base, TimestampMixin):
    __tablename__ = "mentors"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)


class StudentModel(Base, TimestampMixin):
    __tablename__ = "students"
    __table_args__ = (UniqueConstraint("organization_id", "email", name="uq_students_org_email"),)

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    batch_id: Mapped[UUID] = mapped_column(ForeignKey("batches.id"), index=True, nullable=False)
    mentor_id: Mapped[UUID | None] = mapped_column(ForeignKey("mentors.id"), index=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    track: Mapped[str] = mapped_column(String(40), nullable=False, default="track_a")
    consecutive_missed_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ProjectModel(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    student_id: Mapped[UUID] = mapped_column(ForeignKey("students.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    repository_url: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)


class RepositoryModel(Base, TimestampMixin):
    __tablename__ = "repositories"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    external_url: Mapped[str] = mapped_column(String(500), nullable=False)
    default_branch: Mapped[str] = mapped_column(String(120), nullable=False, default="main")
    # Extended fields added in milestone 4
    owner: Mapped[str | None] = mapped_column(String(80))
    name: Mapped[str | None] = mapped_column(String(160))
    full_name: Mapped[str | None] = mapped_column(String(300), index=True)
    external_repository_id: Mapped[int | None] = mapped_column(Integer)
    private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    html_url: Mapped[str | None] = mapped_column(String(500))
    clone_url: Mapped[str | None] = mapped_column(String(500))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DailyTaskModel(Base, TimestampMixin):
    __tablename__ = "daily_tasks"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    batch_id: Mapped[UUID] = mapped_column(ForeignKey("batches.id"), index=True, nullable=False)
    student_id: Mapped[UUID] = mapped_column(ForeignKey("students.id"), index=True, nullable=False)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    task_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    problem_statement: Mapped[str] = mapped_column(Text, nullable=False)
    acceptance_criteria: Mapped[dict] = mapped_column(JSONB, nullable=False)
    expected_concepts: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    due_on: Mapped[date] = mapped_column(Date, index=True, nullable=False)


class SubmissionModel(Base, TimestampMixin):
    __tablename__ = "submissions"
    __table_args__ = (UniqueConstraint("student_id", "task_id", name="uq_submissions_student_task"),)

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    task_id: Mapped[UUID] = mapped_column(ForeignKey("daily_tasks.id"), index=True, nullable=False)
    student_id: Mapped[UUID] = mapped_column(ForeignKey("students.id"), index=True, nullable=False)
    self_status: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    # Milestone-4 state machine column (nullable for backward compat)
    state: Mapped[str | None] = mapped_column(String(40), index=True)
    repository_url: Mapped[str | None] = mapped_column(String(500))
    commit_url: Mapped[str | None] = mapped_column(String(500))
    transcript_url: Mapped[str | None] = mapped_column(String(500))
    transcript_text: Mapped[str | None] = mapped_column(Text)
    approach_note: Mapped[str | None] = mapped_column(Text)

    evaluations: Mapped[list["EvaluationModel"]] = relationship(back_populates="submission")


class EvaluationModel(Base, TimestampMixin):
    __tablename__ = "evaluations"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    submission_id: Mapped[UUID] = mapped_column(ForeignKey("submissions.id"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    verdict: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False)
    flags: Mapped[dict] = mapped_column(JSONB, nullable=False)
    mentor_note: Mapped[str] = mapped_column(Text, nullable=False)
    student_feedback_draft: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_next_action: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)

    submission: Mapped[SubmissionModel] = relationship(back_populates="evaluations")


class MentorReviewModel(Base, TimestampMixin):
    __tablename__ = "mentor_reviews"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    evaluation_id: Mapped[UUID] = mapped_column(ForeignKey("evaluations.id"), index=True, nullable=False)
    mentor_id: Mapped[UUID] = mapped_column(ForeignKey("mentors.id"), index=True, nullable=False)
    decision: Mapped[str] = mapped_column(String(60), nullable=False)
    final_feedback: Mapped[str] = mapped_column(Text, nullable=False)
    override_reason: Mapped[str | None] = mapped_column(Text)


class NotificationModel(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    student_id: Mapped[UUID | None] = mapped_column(ForeignKey("students.id"), index=True)
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)


class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    action: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)


class ActivityLogModel(Base):
    __tablename__ = "activity_logs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    activity_type: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)


class SystemEventModel(Base):
    __tablename__ = "system_events"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    aggregate_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    causation_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    user_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False)


class RefreshTokenModel(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    device_hint: Mapped[str | None] = mapped_column(String(200))


class UserModel(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(256), nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False, default="student")
    organization_id: Mapped[UUID | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------------------
# Milestone 4 — GitHub integration models
# ---------------------------------------------------------------------------


class GitHubConnectionModel(Base, TimestampMixin):
    """Stores a GitHub OAuth connection per organisation.

    The access token is stored encrypted in production; here it's plaintext
    behind the scenes (the API never exposes it).
    """
    __tablename__ = "github_connections"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), unique=True, index=True, nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    github_user_login: Mapped[str] = mapped_column(String(80), nullable=False)
    github_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    access_token: Mapped[str] = mapped_column(String(500), nullable=False)
    token_scope: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class WebhookEventModel(Base):
    """Idempotency store for received GitHub webhook deliveries."""
    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint("delivery_id", name="uq_webhook_events_delivery_id"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    delivery_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    repository_full_name: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    organization_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending", index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class CommitModel(Base, TimestampMixin):
    """Stores metadata for a single ingested Git commit."""
    __tablename__ = "commits"
    __table_args__ = (
        UniqueConstraint("repository_id", "sha", name="uq_commits_repo_sha"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    repository_id: Mapped[UUID] = mapped_column(
        ForeignKey("repositories.id"), index=True, nullable=False
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True, nullable=False
    )
    sha: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    author_name: Mapped[str] = mapped_column(String(200), nullable=False)
    author_email: Mapped[str] = mapped_column(String(254), nullable=False)
    author_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    committer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    committer_email: Mapped[str] = mapped_column(String(254), nullable=False)
    committer_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    branch: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    parent_shas: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    additions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deletions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    diff_truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    files: Mapped[list["CommitFileModel"]] = relationship(back_populates="commit")


class CommitFileModel(Base):
    """Stores per-file diff metadata for a commit."""
    __tablename__ = "commit_files"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    commit_id: Mapped[UUID] = mapped_column(
        ForeignKey("commits.id"), index=True, nullable=False
    )
    path: Mapped[str] = mapped_column(String(800), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    additions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deletions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    changes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    patch: Mapped[str | None] = mapped_column(Text)
    patch_truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    commit: Mapped[CommitModel] = relationship(back_populates="files")


# ---------------------------------------------------------------------------
# Milestone 7 — Personalized 14-Day Learning Plans
# ---------------------------------------------------------------------------


class StudentProfileAnalysisModel(Base, TimestampMixin):
    """AI-generated deep analysis of a student's skills, gaps, and learning profile."""
    __tablename__ = "student_profile_analyses"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    student_id: Mapped[UUID] = mapped_column(ForeignKey("students.id"), index=True, nullable=False)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending", index=True)
    raw_profile: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    observed_skills: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    inferred_skills: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    unknown_areas: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    learning_style: Mapped[str | None] = mapped_column(String(80))
    risk_factors: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    strengths: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    ai_model: Mapped[str | None] = mapped_column(String(80))
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SkillAssessmentModel(Base, TimestampMixin):
    """Baseline skill score (0–100) per dimension for a student."""
    __tablename__ = "skill_assessments"
    __table_args__ = (UniqueConstraint("student_id", "dimension", name="uq_skill_assessments_student_dim"),)

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    student_id: Mapped[UUID] = mapped_column(ForeignKey("students.id"), index=True, nullable=False)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    profile_analysis_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("student_profile_analyses.id"), index=True
    )
    dimension: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_sources: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    confidence: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))


class LearningPlanModel(Base, TimestampMixin):
    """14-day personalised learning plan for a single student."""
    __tablename__ = "learning_plans"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    student_id: Mapped[UUID] = mapped_column(ForeignKey("students.id"), index=True, nullable=False)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    batch_id: Mapped[UUID] = mapped_column(ForeignKey("batches.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft", index=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_days: Mapped[int] = mapped_column(Integer, nullable=False, default=14)
    ai_model: Mapped[str | None] = mapped_column(String(80))
    generation_prompt_hash: Mapped[str | None] = mapped_column(String(64))

    days: Mapped[list["LearningPlanDayModel"]] = relationship(back_populates="plan", order_by="LearningPlanDayModel.day_number")


class LearningPlanDayModel(Base, TimestampMixin):
    """Single day entry within a LearningPlan."""
    __tablename__ = "learning_plan_days"
    __table_args__ = (UniqueConstraint("plan_id", "day_number", name="uq_plan_days_plan_day"),)

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("learning_plans.id"), index=True, nullable=False)
    student_id: Mapped[UUID] = mapped_column(ForeignKey("students.id"), index=True, nullable=False)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="locked", index=True)
    task_id: Mapped[UUID | None] = mapped_column(ForeignKey("daily_tasks.id"), index=True)
    target_skills: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    unlock_condition: Mapped[dict | None] = mapped_column(JSONB)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    score: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)

    plan: Mapped[LearningPlanModel] = relationship(back_populates="days")


class TaskDependencyModel(Base, TimestampMixin):
    """Directed prerequisite relationship between two tasks."""
    __tablename__ = "task_dependencies"
    __table_args__ = (UniqueConstraint("task_id", "depends_on_task_id", name="uq_task_deps_pair"),)

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(ForeignKey("daily_tasks.id"), index=True, nullable=False)
    depends_on_task_id: Mapped[UUID] = mapped_column(ForeignKey("daily_tasks.id"), index=True, nullable=False)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    dependency_type: Mapped[str] = mapped_column(String(40), nullable=False, default="prerequisite")


class SubmissionEvidenceModel(Base, TimestampMixin):
    """Structured evidence pieces attached to a submission (multi-modal)."""
    __tablename__ = "submission_evidences"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    submission_id: Mapped[UUID] = mapped_column(ForeignKey("submissions.id"), index=True, nullable=False)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    url: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    collected_by: Mapped[str] = mapped_column(String(40), nullable=False, default="student")
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    quality_score: Mapped[int | None] = mapped_column(Integer)


class VerificationResultModel(Base, TimestampMixin):
    """Automated verification result for a submission."""
    __tablename__ = "verification_results"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    submission_id: Mapped[UUID] = mapped_column(ForeignKey("submissions.id"), index=True, nullable=False)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    plan_day_id: Mapped[UUID | None] = mapped_column(ForeignKey("learning_plan_days.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending", index=True)
    overall_score: Mapped[int | None] = mapped_column(Integer)
    verdict: Mapped[str | None] = mapped_column(String(80))
    ai_model: Mapped[str | None] = mapped_column(String(80))
    verification_prompt_version: Mapped[str | None] = mapped_column(String(80))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    escalate_to_mentor: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    escalation_reason: Mapped[str | None] = mapped_column(Text)

    evidences: Mapped[list["VerificationEvidenceModel"]] = relationship(back_populates="verification_result")


class VerificationEvidenceModel(Base, TimestampMixin):
    """Individual evidence piece within a verification result."""
    __tablename__ = "verification_evidences"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    verification_result_id: Mapped[UUID] = mapped_column(
        ForeignKey("verification_results.id"), index=True, nullable=False
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    quality: Mapped[str] = mapped_column(String(40), nullable=False, default="moderate")
    weight: Mapped[float] = mapped_column(nullable=False, default=1.0)

    verification_result: Mapped[VerificationResultModel] = relationship(back_populates="evidences")


class StudentProgressModel(Base, TimestampMixin):
    """Daily progress snapshot for a student within a learning plan."""
    __tablename__ = "student_progress"
    __table_args__ = (UniqueConstraint("student_id", "snapshot_date", name="uq_student_progress_date"),)

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    student_id: Mapped[UUID] = mapped_column(ForeignKey("students.id"), index=True, nullable=False)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    plan_id: Mapped[UUID | None] = mapped_column(ForeignKey("learning_plans.id"), index=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    day_number: Mapped[int | None] = mapped_column(Integer)
    days_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    days_remaining: Mapped[int] = mapped_column(Integer, nullable=False, default=14)
    current_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    average_score: Mapped[float | None] = mapped_column(nullable=True)
    skill_velocity: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    completed_task_ids: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)


class DailyAutomationRunModel(Base, TimestampMixin):
    """Record of each daily automation job execution."""
    __tablename__ = "daily_automation_runs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    batch_id: Mapped[UUID | None] = mapped_column(ForeignKey("batches.id"), index=True)
    run_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending", index=True)
    students_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tasks_generated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    verifications_triggered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    plans_adapted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AIInteractionLogModel(Base):
    """Audit log for every AI model call (cost tracking + debugging)."""
    __tablename__ = "ai_interaction_logs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    student_id: Mapped[UUID | None] = mapped_column(ForeignKey("students.id"), index=True)
    interaction_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    ai_model: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    request_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True
    )


class StudentProjectProfileModel(Base, TimestampMixin):
    """Durable project-defense profile for autonomous task generation."""
    __tablename__ = "student_project_profiles"
    __table_args__ = (UniqueConstraint("student_id", name="uq_student_project_profiles_student_id"),)

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    student_id: Mapped[UUID] = mapped_column(ForeignKey("students.id"), index=True, nullable=False)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    github_repository: Mapped[str] = mapped_column(String(500), nullable=False)
    deployed_url: Mapped[str | None] = mapped_column(String(500))
    project_title: Mapped[str] = mapped_column(String(160), nullable=False)
    project_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tech_stack: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    languages: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    frameworks: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    database: Mapped[str | None] = mapped_column(String(120))
    architecture_summary: Mapped[str | None] = mapped_column(Text)
    current_strengths: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    current_weaknesses: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    skill_gaps: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    current_level: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
    mentor_notes: Mapped[str | None] = mapped_column(Text)
    analysis_version: Mapped[str] = mapped_column(String(80), nullable=False, default="project-profile.v1")
    last_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TaskAssignmentModel(Base, TimestampMixin):
    """One visible daily assignment per student per day."""
    __tablename__ = "task_assignments"
    __table_args__ = (UniqueConstraint("student_id", "assigned_on", name="uq_task_assignments_student_day"),)

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    batch_id: Mapped[UUID] = mapped_column(ForeignKey("batches.id"), index=True, nullable=False)
    student_id: Mapped[UUID] = mapped_column(ForeignKey("students.id"), index=True, nullable=False)
    task_id: Mapped[UUID] = mapped_column(ForeignKey("daily_tasks.id"), index=True, nullable=False)
    assigned_on: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="assigned")
    why_this_task: Mapped[str] = mapped_column(Text, nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    expected_deliverables: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    verification_strategy: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    difficulty: Mapped[str] = mapped_column(String(40), nullable=False, default="medium")
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    skills_tested: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    mentor_review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
