from collections.abc import AsyncIterator
from datetime import date

from fastapi.testclient import TestClient

from app.api.dependencies import get_async_service, get_auth_service
from app.application.async_daily_loop_service import AsyncDailyLoopService
from app.infrastructure.repositories.memory import AsyncMemoryUnitOfWork
from app.main import create_app
from app.schemas.core import BatchCreate, OrganizationCreate, ProjectCreate, StudentCreate
from app.schemas.m7 import StudentProjectProfileCreate
from app.services.auth_service import AuthService
from app.services.project_profile_service import StudentProjectProfileService
from app.services.store import InMemoryStore


def _make_client() -> tuple[TestClient, InMemoryStore]:
    app = create_app()
    store = InMemoryStore()

    async def _service_override() -> AsyncIterator[AsyncDailyLoopService]:
        yield AsyncDailyLoopService(AsyncMemoryUnitOfWork(store))

    async def _auth_override() -> AsyncIterator[AuthService]:
        yield AuthService(AsyncMemoryUnitOfWork(store))

    app.dependency_overrides[get_async_service] = _service_override
    app.dependency_overrides[get_auth_service] = _auth_override
    return TestClient(app), store


async def _seed_student_project(store: InMemoryStore):
    uow = AsyncMemoryUnitOfWork(store)
    service = AsyncDailyLoopService(uow)
    org = await service.create_organization(OrganizationCreate(name="Project Defense Pilot", slug="project-defense-pilot"))
    batch = await service.create_batch(
        BatchCreate(
            organization_id=org.id,
            name="Project Defense Pilot",
            starts_on=date(2026, 8, 17),
            ends_on=date(2026, 12, 31),
        )
    )
    student = await service.create_student(
        StudentCreate(
            organization_id=org.id,
            batch_id=batch.id,
            full_name="Akanksha Kumari",
            email="akankshame422@gmail.com",
            track="track_a",
        )
    )
    project = await service.create_project(
        ProjectCreate(
            organization_id=org.id,
            student_id=student.id,
            name="Project Defense AI",
            repository_url="https://github.com/example/project-defense-ai",
            summary="AI-powered engineering project defense platform.",
        )
    )
    return org, batch, student, project


def _profile_payload(org, student, project) -> dict:
    return {
        "student_id": str(student.id),
        "organization_id": str(org.id),
        "project_id": str(project.id),
        "github_repository": "https://github.com/example/project-defense-ai",
        "deployed_url": "https://project-defense-ai.vercel.app",
        "project_title": "Project Defense AI",
        "project_description": "AI-powered engineering project defense and student evaluation platform.",
        "tech_stack": ["Python", "FastAPI", "Next.js", "PostgreSQL"],
        "languages": ["Python", "TypeScript"],
        "frameworks": ["FastAPI", "Next.js"],
        "database": "PostgreSQL",
        "architecture_summary": "Modular monolith with FastAPI backend and Next.js frontend.",
        "current_strengths": ["Backend development", "APIs", "Python"],
        "current_weaknesses": ["System design", "testing", "project explanation"],
        "skill_gaps": ["authorization reasoning", "test strategy"],
        "current_level": "pilot",
        "mentor_notes": "First production pilot student.",
    }


def test_project_profile_service_creates_and_reuses_profile():
    import asyncio

    store = InMemoryStore()
    org, _, student, project = asyncio.run(_seed_student_project(store))
    uow = AsyncMemoryUnitOfWork(store)
    service = StudentProjectProfileService(uow)
    payload = StudentProjectProfileCreate(**_profile_payload(org, student, project))

    created = asyncio.run(service.upsert_profile(payload))
    updated_payload = payload.model_copy(update={"current_weaknesses": ["testing"]})
    updated = asyncio.run(service.upsert_profile(updated_payload))

    assert created.id == updated.id
    assert updated.current_weaknesses == ["testing"]
    assert len(store.student_project_profiles) == 1


def test_project_profile_api_upsert_and_get_for_student():
    import asyncio

    client, store = _make_client()
    org, _, student, project = asyncio.run(_seed_student_project(store))

    upsert = client.post(
        f"/students/{student.id}/project-profile",
        json=_profile_payload(org, student, project),
    )
    fetched = client.get(f"/students/{student.id}/project-profile")

    assert upsert.status_code == 200
    assert fetched.status_code == 200
    assert fetched.json()["student_id"] == str(student.id)
    assert fetched.json()["project_title"] == "Project Defense AI"
    assert fetched.json()["current_strengths"] == ["Backend development", "APIs", "Python"]


def test_current_student_can_read_own_project_profile():
    import asyncio

    client, store = _make_client()
    org, _, student, project = asyncio.run(_seed_student_project(store))
    client.post(f"/students/{student.id}/project-profile", json=_profile_payload(org, student, project))
    login = client.post(
        "/auth/register",
        json={
            "email": "akankshame422@gmail.com",
            "password": "securepass",
            "full_name": "Akanksha Kumari",
            "organization_id": str(org.id),
        },
    ).json()

    response = client.get(
        "/me/project-profile",
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json()["github_repository"] == "https://github.com/example/project-defense-ai"
