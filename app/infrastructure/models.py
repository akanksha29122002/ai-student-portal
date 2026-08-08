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

