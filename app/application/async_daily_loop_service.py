from datetime import date
from uuid import UUID

from app.application.unit_of_work import AsyncUnitOfWork
from app.domain.enums import EvaluationKind, EvaluationVerdict, SelfStatus, SubmissionStatus
from app.domain.events import (
    DailySummaryGenerated,
    EvaluationCompleted,
    MentorReviewed,
    ProjectCreated,
    StudentRegistered,
    SubmissionReceived,
    TaskAssigned,
)
from app.schemas.core import (
    BatchCreate,
    Evaluation,
    EvaluationCreate,
    Evidence,
    MentorReviewCreate,
    OrganizationCreate,
    ProjectCreate,
    StudentCreate,
    Submission,
    SubmissionCreate,
    Task,
    TaskCreate,
)
from app.shared.exceptions import ConflictException, NotFoundException, ValidationException

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agents.orchestrator import AgentOrchestrator


class AsyncDailyLoopService:
    def __init__(self, uow: AsyncUnitOfWork) -> None:
        self.uow = uow

    async def create_organization(self, payload: OrganizationCreate):
        async with self.uow:
            existing = await self.uow.organizations.get_by_slug(payload.slug)
            if existing is not None:
                raise ConflictException(f"Organization slug '{payload.slug}' already exists")
            return await self.uow.organizations.create(payload)

    async def get_organization_by_slug(self, slug: str):
        organization = await self.uow.organizations.get_by_slug(slug)
        if organization is None:
            raise NotFoundException("Organization not found")
        return organization

    async def list_organizations(self):
        return await self.uow.organizations.list()

    async def create_batch(self, payload: BatchCreate):
        async with self.uow:
            existing = await self.uow.batches.get_by_name(payload.organization_id, payload.name)
            if existing is not None:
                raise ConflictException(f"Batch '{payload.name}' already exists in this organization")
            return await self.uow.batches.create(payload)

    async def list_batches_for_org(self, org_id: UUID):
        return await self.uow.batches.list_for_org(org_id)

    async def create_student(self, payload: StudentCreate):
        async with self.uow:
            existing = await self.uow.students.get_by_email(payload.email, payload.organization_id)
            if existing is not None:
                raise ConflictException(f"Student email '{payload.email}' already exists in this organization")
            student = await self.uow.students.create(payload)
            await self.uow.events.append(
                StudentRegistered(
                    aggregate_id=student.id,
                    payload=student.model_dump(mode="json"),
                    user_id=student.mentor_id,
                )
            )
            return student

    async def get_student(self, student_id: UUID):
        student = await self.uow.students.get(student_id)
        if student is None:
            raise NotFoundException("Student not found")
        return student

    async def get_student_by_email(self, email: str, organization_id: UUID | None = None):
        student = await self.uow.students.get_by_email(email, organization_id)
        if student is None:
            raise NotFoundException("No student profile found for this user")
        return student

    async def list_students_for_org(self, org_id: UUID):
        return await self.uow.students.list_for_org(org_id)

    async def create_project(self, payload: ProjectCreate):
        async with self.uow:
            project = await self.uow.projects.create(payload)
            await self.uow.events.append(
                ProjectCreated(aggregate_id=project.id, payload=project.model_dump(mode="json"))
            )
            return project

    async def create_task(self, payload: TaskCreate):
        async with self.uow:
            task = await self.uow.tasks.create(payload)
            await self.uow.events.append(
                TaskAssigned(aggregate_id=task.id, payload=task.model_dump(mode="json"))
            )
            return task

    async def get_task(self, task_id: UUID):
        task = await self.uow.tasks.get(task_id)
        if task is None:
            raise NotFoundException("Task not found")
        return task

    async def create_submission(self, payload: SubmissionCreate):
        async with self.uow:
            submission = await self.uow.submissions.create(payload)
            await self.uow.events.append(
                SubmissionReceived(
                    aggregate_id=submission.id,
                    payload=submission.model_dump(mode="json"),
                    user_id=submission.student_id,
                )
            )
            return submission

    async def list_submissions_for_student(self, student_id: UUID):
        return await self.uow.submissions.list_for_student(student_id)

    async def evaluate_submission(self, submission_id: UUID):
        submission = await self.uow.submissions.get(submission_id)
        if submission is None:
            raise NotFoundException("Submission not found")
        async with self.uow:
            eval_payload = self._build_evaluation_payload(submission)
            evaluation = await self.uow.evaluations.create(eval_payload)
            await self.uow.submissions.update_status(submission_id, SubmissionStatus.MENTOR_REVIEW_PENDING)
            await self.uow.events.append(
                EvaluationCompleted(
                    aggregate_id=evaluation.id,
                    payload=evaluation.model_dump(mode="json"),
                    causation_id=submission.id,
                )
            )
            return evaluation

    async def create_evaluation(self, payload: EvaluationCreate):
        if payload.kind == EvaluationKind.GITHUB_COMMIT and payload.verdict == EvaluationVerdict.STRONG:
            raise ValidationException("Use coding verdicts for GitHub evaluations")
        async with self.uow:
            return await self.uow.evaluations.create(payload)

    async def create_mentor_review(self, payload: MentorReviewCreate):
        evaluation = await self.uow.evaluations.get(payload.evaluation_id)
        if evaluation is None:
            raise NotFoundException("Evaluation not found")
        async with self.uow:
            review = await self.uow.mentor_reviews.create(payload)
            await self.uow.events.append(
                MentorReviewed(
                    aggregate_id=review.id,
                    payload=review.model_dump(mode="json"),
                    causation_id=payload.evaluation_id,
                    user_id=review.mentor_id,
                )
            )
            return review

    async def build_daily_summary(self, batch_id: UUID) -> dict:
        submissions = await self.uow.submissions.list_for_batch(batch_id)
        student_ids = await self.uow.tasks.list_student_ids_for_batch(batch_id)
        rows = []
        totals = {
            "students_expected": len(student_ids),
            "submitted": len(submissions),
            "missing": 0,
            "strong": 0,
            "flagged": 0,
            "needs_human_review": 0,
        }
        for submission in submissions:
            evaluations = await self.uow.evaluations.list_for_submission(submission.id)
            latest = evaluations[-1] if evaluations else None
            status, action, summary = "needs_review", "review_submission", "Submission received but not evaluated yet."
            if latest:
                v = latest.verdict
                if v in {EvaluationVerdict.CORRECT, EvaluationVerdict.STRONG, EvaluationVerdict.ACCEPTABLE} and latest.confidence >= 0.7:
                    status, action = "on_track", "none"
                    totals["strong"] += 1
                elif v == EvaluationVerdict.NO_VALID_SUBMISSION:
                    status, action = "missing", "send_reminder"
                    totals["missing"] += 1
                elif v == EvaluationVerdict.NEEDS_HUMAN_REVIEW:
                    totals["needs_human_review"] += 1
                else:
                    status = "flagged"
                    totals["flagged"] += 1
                summary = latest.mentor_note
            rows.append(
                {
                    "student_id": str(submission.student_id),
                    "submission_id": str(submission.id),
                    "status": status,
                    "one_line_summary": summary,
                    "recommended_mentor_action": action,
                }
            )
        summary_payload = {
            "schema_version": "mentor_daily_summary.v1",
            "batch_id": str(batch_id),
            "totals": totals,
            "students": rows,
            "batch_risks": self._batch_risks(totals),
            "mentor_actions": self._mentor_actions(rows),
        }
        await self.uow.events.append(
            DailySummaryGenerated(aggregate_id=batch_id, payload=summary_payload)
        )
        return summary_payload

    async def ai_evaluate_submission(
        self, submission_id: UUID, orchestrator: "AgentOrchestrator"
    ) -> Evaluation:
        """AI-powered evaluation of a submission using the configured agent orchestrator.

        Unlike ``evaluate_submission`` (deterministic bootstrap), this method calls
        the Anthropic API when configured, and falls back to bootstrap results when not.
        Dispatches ``EvaluationCompleted`` after the transaction commits.
        """
        submission = await self.uow.submissions.get(submission_id)
        if submission is None:
            raise NotFoundException("Submission not found")
        task = await self.uow.tasks.get(submission.task_id)
        if task is None:
            raise NotFoundException("Task not found for submission")
        async with self.uow:
            eval_payload = await orchestrator.evaluate_submission(task, submission)
            evaluation = await self.uow.evaluations.create(eval_payload)
            await self.uow.submissions.update_status(
                submission_id, SubmissionStatus.MENTOR_REVIEW_PENDING
            )
            await self.uow.events.append(
                EvaluationCompleted(
                    aggregate_id=evaluation.id,
                    payload=evaluation.model_dump(mode="json"),
                    causation_id=submission.id,
                )
            )
            return evaluation

    async def suggest_task(
        self,
        student_id: UUID,
        project_id: UUID,
        batch_id: UUID,
        due_on: date,
        orchestrator: "AgentOrchestrator",
    ) -> Task:
        """Generate and persist an AI-suggested daily task for a student.

        Raises ``NotFoundException`` when the student or project cannot be found.
        Raises ``InfrastructureException`` when the AI orchestrator is not configured.
        Dispatches ``TaskAssigned`` after the transaction commits.
        """
        from app.agents.base import TaskGenContext

        student = await self.uow.students.get(student_id)
        if student is None:
            raise NotFoundException("Student not found")
        project = await self.uow.projects.get(project_id)
        if project is None:
            raise NotFoundException("Project not found")
        previous_tasks = await self.uow.tasks.list_for_student(student_id)
        context = TaskGenContext(
            student=student,
            project=project,
            previous_tasks=previous_tasks,
        )
        task_payload = await orchestrator.generate_task(
            context, student.organization_id, batch_id, due_on
        )
        async with self.uow:
            task = await self.uow.tasks.create(task_payload)
            await self.uow.events.append(
                TaskAssigned(aggregate_id=task.id, payload=task.model_dump(mode="json"))
            )
            return task

    def _build_evaluation_payload(self, submission: Submission) -> EvaluationCreate:
        if submission.self_status == SelfStatus.SKIPPED:
            return EvaluationCreate(
                organization_id=submission.organization_id,
                submission_id=submission.id,
                kind=EvaluationKind.TRANSCRIPT,
                verdict=EvaluationVerdict.NO_VALID_SUBMISSION,
                score=0,
                confidence=1.0,
                evidence=[Evidence(type="submission_status", reference=str(submission.id), summary="Student marked the task as skipped.")],
                flags=["student_skipped_task"],
                mentor_note="Student skipped the assigned task.",
                student_feedback_draft="You skipped this task. Please complete the next assigned item or contact your mentor if blocked.",
                recommended_next_action="send_reminder",
            )
        if submission.commit_url:
            return EvaluationCreate(
                organization_id=submission.organization_id,
                submission_id=submission.id,
                kind=EvaluationKind.GITHUB_COMMIT,
                verdict=EvaluationVerdict.NEEDS_HUMAN_REVIEW,
                score=60,
                confidence=0.45,
                evidence=[Evidence(type="commit_url", reference=str(submission.commit_url), summary="Commit URL submitted.")],
                flags=["github_integration_not_connected"],
                mentor_note="Coding submission received. Connect GitHub diff ingestion before automated correctness judgment.",
                student_feedback_draft="Your coding submission was received and is waiting for mentor review.",
                recommended_next_action="mentor_review_required",
            )
        if submission.transcript_text or submission.transcript_url:
            return EvaluationCreate(
                organization_id=submission.organization_id,
                submission_id=submission.id,
                kind=EvaluationKind.TRANSCRIPT,
                verdict=EvaluationVerdict.NEEDS_HUMAN_REVIEW,
                score=60,
                confidence=0.45,
                evidence=[Evidence(type="transcript", reference=str(submission.transcript_url or "inline_transcript"), summary="Transcript submitted.")],
                flags=["transcript_ai_rubric_not_connected"],
                mentor_note="Transcript submission received. Connect transcript rubric evaluation before automated readiness judgment.",
                student_feedback_draft="Your spoken explanation submission was received and is waiting for mentor review.",
                recommended_next_action="mentor_review_required",
            )
        return EvaluationCreate(
            organization_id=submission.organization_id,
            submission_id=submission.id,
            kind=EvaluationKind.GITHUB_COMMIT,
            verdict=EvaluationVerdict.NEEDS_HUMAN_REVIEW,
            score=0,
            confidence=1.0,
            evidence=[Evidence(type="submission", reference=str(submission.id), summary="No machine-readable evidence was attached.")],
            flags=["missing_evidence"],
            mentor_note="Submission is missing usable evidence.",
            student_feedback_draft="Your submission is missing the required evidence link.",
            recommended_next_action="request_revision",
        )

    def _batch_risks(self, totals: dict) -> list[str]:
        risks = []
        if totals["missing"] > 0:
            risks.append("Some students have no valid submission.")
        if totals["needs_human_review"] > 0:
            risks.append("Some evaluations need mentor review before feedback release.")
        return risks

    def _mentor_actions(self, rows: list[dict]) -> list[str]:
        actions = []
        if any(r["recommended_mentor_action"] == "review_submission" for r in rows):
            actions.append("Review pending evaluated submissions.")
        if any(r["recommended_mentor_action"] == "send_reminder" for r in rows):
            actions.append("Send reminders to students with missing or skipped work.")
        return actions
