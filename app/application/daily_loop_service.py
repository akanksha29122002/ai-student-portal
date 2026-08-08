from uuid import UUID

from app.application.unit_of_work import UnitOfWork
from app.domain.enums import EvaluationKind, EvaluationVerdict, SubmissionStatus
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
    EvaluationCreate,
    MentorReviewCreate,
    OrganizationCreate,
    ProjectCreate,
    StudentCreate,
    SubmissionCreate,
    TaskCreate,
)
from app.services.evaluation_service import EvaluationService
from app.shared.exceptions import NotFoundException, ValidationException


class DailyLoopService:
    def __init__(self, uow: UnitOfWork, evaluation_service: EvaluationService) -> None:
        self.uow = uow
        self.evaluation_service = evaluation_service

    def create_organization(self, payload: OrganizationCreate):
        with self.uow:
            return self.uow.organizations.create(payload)

    def create_batch(self, payload: BatchCreate):
        with self.uow:
            return self.uow.batches.create(payload)

    def create_student(self, payload: StudentCreate):
        with self.uow:
            student = self.uow.students.create(payload)
            self.uow.events.append(
                StudentRegistered(
                    aggregate_id=student.id,
                    payload=student.model_dump(mode="json"),
                    user_id=student.mentor_id,
                )
            )
            return student

    def create_project(self, payload: ProjectCreate):
        with self.uow:
            project = self.uow.projects.create(payload)
            self.uow.events.append(ProjectCreated(aggregate_id=project.id, payload=project.model_dump(mode="json")))
            return project

    def create_task(self, payload: TaskCreate):
        with self.uow:
            task = self.uow.tasks.create(payload)
            self.uow.events.append(TaskAssigned(aggregate_id=task.id, payload=task.model_dump(mode="json")))
            return task

    def get_task(self, task_id: UUID):
        task = self.uow.tasks.get(task_id)
        if task is None:
            raise NotFoundException("Task not found")
        return task

    def create_submission(self, payload: SubmissionCreate):
        with self.uow:
            submission = self.uow.submissions.create(payload)
            self.uow.events.append(
                SubmissionReceived(
                    aggregate_id=submission.id,
                    payload=submission.model_dump(mode="json"),
                    user_id=submission.student_id,
                )
            )
            return submission

    def evaluate_submission(self, submission_id: UUID):
        submission = self.uow.submissions.get(submission_id)
        if submission is None:
            raise NotFoundException("Submission not found")
        with self.uow:
            evaluation = self.evaluation_service.evaluate_submission(submission)
            self.uow.submissions.update_status(submission_id, SubmissionStatus.MENTOR_REVIEW_PENDING)
            self.uow.events.append(
                EvaluationCompleted(
                    aggregate_id=evaluation.id,
                    payload=evaluation.model_dump(mode="json"),
                    causation_id=submission.id,
                )
            )
            return evaluation

    def create_evaluation(self, payload: EvaluationCreate):
        if payload.kind == EvaluationKind.GITHUB_COMMIT and payload.verdict == EvaluationVerdict.STRONG:
            raise ValidationException("Use coding verdicts for GitHub evaluations")
        with self.uow:
            return self.uow.evaluations.create(payload)

    def create_mentor_review(self, payload: MentorReviewCreate):
        evaluation = self.uow.evaluations.get(payload.evaluation_id)
        if evaluation is None:
            raise NotFoundException("Evaluation not found")
        with self.uow:
            review = self.uow.mentor_reviews.create(payload)
            self.uow.events.append(
                MentorReviewed(
                    aggregate_id=review.id,
                    payload=review.model_dump(mode="json"),
                    causation_id=payload.evaluation_id,
                    user_id=review.mentor_id,
                )
            )
            return review

    def build_daily_summary(self, batch_id: UUID):
        summary = self.evaluation_service.build_daily_summary(batch_id)
        self.uow.events.append(
            DailySummaryGenerated(
                aggregate_id=batch_id,
                payload=summary,
            )
        )
        return summary

