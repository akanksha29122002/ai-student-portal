"""Production-backed student project profile service.

This is the durable context layer for autonomous task generation. It stores
what the system knows about a student's project without calling AI on every
page load.
"""
from __future__ import annotations

from uuid import UUID

from app.application.unit_of_work import AsyncUnitOfWork
from app.schemas.m7 import (
    StudentProjectProfile,
    StudentProjectProfileCreate,
    StudentProjectProfileUpdate,
)
from app.shared.exceptions import ForbiddenException, NotFoundException


class StudentProjectProfileService:
    def __init__(self, uow: AsyncUnitOfWork) -> None:
        self._uow = uow

    async def get_for_student(self, student_id: UUID) -> StudentProjectProfile:
        profile = await self._uow.project_profiles.get_by_student(student_id)
        if profile is None:
            raise NotFoundException("Student project profile not found")
        return profile

    async def upsert_profile(self, payload: StudentProjectProfileCreate) -> StudentProjectProfile:
        student = await self._uow.students.get(payload.student_id)
        if student is None:
            raise NotFoundException("Student not found")
        if student.organization_id != payload.organization_id:
            raise ForbiddenException("Student belongs to a different organization")

        project = await self._uow.projects.get(payload.project_id)
        if project is None:
            raise NotFoundException("Project not found")
        if project.student_id != payload.student_id or project.organization_id != payload.organization_id:
            raise ForbiddenException("Project does not belong to this student and organization")

        async with self._uow:
            existing = await self._uow.project_profiles.get_by_student(payload.student_id)
            if existing is None:
                return await self._uow.project_profiles.create(payload)
            update = StudentProjectProfileUpdate(**payload.model_dump(exclude={"student_id", "organization_id"}))
            updated = await self._uow.project_profiles.update(payload.student_id, update)
            if updated is None:
                raise NotFoundException("Student project profile not found")
            return updated
