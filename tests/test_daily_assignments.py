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
from app.services.daily_assignment_service import DailyAssignmentService
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


async def _seed_profile(store: InMemoryStore):
    uow = AsyncMemoryUnitOfWork(store)
    service = AsyncDailyLoopService(uow)
    org = await service.create_organization(OrganizationCreate(name="Project Defense Pilot", slug="project-defense-pilot"))
    batch = await service.create_batch(
        BatchCreate(organization_id=org.id, name="Pilot", starts_on=date(2026, 8, 17), ends_on=date(2026, 12, 31))
    )
    student = await service.create_student(
        StudentCreate(organization_id=org.id, batch_id=batch.id, full_name="Akanksha Kumari", email="akankshame422@gmail.com")
    )
    project = await service.create_project(
        ProjectCreate(
            organization_id=org.id,
            student_id=student.id,
            name="Project Defense AI",
            repository_url="https://github.com/example/project-defense-ai",
        )
    )
    await StudentProjectProfileService(uow).upsert_profile(
        StudentProjectProfileCreate(
            student_id=student.id,
            organization_id=org.id,
            project_id=project.id,
            github_repository="https://github.com/example/project-defense-ai",
            project_title="Project Defense AI",
            project_description="AI-powered project defense platform.",
            tech_stack=["Python", "FastAPI", "Next.js", "PostgreSQL"],
            current_strengths=["Backend development"],
            current_weaknesses=["Authentication understanding"],
            skill_gaps=["role-based authorization"],
            current_level="pilot",
        )
    )
    return org, batch, student, project


def test_daily_assignment_service_creates_one_task_per_student_day():
    import asyncio

    store = InMemoryStore()
    org, batch, student, _ = asyncio.run(_seed_profile(store))
    uow = AsyncMemoryUnitOfWork(store)
    assignment_service = DailyAssignmentService(uow)
    today = date(2026, 8, 17)

    first = asyncio.run(assignment_service.assign_for_student(student.id, today))
    second = asyncio.run(assignment_service.assign_for_student(student.id, today))

    assert first.id == second.id
    assert first.student_id == student.id
    assert first.batch_id == batch.id
    assert first.organization_id == org.id
    assert len(store.tasks) == 1
    assert len(store.task_assignments) == 1
    assert "authentication" in first.why_this_task.lower()


def test_run_daily_automation_generates_today_task_and_me_today_reads_it():
    import asyncio

    client, store = _make_client()
    org, batch, student, _ = asyncio.run(_seed_profile(store))

    run = client.post(
        "/automation/run-daily",
        json={"organization_id": str(org.id), "batch_id": str(batch.id), "assigned_on": str(date.today())},
    )
    login = client.post(
        "/auth/register",
        json={
            "email": "akankshame422@gmail.com",
            "password": "securepass",
            "full_name": "Akanksha Kumari",
            "organization_id": str(org.id),
        },
    ).json()
    today = client.get("/me/today", headers={"Authorization": f"Bearer {login['access_token']}"})

    assert run.status_code == 200
    assert run.json()["tasks_generated"] == 1
    assert today.status_code == 200
    assert today.json()["assignment"]["student_id"] == str(student.id)
    assert "Day 1:" in today.json()["task"]["title"]


