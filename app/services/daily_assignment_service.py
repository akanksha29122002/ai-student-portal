"""Autonomous daily task generation and assignment.

Mentors onboard students and maintain project profiles. This service creates
one task per student per day from durable project context and recent history.
It is deterministic by default to control AI cost and keep demos reliable.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from app.application.unit_of_work import AsyncUnitOfWork
from app.domain.enums import TaskType
from app.schemas.core import Student, TaskCreate
from app.schemas.m7 import StudentProjectProfile, TaskAssignment, TaskAssignmentCreate


@dataclass(frozen=True)
class GeneratedDailyTask:
    title: str
    objective: str
    why_this_task: str
    instructions: str
    acceptance_criteria: list[str]
    expected_deliverables: list[str]
    verification_strategy: list[str]
    difficulty: str
    estimated_minutes: int
    skills_tested: list[str]
    mentor_review_required: bool = False


class DailyTaskGenerationService:
    """Generate one project-specific task from profile and recent history."""

    def generate(
        self,
        *,
        student: Student,
        profile: StudentProjectProfile,
        previous_assignments: list[TaskAssignment],
    ) -> GeneratedDailyTask:
        weakness = _pick_focus(profile.current_weaknesses, profile.skill_gaps)
        stack = ", ".join(profile.tech_stack[:4]) if profile.tech_stack else "the existing project stack"
        day_number = len(previous_assignments) + 1

        if "auth" in weakness.lower() or "authorization" in weakness.lower():
            title = "Add role-based authorization to a project endpoint"
            objective = "Prove you can enforce access control in the backend and explain where it lives."
            acceptance = [
                "Unauthenticated requests are rejected.",
                "A low-privilege role cannot perform the protected action.",
                "An allowed mentor/admin role can perform the protected action.",
                "Authorization is enforced in backend code, not only the UI.",
                "Tests or clear evidence cover allowed and denied cases.",
            ]
            skills = ["authentication", "authorization", "backend APIs", "testing"]
        elif "test" in weakness.lower():
            title = "Add focused tests for one critical project workflow"
            objective = "Demonstrate that an important user workflow is protected by meaningful tests."
            acceptance = [
                "At least one success path test is added.",
                "At least one failure/edge path test is added.",
                "Tests can be run with the project test command.",
                "The explanation identifies what regression the tests prevent.",
            ]
            skills = ["testing", "debugging", "quality"]
        elif "system design" in weakness.lower() or "architecture" in weakness.lower():
            title = "Document and improve one architecture boundary"
            objective = "Show that you understand how your frontend, backend, database, and services connect."
            acceptance = [
                "A short architecture note or diagram is added.",
                "One unclear boundary or coupling point is improved or justified.",
                "The explanation names the files/modules involved.",
                "Tradeoffs and limitations are documented.",
            ]
            skills = ["architecture", "system_design", "communication"]
        else:
            title = f"Improve one production-readiness gap in {profile.project_title}"
            objective = "Make a small, verifiable improvement that moves the project closer to defense readiness."
            acceptance = [
                "The change is scoped to one concrete project improvement.",
                "The implementation is committed to GitHub.",
                "The explanation states why this matters for the project defense.",
                "Evidence is sufficient for automated verification.",
            ]
            skills = ["project_maturity", "implementation", "communication"]

        instructions = (
            f"Work in {profile.project_title} using {stack}. "
            f"Focus area: {weakness}. Submit a GitHub commit link, explain the implementation, "
            "and identify exactly where the change is enforced."
        )
        return GeneratedDailyTask(
            title=f"Day {day_number}: {title}",
            objective=objective,
            why_this_task=(
                f"This targets {student.full_name}'s current gap: {weakness}. "
                "The task is specific to the submitted project profile and can be verified from code evidence."
            ),
            instructions=instructions,
            acceptance_criteria=acceptance,
            expected_deliverables=[
                "GitHub commit link",
                "Implementation explanation",
                "Files/modules changed",
                "Test or manual verification evidence",
            ],
            verification_strategy=[
                "Compare acceptance criteria with the submitted explanation.",
                "Inspect the GitHub commit/diff for matching implementation evidence.",
                "Flag unverifiable implementation claims for mentor review.",
            ],
            difficulty=_difficulty_for(profile.current_level, previous_assignments),
            estimated_minutes=60,
            skills_tested=skills,
        )


class DailyAssignmentService:
    def __init__(self, uow: AsyncUnitOfWork) -> None:
        self._uow = uow
        self._generator = DailyTaskGenerationService()

    async def assign_for_student(self, student_id: UUID, assigned_on: date) -> TaskAssignment:
        existing = await self._uow.task_assignments.get_for_student_on(student_id, assigned_on)
        if existing is not None:
            return existing

        student = await self._uow.students.get(student_id)
        if student is None:
            raise ValueError("Student not found")

        profile = await self._uow.project_profiles.get_by_student(student_id)
        if profile is None:
            raise ValueError("Student project profile is required before daily assignment")

        previous = await self._uow.task_assignments.list_for_student(student_id)
        generated = self._generator.generate(student=student, profile=profile, previous_assignments=previous)

        async with self._uow:
            again = await self._uow.task_assignments.get_for_student_on(student_id, assigned_on)
            if again is not None:
                return again
            task = await self._uow.tasks.create(
                TaskCreate(
                    organization_id=student.organization_id,
                    batch_id=student.batch_id,
                    student_id=student.id,
                    project_id=profile.project_id,
                    task_type=TaskType.CODING,
                    title=generated.title,
                    problem_statement=f"{generated.objective}\n\n{generated.instructions}",
                    acceptance_criteria=generated.acceptance_criteria,
                    expected_concepts=generated.skills_tested,
                    due_on=assigned_on,
                )
            )
            return await self._uow.task_assignments.create(
                TaskAssignmentCreate(
                    organization_id=student.organization_id,
                    batch_id=student.batch_id,
                    student_id=student.id,
                    task_id=task.id,
                    assigned_on=assigned_on,
                    why_this_task=generated.why_this_task,
                    instructions=generated.instructions,
                    expected_deliverables=generated.expected_deliverables,
                    verification_strategy=generated.verification_strategy,
                    difficulty=generated.difficulty,
                    estimated_minutes=generated.estimated_minutes,
                    skills_tested=generated.skills_tested,
                    mentor_review_required=generated.mentor_review_required,
                )
            )

    async def run_for_batch(self, organization_id: UUID, batch_id: UUID, assigned_on: date) -> dict:
        students = [
            student
            for student in await self._uow.students.list_for_org(organization_id)
            if student.batch_id == batch_id
        ]
        generated = 0
        reused = 0
        errors: list[dict] = []
        assignment_ids: list[str] = []
        for student in students:
            try:
                before = await self._uow.task_assignments.get_for_student_on(student.id, assigned_on)
                assignment = await self.assign_for_student(student.id, assigned_on)
                assignment_ids.append(str(assignment.id))
                if before is None:
                    generated += 1
                else:
                    reused += 1
            except Exception as exc:
                errors.append({"student_id": str(student.id), "error": str(exc)})
        return {
            "organization_id": str(organization_id),
            "batch_id": str(batch_id),
            "assigned_on": str(assigned_on),
            "students_processed": len(students),
            "tasks_generated": generated,
            "tasks_reused": reused,
            "assignment_ids": assignment_ids,
            "errors": errors,
        }


def _pick_focus(weaknesses: list[str], skill_gaps: list[str]) -> str:
    for item in [*weaknesses, *skill_gaps]:
        if item and item.strip():
            return item.strip()
    return "project explanation"


def _difficulty_for(level: str, previous_assignments: list[TaskAssignment]) -> str:
    if len(previous_assignments) >= 5 and level in {"intermediate", "advanced"}:
        return "hard"
    if level in {"beginner", "pilot", "unknown"}:
        return "medium"
    return "medium"
