"""Frontend-facing read endpoints.

These endpoints power the student dashboard, mentor dashboard, and list/detail
views. They intentionally go through the application service so production uses
the active PostgreSQL repository path instead of the development InMemoryStore.
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_async_service, get_current_user
from app.application.async_daily_loop_service import AsyncDailyLoopService
from app.domain.enums import UserRole
from app.schemas.auth import CurrentUser
from app.shared.exceptions import ForbiddenException

router = APIRouter(tags=["frontend"])

_Service = Annotated[AsyncDailyLoopService, Depends(get_async_service)]
_CurrentUser = Annotated[CurrentUser, Depends(get_current_user)]


@router.get("/me/student")
async def get_my_student_profile(current_user: _CurrentUser, service: _Service):
    """Return the student profile for the currently logged-in user."""
    return await service.get_student_by_email(current_user.email, current_user.organization_id)


@router.get("/me/tasks")
async def list_my_tasks(current_user: _CurrentUser, service: _Service):
    """Return all tasks assigned to the current student."""
    student = await service.get_student_by_email(current_user.email, current_user.organization_id)
    return await service.uow.tasks.list_for_student(student.id)


@router.get("/me/submissions")
async def list_my_submissions(
    current_user: _CurrentUser,
    service: _Service,
    task_id: UUID | None = Query(default=None),
):
    """Return submissions made by the current student."""
    student = await service.get_student_by_email(current_user.email, current_user.organization_id)
    submissions = await service.list_submissions_for_student(student.id)
    if task_id:
        submissions = [s for s in submissions if s.task_id == task_id]
    return sorted(submissions, key=lambda s: s.created_at, reverse=True)


@router.get("/students")
async def list_students(
    current_user: _CurrentUser,
    service: _Service,
    org_id: UUID | None = Query(default=None),
):
    """List students for an organisation. Restricted to mentors and admins."""
    if not current_user.can(
        UserRole.SUPER_ADMIN,
        UserRole.ORGANIZATION_ADMIN,
        UserRole.PROGRAM_MANAGER,
        UserRole.MENTOR,
    ):
        raise ForbiddenException("Insufficient permissions to list students")

    effective_org = org_id or current_user.organization_id
    if effective_org is None:
        raise ForbiddenException("Organization scope is required to list students")
    return await service.list_students_for_org(effective_org)


@router.get("/students/{student_id}")
async def get_student(student_id: UUID, current_user: _CurrentUser, service: _Service):
    student = await service.get_student(student_id)
    if (
        current_user.organization_id is not None
        and student.organization_id != current_user.organization_id
    ):
        raise ForbiddenException("Student belongs to a different organisation")
    return student


@router.get("/students/{student_id}/tasks")
async def list_student_tasks(student_id: UUID, current_user: _CurrentUser, service: _Service):
    if not current_user.can(
        UserRole.SUPER_ADMIN,
        UserRole.ORGANIZATION_ADMIN,
        UserRole.PROGRAM_MANAGER,
        UserRole.MENTOR,
        UserRole.SYSTEM,
    ):
        raise ForbiddenException("Insufficient permissions")
    student = await service.get_student(student_id)
    return await service.uow.tasks.list_for_student(student.id)


@router.get("/students/{student_id}/submissions")
async def list_student_submissions(student_id: UUID, current_user: _CurrentUser, service: _Service):
    if not current_user.can(
        UserRole.SUPER_ADMIN,
        UserRole.ORGANIZATION_ADMIN,
        UserRole.PROGRAM_MANAGER,
        UserRole.MENTOR,
        UserRole.SYSTEM,
    ):
        raise ForbiddenException("Insufficient permissions")
    submissions = await service.list_submissions_for_student(student_id)
    return sorted(submissions, key=lambda s: s.created_at, reverse=True)


@router.get("/batches")
async def list_batches(
    current_user: _CurrentUser,
    service: _Service,
    org_id: UUID | None = Query(default=None),
):
    effective_org = org_id or current_user.organization_id
    if effective_org is None:
        raise ForbiddenException("Organization scope is required to list batches")
    return await service.list_batches_for_org(effective_org)


@router.get("/batches/{batch_id}/dashboard")
async def batch_dashboard(
    batch_id: UUID,
    service: _Service,
    current_user: _CurrentUser,
):
    """Mentor dashboard: stats + per-student status for a batch."""
    if not current_user.can(
        UserRole.SUPER_ADMIN,
        UserRole.ORGANIZATION_ADMIN,
        UserRole.PROGRAM_MANAGER,
        UserRole.MENTOR,
        UserRole.SYSTEM,
    ):
        raise ForbiddenException("Insufficient permissions")
    return await service.build_daily_summary(batch_id)
