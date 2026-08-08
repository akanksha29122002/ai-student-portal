"""Core types and fallback utilities shared by all AI agents."""
from __future__ import annotations

from typing import Protocol

from app.domain.enums import EvaluationKind, EvaluationVerdict
from app.integrations.github.schemas import CommitInfo
from app.schemas.base import ApiModel
from app.schemas.core import EvaluationCreate, Evidence, Project, Student, Submission, Task


class AgentContext(ApiModel):
    """All context needed by an evaluation agent."""

    task: Task
    submission: Submission
    commit_info: CommitInfo | None = None


class TaskGenContext(ApiModel):
    """Context passed to the task-generation agent."""

    student: Student
    project: Project
    previous_tasks: list[Task]


class EvaluationAgent(Protocol):
    """Async-callable that turns an AgentContext into an EvaluationCreate."""

    async def evaluate(self, context: AgentContext) -> EvaluationCreate: ...


def bootstrap_github_evaluation(context: AgentContext) -> EvaluationCreate:
    """Deterministic fallback for GitHub-commit submissions when AI is unavailable."""
    s = context.submission
    return EvaluationCreate(
        organization_id=s.organization_id,
        submission_id=s.id,
        kind=EvaluationKind.GITHUB_COMMIT,
        verdict=EvaluationVerdict.NEEDS_HUMAN_REVIEW,
        score=60,
        confidence=0.45,
        evidence=[Evidence(
            type="commit_url",
            reference=str(s.commit_url or ""),
            summary="Commit URL submitted; AI evaluation not configured.",
        )],
        flags=["ai_evaluation_not_configured"],
        mentor_note="Coding submission received. Configure ANTHROPIC_API_KEY for AI evaluation.",
        student_feedback_draft="Your submission was received and is queued for mentor review.",
        recommended_next_action="mentor_review_required",
        prompt_version="deterministic-bootstrap.v1",
    )


def bootstrap_transcript_evaluation(context: AgentContext) -> EvaluationCreate:
    """Deterministic fallback for transcript submissions when AI is unavailable."""
    s = context.submission
    return EvaluationCreate(
        organization_id=s.organization_id,
        submission_id=s.id,
        kind=EvaluationKind.TRANSCRIPT,
        verdict=EvaluationVerdict.NEEDS_HUMAN_REVIEW,
        score=60,
        confidence=0.45,
        evidence=[Evidence(
            type="transcript",
            reference=str(s.transcript_url or "inline_transcript"),
            summary="Transcript submitted; AI evaluation not configured.",
        )],
        flags=["ai_evaluation_not_configured"],
        mentor_note="Transcript submitted. Configure ANTHROPIC_API_KEY for AI evaluation.",
        student_feedback_draft="Your transcript was received and is queued for mentor review.",
        recommended_next_action="mentor_review_required",
        prompt_version="deterministic-bootstrap.v1",
    )
