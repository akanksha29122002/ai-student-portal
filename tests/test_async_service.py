"""Tests for AsyncDailyLoopService backed by AsyncMemoryUnitOfWork."""
import asyncio
from datetime import date
from uuid import uuid4

import pytest

from app.application.async_daily_loop_service import AsyncDailyLoopService
from app.domain.enums import EvaluationKind, EvaluationVerdict, MentorReviewDecision, SelfStatus, SubmissionStatus, TaskType
from app.infrastructure.repositories.memory import AsyncMemoryUnitOfWork
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
from app.services.store import InMemoryStore
from app.shared.exceptions import NotFoundException, ValidationException


def _run(coro):
    return asyncio.run(coro)


def _make_service() -> tuple[AsyncDailyLoopService, InMemoryStore]:
    store = InMemoryStore()
    uow = AsyncMemoryUnitOfWork(store)
    return AsyncDailyLoopService(uow), store


def test_async_service_creates_organization():
    service, store = _make_service()

    org = _run(service.create_organization(OrganizationCreate(name="Kalvium", slug="kalvium")))

    assert org.name == "Kalvium"
    assert org.id is not None


def test_async_service_creates_batch():
    service, _ = _make_service()
    org = _run(service.create_organization(OrganizationCreate(name="Kalvium", slug="kalvium")))

    batch = _run(service.create_batch(BatchCreate(
        organization_id=org.id, name="Batch 1",
        starts_on=date(2026, 8, 1), ends_on=date(2026, 8, 31),
    )))

    assert batch.organization_id == org.id


def test_async_service_create_student_emits_registered_event():
    service, store = _make_service()
    org = _run(service.create_organization(OrganizationCreate(name="Kalvium", slug="kalvium")))
    batch = _run(service.create_batch(BatchCreate(
        organization_id=org.id, name="Batch 1",
        starts_on=date(2026, 8, 1), ends_on=date(2026, 8, 31),
    )))

    student = _run(service.create_student(StudentCreate(
        organization_id=org.id, batch_id=batch.id,
        full_name="Asha Kumar", email="asha@example.com",
    )))

    events = store.domain_events
    assert any(e.event_type == "StudentRegistered" and e.aggregate_id == student.id for e in events)


def test_async_service_get_task_raises_not_found_for_missing_id():
    service, _ = _make_service()

    with pytest.raises(NotFoundException):
        _run(service.get_task(uuid4()))


def test_async_service_create_task_and_get():
    service, _ = _make_service()
    org = _run(service.create_organization(OrganizationCreate(name="Kalvium", slug="kalvium")))
    batch = _run(service.create_batch(BatchCreate(
        organization_id=org.id, name="Batch 1",
        starts_on=date(2026, 8, 1), ends_on=date(2026, 8, 31),
    )))
    student = _run(service.create_student(StudentCreate(
        organization_id=org.id, batch_id=batch.id, full_name="Asha Kumar", email="asha@example.com",
    )))
    project = _run(service.create_project(ProjectCreate(
        organization_id=org.id, student_id=student.id,
        name="Defense App", repository_url="https://github.com/example/defense",
    )))

    task = _run(service.create_task(TaskCreate(
        organization_id=org.id, batch_id=batch.id, student_id=student.id,
        project_id=project.id, task_type=TaskType.CODING,
        title="Add rate limiting",
        problem_statement="Protect login endpoint from brute-force attacks.",
        acceptance_criteria=["Failed attempts throttled after 5 tries."],
        due_on=date(2026, 8, 7),
    )))
    fetched = _run(service.get_task(task.id))

    assert fetched.id == task.id
    assert fetched.title == "Add rate limiting"


def test_async_service_create_submission_emits_received_event():
    service, store = _make_service()
    org = _run(service.create_organization(OrganizationCreate(name="Kalvium", slug="kalvium")))
    batch = _run(service.create_batch(BatchCreate(
        organization_id=org.id, name="Batch 1",
        starts_on=date(2026, 8, 1), ends_on=date(2026, 8, 31),
    )))
    student = _run(service.create_student(StudentCreate(
        organization_id=org.id, batch_id=batch.id, full_name="Asha Kumar", email="asha@example.com",
    )))
    project = _run(service.create_project(ProjectCreate(
        organization_id=org.id, student_id=student.id,
        name="Defense App", repository_url="https://github.com/example/defense",
    )))
    task = _run(service.create_task(TaskCreate(
        organization_id=org.id, batch_id=batch.id, student_id=student.id,
        project_id=project.id, task_type=TaskType.CODING, title="Task 1",
        problem_statement="Problem statement for task 1.", acceptance_criteria=["Criterion 1."],
        due_on=date(2026, 8, 7),
    )))

    submission = _run(service.create_submission(SubmissionCreate(
        organization_id=org.id, task_id=task.id, student_id=student.id,
        self_status=SelfStatus.SOLVED, commit_url="https://github.com/example/defense/commit/abc",
    )))

    assert any(e.event_type == "SubmissionReceived" and e.aggregate_id == submission.id for e in store.domain_events)
    assert submission.status == SubmissionStatus.RECEIVED


