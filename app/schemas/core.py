from datetime import date
from uuid import UUID

from pydantic import Field, HttpUrl, model_validator

from app.domain.enums import (
    EvaluationKind,
    EvaluationVerdict,
    MentorReviewDecision,
    SelfStatus,
    SubmissionStatus,
    TaskType,
    Track,
)
from app.schemas.base import ApiModel, Entity


class OrganizationCreate(ApiModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")


class Organization(Entity, OrganizationCreate):
    pass


class BatchCreate(ApiModel):
    organization_id: UUID
    name: str = Field(min_length=2, max_length=160)
    starts_on: date
    ends_on: date

    @model_validator(mode="after")
    def validate_dates(self):
        if self.ends_on < self.starts_on:
            raise ValueError("ends_on must be on or after starts_on")
        return self


class Batch(Entity, BatchCreate):
    pass


class StudentCreate(ApiModel):
    organization_id: UUID
    batch_id: UUID
    full_name: str = Field(min_length=2, max_length=160)
    email: str = Field(min_length=5, max_length=254)
    track: Track = Track.TRACK_A
    mentor_id: UUID | None = None


class Student(Entity, StudentCreate):
    consecutive_missed_days: int = 0


class ProjectCreate(ApiModel):
    organization_id: UUID
    student_id: UUID
    name: str = Field(min_length=2, max_length=160)
    repository_url: HttpUrl
    summary: str | None = Field(default=None, max_length=2000)


class Project(Entity, ProjectCreate):
    repository_url: str


class TaskCreate(ApiModel):
    organization_id: UUID
    batch_id: UUID
    student_id: UUID
    project_id: UUID
    task_type: TaskType
    title: str = Field(min_length=3, max_length=180)
    problem_statement: str = Field(min_length=10, max_length=4000)
    acceptance_criteria: list[str] = Field(min_length=1, max_length=10)
    expected_concepts: list[str] = Field(default_factory=list, max_length=12)
    due_on: date


class Task(Entity, TaskCreate):
    pass


class SubmissionCreate(ApiModel):
    organization_id: UUID
    task_id: UUID
    student_id: UUID
    self_status: SelfStatus
    repository_url: HttpUrl | None = None
    commit_url: HttpUrl | None = None
    transcript_url: HttpUrl | None = None
    transcript_text: str | None = Field(default=None, max_length=30000)
    approach_note: str | None = Field(default=None, max_length=1200)

    @model_validator(mode="after")
    def validate_submission_material(self):
        has_code = self.commit_url is not None or self.repository_url is not None
        has_transcript = self.transcript_url is not None or bool(self.transcript_text)
        if not has_code and not has_transcript and self.self_status != SelfStatus.SKIPPED:
            raise ValueError("submission must include code evidence or transcript evidence unless skipped")
        return self


class Submission(Entity, SubmissionCreate):
    repository_url: str | None = None
    commit_url: str | None = None
    transcript_url: str | None = None
    status: SubmissionStatus = SubmissionStatus.RECEIVED


class Evidence(ApiModel):
    type: str = Field(min_length=2, max_length=80)
    reference: str = Field(min_length=1, max_length=500)
    summary: str = Field(min_length=1, max_length=1000)


class EvaluationCreate(ApiModel):
    organization_id: UUID
    submission_id: UUID
    kind: EvaluationKind
    verdict: EvaluationVerdict
    score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    evidence: list[Evidence] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list, max_length=20)
    mentor_note: str = Field(min_length=1, max_length=2000)
    student_feedback_draft: str = Field(min_length=1, max_length=2000)
    recommended_next_action: str = Field(min_length=1, max_length=80)
    prompt_version: str = Field(default="deterministic-bootstrap.v1", max_length=80)


class Evaluation(Entity, EvaluationCreate):
    pass


class MentorReviewCreate(ApiModel):
    organization_id: UUID
    evaluation_id: UUID
    mentor_id: UUID
    decision: MentorReviewDecision
    final_feedback: str = Field(min_length=1, max_length=2000)
    override_reason: str | None = Field(default=None, max_length=1200)


class MentorReview(Entity, MentorReviewCreate):
    pass

