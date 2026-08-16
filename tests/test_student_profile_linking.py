from collections.abc import AsyncIterator
from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_async_service, get_auth_service
from app.application.async_daily_loop_service import AsyncDailyLoopService
from app.infrastructure.repositories.memory import AsyncMemoryUnitOfWork
from app.main import create_app
from app.services.auth_service import AuthService
from app.services.store import InMemoryStore


def _make_client() -> tuple[TestClient, InMemoryStore]:
    application = create_app()
    store = InMemoryStore()

    async def _service_override() -> AsyncIterator[AsyncDailyLoopService]:
        yield AsyncDailyLoopService(AsyncMemoryUnitOfWork(store))

    async def _auth_override() -> AsyncIterator[AuthService]:
        yield AuthService(AsyncMemoryUnitOfWork(store))

    application.dependency_overrides[get_async_service] = _service_override
    application.dependency_overrides[get_auth_service] = _auth_override
    return TestClient(application), store


def _create_org_batch_student(client: TestClient, email: str, full_name: str = "Asha Kumar"):
    org = client.post(
        "/organizations",
        json={"name": "Project Defense Pilot", "slug": f"project-defense-{uuid4().hex[:8]}"},
    ).json()
    batch = client.post(
        "/batches",
        json={
            "organization_id": org["id"],
            "name": "Project Defense Pilot",
            "starts_on": str(date(2026, 8, 1)),
            "ends_on": str(date(2026, 12, 31)),
        },
    ).json()
    student_response = client.post(
        "/students",
        json={
            "organization_id": org["id"],
            "batch_id": batch["id"],
            "full_name": full_name,
            "email": email,
            "track": "track_a",
        },
    )
    return org, batch, student_response


def test_registered_user_can_resolve_created_student_profile():
    client, _ = _make_client()

    client.post(
        "/auth/register",
        json={"email": "asha@example.com", "password": "securepass", "full_name": "Asha Kumar"},
    )
    _, _, student_response = _create_org_batch_student(client, "asha@example.com")
    assert student_response.status_code == 201

    login = client.post(
        "/auth/token",
        json={"email": "asha@example.com", "password": "securepass"},
    ).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    me = client.get("/auth/me", headers=headers)
    profile = client.get("/me/student", headers=headers)

    assert me.status_code == 200
    assert me.json()["email"] == "asha@example.com"
    assert profile.status_code == 200
    assert profile.json()["email"] == "asha@example.com"
    assert profile.json()["full_name"] == "Asha Kumar"


def test_student_profile_persists_across_new_repository_session():
    client, store = _make_client()
    client.post(
        "/auth/register",
        json={"email": "persist@example.com", "password": "securepass", "full_name": "Persist User"},
    )
    _, _, student_response = _create_org_batch_student(client, "persist@example.com", "Persist User")
    student_id = student_response.json()["id"]

    async def _load_again():
        uow = AsyncMemoryUnitOfWork(store)
        return await uow.students.get_by_email("persist@example.com")

    import asyncio

    student = asyncio.run(_load_again())
    assert student is not None
    assert str(student.id) == student_id


def test_missing_student_profile_returns_404():
    client, _ = _make_client()
    login = client.post(
        "/auth/register",
        json={"email": "nostudent@example.com", "password": "securepass", "full_name": "No Student"},
    ).json()

    response = client.get("/me/student", headers={"Authorization": f"Bearer {login['access_token']}"})

    assert response.status_code == 404
    assert response.json()["detail"] == "No student profile found for this user"


def test_duplicate_student_email_in_same_organization_returns_409():
    client, _ = _make_client()
    org, batch, first = _create_org_batch_student(client, "duplicate@example.com")

    second = client.post(
        "/students",
        json={
            "organization_id": org["id"],
            "batch_id": batch["id"],
            "full_name": "Duplicate User",
            "email": "duplicate@example.com",
            "track": "track_a",
        },
    )

    assert first.status_code == 201
    assert second.status_code == 409


def test_student_profile_lookup_respects_user_organization_scope():
    client, _ = _make_client()
    org_a = client.post(
        "/organizations",
        json={"name": "Org A", "slug": f"org-a-{uuid4().hex[:8]}"},
    ).json()
    org_b, batch_b, _ = _create_org_batch_student(client, "scoped@example.com", "Scoped Student")

    register = client.post(
        "/auth/register",
        json={
            "email": "scoped@example.com",
            "password": "securepass",
            "full_name": "Scoped User",
            "organization_id": org_a["id"],
        },
    ).json()

    response = client.get(
        "/me/student",
        headers={"Authorization": f"Bearer {register['access_token']}"},
    )

    assert org_b["id"] != org_a["id"]
    assert batch_b["organization_id"] == org_b["id"]
    assert response.status_code == 404


def test_me_student_requires_auth_when_dev_bypass_disabled(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "dev_auth_bypass", False)
    client, _ = _make_client()

    response = client.get("/me/student")

    assert response.status_code == 401
