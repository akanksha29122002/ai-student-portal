from collections.abc import AsyncIterator
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_async_service
from app.application.async_daily_loop_service import AsyncDailyLoopService
from app.domain.events import DomainEvent
from app.domain.enums import UserRole
from app.events.bus import EventDispatchingUnitOfWork, InMemoryEventBus, OptionalEventBus
from app.infrastructure.repositories.memory import AsyncMemoryUnitOfWork
from app.main import create_app
from app.schemas.auth import CurrentUser
from app.services.store import InMemoryStore
from app.shared.exceptions import InfrastructureException


class FailingEventBus:
    async def publish(self, event: DomainEvent) -> None:
        raise ConnectionError("redis unavailable")


def _headers() -> dict[str, str]:
    return {}


def _make_client_with_bus(bus, *, raise_server_exceptions: bool = True) -> tuple[TestClient, InMemoryStore]:
    store = InMemoryStore()
    app = create_app()

    async def _service_override() -> AsyncIterator[AsyncDailyLoopService]:
        uow = EventDispatchingUnitOfWork(AsyncMemoryUnitOfWork(store), bus)
        yield AsyncDailyLoopService(uow)

    app.dependency_overrides[get_async_service] = _service_override
    return TestClient(app, raise_server_exceptions=raise_server_exceptions), store


def _create_org_batch_student(client: TestClient) -> tuple[dict, dict, dict]:
    org = client.post(
        "/organizations",
        json={"name": "Project Defense Pilot", "slug": "project-defense-pilot"},
        headers=_headers(),
    )
    assert org.status_code == 201
    batch = client.post(
        "/batches",
        json={
            "organization_id": org.json()["id"],
            "name": "Project Defense Pilot",
            "starts_on": str(date(2026, 8, 17)),
            "ends_on": str(date(2026, 12, 31)),
        },
        headers=_headers(),
    )
    assert batch.status_code == 201
    student = client.post(
        "/students",
        json={
            "organization_id": org.json()["id"],
            "batch_id": batch.json()["id"],
            "full_name": "Akanksha Kumari",
            "email": "akankshame422@gmail.com",
            "track": "track_a",
        },
        headers=_headers(),
    )
    assert student.status_code == 201
    return org.json(), batch.json(), student.json()


def test_no_redis_url_uses_in_memory_event_bus(monkeypatch):
    from app.api import dependencies
    from app.core.config import Environment, settings

    monkeypatch.setattr(settings, "environment", Environment.DEVELOPMENT)
    monkeypatch.setattr(settings, "redis_url", "")
    monkeypatch.setattr(settings, "redis_required", False)

    assert isinstance(dependencies._get_bus(), InMemoryEventBus)


def test_production_without_redis_url_does_not_attempt_localhost_redis(monkeypatch):
    from app.api import dependencies
    from app.core.config import Environment, settings

    monkeypatch.setattr(settings, "environment", Environment.PRODUCTION)
    monkeypatch.setattr(settings, "redis_url", "")
    monkeypatch.setattr(settings, "redis_required", False)

    bus = dependencies._get_bus()

    assert isinstance(bus, InMemoryEventBus)


def test_redis_unavailable_required_false_falls_back_to_in_memory(monkeypatch):
    from app.api import dependencies
    from app.core.config import Environment, settings
    from app.events import redis_bus

    def _fail(_redis_url=None):
        raise ConnectionError("redis unavailable")

    monkeypatch.setattr(settings, "environment", Environment.PRODUCTION)
    monkeypatch.setattr(settings, "redis_url", "redis://example.invalid:6379/0")
    monkeypatch.setattr(settings, "redis_required", False)
    monkeypatch.setattr(redis_bus, "make_redis_bus", _fail)

    assert isinstance(dependencies._get_bus(), InMemoryEventBus)


def test_redis_unavailable_required_true_fails_clearly(monkeypatch):
    from app.api import dependencies
    from app.core.config import Environment, settings
    from app.events import redis_bus

    def _fail(_redis_url=None):
        raise ConnectionError("redis unavailable")

    monkeypatch.setattr(settings, "environment", Environment.PRODUCTION)
    monkeypatch.setattr(settings, "redis_url", "redis://example.invalid:6379/0")
    monkeypatch.setattr(settings, "redis_required", True)
    monkeypatch.setattr(redis_bus, "make_redis_bus", _fail)

    with pytest.raises(InfrastructureException, match="Redis event bus is required"):
        dependencies._get_bus()


def test_redis_required_true_without_url_fails_clearly(monkeypatch):
    from app.api import dependencies
    from app.core.config import Environment, settings

    monkeypatch.setattr(settings, "environment", Environment.PRODUCTION)
    monkeypatch.setattr(settings, "redis_url", "")
    monkeypatch.setattr(settings, "redis_required", True)

    with pytest.raises(InfrastructureException, match="REDIS_REQUIRED=true"):
        dependencies._get_bus()


def test_create_student_succeeds_when_optional_redis_publish_fails():
    bus = OptionalEventBus(FailingEventBus(), required=False)
    client, store = _make_client_with_bus(bus)

    org, batch, student = _create_org_batch_student(client)

    assert org["id"] in {str(item.id) for item in store.organizations.values()}
    assert batch["id"] in {str(item.id) for item in store.batches.values()}
    assert student["id"] in {str(item.id) for item in store.students.values()}


def test_required_redis_publish_failure_returns_server_error_after_commit():
    bus = OptionalEventBus(FailingEventBus(), required=True)
    client, store = _make_client_with_bus(bus, raise_server_exceptions=False)

    org_response = client.post(
        "/organizations",
        json={"name": "Project Defense Pilot", "slug": "project-defense-pilot"},
    )
    batch_response = client.post(
        "/batches",
        json={
            "organization_id": org_response.json()["id"],
            "name": "Project Defense Pilot",
            "starts_on": str(date(2026, 8, 17)),
            "ends_on": str(date(2026, 12, 31)),
        },
    )
    student_response = client.post(
        "/students",
        json={
            "organization_id": org_response.json()["id"],
            "batch_id": batch_response.json()["id"],
            "full_name": "Akanksha Kumari",
            "email": "akankshame422@gmail.com",
            "track": "track_a",
        },
    )

    assert org_response.status_code == 201
    assert batch_response.status_code == 201
    assert student_response.status_code == 500
    assert len(store.students) == 1


def test_duplicate_retry_after_publish_failure_does_not_create_duplicate_student():
    bus = OptionalEventBus(FailingEventBus(), required=False)
    client, store = _make_client_with_bus(bus)

    org, batch, student = _create_org_batch_student(client)
    retry = client.post(
        "/students",
        json={
            "organization_id": org["id"],
            "batch_id": batch["id"],
            "full_name": "Akanksha Kumari",
            "email": "akankshame422@gmail.com",
            "track": "track_a",
        },
    )

    assert retry.status_code == 409
    assert len(store.students) == 1
    assert next(iter(store.students.values())).id.hex == student["id"].replace("-", "")
