"""Structured schemas for AI evaluation output (Milestone 5).

These are separate from the existing EvaluationCreate/Evaluation in core.py.
Both coexist: core.py handles the legacy simple schema; this module handles
the rich 9-dimension rubric schema.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import ConfigDict, Field

from app.schemas.base import ApiModel, Entity


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EvaluationState(StrEnum):
    PENDING = "pending"
    CONTEXT_BUILDING = "context_building"
    EVALUATING = "evaluating"
    VALIDATING = "validating"
    COMPLETED = "completed"
    NEEDS_HUMAN_REVIEW = "needs_human_review"
    FAILED = "failed"


class CriterionStatus(StrEnum):
    PASS = "PASS"
    PARTIAL = "PARTIAL"
    FAIL = "FAIL"
    CANNOT_VERIFY = "CANNOT_VERIFY"


class EvidenceSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class SubmissionVerdict(StrEnum):
    SOLVED = "SOLVED"
    PARTIALLY_SOLVED = "PARTIALLY_SOLVED"
    NOT_SOLVED = "NOT_SOLVED"
    NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"


class MentorDecision(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    OVERRIDE_SCORE = "OVERRIDE_SCORE"


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


class EvidenceItem(ApiModel):
    """A single piece of evidence from the AI evaluation."""
    file: str = Field(max_length=800)
    line: int | None = None
    type: str = Field(max_length=80)  # "correctness", "security", "quality", etc.
    severity: EvidenceSeverity = EvidenceSeverity.INFO
    description: str = Field(min_length=5, max_length=1000)


# ---------------------------------------------------------------------------
# Per-criterion result
# ---------------------------------------------------------------------------


class CriterionResult(ApiModel):
    criterion: str = Field(max_length=500)
    status: CriterionStatus
    evidence: list[str] = Field(default_factory=list, max_length=10)
    notes: str = ""


# ---------------------------------------------------------------------------
# Dimension scores (one per rubric dimension)
# ---------------------------------------------------------------------------


class DimensionScore(ApiModel):
    score: float = Field(ge=0.0, le=10.0)
    reason: str = Field(min_length=1, max_length=1000)
    evidence: list[EvidenceItem] = Field(default_factory=list, max_length=10)


class EvaluationDimensions(ApiModel):
    correctness: DimensionScore
    task_completeness: DimensionScore
    code_quality: DimensionScore
    architecture: DimensionScore
    security: DimensionScore
    performance: DimensionScore
    maintainability: DimensionScore
    edge_cases: DimensionScore
    testing: DimensionScore


# ---------------------------------------------------------------------------
# Full evaluation result (the structured AI output)
# ---------------------------------------------------------------------------


class EvaluationResult(ApiModel):
    status: SubmissionVerdict
    overall_score: float = Field(ge=0.0, le=10.0)
    confidence: float = Field(ge=0.0, le=1.0)
    dimensions: EvaluationDimensions
    acceptance_criteria_results: list[CriterionResult] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list, max_length=20)
    issues: list[EvidenceItem] = Field(default_factory=list, max_length=30)
    missing_requirements: list[str] = Field(default_factory=list, max_length=20)
    security_concerns: list[EvidenceItem] = Field(default_factory=list, max_length=20)
    performance_concerns: list[EvidenceItem] = Field(default_factory=list, max_length=20)
    suggested_improvements: list[str] = Field(default_factory=list, max_length=20)
    mentor_attention_required: bool = False
    mentor_attention_reasons: list[str] = Field(default_factory=list, max_length=10)
    summary: str = Field(min_length=1, max_length=3000)


# ---------------------------------------------------------------------------
# Raw AI output schema (relaxed for parsing — extra fields ignored)
# ---------------------------------------------------------------------------


class _RawDimensionScore(ApiModel):
    model_config = ConfigDict(extra="ignore", use_enum_values=True)
    score: float = Field(ge=0.0, le=10.0, default=5.0)
    reason: str = ""
    evidence: list[Any] = Field(default_factory=list)


class _RawDimensions(ApiModel):
    model_config = ConfigDict(extra="ignore", use_enum_values=True)
    correctness: _RawDimensionScore = Field(default_factory=_RawDimensionScore)
    task_completeness: _RawDimensionScore = Field(default_factory=_RawDimensionScore)
    code_quality: _RawDimensionScore = Field(default_factory=_RawDimensionScore)
    architecture: _RawDimensionScore = Field(default_factory=_RawDimensionScore)
    security: _RawDimensionScore = Field(default_factory=_RawDimensionScore)
    performance: _RawDimensionScore = Field(default_factory=_RawDimensionScore)
    maintainability: _RawDimensionScore = Field(default_factory=_RawDimensionScore)
    edge_cases: _RawDimensionScore = Field(default_factory=_RawDimensionScore)
    testing: _RawDimensionScore = Field(default_factory=_RawDimensionScore)


class _RawCriterionResult(ApiModel):
    model_config = ConfigDict(extra="ignore", use_enum_values=True)
    criterion: str = ""
    status: str = "CANNOT_VERIFY"
    evidence: list[str] = Field(default_factory=list)
    notes: str = ""


class _RawEvidenceItem(ApiModel):
    model_config = ConfigDict(extra="ignore", use_enum_values=True)
    file: str = ""
    line: int | None = None
    type: str = "quality"
    severity: str = "info"
    description: str = ""


class RawEvaluationResult(ApiModel):
    """Permissive schema for parsing AI JSON output — extra fields are ignored."""
    model_config = ConfigDict(extra="ignore", use_enum_values=True)

    status: str = "NEEDS_HUMAN_REVIEW"
    overall_score: float = Field(ge=0.0, le=10.0, default=5.0)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    dimensions: _RawDimensions = Field(default_factory=_RawDimensions)
    acceptance_criteria_results: list[_RawCriterionResult] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    issues: list[_RawEvidenceItem] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    security_concerns: list[_RawEvidenceItem] = Field(default_factory=list)
    performance_concerns: list[_RawEvidenceItem] = Field(default_factory=list)
    suggested_improvements: list[str] = Field(default_factory=list)
    mentor_attention_required: bool = False
    mentor_attention_reasons: list[str] = Field(default_factory=list)
    summary: str = "AI evaluation completed."


# ---------------------------------------------------------------------------
# Evaluation record (stored in AIEvaluationStore)
# ---------------------------------------------------------------------------


class EvaluationRecord(Entity):
    submission_id: UUID
    organization_id: UUID
    task_id: UUID
    state: EvaluationState = EvaluationState.PENDING
    result: EvaluationResult | None = None
    provider: str = ""
    model: str = ""
    prompt_version: str = ""
    context_hash: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0
    error: str | None = None
    # Mentor review fields
    mentor_decision: MentorDecision | None = None
    mentor_feedback: str | None = None
    mentor_id: UUID | None = None
    reviewed_at: datetime | None = None
    mentor_override_score: float | None = None


# ---------------------------------------------------------------------------
# API request/response schemas
# ---------------------------------------------------------------------------


class EvaluationRequest(ApiModel):
    force_reevaluate: bool = False


class MentorReviewRequest(ApiModel):
    decision: MentorDecision
    feedback: str = Field(min_length=1, max_length=3000)
    override_score: float | None = Field(default=None, ge=0.0, le=10.0)


class EvaluationResponse(ApiModel):
    evaluation_id: UUID
    submission_id: UUID
    state: EvaluationState
    result: EvaluationResult | None
    provider: str
    model: str
    mock_mode: bool
    context_hash: str
    input_tokens: int
    output_tokens: int
    duration_ms: int
    error: str | None
    created_at: datetime
    updated_at: datetime
    mentor_decision: MentorDecision | None = None
    mentor_feedback: str | None = None
