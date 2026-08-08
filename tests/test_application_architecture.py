from datetime import date

import pytest

from app.application.daily_loop_service import DailyLoopService
from app.domain.events import SubmissionReceived
from app.schemas.core import BatchCreate, OrganizationCreate, StudentCreate, SubmissionCreate
from app.domain.enums import SelfStatus
from app.infrastructure.repositories.memory import MemoryUnitOfWork
from app.services.evaluation_service import EvaluationService
from app.services.store import InMemoryStore
from app.shared.exceptions import NotFoundException


def test_memory_unit_of_work_rolls_back_failed_transaction():
    store = InMemoryStore()
    uow = MemoryUnitOfWork(store)

    with pytest.raises(RuntimeError):
        with uow:
            uow.organizations.create(OrganizationCreate(name="Rollback University", slug="rollback-university"))
            raise RuntimeError("force rollback")

    assert store.organizations == {}


def test_daily_loop_service_records_student_registered_event():
    store = InMemoryStore()
    service = DailyLoopService(MemoryUnitOfWork(store), EvaluationService(store))
    org = service.create_organization(OrganizationCreate(name="Acme University", slug="acme-university"))
    batch = service.create_batch(BatchCreate(organization_id=org.id, name="Batch A", starts_on=date(2026, 8, 7), ends_on=date(2026, 8, 14)))

    student = service.create_student(StudentCreate(organization_id=org.id, batch_id=batch.id, full_name="Asha Kumar", email="asha@example.com"))

    events = store.domain_events
    assert events[0].event_type == "StudentRegistered"
    assert events[0].aggregate_id == student.id


def test_event_store_filters_by_aggregate():
    store = InMemoryStore()
    uow = MemoryUnitOfWork(store)
    org = uow.organizations.create(OrganizationCreate(name="Acme University", slug="acme-university"))
    event = SubmissionReceived(aggregate_id=org.id, payload={"status": "received"})

    uow.events.append(event)

    assert uow.events.list_by_aggregate(org.id) == [event]


def test_get_missing_task_raises_domain_not_found():
    store = InMemoryStore()
    service = DailyLoopService(MemoryUnitOfWork(store), EvaluationService(store))

    with pytest.raises(NotFoundException):
        service.get_task(store.create_organization(OrganizationCreate(name="Acme", slug="acme")).id)

