"""14-day personalised learning plan generator.

Phase 5: Uses skill assessments to pick which dimensions to focus each day,
assigns tasks from the store (or generates placeholders if none exist),
and sets up the day-unlock chain.
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from app.domain.enums import LearningPlanStatus, PlanDayStatus
from app.schemas.core import Task, TaskCreate, TaskType
from app.schemas.m7 import LearningPlanCreate, LearningPlanDayCreate

logger = logging.getLogger("project_defense.services.plan")

# Ordered list: front-load weaker dimensions in the first half,
# move to higher-order skills in the second half.
_DAY_FOCUS: list[list[str]] = [
    ["problem_solving", "algorithms"],        # day 1 — warm-up
    ["debugging", "code_quality"],            # day 2
    ["testing", "code_quality"],              # day 3
    ["system_design", "architecture"],        # day 4
    ["algorithms", "problem_solving"],        # day 5
    ["code_quality", "testing"],              # day 6 — mid-check
    ["communication", "domain_knowledge"],    # day 7 — soft skills day
    ["architecture", "system_design"],        # day 8
    ["testing", "debugging"],                 # day 9 — consolidation
    ["project_management", "communication"],  # day 10
    ["domain_knowledge", "algorithms"],       # day 11
    ["code_quality", "architecture"],         # day 12
    ["problem_solving", "system_design"],     # day 13 — mock defense prep
    ["communication", "project_management"],  # day 14 — final review
]


class LearningPlanService:
    def __init__(self, store) -> None:
        self._store = store

    async def generate_plan(self, student_id: UUID, student) -> dict:
        """Create LearningPlan + 14 LearningPlanDay records.

        - Picks focus skills per day based on skill assessment scores
          (lowest-scoring dimensions get front-loaded).
        - Links existing tasks for the student when available, otherwise
          leaves task_id null (to be filled by daily automation engine).
        - Day 1 starts today, each subsequent day unlocks when the prior
          day is completed (Day 1 starts as AVAILABLE).
        """
        today = date.today()
        end = today + timedelta(days=13)

        plan = self._store.create_learning_plan(
            LearningPlanCreate(
                student_id=student_id,
                organization_id=student.organization_id,
                batch_id=student.batch_id,
                status=LearningPlanStatus.ACTIVE,
                start_date=today,
                end_date=end,
                total_days=14,
            )
        )

        # Get skill assessments to reorder focus dimensions
        skills = {a.dimension: a.score for a in self._store.list_skill_assessments(student_id)}
        ordered_days = _reorder_days_by_weakness(skills)

        # Pre-fetch student tasks sorted by due_on
        student_tasks: list[Task] = sorted(
            self._store.list_student_tasks(student_id),
            key=lambda t: t.due_on,
        )
        task_by_day: dict[int, UUID | None] = {}
        for i, task in enumerate(student_tasks[:14]):
            task_by_day[i + 1] = task.id

        # Create plan days
        created_days = []
        for day_num in range(1, 15):
            scheduled = today + timedelta(days=day_num - 1)
            # Day 1 starts available; rest locked (unlock_condition set)
            day_status = PlanDayStatus.AVAILABLE if day_num == 1 else PlanDayStatus.LOCKED
            focus = ordered_days[day_num - 1] if day_num - 1 < len(ordered_days) else []

            unlock_cond = None
            if day_num > 1:
                unlock_cond = {"requires_day_completed": day_num - 1}

            day = self._store.create_learning_plan_day(
                LearningPlanDayCreate(
                    plan_id=plan.id,
                    student_id=student_id,
                    organization_id=student.organization_id,
                    day_number=day_num,
                    scheduled_date=scheduled,
                    status=day_status,
                    task_id=task_by_day.get(day_num),
                    target_skills=focus,
                    unlock_condition=unlock_cond,
                )
            )
            created_days.append(day)

        logger.info(
            "Generated 14-day plan %s for student %s (batch %s)",
            plan.id, student_id, student.batch_id,
        )
        return {"plan": plan, "days": created_days}


def _reorder_days_by_weakness(skills: dict[str, int]) -> list[list[str]]:
    """Reorder the daily focus lists so weaker dimensions appear earlier."""
    if not skills:
        return _DAY_FOCUS

    sorted_dims = sorted(skills.items(), key=lambda kv: kv[1])
    weak_dims = [d for d, _ in sorted_dims[:4]]

    reordered = []
    for focus in _DAY_FOCUS:
        new_focus = []
        for dim in weak_dims:
            if dim in focus:
                new_focus.insert(0, dim)
            else:
                new_focus.append(dim)
        for dim in focus:
            if dim not in new_focus:
                new_focus.append(dim)
        reordered.append(new_focus[:2])
    return reordered
