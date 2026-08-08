"""Pydantic schemas for Milestone 7 — Personalized 14-Day Learning Plans."""
from datetime import date, datetime
from uuid import UUID, uuid4

from pydantic import Field

from app.domain.enums import (
    AIInteractionType,
    AutomationRunStatus,
    DependencyType,
    EvidenceCollectedBy,
    EvidenceQuality,
    LearningPlanStatus,
    PlanDayStatus,
    ProfileAnalysisStatus,
    SkillConfidence,
    SubmissionEvidenceType,
    VerificationStatus,
)
from app.schemas.base import ApiModel, Entity


# ---------------------------------------------------------------------------
# Student Profile Analysis
# ---------------------------------------------------------------------------


class StudentProfileAnalysisCreate(ApiModel):
    student_id: UUID
    organization_id: UUID
    status: ProfileAnalysisStatus = ProfileAnalysisStatus.PENDING
    raw_profile: dict = Field(default_factory=dict)
    observed_skills: list[dict] = Field(default_factory=list)
    inferred_skills: list[dict] = Field(default_factory=list)
    unknown_areas: list[str] = Field(default_factory=list)
    learning_style: str | None = None
    risk_factors: list[dict] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    ai_model: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    generated_at: datetime | None = None


class StudentProfileAnalysis(Entity, StudentProfileAnalysisCreate):
    pass


# ---------------------------------------------------------------------------
# Skill Assessment
# ---------------------------------------------------------------------------


class SkillAssessmentCreate(ApiModel):
    student_id: UUID
    organization_id: UUID
    profile_analysis_id: UUID | None = None
    dimension: str = Field(min_length=2, max_length=80)
    score: int = Field(ge=0, le=100)
    evidence_sources: list[dict] = Field(default_factory=list)
    confidence: SkillConfidence = SkillConfidence.UNKNOWN
    assessed_at: datetime = Field(default_factory=datetime.utcnow)


class SkillAssessment(Entity, SkillAssessmentCreate):
    pass


# ---------------------------------------------------------------------------
# Learning Plan
# ---------------------------------------------------------------------------


class LearningPlanCreate(ApiModel):
    student_id: UUID
    organization_id: UUID
    batch_id: UUID
    status: LearningPlanStatus = LearningPlanStatus.DRAFT
    start_date: date
    end_date: date
    total_days: int = Field(default=14, ge=1, le=90)
    ai_model: str | None = None
    generation_prompt_hash: str | None = Field(default=None, max_length=64)


class LearningPlan(Entity, LearningPlanCreate):
    pass


# ---------------------------------------------------------------------------
# Learning Plan Day
# ---------------------------------------------------------------------------


class LearningPlanDayCreate(ApiModel):
    plan_id: UUID
    student_id: UUID
    organization_id: UUID
    day_number: int = Field(ge=1, le=90)
    scheduled_date: date
    status: PlanDayStatus = PlanDayStatus.LOCKED
    task_id: UUID | None = None
    target_skills: list[str] = Field(default_factory=list)
    unlock_condition: dict | None = None
    completed_at: datetime | None = None
    score: int | None = Field(default=None, ge=0, le=100)
    notes: str | None = Field(default=None, max_length=2000)


class LearningPlanDay(Entity, LearningPlanDayCreate):
    pass


# ---------------------------------------------------------------------------
# Task Dependency
# ---------------------------------------------------------------------------


class TaskDependencyCreate(ApiModel):
    task_id: UUID
    depends_on_task_id: UUID
    organization_id: UUID
    dependency_type: DependencyType = DependencyType.PREREQUISITE


class TaskDependency(Entity, TaskDependencyCreate):
    pass


# ---------------------------------------------------------------------------
# Submission Evidence
# ---------------------------------------------------------------------------


