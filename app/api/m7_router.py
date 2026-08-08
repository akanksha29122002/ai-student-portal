"""Milestone 7 API endpoints — Learning Plans, Profile Analysis, Verification."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_current_user
from app.domain.enums import UserRole
from app.schemas.auth import CurrentUser
from app.shared.exceptions import NotFoundException, UnauthorizedException

router = APIRouter(tags=["m7-learning"])

_CurrentUser = Annotated[CurrentUser, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Helper: resolve the InMemoryStore (always available; SQL path TBD later)
# ---------------------------------------------------------------------------


def _get_store():
    from app.api.dependencies import _dev_store
    return _dev_store


# ---------------------------------------------------------------------------
# Phase 3 + 4 — Student Profile Analysis
# ---------------------------------------------------------------------------


@router.post(
    "/students/{student_id}/analyze",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger AI profile analysis for a student (Phase 3+4)",
)
async def analyze_student_profile(
    student_id: UUID,
    current_user: _CurrentUser,
    raw_profile: dict = None,
):
    """Run AI analysis on a student's background.

    Generates StudentProfileAnalysis (OBSERVED/INFERRED/UNKNOWN skill distinctions)
    and SkillAssessment records for all canonical dimensions.

    Body: optional dict with any profile fields (prior_projects, education,
    languages, frameworks, etc.). Falls back to whatever is already stored.
    """
    if not current_user.can(
        UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.PROGRAM_MANAGER, UserRole.MENTOR
    ):
        raise UnauthorizedException("Insufficient permissions for profile analysis")

    store = _get_store()
    student = store.get_student(student_id)
    if student is None:
        raise NotFoundException("Student not found")

    from app.services.profile_service import StudentProfileService
    svc = StudentProfileService(store)
    analysis = await svc.analyze_student(
        student_id=student_id,
        organization_id=student.organization_id,
        student_name=student.full_name,
        raw_profile=raw_profile or {},
    )
    return analysis


@router.get(
    "/students/{student_id}/profile",
    summary="Get the latest AI profile analysis for a student",
)
async def get_student_profile(student_id: UUID, current_user: _CurrentUser):
    store = _get_store()
    student = store.get_student(student_id)
    if student is None:
        raise NotFoundException("Student not found")
    if not current_user.can(
        UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.PROGRAM_MANAGER, UserRole.MENTOR
    ) and current_user.id != student_id:
        raise UnauthorizedException("Access denied")

    analysis = store.get_latest_profile_analysis(student_id)
    if analysis is None:
        raise NotFoundException("No profile analysis found — trigger POST /students/{id}/analyze first")
    return analysis


@router.get(
    "/students/{student_id}/skills",
    summary="Get baseline skill assessments for a student (Phase 4)",
)
async def get_student_skills(student_id: UUID, current_user: _CurrentUser):
    store = _get_store()
    student = store.get_student(student_id)
    if student is None:
        raise NotFoundException("Student not found")
    if not current_user.can(
        UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.PROGRAM_MANAGER, UserRole.MENTOR
    ) and current_user.id != student_id:
        raise UnauthorizedException("Access denied")

    skills = store.list_skill_assessments(student_id)
    return {"student_id": str(student_id), "assessments": skills}


# ---------------------------------------------------------------------------
# Phase 5 — Learning Plan
# ---------------------------------------------------------------------------


@router.post(
    "/students/{student_id}/learning-plan",
    status_code=status.HTTP_201_CREATED,
    summary="Generate a 14-day personalised learning plan (Phase 5)",
)
async def generate_learning_plan(
    student_id: UUID,
    current_user: _CurrentUser,
):
    if not current_user.can(
        UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.PROGRAM_MANAGER, UserRole.MENTOR
    ):
        raise UnauthorizedException("Insufficient permissions")

    store = _get_store()
    student = store.get_student(student_id)
    if student is None:
        raise NotFoundException("Student not found")

    from app.services.plan_service import LearningPlanService
    svc = LearningPlanService(store)
    plan = await svc.generate_plan(student_id=student_id, student=student)
    return plan


@router.get(
    "/students/{student_id}/learning-plan",
    summary="Get active learning plan for a student",
)
async def get_learning_plan(student_id: UUID, current_user: _CurrentUser):
    store = _get_store()
    student = store.get_student(student_id)
    if student is None:
        raise NotFoundException("Student not found")

    plan = store.get_active_plan(student_id)
    if plan is None:
        plans = store.list_learning_plans(student_id)
        if plans:
            plan = max(plans, key=lambda p: p.created_at)
        else:
            raise NotFoundException("No learning plan found")

    days = store.list_plan_days(plan.id)
    return {"plan": plan, "days": days}


# ---------------------------------------------------------------------------
# Phase 6 — Today's tasks for a student
# ---------------------------------------------------------------------------


@router.get(
    "/students/{student_id}/today",
    summary="Get today's plan day with task details (Phase 6)",
)
async def get_today(student_id: UUID, current_user: _CurrentUser):
    from datetime import date
    store = _get_store()
    student = store.get_student(student_id)
    if student is None:
        raise NotFoundException("Student not found")

    plan = store.get_active_plan(student_id)
    if plan is None:
        raise NotFoundException("No active learning plan found")

    today = date.today()
    days = store.list_plan_days(plan.id)
    today_day = next((d for d in days if d.scheduled_date == today), None)

    if today_day is None:
        return {"message": "No task scheduled for today", "plan_id": str(plan.id)}

    task = store.get_task(today_day.task_id) if today_day.task_id else None
    return {"day": today_day, "task": task}


# ---------------------------------------------------------------------------
# Phase 7 — Submission Evidence
# ---------------------------------------------------------------------------


@router.post(
    "/submissions/{submission_id}/evidence",
    status_code=status.HTTP_201_CREATED,
    summary="Add evidence to a submission (Phase 7)",
)
async def add_submission_evidence(
    submission_id: UUID,
    current_user: _CurrentUser,
    payload: dict,
):
    from datetime import datetime
    from app.domain.enums import EvidenceCollectedBy, SubmissionEvidenceType
    from app.schemas.m7 import SubmissionEvidenceCreate

    store = _get_store()
    submission = store.get_submission(submission_id)
    if submission is None:
        raise NotFoundException("Submission not found")

    evidence_type_str = payload.get("evidence_type", "github_commit")
    try:
        evidence_type = SubmissionEvidenceType(evidence_type_str)
    except ValueError:
        evidence_type = SubmissionEvidenceType.GITHUB_COMMIT

    collected_by = EvidenceCollectedBy.STUDENT
    if current_user.can(UserRole.MENTOR, UserRole.SUPER_ADMIN):
        collected_by = EvidenceCollectedBy.MENTOR

    evidence = store.create_submission_evidence(
        SubmissionEvidenceCreate(
            submission_id=submission_id,
            organization_id=submission.organization_id,
            evidence_type=evidence_type,
            url=payload.get("url"),
            content=payload.get("content"),
            metadata=payload.get("metadata", {}),
            collected_by=collected_by,
            collected_at=datetime.now(UTC),
            quality_score=payload.get("quality_score"),
        )
    )
    return evidence


@router.get(
    "/submissions/{submission_id}/evidence",
    summary="List evidence for a submission",
)
async def list_submission_evidence(submission_id: UUID, current_user: _CurrentUser):
    store = _get_store()
    submission = store.get_submission(submission_id)
    if submission is None:
        raise NotFoundException("Submission not found")
    return store.list_submission_evidences(submission_id)


# ---------------------------------------------------------------------------
# Phase 8 — Automated Verification
# ---------------------------------------------------------------------------


@router.post(
    "/submissions/{submission_id}/verify",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger automated verification (Phase 8)",
)
async def verify_submission(submission_id: UUID, current_user: _CurrentUser):
    store = _get_store()
    submission = store.get_submission(submission_id)
    if submission is None:
        raise NotFoundException("Submission not found")

    from app.services.verification_service import VerificationService
    svc = VerificationService(store)
    result = await svc.verify(submission_id=submission_id, submission=submission)
    return result


@router.get(
    "/submissions/{submission_id}/verification",
    summary="Get latest verification result for a submission",
)
async def get_verification(submission_id: UUID, current_user: _CurrentUser):
    store = _get_store()
    result = store.get_latest_verification(submission_id)
    if result is None:
        raise NotFoundException("No verification found — trigger POST /submissions/{id}/verify first")
    evidences = store.list_verification_evidences(result.id)
    return {"result": result, "evidences": evidences}


# ---------------------------------------------------------------------------
# Phase 9 — Daily Automation (advance plan days, adapt tasks, snapshot progress)
# ---------------------------------------------------------------------------


@router.post(
    "/batches/{batch_id}/run-daily-automation",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Run daily automation for a batch (Phase 9)",
)
async def run_daily_automation(
    batch_id: UUID,
    current_user: _CurrentUser,
    organization_id: UUID | None = None,
):
    if not current_user.can(
        UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.PROGRAM_MANAGER
    ):
        raise UnauthorizedException("Insufficient permissions for automation")

    store = _get_store()
    batch = store.batches.get(batch_id)
    if batch is None:
        raise NotFoundException("Batch not found")

    org_id = organization_id or batch.organization_id
    from app.services.automation_service import DailyAutomationService
    svc = DailyAutomationService(store)
    return await svc.run_for_batch(organization_id=org_id, batch_id=batch_id)


# ---------------------------------------------------------------------------
# Phase 10 — Mentor Escalation Queue
# ---------------------------------------------------------------------------


@router.get(
    "/mentor/escalations",
    summary="List submissions that need mentor review (Phase 10)",
)
async def get_escalation_queue(current_user: _CurrentUser, limit: int = 50):
    if not current_user.can(UserRole.MENTOR, UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN):
        raise UnauthorizedException("Mentors only")

    store = _get_store()
    results = [
        r for r in store.verification_results.values()
        if r.escalate_to_mentor
    ]
    results.sort(key=lambda r: r.created_at, reverse=True)
    return {"total": len(results), "items": results[:limit]}


# ---------------------------------------------------------------------------
# Phase 11 — Progress Analytics
# ---------------------------------------------------------------------------


@router.get(
    "/students/{student_id}/progress",
    summary="Get progress snapshots for a student (Phase 11)",
)
async def get_student_progress(student_id: UUID, current_user: _CurrentUser):
    store = _get_store()
    student = store.get_student(student_id)
    if student is None:
        raise NotFoundException("Student not found")

    progress = store.get_student_progress(student_id)
    skills = store.list_skill_assessments(student_id)
    plan = store.get_active_plan(student_id)

    return {
        "student_id": str(student_id),
        "plan_id": str(plan.id) if plan else None,
        "progress_history": progress,
        "current_skills": skills,
    }


# ---------------------------------------------------------------------------
# Phase 12 — Final Readiness Report
# ---------------------------------------------------------------------------


@router.get(
    "/students/{student_id}/readiness-report",
    summary="Generate final readiness report (Phase 12)",
)
async def get_readiness_report(student_id: UUID, current_user: _CurrentUser):
    if not current_user.can(
        UserRole.MENTOR, UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.PROGRAM_MANAGER
    ) and current_user.id != student_id:
        raise UnauthorizedException("Access denied")

    store = _get_store()
    student = store.get_student(student_id)
    if student is None:
        raise NotFoundException("Student not found")

    plan = store.get_active_plan(student_id) or (
        max(store.list_learning_plans(student_id), key=lambda p: p.created_at, default=None)
    )
    days = store.list_plan_days(plan.id) if plan else []
    skills = store.list_skill_assessments(student_id)
    profile = store.get_latest_profile_analysis(student_id)
    progress = store.get_student_progress(student_id)
    submissions = store.list_submissions_for_student(student_id)

    completed_days = [d for d in days if d.status == "completed"]
    scored_days = [d for d in completed_days if d.score is not None]
    avg_score = (
        sum(d.score for d in scored_days) / len(scored_days)
        if scored_days else None
    )

    return {
        "student_id": str(student_id),
        "student_name": student.full_name,
        "plan_id": str(plan.id) if plan else None,
        "total_days": len(days),
        "completed_days": len(completed_days),
        "average_score": round(avg_score, 1) if avg_score else None,
        "completion_rate": round(len(completed_days) / len(days), 2) if days else 0,
        "total_submissions": len(submissions),
        "skill_summary": [
            {
                "dimension": s.dimension,
                "score": s.score,
                "confidence": str(s.confidence),
            }
            for s in sorted(skills, key=lambda s: s.score, reverse=True)
        ],
        "strengths": profile.strengths if profile else [],
        "risk_factors": profile.risk_factors if profile else [],
        "progress_snapshots": len(progress),
        "ready_for_defense": avg_score is not None and avg_score >= 70 and len(completed_days) >= 10,
    }