def test_async_service_evaluate_submission_raises_not_found():
    service, _ = _make_service()

    with pytest.raises(NotFoundException):
        _run(service.evaluate_submission(uuid4()))


def test_async_service_evaluate_submission_creates_evaluation():
    service, store = _make_service()
    org = _run(service.create_organization(OrganizationCreate(name="Kalvium", slug="kalvium")))
    batch = _run(service.create_batch(BatchCreate(
        organization_id=org.id, name="Batch 1",
        starts_on=date(2026, 8, 1), ends_on=date(2026, 8, 31),
    )))
    student = _run(service.create_student(StudentCreate(
        organization_id=org.id, batch_id=batch.id, full_name="Asha Kumar", email="asha@example.com",
    )))
    project = _run(service.create_project(ProjectCreate(
        organization_id=org.id, student_id=student.id,
        name="Defense App", repository_url="https://github.com/example/defense",
    )))
    task = _run(service.create_task(TaskCreate(
        organization_id=org.id, batch_id=batch.id, student_id=student.id,
        project_id=project.id, task_type=TaskType.CODING, title="Task 1",
        problem_statement="Problem statement for task 1.", acceptance_criteria=["Criterion 1."],
        due_on=date(2026, 8, 7),
    )))
    submission = _run(service.create_submission(SubmissionCreate(
        organization_id=org.id, task_id=task.id, student_id=student.id,
        self_status=SelfStatus.SOLVED, commit_url="https://github.com/example/defense/commit/abc",
    )))

    evaluation = _run(service.evaluate_submission(submission.id))

    assert evaluation.verdict == EvaluationVerdict.NEEDS_HUMAN_REVIEW
    assert any(e.event_type == "EvaluationCompleted" for e in store.domain_events)


def test_async_service_create_evaluation_rejects_wrong_verdict_kind():
    service, _ = _make_service()

    with pytest.raises(ValidationException):
        _run(service.create_evaluation(EvaluationCreate(
            organization_id=uuid4(),
            submission_id=uuid4(),
            kind=EvaluationKind.GITHUB_COMMIT,
            verdict=EvaluationVerdict.STRONG,
            score=80,
            confidence=0.9,
            evidence=[],
            flags=[],
            mentor_note="Good work.",
            student_feedback_draft="Excellent submission.",
            recommended_next_action="none",
        )))


def test_async_service_create_mentor_review_raises_not_found_for_missing_evaluation():
    service, _ = _make_service()

    with pytest.raises(NotFoundException):
        _run(service.create_mentor_review(MentorReviewCreate(
            organization_id=uuid4(),
            evaluation_id=uuid4(),
            mentor_id=uuid4(),
            decision=MentorReviewDecision.APPROVED,
            final_feedback="Well done overall.",
        )))


def test_async_service_build_daily_summary_empty_batch():
    service, _ = _make_service()

    summary = _run(service.build_daily_summary(uuid4()))

    assert summary["schema_version"] == "mentor_daily_summary.v1"
    assert summary["totals"]["students_expected"] == 0
    assert summary["totals"]["submitted"] == 0


def test_async_uow_rollback_on_exception():
    store = InMemoryStore()
    uow = AsyncMemoryUnitOfWork(store)

    async def _run_tx():
        async with uow:
            await uow.organizations.create(OrganizationCreate(name="Kalvium", slug="kalvium"))
            raise RuntimeError("force rollback")

    with pytest.raises(RuntimeError):
        _run(_run_tx())

    assert store.organizations == {}


def test_async_uow_commit_persists_changes():
    store = InMemoryStore()
    uow = AsyncMemoryUnitOfWork(store)

    async def _run_tx():
        async with uow:
            await uow.organizations.create(OrganizationCreate(name="Kalvium", slug="kalvium"))

    _run(_run_tx())

    assert len(store.organizations) == 1
