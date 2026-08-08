from datetime import date
from uuid import uuid4

import pytest

from app.domain.enums import SelfStatus, SubmissionStatus, TaskType
from app.infrastructure.repositories.memory import MemoryUnitOfWork
from app.schemas.core import (
    BatchCreate,
    EvaluationCreate,
    EvaluationKind,
    EvaluationVerdict,
    MentorReviewCreate,
    MentorReviewDecision,
    OrganizationCreate,
    ProjectCreate,
    StudentCreate,
    SubmissionCreate,
    TaskCreate,
)
from app.services.store import InMemoryStore


@pytest.fixture
def uow() -> MemoryUnitOfWork:
    return MemoryUnitOfWork(InMemoryStore())


def test_organization_repository_create(uow):
    org = uow.organizations.create(OrganizationCreate(name="Kalvium", slug="kalvium"))

    assert org.id is not None
    assert org.name == "Kalvium"
    assert org.slug == "kalvium"


def test_batch_repository_create(uow):
    org = uow.organizations.create(OrganizationCreate(name="Kalvium", slug="kalvium"))
    batch = uow.batches.create(
        BatchCreate(organization_id=org.id, name="Batch 1", starts_on=date(2026, 8, 1), ends_on=date(2026, 8, 31))
    )

    assert batch.id is not None
    assert batch.organization_id == org.id


def test_student_repository_create(uow):
    org = uow.organizations.create(OrganizationCreate(name="Kalvium", slug="kalvium"))
    batch = uow.batches.create(
        BatchCreate(organization_id=org.id, name="Batch 1", starts_on=date(2026, 8, 1), ends_on=date(2026, 8, 31))
    )
    student = uow.students.create(
        StudentCreate(organization_id=org.id, batch_id=batch.id, full_name="Asha Kumar", email="asha@example.com")
    )

    assert student.id is not None
    assert student.email == "asha@example.com"
    assert student.consecutive_missed_days == 0


def test_project_repository_create(uow):
    org = uow.organizations.create(OrganizationCreate(name="Kalvium", slug="kalvium"))
    batch = uow.batches.create(
        BatchCreate(organization_id=org.id, name="Batch 1", starts_on=date(2026, 8, 1), ends_on=date(2026, 8, 31))
    )
    student = uow.students.create(
        StudentCreate(organization_id=org.id, batch_id=batch.id, full_name="Asha Kumar", email="asha@example.com")
    )
    project = uow.projects.create(
        ProjectCreate(
            organization_id=org.id,
            student_id=student.id,
            name="Defense App",
            repository_url="https://github.com/example/defense",
        )
    )

    assert project.id is not None
    assert project.student_id == student.id


def test_task_repository_create_and_get(uow):
    org = uow.organizations.create(OrganizationCreate(name="Kalvium", slug="kalvium"))
    batch = uow.batches.create(
        BatchCreate(organization_id=org.id, name="Batch 1", starts_on=date(2026, 8, 1), ends_on=date(2026, 8, 31))
    )
    student = uow.students.create(
        StudentCreate(organization_id=org.id, batch_id=batch.id, full_name="Asha Kumar", email="asha@example.com")
    )
    project = uow.projects.create(
        ProjectCreate(
            organization_id=org.id,
            student_id=student.id,
            name="Defense App",
            repository_url="https://github.com/example/defense",
        )
    )
    task = uow.tasks.create(
        TaskCreate(
            organization_id=org.id,
            batch_id=batch.id,
            student_id=student.id,
            project_id=project.id,
            task_type=TaskType.CODING,
            title="Add rate limiting",
            problem_statement="Protect login endpoint from brute-force attacks using rate limiting.",
            acceptance_criteria=["Failed attempts are throttled after 5 tries."],
            due_on=date(2026, 8, 7),
        )
    )

    fetched = uow.tasks.get(task.id)
    assert fetched is not None
    assert fetched.id == task.id
    assert fetched.title == "Add rate limiting"


def test_task_repository_get_returns_none_for_missing(uow):
    assert uow.tasks.get(uuid4()) is None


