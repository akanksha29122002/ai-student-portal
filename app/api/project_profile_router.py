"""Project profile endpoints for the autonomous daily workflow."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_async_service, get_current_user
from app.application.async_daily_loop_service import AsyncDailyLoopService
from app.domain.enums import UserRole
from app.schemas.auth import CurrentUser
from app.schemas.m7 import StudentProjectProfileCreate
from app.services.project_profile_service import StudentProjectProfileService
from app.shared.exceptions import ForbiddenException

router = APIRouter(tags=["project-profiles"])

_Service = Annotated[AsyncDailyLoopService, Depends(get_async_service)]
_CurrentUser = Annotated[CurrentUser, Depends(get_current_user)]


def _can_manage_profiles(user: CurrentUser) -> bool:
    return user.can(UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.PROGRAM_MANAGER, UserRole.MENTOR)


@router.post(
    "/students/{student_id}/project-profile",
    status_code=status.HTTP_200_OK,
    summary="Create or update a student's Project Defense profile",
)
async def upsert_student_project_profile(
    student_id: UUID,
    payload: StudentProjectProfileCreate,
    service: _Service,
    current_user: _CurrentUser,
):
    if not _can_manage_profiles(current_user):
        raise ForbiddenException("Insufficient permissions to manage project profiles")
    if payload.student_id != student_id:
        raise ForbiddenException("Path student_id must match payload student_id")
    if current_user.organization_id is not None and payload.organization_id != current_user.organization_id:
        raise ForbiddenException("Cannot manage project profile outside your organization")

    profile_service = StudentProjectProfileService(service.uow)
    return await profile_service.upsert_profile(payload)


@router.get(
    "/students/{student_id}/project-profile",
    summary="Get a student's Project Defense profile",
)
async def get_student_project_profile(
    student_id: UUID,
    service: _Service,
    current_user: _CurrentUser,
):
    student = await service.get_student(student_id)
    if current_user.organization_id is not None and student.organization_id != current_user.organization_id:
        raise ForbiddenException("Cannot view project profile outside your organization")
    if not _can_manage_profiles(current_user) and current_user.email.lower() != student.email.lower():
        raise ForbiddenException("Insufficient permissions to view this project profile")

    profile_service = StudentProjectProfileService(service.uow)
    return await profile_service.get_for_student(student_id)


@router.get("/me/project-profile", summary="Get the current student's Project Defense profile")
async def get_my_project_profile(service: _Service, current_user: _CurrentUser):
    student = await service.get_student_by_email(current_user.email, current_user.organization_id)
    profile_service = StudentProjectProfileService(service.uow)
    return await profile_service.get_for_student(student.id)