def test_student_submit_task_creates_submission_and_evaluation():
    import asyncio

    client, store = _make_client()
    org, batch, student, _ = asyncio.run(_seed_profile(store))
    client.post(
        "/automation/run-daily",
        json={"organization_id": str(org.id), "batch_id": str(batch.id), "assigned_on": str(date.today())},
    )
    login = client.post(
        "/auth/register",
        json={
            "email": "akankshame422@gmail.com",
            "password": "securepass",
            "full_name": "Akanksha Kumari",
            "organization_id": str(org.id),
        },
    ).json()
    today = client.get("/me/today", headers={"Authorization": f"Bearer {login['access_token']}"}).json()

    response = client.post(
        f"/me/tasks/{today['task']['id']}/submit",
        headers={"Authorization": f"Bearer {login['access_token']}"},
        json={
            "commit_url": "https://github.com/example/project-defense-ai/commit/abc123",
            "explanation": "I implemented backend authorization checks and added tests for unauthorized access.",
            "implementation_statement": "The FastAPI dependency verifies the current user role before task creation.",
            "deployed_url": "https://project-defense-ai.vercel.app",
            "evidence_notes": "pytest passed locally",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["submission"]["student_id"] == str(student.id)
    assert body["evaluation"]["score"] >= 70
    assert "GITHUB_DIFF_NOT_INGESTED" in body["evaluation"]["flags"]
    assert len(store.submissions) == 1
    assert len(store.evaluations) == 1

    fetched = client.get(
        f"/me/submissions/{body['submission']['id']}/evaluation",
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )
    assert fetched.status_code == 200
    assert fetched.json()["evaluation"]["id"] == body["evaluation"]["id"]


def test_mentor_today_and_review_queue_show_flagged_submission():
    import asyncio

    client, store = _make_client()
    org, batch, _, _ = asyncio.run(_seed_profile(store))
    client.post(
        "/automation/run-daily",
        json={"organization_id": str(org.id), "batch_id": str(batch.id), "assigned_on": str(date.today())},
    )
    login = client.post(
        "/auth/register",
        json={
            "email": "akankshame422@gmail.com",
            "password": "securepass",
            "full_name": "Akanksha Kumari",
            "organization_id": str(org.id),
        },
    ).json()
    today = client.get("/me/today", headers={"Authorization": f"Bearer {login['access_token']}"}).json()
    client.post(
        f"/me/tasks/{today['task']['id']}/submit",
        headers={"Authorization": f"Bearer {login['access_token']}"},
        json={
            "commit_url": "https://github.com/example/project-defense-ai/commit/abc123",
            "explanation": "I implemented backend authorization checks and added tests for unauthorized access.",
            "implementation_statement": "The FastAPI dependency verifies the current user role before task creation.",
        },
    )

    mentor_today = client.get("/mentor/today", params={"organization_id": str(org.id), "batch_id": str(batch.id)})
    queue = client.get("/mentor/review-queue", params={"organization_id": str(org.id)})

    assert mentor_today.status_code == 200
    assert mentor_today.json()["totals"]["total_students"] == 1
    assert mentor_today.json()["totals"]["submitted"] == 1
    assert mentor_today.json()["totals"]["needs_review"] == 1
    assert queue.status_code == 200
    assert queue.json()["total"] == 1
    assert "GITHUB_DIFF_NOT_INGESTED" in queue.json()["items"][0]["reasons"]


def test_50_student_daily_assignment_simulation_has_no_duplicates():
    import asyncio

    async def _seed_50(store: InMemoryStore):
        uow = AsyncMemoryUnitOfWork(store)
        service = AsyncDailyLoopService(uow)
        org = await service.create_organization(OrganizationCreate(name="Simulation Org", slug="simulation-org"))
        batch = await service.create_batch(
            BatchCreate(organization_id=org.id, name="Simulation Batch", starts_on=date(2026, 8, 17), ends_on=date(2026, 12, 31))
        )
        for index in range(50):
            student = await service.create_student(
                StudentCreate(
                    organization_id=org.id,
                    batch_id=batch.id,
                    full_name=f"Student {index}",
                    email=f"student{index}@example.com",
                )
            )
            project = await service.create_project(
                ProjectCreate(
                    organization_id=org.id,
                    student_id=student.id,
                    name=f"Project {index}",
                    repository_url=f"https://github.com/example/project-{index}",
                )
            )
            await StudentProjectProfileService(uow).upsert_profile(
                StudentProjectProfileCreate(
                    student_id=student.id,
                    organization_id=org.id,
                    project_id=project.id,
                    github_repository=f"https://github.com/example/project-{index}",
                    project_title=f"Project {index}",
                    current_weaknesses=["testing" if index % 2 else "system design"],
                    tech_stack=["Python", "FastAPI"],
                )
            )
        return org, batch

    store = InMemoryStore()
    org, batch = asyncio.run(_seed_50(store))
    result = asyncio.run(DailyAssignmentService(AsyncMemoryUnitOfWork(store)).run_for_batch(org.id, batch.id, date(2026, 8, 17)))

    assert result["students_processed"] == 50
    assert result["tasks_generated"] == 50
    assert result["errors"] == []
    assert len(store.tasks) == 50
    assert len(store.task_assignments) == 50
    assert len({(a.student_id, a.assigned_on) for a in store.task_assignments.values()}) == 50
    assert {a.organization_id for a in store.task_assignments.values()} == {org.id}
    assert {a.batch_id for a in store.task_assignments.values()} == {batch.id}

    second = asyncio.run(DailyAssignmentService(AsyncMemoryUnitOfWork(store)).run_for_batch(org.id, batch.id, date(2026, 8, 17)))
    assert second["tasks_generated"] == 0
    assert second["tasks_reused"] == 50
    assert len(store.tasks) == 50
    assert len(store.task_assignments) == 50
