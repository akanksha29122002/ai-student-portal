"""HTTP-layer tests exercising routes end-to-end via TestClient.

Each test gets its own isolated InMemoryStore via dependency_overrides so
there is no cross-test contamination.
"""
from collections.abc import AsyncIterator
from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_async_service
from app.application.async_daily_loop_service import AsyncDailyLoopService
from app.domain.enums import SelfStatus, TaskType
from app.infrastructure.repositories.memory import AsyncMemoryUnitOfWork
from app.main import create_app
from app.services.store import InMemoryStore


def _make_client() -> tuple[TestClient, InMemoryStore]:
    application = create_app()
    store = InMemoryStore()

    async def _override() -> AsyncIterator[AsyncDailyLoopService]:
        yield AsyncDailyLoopService(AsyncMemoryUnitOfWork(store))

    application.dependency_overrides[get_async_service] = _override
    return TestClient(application), store


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_health_returns_ok():
    client, _ = _make_client()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "project-defense-ai"}


# ---------------------------------------------------------------------------
# 404 / error format
# ---------------------------------------------------------------------------


def test_missing_task_returns_problem_details():
    client, _ = _make_client()
    response = client.get(f"/tasks/{uuid4()}")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["title"] == "Not Found"


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------


def test_create_organization_returns_201():
    client, _ = _make_client()
    response = client.post("/organizations", json={"name": "Kalvium", "slug": "kalvium"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Kalvium"
    assert body["slug"] == "kalvium"
    assert "id" in body


def test_create_organization_invalid_slug_returns_422():
    client, _ = _make_client()
    response = client.post("/organizations", json={"name": "Kalvium", "slug": "INVALID SLUG!"})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Batches
# ---------------------------------------------------------------------------


def test_create_batch_returns_201():
    client, _ = _make_client()
    org = client.post("/organizations", json={"name": "Kalvium", "slug": "kalvium"}).json()
    response = client.post("/batches", json={
        "organization_id": org["id"],
        "name": "Batch 2026",
        "starts_on": "2026-08-01",
        "ends_on": "2026-08-31",
    })
    assert response.status_code == 201
    assert response.json()["organization_id"] == org["id"]


def test_create_batch_with_inverted_dates_returns_422():
    client, _ = _make_client()
    org = client.post("/organizations", json={"name": "Kalvium", "slug": "kalvium"}).json()
    response = client.post("/batches", json={
        "organization_id": org["id"],
        "name": "Bad Batch",
        "starts_on": "2026-08-31",
        "ends_on": "2026-08-01",
    })
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------


def test_create_student_returns_201():
    client, _ = _make_client()
    org = client.post("/organizations", json={"name": "Kalvium", "slug": "kalvium"}).json()
    batch = client.post("/batches", json={
        "organization_id": org["id"], "name": "Batch 1",
        "starts_on": "2026-08-01", "ends_on": "2026-08-31",
    }).json()
    response = client.post("/students", json={
        "organization_id": org["id"],
        "batch_id": batch["id"],
        "full_name": "Asha Kumar",
        "email": "asha@example.com",
    })
    assert response.status_code == 201
    assert response.json()["email"] == "asha@example.com"


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


def test_create_and_get_task():
    client, _ = _make_client()
    org = client.post("/organizations", json={"name": "Kalvium", "slug": "kalvium"}).json()
    batch = client.post("/batches", json={
        "organization_id": org["id"], "name": "Batch 1",
        "starts_on": "2026-08-01", "ends_on": "2026-08-31",
    }).json()
    student = client.post("/students", json={
        "organization_id": org["id"], "batch_id": batch["id"],
        "full_name": "Asha Kumar", "email": "asha@example.com",
    }).json()
    project = client.post("/projects", json={
        "organization_id": org["id"], "student_id": student["id"],
        "name": "Defense App", "repository_url": "https://github.com/example/defense",
    }).json()

    created = client.post("/tasks", json={
        "organization_id": org["id"],
        "batch_id": batch["id"],
        "student_id": student["id"],
        "project_id": project["id"],
        "task_type": "coding",
        "title": "Add rate limiting",
        "problem_statement": "Protect login endpoint from brute-force attacks.",
        "acceptance_criteria": ["Failed attempts throttled after 5 tries."],
        "due_on": "2026-08-07",
    }).json()
    fetched = client.get(f"/tasks/{created['id']}")

    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Add rate limiting"


# ---------------------------------------------------------------------------
# Submissions
# ---------------------------------------------------------------------------


def test_create_submission_returns_201():
    client, _ = _make_client()
    org = client.post("/organizations", json={"name": "Kalvium", "slug": "kalvium"}).json()
    batch = client.post("/batches", json={
        "organization_id": org["id"], "name": "Batch 1",
        "starts_on": "2026-08-01", "ends_on": "2026-08-31",
    }).json()
    student = client.post("/students", json={
        "organization_id": org["id"], "batch_id": batch["id"],
        "full_name": "Asha Kumar", "email": "asha@example.com",
    }).json()
    project = client.post("/projects", json={
        "organization_id": org["id"], "student_id": student["id"],
        "name": "Defense App", "repository_url": "https://github.com/example/defense",
    }).json()
    task = client.post("/tasks", json={
        "organization_id": org["id"], "batch_id": batch["id"],
        "student_id": student["id"], "project_id": project["id"],
        "task_type": "coding", "title": "Task 1",
        "problem_statement": "Problem statement for task 1.",
        "acceptance_criteria": ["Criterion 1."], "due_on": "2026-08-07",
    }).json()

    response = client.post("/submissions", json={
        "organization_id": org["id"],
        "task_id": task["id"],
        "student_id": student["id"],
        "self_status": "solved",
        "commit_url": "https://github.com/example/defense/commit/abc123",
    })

    assert response.status_code == 201
    assert response.json()["status"] == "received"


def test_submission_without_evidence_returns_422():
    client, _ = _make_client()
    response = client.post("/submissions", json={
        "organization_id": str(uuid4()),
        "task_id": str(uuid4()),
        "student_id": str(uuid4()),
        "self_status": "attempted",
    })
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Evaluate + mentor summary
# ---------------------------------------------------------------------------


def test_evaluate_submission_returns_evaluation():
    client, _ = _make_client()
    org = client.post("/organizations", json={"name": "Kalvium", "slug": "kalvium"}).json()
    batch = client.post("/batches", json={
        "organization_id": org["id"], "name": "Batch 1",
        "starts_on": "2026-08-01", "ends_on": "2026-08-31",
    }).json()
    student = client.post("/students", json={
        "organization_id": org["id"], "batch_id": batch["id"],
        "full_name": "Asha Kumar", "email": "asha@example.com",
    }).json()
    project = client.post("/projects", json={
        "organization_id": org["id"], "student_id": student["id"],
        "name": "Defense App", "repository_url": "https://github.com/example/defense",
    }).json()
    task = client.post("/tasks", json={
        "organization_id": org["id"], "batch_id": batch["id"],
        "student_id": student["id"], "project_id": project["id"],
        "task_type": "coding", "title": "Task 1",
        "problem_statement": "Problem statement for task 1.",
        "acceptance_criteria": ["Criterion 1."], "due_on": "2026-08-07",
    }).json()
    submission = client.post("/submissions", json={
        "organization_id": org["id"], "task_id": task["id"], "student_id": student["id"],
        "self_status": "solved", "commit_url": "https://github.com/example/defense/commit/abc123",
    }).json()

    response = client.post(f"/submissions/{submission['id']}/evaluate")

    assert response.status_code == 200
    assert response.json()["verdict"] == "needs_human_review"


def test_mentor_summary_returns_schema_version():
    client, _ = _make_client()
    response = client.get(f"/mentor-summaries/{uuid4()}")
    assert response.status_code == 200
    assert response.json()["schema_version"] == "mentor_daily_summary.v1"
