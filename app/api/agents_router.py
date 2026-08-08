"""AI agent routes.

Endpoints:
- POST /submissions/{submission_id}/ai-evaluate   — AI evaluation of a submission
- POST /students/{student_id}/suggest-task         — AI-generated task suggestion
"""
from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.agents.orchestrator import get_orchestrator
from app.api.dependencies import get_async_service, get_current_user
from app.application.async_daily_loop_service import AsyncDailyLoopService
from app.domain.enums import UserRole
from app.schemas.auth import CurrentUser
from app.schemas.base import ApiModel
from app.shared.exceptions import UnauthorizedException

router = APIRouter(tags=["ai-agents"])

_Service = Annotated[AsyncDailyLoopService, Depends(get_async_service)]
_CurrentUser = Annotated[CurrentUser, Depends(get_current_user)]


@router.post("/submissions/{submission_id}/ai-evaluate", tags=["evaluations"])
async def ai_evaluate_submission(
    submission_id: UUID,
    service: _Service,
    current_user: _CurrentUser,
):
    """Run AI evaluation on a submission.

    Uses the configured Anthropic model to assess the submission against the
    task acceptance criteria.  Falls back to deterministic bootstrap results
    when ``ANTHROPIC_API_KEY`` is not configured.

    Restricted to SUPER_ADMIN, MENTOR, and AI_AGENT roles.
    """
    if not current_user.can(
        UserRole.SUPER_ADMIN, UserRole.MENTOR, UserRole.AI_AGENT
    ):
        raise UnauthorizedException("Insufficient permissions to run AI evaluation")
    return await service.ai_evaluate_submission(submission_id, get_orchestrator())


class SuggestTaskRequest(ApiModel):
    project_id: UUID
    batch_id: UUID
    due_on: date


@router.post(
    "/students/{student_id}/suggest-task",
    status_code=status.HTTP_201_CREATED,
    tags=["tasks"],
)
async def suggest_task(
    student_id: UUID,
    payload: SuggestTaskRequest,
    service: _Service,
    current_user: _CurrentUser,
):
    """Generate and persist an AI-suggested daily task for a student.

    Requires ``ANTHROPIC_API_KEY`` to be configured; returns 500 when not set.

    Restricted to SUPER_ADMIN, ORGANIZATION_ADMIN, PROGRAM_MANAGER, MENTOR,
    and AI_AGENT roles.
    """
    if not current_user.can(
        UserRole.SUPER_ADMIN,
        UserRole.ORGANIZATION_ADMIN,
        UserRole.PROGRAM_MANAGER,
        UserRole.MENTOR,
        UserRole.AI_AGENT,
    ):
        raise UnauthorizedException("Insufficient permissions to generate a task")
    return await service.suggest_task(
        student_id=student_id,
        project_id=payload.project_id,
        batch_id=payload.batch_id,
        due_on=payload.due_on,
        orchestrator=get_orchestrator(),
    )
