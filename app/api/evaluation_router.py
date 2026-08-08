"""AI Evaluation endpoints (Milestone 5).

POST /submissions/{submission_id}/evaluate
GET  /submissions/{submission_id}/evaluation
GET  /evaluations/{evaluation_id}
POST /evaluations/{evaluation_id}/mentor-review
GET  /evaluations/                              (list — mentor dashboard)
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status

from app.ai.context_builder import ContextBuilder
from app.ai.engine import EvaluationEngine
from app.ai.provider import get_ai_provider
from app.ai.rubric import DEFAULT_CONFIDENCE_THRESHOLD
from app.ai.schemas import (
    EvaluationRecord,
    EvaluationRequest,
    EvaluationResponse,
    EvaluationState,
    MentorDecision,
    MentorReviewRequest,
)
from app.ai.store import AIEvaluationStore, get_ai_store
from app.api.dependencies import get_async_service, get_current_user
from app.application.async_daily_loop_service import AsyncDailyLoopService
from app.core.config import settings
from app.domain.enums import UserRole
from app.schemas.auth import CurrentUser
from app.shared.exceptions import ConflictException, ForbiddenException, NotFoundException, UnauthorizedException

logger = logging.getLogger("project_defense.api.evaluation_router")

router = APIRouter(tags=["evaluations-v2"])

_Service = Annotated[AsyncDailyLoopService, Depends(get_async_service)]
_CurrentUser = Annotated[CurrentUser, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Dependency factories
# ---------------------------------------------------------------------------


def _get_store() -> AIEvaluationStore:
    return get_ai_store()


_Store = Annotated[AIEvaluationStore, Depends(_get_store)]


# ---------------------------------------------------------------------------
# POST /submissions/{id}/evaluate
# ---------------------------------------------------------------------------


@router.post(
    "/submissions/{submission_id}/evaluate",
    response_model=EvaluationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger AI evaluation for a submission",
)
async def evaluate_submission(
    submission_id: UUID,
    payload: EvaluationRequest,
    background_tasks: BackgroundTasks,
    service: _Service,
    store: _Store,
    current_user: _CurrentUser,
) -> EvaluationResponse:
    """Start AI evaluation of a submission.

    - Requires SUPER_ADMIN, MENTOR, PROGRAM_MANAGER, or AI_AGENT role.
    - If an evaluation already exists with the same context hash and
      force_reevaluate=False, returns the existing result.
    - Synchronous mode (AI_EVALUATION_SYNC_MODE=true): runs inline.
    - Async mode: starts evaluation in background, returns 202 immediately.
    """
    if not current_user.can(
        UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN,
        UserRole.PROGRAM_MANAGER, UserRole.MENTOR, UserRole.AI_AGENT,
    ):
        raise UnauthorizedException("Insufficient permissions to run AI evaluation")

    submission = await service.uow.submissions.get(submission_id)
    if submission is None:
        raise NotFoundException("Submission not found")

    # Org isolation
    if (
        current_user.organization_id is not None
        and submission.organization_id != current_user.organization_id
    ):
        raise ForbiddenException("Submission belongs to a different organisation")

    task = await service.uow.tasks.get(submission.task_id)
    if task is None:
        raise NotFoundException("Task not found for submission")

    # Build context
    builder = ContextBuilder()
    commit, commit_files = await _fetch_commit_context(submission)
    context = builder.build(task, submission, commit, commit_files)

    # Deduplication: return existing if context hash unchanged and not forced
    if not payload.force_reevaluate:
        existing = store.find_by_context_hash(context.context_hash())
        if existing is None:
            existing = store.get_by_submission(submission_id)
            if (
                existing is not None
                and existing.context_hash == context.context_hash()
                and existing.state == EvaluationState.COMPLETED
            ):
                pass
            else:
                existing = None
        if existing is not None:
            logger.info(
                "Returning cached evaluation (same context hash)",
                extra={"evaluation_id": str(existing.id), "submission_id": str(submission_id)},
            )
            return _to_response(existing)

    # Create new record in PENDING state
    provider = get_ai_provider()
    record = EvaluationRecord(
        submission_id=submission_id,
        organization_id=submission.organization_id,
        task_id=task.id,
        state=EvaluationState.PENDING,
        provider=provider.provider_name(),
        model=provider.model_name(),
        context_hash=context.context_hash(),
    )
    record = store.create(record)

    engine = EvaluationEngine(
        provider=provider,
        store=store,
        confidence_threshold=_get_confidence_threshold(),
    )

    sync_mode = getattr(settings, "ai_evaluation_sync_mode", True)
    if sync_mode:
        record = await engine.evaluate(record, context)
    else:
        background_tasks.add_task(_run_evaluation_background, engine, record, context, store)

    return _to_response(record)


async def _run_evaluation_background(engine, record, context, store):
    try:
        await engine.evaluate(record, context)
    except Exception as exc:
        logger.error("Background evaluation failed: %s", exc, extra={"evaluation_id": str(record.id)})


# ---------------------------------------------------------------------------
# GET /submissions/{id}/evaluation
# ---------------------------------------------------------------------------


@router.get(
    "/submissions/{submission_id}/evaluation",
    response_model=EvaluationResponse,
    summary="Get the latest AI evaluation for a submission",
)
async def get_submission_evaluation(
    submission_id: UUID,
    store: _Store,
    service: _Service,
    current_user: _CurrentUser,
) -> EvaluationResponse:
    submission = await service.uow.submissions.get(submission_id)
    if submission is None:
        raise NotFoundException("Submission not found")

    if (
        current_user.role == UserRole.STUDENT
        and str(submission.student_id) != str(current_user.id)
    ):
        raise ForbiddenException("Cannot view another student's evaluation")

    if (
        current_user.organization_id is not None
        and submission.organization_id != current_user.organization_id
    ):
        raise ForbiddenException("Submission belongs to a different organisation")

    record = store.get_by_submission(submission_id)
    if record is None:
        raise NotFoundException("No evaluation found for this submission")

    return _to_response(record)


# ---------------------------------------------------------------------------
# GET /evaluations/{id}
# ---------------------------------------------------------------------------


@router.get(
    "/evaluations/{evaluation_id}",
    response_model=EvaluationResponse,
    summary="Get a specific evaluation by ID",
)
async def get_evaluation(
    evaluation_id: UUID,
    store: _Store,
    current_user: _CurrentUser,
) -> EvaluationResponse:
    record = store.get(evaluation_id)
    if record is None:
        raise NotFoundException("Evaluation not found")

    if (
        current_user.organization_id is not None
        and record.organization_id != current_user.organization_id
    ):
        raise ForbiddenException("Evaluation belongs to a different organisation")

    return _to_response(record)


# ---------------------------------------------------------------------------
# POST /evaluations/{id}/mentor-review
# ---------------------------------------------------------------------------


@router.post(
    "/evaluations/{evaluation_id}/mentor-review",
    response_model=EvaluationResponse,
    summary="Submit a mentor review decision for an evaluation",
)
async def submit_mentor_review(
    evaluation_id: UUID,
    payload: MentorReviewRequest,
    store: _Store,
    current_user: _CurrentUser,
) -> EvaluationResponse:
    """Mentor reviews and approves, rejects, or overrides the AI evaluation.

    Restricted to SUPER_ADMIN, ORGANIZATION_ADMIN, PROGRAM_MANAGER, MENTOR.
    """
    if not current_user.can(
        UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN,
        UserRole.PROGRAM_MANAGER, UserRole.MENTOR,
    ):
        raise ForbiddenException("Only mentors can submit evaluation reviews")

    record = store.get(evaluation_id)
    if record is None:
        raise NotFoundException("Evaluation not found")

    if (
        current_user.organization_id is not None
        and record.organization_id != current_user.organization_id
    ):
        raise ForbiddenException("Evaluation belongs to a different organisation")

    if record.state not in (EvaluationState.COMPLETED, EvaluationState.NEEDS_HUMAN_REVIEW):
        raise ConflictException(
            f"Cannot review evaluation in state {record.state!r}. "
            "Evaluation must be COMPLETED or NEEDS_HUMAN_REVIEW."
        )

    updates: dict = {
        "mentor_decision": payload.decision,
        "mentor_feedback": payload.feedback,
        "mentor_id": current_user.id,
        "reviewed_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    if payload.override_score is not None:
        updates["mentor_override_score"] = payload.override_score

    updated = record.model_copy(update=updates)
    updated = store.update(updated)

    logger.info(
        "Mentor review submitted",
        extra={
            "evaluation_id": str(evaluation_id),
            "decision": payload.decision,
            "mentor_id": str(current_user.id),
        },
    )
    return _to_response(updated)


# ---------------------------------------------------------------------------
# GET /evaluations/ (list for mentor dashboard)
# ---------------------------------------------------------------------------


@router.get(
    "/evaluations/",
    response_model=list[EvaluationResponse],
    summary="List evaluations for the current organisation (mentor dashboard)",
)
async def list_evaluations(
    store: _Store,
    current_user: _CurrentUser,
    needs_review_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[EvaluationResponse]:
    if not current_user.can(
        UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN,
        UserRole.PROGRAM_MANAGER, UserRole.MENTOR, UserRole.AI_AGENT,
    ):
        raise ForbiddenException("Insufficient permissions to list evaluations")

    org_id = current_user.organization_id
    if org_id is None:
        return []

    if needs_review_only:
        records = store.list_needs_review(org_id)
    else:
        records = store.list_for_org(org_id, limit=limit)

    return [_to_response(r) for r in records]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _fetch_commit_context(submission):
    """Try to load commit + files from GitHubMemoryStore using the commit URL."""
    commit_url = getattr(submission, "commit_url", None)
    if not commit_url:
        return None, []

    try:
        from app.api.github_router import _github_store
        # Parse SHA from URL like https://github.com/owner/repo/commit/<sha>
        url_str = str(commit_url)
        parts = url_str.rstrip("/").split("/")
        sha = parts[-1] if parts else None
        if not sha or len(sha) < 7:
            return None, []

        # Search across all repos for this SHA
        for repo in _github_store._repositories.values():
            commit = _github_store.get_commit_by_sha(repo.id, sha)
            if commit is not None:
                files = _github_store.get_commit_files(commit.id)
                return commit, files
    except Exception as exc:
        logger.debug("Could not load commit from GitHub store: %s", exc)

    return None, []


def _get_confidence_threshold() -> float:
    return getattr(settings, "ai_confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD)


def _to_response(record: EvaluationRecord) -> EvaluationResponse:
    provider_is_mock = record.provider in ("development_mock", "mock", "")
    return EvaluationResponse(
        evaluation_id=record.id,
        submission_id=record.submission_id,
        state=record.state,
        result=record.result,
        provider=record.provider or "unknown",
        model=record.model or "unknown",
        mock_mode=provider_is_mock,
        context_hash=record.context_hash,
        input_tokens=record.input_tokens,
        output_tokens=record.output_tokens,
        duration_ms=record.duration_ms,
        error=record.error,
        created_at=record.created_at,
        updated_at=record.updated_at,
        mentor_decision=record.mentor_decision,
        mentor_feedback=record.mentor_feedback,
    )
