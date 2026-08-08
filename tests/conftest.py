from datetime import date
from uuid import uuid4

import pytest

from app.application.daily_loop_service import DailyLoopService
from app.domain.enums import SelfStatus, TaskType
from app.infrastructure.repositories.memory import MemoryUnitOfWork
from app.schemas.core import (
    BatchCreate,
    OrganizationCreate,
    ProjectCreate,
    StudentCreate,
    SubmissionCreate,
    TaskCreate,
)
from app.services.evaluation_service import EvaluationService
from app.services.store import InMemoryStore


@pytest.fixture
def store() -> InMemoryStore:
    return InMemoryStore()


@pytest.fixture
def uow(store: InMemoryStore) -> MemoryUnitOfWork:
    return MemoryUnitOfWork(store)


@pytest.fixture
def evaluation_service(store: InMemoryStore) -> EvaluationService:
    return EvaluationService(store)


@pytest.fixture
def service(uow: MemoryUnitOfWork, evaluation_service: EvaluationService) -> DailyLoopService:
    return DailyLoopService(uow, evaluation_service)


@pytest.fixture
def org_payload() -> OrganizationCreate:
    return OrganizationCreate(name="Test University", slug="test-university")


@pytest.fixture
def batch_payload(org_payload: OrganizationCreate) -> BatchCreate:
    return BatchCreate(
        organization_id=uuid4(),
        name="Batch 2026",
        starts_on=date(2026, 8, 1),
        ends_on=date(2026, 8, 31),
    )


@pytest.fixture
def student_payload() -> StudentCreate:
    return StudentCreate(
        organization_id=uuid4(),
        batch_id=uuid4(),
        full_name="Asha Kumar",
        email="asha@example.com",
    )


@pytest.fixture
def project_payload() -> ProjectCreate:
    return ProjectCreate(
        organization_id=uuid4(),
        student_id=uuid4(),
        name="Defense Prep App",
        repository_url="https://github.com/example/defense-prep",
    )


@pytest.fixture
def task_payload() -> TaskCreate:
    return TaskCreate(
        organization_id=uuid4(),
        batch_id=uuid4(),
        student_id=uuid4(),
        project_id=uuid4(),
        task_type=TaskType.CODING,
        title="Implement rate limiting",
        problem_statement="Add rate limiting to protect the login endpoint from brute-force attacks.",
        acceptance_criteria=["Repeated failed login attempts are throttled after 5 tries."],
        due_on=date(2026, 8, 7),
    )


@pytest.fixture
def submission_payload(task_payload: TaskCreate) -> SubmissionCreate:
    return SubmissionCreate(
        organization_id=task_payload.organization_id,
        task_id=uuid4(),
        student_id=task_payload.student_id,
        self_status=SelfStatus.SOLVED,
        commit_url="https://github.com/example/defense-prep/commit/abc123",
    )
