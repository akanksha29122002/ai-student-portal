"""Automation APIs for autonomous daily workflow."""
from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import Field

from app.api.dependencies import get_async_service, get_current_user
from app.application.async_daily_loop_service import AsyncDailyLoopService
from app.domain.enums import UserRole
from app.domain.enums import SelfStatus
from app.schemas.auth import CurrentUser
from app.schemas.base import ApiModel
from app.schemas.core import SubmissionCreate
from app.services.daily_assignment_service import DailyAssignmentService
from app.services.task_verification_service import TaskVerificationService
from app.shared.exceptions import ForbiddenException, NotFoundException

router = APIRouter(tags=["automation"])

_Service = Annotated[AsyncDailyLoopService, Depends(get_async_service)]
_CurrentUser = Annotated[CurrentUser, Depends(get_current_user)]


class RunDailyRequest(ApiModel):
    organization_id: UUID
    batch_id: UUID
    assigned_on: date = Field(default_factory=date.today)


class StudentWorkSubmissionRequest(ApiModel):
    commit_url: str = Field(min_length=8, max_length=500)
    explanation: str = Field(min_length=10, max_length=30000)
    implementation_statement: str = Field(min_length=10, max_length=4000)
    deployed_url: str | None = Field(default=None, max_length=500)
    evidence_notes: str | None = Field(default=None, max_length=4000)


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


@router.post("/me/tasks/{task_id}/submit")
async def submit_my_task(
    task_id: UUID,
    payload: StudentWorkSubmissionRequest,
    service: _Service,
    current_user: _CurrentUser,
):
    student = await service.get_student_by_email(current_user.email, current_user.organization_id)
    task = await service.uow.tasks.get(task_id)
    if task is None:
        raise NotFoundException("Task not found")
    if task.student_id != student.id:
        raise ForbiddenException("Cannot submit work for another student's task")

    approach_parts = [payload.implementation_statement]
    if payload.deployed_url:
        approach_parts.append(f"Deployed URL: {payload.deployed_url}")
    if payload.evidence_notes:
        approach_parts.append(f"Evidence notes: {payload.evidence_notes}")

    submission = await service.create_submission(
        SubmissionCreate(
            organization_id=student.organization_id,
            task_id=task.id,
            student_id=student.id,
            self_status=SelfStatus.SOLVED,
            commit_url=payload.commit_url,
            transcript_text=payload.explanation,
            approach_note="\n\n".join(approach_parts),
        )
    )
    evaluation = await TaskVerificationService(service.uow).verify_submission(submission.id)
    return {"submission": submission, "evaluation": evaluation}


@router.get("/me/submissions/{submission_id}/evaluation")
async def get_my_submission_evaluation(
    submission_id: UUID,
    service: _Service,
    current_user: _CurrentUser,
):
    student = await service.get_student_by_email(current_user.email, current_user.organization_id)
    submission = await service.uow.submissions.get(submission_id)
    if submission is None:
        raise NotFoundException("Submission not found")
    if submission.student_id != student.id:
        raise ForbiddenException("Cannot view another student's submission")
    evaluations = await service.uow.evaluations.list_for_submission(submission.id)
    if not evaluations:
        raise NotFoundException("No evaluation found for submission")
    return {"submission": submission, "evaluation": evaluations[-1]}


@router.get("/mentor/today")
async def mentor_today(
    service: _Service,
    current_user: _CurrentUser,
    organization_id: UUID | None = Query(default=None),
    batch_id: UUID | None = Query(default=None),
    day: date | None = Query(default=None),
):
    if not current_user.can(UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.PROGRAM_MANAGER, UserRole.MENTOR):
        raise ForbiddenException("Insufficient permissions")
    effective_org = organization_id or current_user.organization_id
    if effective_org is None:
        raise ForbiddenException("Organization scope is required")
    day = day or date.today()
    students = await service.uow.students.list_for_org(effective_org)
    if batch_id is not None:
        students = [student for student in students if student.batch_id == batch_id]

    rows = []
    totals = {
        "total_students": len(students),
        "tasks_assigned": 0,
        "submitted": 0,
        "evaluated": 0,
        "verified": 0,
        "partial": 0,
        "failed": 0,
        "needs_review": 0,
        "not_submitted": 0,
    }
    for student in students:
        assignment = await service.uow.task_assignments.get_for_student_on(student.id, day)
        task = await service.uow.tasks.get(assignment.task_id) if assignment else None
        submissions = await service.uow.submissions.list_for_student(student.id)
        submission = next((item for item in submissions if assignment and item.task_id == assignment.task_id), None)
        evaluations = await service.uow.evaluations.list_for_submission(submission.id) if submission else []
        evaluation = evaluations[-1] if evaluations else None

        if assignment:
            totals["tasks_assigned"] += 1
        if submission:
            totals["submitted"] += 1
        else:
            totals["not_submitted"] += 1
        if evaluation:
            totals["evaluated"] += 1
            if evaluation.score >= 80 and not evaluation.flags:
                totals["verified"] += 1
            elif evaluation.score < 50:
                totals["failed"] += 1
            else:
                totals["partial"] += 1
            if str(evaluation.verdict) == "needs_human_review" or evaluation.flags:
                totals["needs_review"] += 1

        rows.append(
            {
                "student_id": str(student.id),
                "student": student.full_name,
                "today_task": task.title if task else None,
                "submission_status": "submitted" if submission else "not_submitted",
                "score": evaluation.score if evaluation else None,
                "confidence": evaluation.confidence if evaluation else None,
                "flag": evaluation.flags[0] if evaluation and evaluation.flags else None,
                "action": "review" if evaluation and (evaluation.flags or str(evaluation.verdict) == "needs_human_review") else "none",
            }
        )
    return {"date": str(day), "organization_id": str(effective_org), "totals": totals, "students": rows}


@router.get("/mentor/review-queue")
async def mentor_review_queue(
    service: _Service,
    current_user: _CurrentUser,
    organization_id: UUID | None = Query(default=None),
):
    if not current_user.can(UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.PROGRAM_MANAGER, UserRole.MENTOR):
        raise ForbiddenException("Insufficient permissions")
    effective_org = organization_id or current_user.organization_id
    if effective_org is None:
        raise ForbiddenException("Organization scope is required")
    students = await service.uow.students.list_for_org(effective_org)
    items = []
    for student in students:
        submissions = await service.uow.submissions.list_for_student(student.id)
        for submission in submissions:
            evaluations = await service.uow.evaluations.list_for_submission(submission.id)
            if not evaluations:
                continue
            evaluation = evaluations[-1]
            if str(evaluation.verdict) == "needs_human_review" or evaluation.flags or evaluation.score < 60:
                task = await service.uow.tasks.get(submission.task_id)
                items.append(
                    {
                        "student_id": str(student.id),
                        "student": student.full_name,
                        "submission_id": str(submission.id),
                        "evaluation_id": str(evaluation.id),
                        "task": task.title if task else None,
                        "score": evaluation.score,
                        "confidence": evaluation.confidence,
                        "reasons": evaluation.flags or ["LOW_SCORE"],
                    }
                )
    return {"total": len(items), "items": items}