def test_task_repository_list_student_ids_for_batch(uow):
    org = uow.organizations.create(OrganizationCreate(name="Kalvium", slug="kalvium"))
    batch = uow.batches.create(
        BatchCreate(organization_id=org.id, name="Batch 1", starts_on=date(2026, 8, 1), ends_on=date(2026, 8, 31))
    )
    student = uow.students.create(
        StudentCreate(organization_id=org.id, batch_id=batch.id, full_name="Asha Kumar", email="asha@example.com")
    )
    project = uow.projects.create(
        ProjectCreate(organization_id=org.id, student_id=student.id, name="Defense App", repository_url="https://github.com/example/defense")
    )
    uow.tasks.create(
        TaskCreate(
            organization_id=org.id, batch_id=batch.id, student_id=student.id, project_id=project.id,
            task_type=TaskType.CODING, title="Task 1",
            problem_statement="Problem statement for task 1 that is at least 10 characters.",
            acceptance_criteria=["Criterion one."], due_on=date(2026, 8, 7),
        )
    )

    ids = uow.tasks.list_student_ids_for_batch(batch.id)
    assert student.id in ids


def test_submission_repository_create_and_get(uow):
    org = uow.organizations.create(OrganizationCreate(name="Kalvium", slug="kalvium"))
    batch = uow.batches.create(
        BatchCreate(organization_id=org.id, name="Batch 1", starts_on=date(2026, 8, 1), ends_on=date(2026, 8, 31))
    )
    student = uow.students.create(
        StudentCreate(organization_id=org.id, batch_id=batch.id, full_name="Asha Kumar", email="asha@example.com")
    )
    project = uow.projects.create(
        ProjectCreate(organization_id=org.id, student_id=student.id, name="Defense App", repository_url="https://github.com/example/defense")
    )
    task = uow.tasks.create(
        TaskCreate(
            organization_id=org.id, batch_id=batch.id, student_id=student.id, project_id=project.id,
            task_type=TaskType.CODING, title="Task 1",
            problem_statement="Problem statement for task 1 that is at least 10 characters.",
            acceptance_criteria=["Criterion one."], due_on=date(2026, 8, 7),
        )
    )
    submission = uow.submissions.create(
        SubmissionCreate(
            organization_id=org.id,
            task_id=task.id,
            student_id=student.id,
            self_status=SelfStatus.SOLVED,
            commit_url="https://github.com/example/defense/commit/abc123",
        )
    )

    fetched = uow.submissions.get(submission.id)
    assert fetched is not None
    assert fetched.status == SubmissionStatus.RECEIVED
    assert fetched.student_id == student.id


def test_submission_repository_update_status(uow):
    org = uow.organizations.create(OrganizationCreate(name="Kalvium", slug="kalvium"))
    batch = uow.batches.create(
        BatchCreate(organization_id=org.id, name="Batch 1", starts_on=date(2026, 8, 1), ends_on=date(2026, 8, 31))
    )
    student = uow.students.create(
        StudentCreate(organization_id=org.id, batch_id=batch.id, full_name="Asha Kumar", email="asha@example.com")
    )
    project = uow.projects.create(
        ProjectCreate(organization_id=org.id, student_id=student.id, name="Defense App", repository_url="https://github.com/example/defense")
    )
    task = uow.tasks.create(
        TaskCreate(
            organization_id=org.id, batch_id=batch.id, student_id=student.id, project_id=project.id,
            task_type=TaskType.CODING, title="Task 1",
            problem_statement="Problem statement for task 1 that is at least 10 characters.",
            acceptance_criteria=["Criterion one."], due_on=date(2026, 8, 7),
        )
    )
    submission = uow.submissions.create(
        SubmissionCreate(
            organization_id=org.id,
            task_id=task.id,
            student_id=student.id,
            self_status=SelfStatus.SOLVED,
            commit_url="https://github.com/example/defense/commit/abc123",
        )
    )

    uow.submissions.update_status(submission.id, SubmissionStatus.EVALUATED)

    updated = uow.submissions.get(submission.id)
    assert updated.status == SubmissionStatus.EVALUATED


