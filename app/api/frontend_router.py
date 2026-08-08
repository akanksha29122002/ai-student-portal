"""Read-only list endpoints for the frontend UI.

These endpoints power the student dashboard, mentor dashboard, and
all list/detail views. They work with both in-memory (demo) and
PostgreSQL (production) stores.
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_current_user, get_async_service, _dev_store
from app.application.async_daily_loop_service import AsyncDailyLoopService
from app.domain.enums import UserRole
from app.schemas.auth import CurrentUser
from app.shared.exceptions import ForbiddenException, NotFoundException

router = APIRouter(tags=["frontend"])

_Service = Annotated[AsyncDailyLoopService, Depends(get_async_service)]
_CurrentUser = Annotated[CurrentUser, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# /me/student — current user's student profile
# ---------------------------------------------------------------------------

@router.get("/me/student")
async def get_my_student_profile(current_user: _CurrentUser):
    """Return the student profile for the currently logged-in user."""
    store = _dev_store
    student = store.get_student_by_email(current_user.email)
    if student is None:
        raise NotFoundException("No student profile found for this user")
    return student


# ---------------------------------------------------------------------------
# /me/tasks — tasks for current student
# ---------------------------------------------------------------------------

@router.get("/me/tasks")
async def list_my_tasks(current_user: _CurrentUser):
    """Return all tasks assigned to the current student."""
    store = _dev_store
    student = store.get_student_by_email(current_user.email)
    if student is None:
        raise NotFoundException("No student profile found for this user")
    return store.list_student_tasks(student.id)


# ---------------------------------------------------------------------------
# /me/submissions — submissions by current student
# ---------------------------------------------------------------------------

@router.get("/me/submissions")
async def list_my_submissions(
    current_user: _CurrentUser,
    task_id: UUID | None = Query(default=None),
):
    """Return submissions made by the current student."""
    store = _dev_store
    student = store.get_student_by_email(current_user.email)
    if student is None:
        raise NotFoundException("No student profile found for this user")
    subs = store.list_submissions_for_student(student.id)
    if task_id:
        subs = [s for s in subs if s.task_id == task_id]
    # newest first
    return sorted(subs, key=lambda s: s.created_at, reverse=True)


# ---------------------------------------------------------------------------
# /students — list students for org (mentor/admin)
# ---------------------------------------------------------------------------

@router.get("/students")
async def list_students(
    current_user: _CurrentUser,
    org_id: UUID | None = Query(default=None),
):
    """List students for an organisation. Restricted to mentors and admins."""
    if not current_user.can(
        UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN,
        UserRole.PROGRAM_MANAGER, UserRole.MENTOR,
    ):
        raise ForbiddenException("Insufficient permissions to list students")

    store = _dev_store
    effective_org = org_id or current_user.organization_id
    if effective_org is None:
        # SYSTEM user — return all students
        return list(store.students.values())
    return store.list_students_for_org(effective_org)


# ---------------------------------------------------------------------------
# /students/{id} — get a specific student
# ---------------------------------------------------------------------------

@router.get("/students/{student_id}")
async def get_student(student_id: UUID, current_user: _CurrentUser):
    store = _dev_store
    student = store.get_student(student_id)
    if student is None:
        raise NotFoundException("Student not found")
    if (
        current_user.organization_id is not None
        and student.organization_id != current_user.organization_id
    ):
        raise ForbiddenException("Student belongs to a different organisation")
    return student


# ---------------------------------------------------------------------------
# /students/{id}/tasks — tasks for a specific student (mentor view)
# ---------------------------------------------------------------------------

@router.get("/students/{student_id}/tasks")
async def list_student_tasks(student_id: UUID, current_user: _CurrentUser):
    if not current_user.can(
        UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN,
        UserRole.PROGRAM_MANAGER, UserRole.MENTOR, UserRole.SYSTEM,
    ):
        raise ForbiddenException("Insufficient permissions")
    store = _dev_store
    student = store.get_student(student_id)
    if student is None:
        raise NotFoundException("Student not found")
    return store.list_student_tasks(student.id)


# ---------------------------------------------------------------------------
# /students/{id}/submissions — submissions for a specific student
# ---------------------------------------------------------------------------

@router.get("/students/{student_id}/submissions")
async def list_student_submissions(student_id: UUID, current_user: _CurrentUser):
    if not current_user.can(
        UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN,
        UserRole.PROGRAM_MANAGER, UserRole.MENTOR, UserRole.SYSTEM,
    ):
        raise ForbiddenException("Insufficient permissions")
    store = _dev_store
    subs = store.list_submissions_for_student(student_id)
    return sorted(subs, key=lambda s: s.created_at, reverse=True)


# ---------------------------------------------------------------------------
# /batches — list batches for org
# ---------------------------------------------------------------------------

@router.get("/batches")
async def list_batches(
    current_user: _CurrentUser,
    org_id: UUID | None = Query(default=None),
):
    store = _dev_store
    effective_org = org_id or current_user.organization_id
    if effective_org is None:
        return list(store.batches.values())
    return store.list_batches_for_org(effective_org)


# ---------------------------------------------------------------------------
# /batches/{id}/dashboard — mentor dashboard summary for a batch
# ---------------------------------------------------------------------------

@router.get("/batches/{batch_id}/dashboard")
async def batch_dashboard(
    batch_id: UUID,
    service: _Service,
    current_user: _CurrentUser,
):
    """Mentor dashboard: stats + per-student status for a batch."""
    if not current_user.can(
        UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN,
        UserRole.PROGRAM_MANAGER, UserRole.MENTOR, UserRole.SYSTEM,
    ):
        raise ForbiddenException("Insufficient permissions")
    return await service.build_daily_summary(batch_id)
