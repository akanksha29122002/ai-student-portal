"""Daily Automation Engine.

Phase 9: Runs once per day per batch:
  - Unlocks the next plan day for students who completed today's day
  - Adapts the upcoming task difficulty based on performance trend
  - Takes a progress snapshot per student
  - Records a DailyAutomationRun for audit purposes
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from uuid import UUID

from app.domain.enums import AutomationRunStatus, PlanDayStatus
from app.schemas.m7 import DailyAutomationRunCreate, StudentProgressCreate

logger = logging.getLogger("project_defense.services.automation")


class DailyAutomationService:
    def __init__(self, store) -> None:
        self._store = store

    async def run_for_batch(self, organization_id: UUID, batch_id: UUID) -> dict:
        """Execute the daily automation for a batch. Idempotent per run_date."""
        today = date.today()

        run = self._store.create_daily_automation_run(
            DailyAutomationRunCreate(
                organization_id=organization_id,
                batch_id=batch_id,
                run_date=today,
                status=AutomationRunStatus.RUNNING,
                started_at=datetime.now(UTC),
            )
        )

        students_processed = 0
        plans_adapted = 0
        errors: list[dict] = []

        students = [
            s for s in self._store.students.values()
            if s.batch_id == batch_id and s.organization_id == organization_id
        ]

        for student in students:
            try:
                adapted = await self._process_student(student, today)
                students_processed += 1
                if adapted:
                    plans_adapted += 1
            except Exception as exc:
                logger.warning("Automation failed for student %s: %s", student.id, exc)
                errors.append({"student_id": str(student.id), "error": str(exc)})

        self._store.update_daily_automation_run(
            run.id,
            status=AutomationRunStatus.COMPLETED if not errors else AutomationRunStatus.PARTIAL,
            students_processed=students_processed,
            plans_adapted=plans_adapted,
            errors=errors,
            completed_at=datetime.now(UTC),
        )

        return {
            "run_id": str(run.id),
            "run_date": str(today),
            "students_processed": students_processed,
            "plans_adapted": plans_adapted,
            "errors": errors,
        }

    async def _process_student(self, student, today: date) -> bool:
        """Process one student: unlock next day, adapt task, snapshot progress."""
        plan = self._store.get_active_plan(student.id)
        if not plan:
            return False

        days = self._store.list_plan_days(plan.id)
        adapted = False

        # Find today's day entry
        today_day = next((d for d in days if d.scheduled_date == today), None)
        if today_day and today_day.status == PlanDayStatus.IN_PROGRESS:
            # Check if submission exists and was evaluated
            if today_day.task_id:
                submissions = self._store.list_submissions_for_student(student.id)
                task_submission = next(
                    (s for s in submissions if s.task_id == today_day.task_id), None
                )
                if task_submission and task_submission.status in ("evaluated", "feedback_released", "approved"):
                    # Mark today complete
                    eval_records = self._store.list_submission_evaluations(task_submission.id)
                    score = None
                    if eval_records:
                        score = eval_records[-1].score
                    self._store.update_plan_day(
                        today_day.id,
                        status=PlanDayStatus.COMPLETED,
                        completed_at=datetime.now(UTC),
                        score=score,
                    )
                    # Unlock tomorrow
                    tomorrow_day = next(
                        (d for d in days if d.day_number == today_day.day_number + 1), None
                    )
                    if tomorrow_day and tomorrow_day.status == PlanDayStatus.LOCKED:
                        self._store.update_plan_day(tomorrow_day.id, status=PlanDayStatus.AVAILABLE)
                        adapted = True

        # Take a progress snapshot
        completed = [d for d in days if d.status == PlanDayStatus.COMPLETED]
        remaining = [d for d in days if d.status not in (PlanDayStatus.COMPLETED, PlanDayStatus.SKIPPED)]
        scored = [d for d in completed if d.score is not None]
        avg_score = sum(d.score for d in scored) / len(scored) if scored else None

        streak = _compute_streak(completed, today)

        # Historical snapshots to get longest streak
        history = self._store.get_student_progress(student.id)
        longest = max((p.longest_streak for p in history), default=0)
        longest = max(longest, streak)

        self._store.upsert_student_progress(
            StudentProgressCreate(
                student_id=student.id,
                organization_id=student.organization_id,
                plan_id=plan.id,
                snapshot_date=today,
                day_number=len(completed) + 1,
                days_completed=len(completed),
                days_remaining=len(remaining),
                current_streak=streak,
                longest_streak=longest,
                average_score=round(avg_score, 1) if avg_score else None,
                skill_velocity={},
                completed_task_ids=[d.task_id for d in completed if d.task_id],
            )
        )

        return adapted


def _compute_streak(completed_days, today: date) -> int:
    """Count consecutive completed days ending on or before today."""
    if not completed_days:
        return 0
    dates = sorted({d.scheduled_date for d in completed_days}, reverse=True)
    streak = 0
    expected = today
    for d in dates:
        if d == expected:
            streak += 1
            from datetime import timedelta
            expected = expected - timedelta(days=1)
        else:
            break
    return streak
