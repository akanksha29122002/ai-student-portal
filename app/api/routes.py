from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_async_service, get_current_user
from app.application.async_daily_loop_service import AsyncDailyLoopService
from app.domain.enums import UserRole
from app.schemas.auth import CurrentUser
from app.schemas.core import (
    BatchCreate,
    EvaluationCreate,
    MentorReviewCreate,
    OrganizationCreate,
    ProjectCreate,
    StudentCreate,
    SubmissionCreate,
    TaskCreate,
)
from app.schemas.responses import HealthResponse
from app.shared.exceptions import UnauthorizedException

router = APIRouter()

_Service = Annotated[AsyncDailyLoopService, Depends(get_async_service)]
_CurrentUser = Annotated[CurrentUser, Depends(get_current_user)]


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="project-defense-ai")


@router.post("/organizations", status_code=status.HTTP_201_CREATED, tags=["organizations"])
async def create_organization(payload: OrganizationCreate, service: _Service, current_user: _CurrentUser):
    if not current_user.can(UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN):
        raise UnauthorizedException("Only organization admins can create organizations")
    return await service.create_organization(payload)


@router.post("/batches", status_code=status.HTTP_201_CREATED, tags=["programs"])
async def create_batch(payload: BatchCreate, service: _Service, current_user: _CurrentUser):
    if not current_user.can(UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.PROGRAM_MANAGER):
        raise UnauthorizedException("Insufficient permissions to create a batch")
    return await service.create_batch(payload)


@router.post("/students", status_code=status.HTTP_201_CREATED, tags=["students"])
async def create_student(payload: StudentCreate, service: _Service, current_user: _CurrentUser):
    if not current_user.can(UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.PROGRAM_MANAGER, UserRole.MENTOR):
        raise UnauthorizedException("Insufficient permissions to register a student")
    return await service.create_student(payload)


@router.post("/projects", status_code=status.HTTP_201_CREATED, tags=["projects"])
async def create_project(payload: ProjectCreate, service: _Service, current_user: _CurrentUser):
    return await service.create_project(payload)


@router.post("/tasks", status_code=status.HTTP_201_CREATED, tags=["tasks"])
async def create_task(payload: TaskCreate, service: _Service, current_user: _CurrentUser):
    if not current_user.can(UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.PROGRAM_MANAGER, UserRole.MENTOR, UserRole.AI_AGENT):
        raise UnauthorizedException("Insufficient permissions to create a task")
    return await service.create_task(payload)


@router.get("/tasks/{task_id}", tags=["tasks"])
async def get_task(task_id: UUID, service: _Service, current_user: _CurrentUser):
    return await service.get_task(task_id)


@router.post("/submissions", status_code=status.HTTP_201_CREATED, tags=["submissions"])
async def create_submission(payload: SubmissionCreate, service: _Service, current_user: _CurrentUser):
    return await service.create_submission(payload)


@router.post("/submissions/{submission_id}/evaluate", tags=["evaluations"])
async def evaluate_submission(submission_id: UUID, service: _Service, current_user: _CurrentUser):
    if not current_user.can(UserRole.SUPER_ADMIN, UserRole.MENTOR, UserRole.AI_AGENT):
        raise UnauthorizedException("Insufficient permissions to evaluate a submission")
    return await service.evaluate_submission(submission_id)


@router.post("/evaluations", status_code=status.HTTP_201_CREATED, tags=["evaluations"])
async def create_evaluation(payload: EvaluationCreate, service: _Service, current_user: _CurrentUser):
    if not current_user.can(UserRole.SUPER_ADMIN, UserRole.MENTOR, UserRole.AI_AGENT):
        raise UnauthorizedException("Insufficient permissions to create an evaluation")
    return await service.create_evaluation(payload)


@router.post("/mentor-reviews", status_code=status.HTTP_201_CREATED, tags=["mentor-reviews"])
async def create_mentor_review(payload: MentorReviewCreate, service: _Service, current_user: _CurrentUser):
    if not current_user.can(UserRole.SUPER_ADMIN, UserRole.MENTOR):
        raise UnauthorizedException("Only mentors can submit reviews")
    return await service.create_mentor_review(payload)


@router.get("/mentor-summaries/{batch_id}", tags=["mentor-summaries"])
async def get_mentor_summary(batch_id: UUID, service: _Service, current_user: _CurrentUser):
    if not current_user.can(UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.PROGRAM_MANAGER, UserRole.MENTOR):
        raise UnauthorizedException("Insufficient permissions to view mentor summaries")
    return await service.build_daily_summary(batch_id)
