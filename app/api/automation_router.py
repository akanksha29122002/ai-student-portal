"""Automation APIs for autonomous daily workflow."""
from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import Field

from app.api.dependencies import get_async_service, get_current_user
from app.application.async_daily_loop_service import AsyncDailyLoopService
from app.domain.enums import UserRole
from app.schemas.auth import CurrentUser
from app.schemas.base import ApiModel
from app.services.daily_assignment_service import DailyAssignmentService
from app.shared.exceptions import ForbiddenException, NotFoundException

router = APIRouter(tags=["automation"])

_Service = Annotated[AsyncDailyLoopService, Depends(get_async_service)]
_CurrentUser = Annotated[CurrentUser, Depends(get_current_user)]


class RunDailyRequest(ApiModel):
    organization_id: UUID
    batch_id: UUID
    assigned_on: date = Field(default_factory=date.today)


@router.post("/automation/run-daily")
async def run_daily_automation(
    payload: RunDailyRequest,
    service: _Service,
    current_user: _CurrentUser,
):
    if not current_user.can(UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.PROGRAM_MANAGER, UserRole.MENTOR):
        raise ForbiddenException("Insufficient permissions to run daily automation")
    if current_user.organization_id is not None and payload.organization_id != current_user.organization_id:
        raise ForbiddenException("Cannot run automation outside your organization")
    assignment_service = DailyAssignmentService(service.uow)
    return await assignment_service.run_for_batch(payload.organization_id, payload.batch_id, payload.assigned_on)


@router.get("/automation/status")
async def automation_status(current_user: _CurrentUser):
    if not current_user.can(UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.PROGRAM_MANAGER, UserRole.MENTOR):
        raise ForbiddenException("Insufficient permissions")
    return {"status": "ready", "mode": "manual_or_scheduler", "daily_assignment": "enabled"}


@router.get("/me/today")
async def get_my_today(service: _Service, current_user: _CurrentUser):
    student = await service.get_student_by_email(current_user.email, current_user.organization_id)
    assignment = await service.uow.task_assignments.get_for_student_on(student.id, date.today())
    if assignment is None:
        raise NotFoundException("No task assigned for today")
    task = await service.uow.tasks.get(assignment.task_id)
    return {"assignment": assignment, "task": task}