def test_evaluation_repository_create_and_get(uow):
    org = uow.organizations.create(OrganizationCreate(name="Kalvium", slug="kalvium"))
    batch = uow.batches.create(
        BatchCreate(organization_id=org.id, name="Batch 1", starts_on=date(2026, 8, 1), ends_on=date(2026, 8, 31))
    )
    student = uow.students.create(
        StudentCreate(organization_id=org.id, batch_id=batch.id, full_name="Asha Kumar", email="asha@example.com")
    )
    project = uow.projects.create(
        ProjectCreate(organization_id=org.id, student_id=student.id, name="Defense App", repository_url="https://github.com/example/defense")
    )
    task = uow.tasks.create(
        TaskCreate(
            organization_id=org.id, batch_id=batch.id, student_id=student.id, project_id=project.id,
            task_type=TaskType.CODING, title="Task 1",
            problem_statement="Problem statement for task 1 that is at least 10 characters.",
            acceptance_criteria=["Criterion one."], due_on=date(2026, 8, 7),
        )
    )
    submission = uow.submissions.create(
        SubmissionCreate(
            organization_id=org.id, task_id=task.id, student_id=student.id,
            self_status=SelfStatus.SOLVED, commit_url="https://github.com/example/defense/commit/abc123",
        )
    )
    evaluation = uow.evaluations.create(
        EvaluationCreate(
            organization_id=org.id,
            submission_id=submission.id,
            kind=EvaluationKind.GITHUB_COMMIT,
            verdict=EvaluationVerdict.NEEDS_HUMAN_REVIEW,
            score=60,
            confidence=0.45,
            evidence=[],
            flags=["github_not_connected"],
            mentor_note="Awaiting GitHub integration.",
            student_feedback_draft="Submission received.",
            recommended_next_action="mentor_review_required",
        )
    )

    fetched = uow.evaluations.get(evaluation.id)
    assert fetched is not None
    assert fetched.verdict == EvaluationVerdict.NEEDS_HUMAN_REVIEW


def test_evaluation_repository_list_for_submission(uow):
    org = uow.organizations.create(OrganizationCreate(name="Kalvium", slug="kalvium"))
    batch = uow.batches.create(
        BatchCreate(organization_id=org.id, name="Batch 1", starts_on=date(2026, 8, 1), ends_on=date(2026, 8, 31))
    )
    student = uow.students.create(
        StudentCreate(organization_id=org.id, batch_id=batch.id, full_name="Asha Kumar", email="asha@example.com")
    )
    project = uow.projects.create(
        ProjectCreate(organization_id=org.id, student_id=student.id, name="Defense App", repository_url="https://github.com/example/defense")
    )
    task = uow.tasks.create(
        TaskCreate(
            organization_id=org.id, batch_id=batch.id, student_id=student.id, project_id=project.id,
            task_type=TaskType.CODING, title="Task 1",
            problem_statement="Problem statement for task 1 that is at least 10 characters.",
            acceptance_criteria=["Criterion one."], due_on=date(2026, 8, 7),
        )
    )
    submission = uow.submissions.create(
        SubmissionCreate(
            organization_id=org.id, task_id=task.id, student_id=student.id,
            self_status=SelfStatus.SOLVED, commit_url="https://github.com/example/defense/commit/abc123",
        )
    )
    uow.evaluations.create(
        EvaluationCreate(
            organization_id=org.id, submission_id=submission.id,
            kind=EvaluationKind.GITHUB_COMMIT, verdict=EvaluationVerdict.NEEDS_HUMAN_REVIEW,
            score=60, confidence=0.45, evidence=[], flags=[],
            mentor_note="Awaiting GitHub integration.", student_feedback_draft="Submission received.",
            recommended_next_action="mentor_review_required",
        )
    )

    evaluations = uow.evaluations.list_for_submission(submission.id)
    assert len(evaluations) == 1
    assert uow.evaluations.list_for_submission(uuid4()) == []


def test_evaluation_repository_get_returns_none_for_missing(uow):
    assert uow.evaluations.get(uuid4()) is None


def test_mentor_review_repository_create(uow):
    review = uow.mentor_reviews.create(
        MentorReviewCreate(
            organization_id=uuid4(),
            evaluation_id=uuid4(),
            mentor_id=uuid4(),
            decision=MentorReviewDecision.APPROVED,
            final_feedback="Great work, well-structured implementation.",
        )
    )

    assert review.id is not None
    assert review.decision == MentorReviewDecision.APPROVED