class SubmissionEvidenceCreate(ApiModel):
    submission_id: UUID
    organization_id: UUID
    evidence_type: SubmissionEvidenceType
    url: str | None = Field(default=None, max_length=500)
    content: str | None = None
    metadata: dict = Field(default_factory=dict)
    collected_by: EvidenceCollectedBy = EvidenceCollectedBy.STUDENT
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    quality_score: int | None = Field(default=None, ge=0, le=100)


class SubmissionEvidence(Entity, SubmissionEvidenceCreate):
    pass


# ---------------------------------------------------------------------------
# Verification Result
# ---------------------------------------------------------------------------


class VerificationResultCreate(ApiModel):
    submission_id: UUID
    organization_id: UUID
    plan_day_id: UUID | None = None
    status: VerificationStatus = VerificationStatus.PENDING
    overall_score: int | None = Field(default=None, ge=0, le=100)
    verdict: str | None = Field(default=None, max_length=80)
    ai_model: str | None = None
    verification_prompt_version: str | None = Field(default=None, max_length=80)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    escalate_to_mentor: bool = False
    escalation_reason: str | None = None


class VerificationResult(Entity, VerificationResultCreate):
    pass


# ---------------------------------------------------------------------------
# Verification Evidence
# ---------------------------------------------------------------------------


class VerificationEvidenceCreate(ApiModel):
    verification_result_id: UUID
    organization_id: UUID
    evidence_type: str = Field(min_length=2, max_length=80)
    source: str = Field(min_length=2, max_length=80)
    content: dict = Field(default_factory=dict)
    quality: EvidenceQuality = EvidenceQuality.MODERATE
    weight: float = Field(default=1.0, ge=0.0, le=1.0)


class VerificationEvidence(Entity, VerificationEvidenceCreate):
    pass


# ---------------------------------------------------------------------------
# Student Progress
# ---------------------------------------------------------------------------


class StudentProgressCreate(ApiModel):
    student_id: UUID
    organization_id: UUID
    plan_id: UUID | None = None
    snapshot_date: date
    day_number: int | None = None
    days_completed: int = Field(default=0, ge=0)
    days_remaining: int = Field(default=14, ge=0)
    current_streak: int = Field(default=0, ge=0)
    longest_streak: int = Field(default=0, ge=0)
    average_score: float | None = Field(default=None, ge=0.0, le=100.0)
    skill_velocity: dict = Field(default_factory=dict)
    completed_task_ids: list[UUID] = Field(default_factory=list)


class StudentProgress(Entity, StudentProgressCreate):
    pass


# ---------------------------------------------------------------------------
# Daily Automation Run
# ---------------------------------------------------------------------------


class DailyAutomationRunCreate(ApiModel):
    organization_id: UUID
    batch_id: UUID | None = None
    run_date: date
    status: AutomationRunStatus = AutomationRunStatus.PENDING
    students_processed: int = Field(default=0, ge=0)
    tasks_generated: int = Field(default=0, ge=0)
    verifications_triggered: int = Field(default=0, ge=0)
    plans_adapted: int = Field(default=0, ge=0)
    errors: list[dict] = Field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class DailyAutomationRun(Entity, DailyAutomationRunCreate):
    pass


# ---------------------------------------------------------------------------
# AI Interaction Log  (no updated_at — append-only audit record)
# ---------------------------------------------------------------------------


class AIInteractionLogCreate(ApiModel):
    organization_id: UUID
    student_id: UUID | None = None
    interaction_type: AIInteractionType
    ai_model: str = Field(min_length=1, max_length=80)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    success: bool = True
    error_message: str | None = None
    request_hash: str | None = Field(default=None, max_length=64)
    metadata: dict = Field(default_factory=dict)


class AIInteractionLog(ApiModel):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    organization_id: UUID
    student_id: UUID | None = None
    interaction_type: AIInteractionType
    ai_model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int | None = None
    success: bool = True
    error_message: str | None = None
    request_hash: str | None = None
    metadata: dict = Field(default_factory=dict)
