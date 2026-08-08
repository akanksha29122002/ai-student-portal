"""Tests for the Event Bus milestone.

Covers:
- InMemoryEventBus: subscribe, publish, wildcard, handler exceptions
- EventDispatchingUnitOfWork: dispatch after commit, suppress after rollback
- HandlerRegistry: wire workers to bus, workers_for lookup
- Integration: service operation → event collected → dispatched → handler called
"""
import asyncio
from uuid import uuid4

import pytest

from app.domain.events import (
    DomainEvent,
    EvaluationCompleted,
    MentorReviewed,
    StudentRegistered,
    SubmissionReceived,
    SubmissionValidated,
    TaskAssigned,
)
from app.events.bus import EventDispatchingUnitOfWork, InMemoryEventBus
from app.events.registry import HandlerRegistry, _sync_adapter, make_default_registry
from app.infrastructure.repositories.memory import AsyncMemoryUnitOfWork
from app.schemas.core import OrganizationCreate, StudentCreate, BatchCreate
from app.services.store import InMemoryStore


def _run(coro):
    return asyncio.run(coro)


def _student_event(student_id=None) -> StudentRegistered:
    return StudentRegistered(
        aggregate_id=student_id or uuid4(),
        payload={"email": "test@example.com"},
    )


def _submission_event(submission_id=None) -> SubmissionReceived:
    return SubmissionReceived(
        aggregate_id=submission_id or uuid4(),
        payload={"task_id": str(uuid4())},
    )


# ---------------------------------------------------------------------------
# InMemoryEventBus
# ---------------------------------------------------------------------------


def test_bus_publish_invokes_subscribed_handler():
    bus = InMemoryEventBus()
    received: list[DomainEvent] = []

    async def handler(event: DomainEvent) -> None:
        received.append(event)

    bus.subscribe("StudentRegistered", handler)
    event = _student_event()
    _run(bus.publish(event))

    assert len(received) == 1
    assert received[0].event_id == event.event_id


def test_bus_publish_does_not_invoke_wrong_handler():
    bus = InMemoryEventBus()
    received: list[DomainEvent] = []

    async def handler(event: DomainEvent) -> None:
        received.append(event)

    bus.subscribe("EvaluationCompleted", handler)
    _run(bus.publish(_student_event()))

    assert received == []


def test_bus_wildcard_handler_receives_all_events():
    bus = InMemoryEventBus()
    received: list[str] = []

    async def handler(event: DomainEvent) -> None:
        received.append(event.event_type)

    bus.subscribe("*", handler)
    _run(bus.publish(_student_event()))
    _run(bus.publish(_submission_event()))

    assert received == ["StudentRegistered", "SubmissionReceived"]


def test_bus_multiple_handlers_for_same_event_type():
    bus = InMemoryEventBus()
    calls: list[str] = []

    async def h1(event):
        calls.append("h1")

    async def h2(event):
        calls.append("h2")

    bus.subscribe("StudentRegistered", h1)
    bus.subscribe("StudentRegistered", h2)
    _run(bus.publish(_student_event()))

    assert calls == ["h1", "h2"]


def test_bus_handler_exception_does_not_prevent_sibling_handlers():
    bus = InMemoryEventBus()
    calls: list[str] = []

    async def bad_handler(event):
        raise RuntimeError("boom")

    async def good_handler(event):
        calls.append("good")

    bus.subscribe("StudentRegistered", bad_handler)
    bus.subscribe("StudentRegistered", good_handler)
    _run(bus.publish(_student_event()))

    assert calls == ["good"]


def test_bus_published_property_accumulates_events():
    bus = InMemoryEventBus()
    e1 = _student_event()
    e2 = _submission_event()
    _run(bus.publish(e1))
    _run(bus.publish(e2))

    assert len(bus.published) == 2
    assert {e.event_id for e in bus.published} == {e1.event_id, e2.event_id}


def test_bus_clear_resets_published():
    bus = InMemoryEventBus()
    _run(bus.publish(_student_event()))
    bus.clear()
    assert bus.published == []


# ---------------------------------------------------------------------------
# EventDispatchingUnitOfWork
# ---------------------------------------------------------------------------


def _make_dispatching_uow(bus=None):
    store = InMemoryStore()
    inner = AsyncMemoryUnitOfWork(store)
    if bus is None:
        bus = InMemoryEventBus()
    return EventDispatchingUnitOfWork(inner, bus), bus, store


def test_dispatching_uow_publishes_event_after_commit():
    uow, bus, _ = _make_dispatching_uow()
    event = _student_event()

    async def _go():
        async with uow:
            await uow.events.append(event)

    _run(_go())

    assert any(e.event_id == event.event_id for e in bus.published)


def test_dispatching_uow_suppresses_event_on_rollback():
    uow, bus, _ = _make_dispatching_uow()
    event = _student_event()

    async def _go():
        try:
            async with uow:
                await uow.events.append(event)
                raise RuntimeError("force rollback")
        except RuntimeError:
            pass

    _run(_go())

    assert bus.published == []


def test_dispatching_uow_delegates_repo_attributes():
    uow, bus, store = _make_dispatching_uow()

    async def _go():
        async with uow:
            org = await uow.organizations.create(OrganizationCreate(name="Kalvium", slug="kalvium"))
        return org

    org = _run(_go())
    assert org.id in store.organizations


def test_dispatching_uow_dispatches_multiple_events():
    uow, bus, _ = _make_dispatching_uow()
    e1 = _student_event()
    e2 = _submission_event()

    async def _go():
        async with uow:
            await uow.events.append(e1)
            await uow.events.append(e2)

    _run(_go())

    published_ids = {e.event_id for e in bus.published}
    assert {e1.event_id, e2.event_id} == published_ids


def test_dispatching_uow_pending_cleared_between_transactions():
    uow, bus, _ = _make_dispatching_uow()
    e1 = _student_event()

    async def _go():
        async with uow:
            await uow.events.append(e1)

    _run(_go())
    bus.clear()

    e2 = _submission_event()

    async def _go2():
        async with uow:
            await uow.events.append(e2)

    _run(_go2())

    assert len(bus.published) == 1
    assert bus.published[0].event_id == e2.event_id


# ---------------------------------------------------------------------------
# HandlerRegistry
# ---------------------------------------------------------------------------


def test_registry_workers_for_returns_matching_workers():
    from app.workers.submission_worker import SubmissionWorker
    from app.workers.evaluation_worker import EvaluationWorker

    registry = HandlerRegistry()
    sw = SubmissionWorker()
    ew = EvaluationWorker()
    registry.register(sw, ew)

    assert registry.workers_for("SubmissionReceived") == [sw]
    assert registry.workers_for("SubmissionValidated") == [ew]
    assert registry.workers_for("EvaluationStarted") == [ew]
    assert registry.workers_for("MentorReviewed") == []


def test_registry_wire_subscribes_workers_to_bus():
    from app.workers.submission_worker import SubmissionWorker

    bus = InMemoryEventBus()
    registry = HandlerRegistry()
    registry.register(SubmissionWorker())
    registry.wire(bus)

    handled: list[str] = []

    async def spy(event: DomainEvent) -> None:
        handled.append(event.event_type)

    bus.subscribe("SubmissionReceived", spy)
    _run(bus.publish(_submission_event()))

    assert "SubmissionReceived" in handled


def test_default_registry_includes_all_workers():
    registry = make_default_registry()
    assert registry.workers_for("SubmissionReceived")
    assert registry.workers_for("SubmissionValidated")
    assert registry.workers_for("EvaluationStarted")
    assert registry.workers_for("EvaluationCompleted")
    assert registry.workers_for("MentorReviewed")
    assert registry.workers_for("ReminderTriggered")


# ---------------------------------------------------------------------------
# Integration — service creates entity → event dispatched → handler called
# ---------------------------------------------------------------------------


def test_service_student_creation_dispatches_student_registered():
    from datetime import date
    from app.application.async_daily_loop_service import AsyncDailyLoopService
    from app.schemas.core import BatchCreate

    bus = InMemoryEventBus()
    store = InMemoryStore()
    inner = AsyncMemoryUnitOfWork(store)
    dispatching_uow = EventDispatchingUnitOfWork(inner, bus)
    service = AsyncDailyLoopService(dispatching_uow)

    async def _go():
        org = await service.create_organization(OrganizationCreate(name="Kalvium", slug="kalvium"))
        batch = await service.create_batch(BatchCreate(
            organization_id=org.id, name="B1",
            starts_on=date(2026, 8, 1), ends_on=date(2026, 8, 31),
        ))
        student = await service.create_student(StudentCreate(
            organization_id=org.id, batch_id=batch.id,
            full_name="Asha Kumar", email="asha@example.com",
        ))
        return student

    student = _run(_go())

    student_registered = [
        e for e in bus.published
        if e.event_type == "StudentRegistered" and e.aggregate_id == student.id
    ]
    assert len(student_registered) == 1


def test_service_submission_creation_dispatches_submission_received():
    from datetime import date
    from app.application.async_daily_loop_service import AsyncDailyLoopService
    from app.domain.enums import SelfStatus, TaskType
    from app.schemas.core import BatchCreate, ProjectCreate, SubmissionCreate, TaskCreate

    bus = InMemoryEventBus()
    store = InMemoryStore()
    dispatching_uow = EventDispatchingUnitOfWork(AsyncMemoryUnitOfWork(store), bus)
    service = AsyncDailyLoopService(dispatching_uow)

    async def _go():
        org = await service.create_organization(OrganizationCreate(name="Kalvium", slug="kalvium"))
        batch = await service.create_batch(BatchCreate(
            organization_id=org.id, name="B1",
            starts_on=date(2026, 8, 1), ends_on=date(2026, 8, 31),
        ))
        student = await service.create_student(StudentCreate(
            organization_id=org.id, batch_id=batch.id,
            full_name="Alice", email="alice@example.com",
        ))
        project = await service.create_project(ProjectCreate(
            organization_id=org.id, student_id=student.id,
            name="Defense App", repository_url="https://github.com/x/y",
        ))
        task = await service.create_task(TaskCreate(
            organization_id=org.id, batch_id=batch.id,
            student_id=student.id, project_id=project.id,
            task_type=TaskType.CODING, title="Rate limiting",
            problem_statement="Protect login endpoint.", acceptance_criteria=["AC1."],
            due_on=date(2026, 8, 7),
        ))
        return await service.create_submission(SubmissionCreate(
            organization_id=org.id, task_id=task.id, student_id=student.id,
            self_status=SelfStatus.SOLVED,
            commit_url="https://github.com/x/y/commit/abc",
        ))

    submission = _run(_go())

    assert any(
        e.event_type == "SubmissionReceived" and e.aggregate_id == submission.id
        for e in bus.published
    )


def test_dispatching_uow_rollback_does_not_leak_events_to_store():
    """Rolled-back transaction leaves the store AND bus clean."""
    bus = InMemoryEventBus()
    store = InMemoryStore()
    uow = EventDispatchingUnitOfWork(AsyncMemoryUnitOfWork(store), bus)

    async def _go():
        try:
            async with uow:
                await uow.organizations.create(OrganizationCreate(name="X", slug="x"))
                await uow.events.append(_student_event())
                raise ValueError("abort")
        except ValueError:
            pass

    _run(_go())

    assert store.organizations == {}
    assert bus.published == []
