"""Development seed script.

Usage:
    python -m app.scripts.seed_dev

Creates a minimal but complete dataset for local development and manual testing:
  - 1 organization (Kalvium)
  - 1 SUPER_ADMIN user  (admin@kalvium.dev / admin1234)
  - 1 MENTOR user       (mentor@kalvium.dev / mentor1234)
  - 1 STUDENT user      (student@kalvium.dev / student1234)
  - 1 Batch
  - 1 Student profile
  - 1 Project
  - 1 Task

This script MUST NOT run in production. It raises ValueError if
ENVIRONMENT=production.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from datetime import date, timedelta

from app.core.config import Environment, settings
from app.core.security import security

logger = logging.getLogger("seed_dev")


def _guard_non_production() -> None:
    if settings.environment == Environment.PRODUCTION:
        raise ValueError(
            "seed_dev refuses to run in production. "
            "Set ENVIRONMENT=development or ENVIRONMENT=testing."
        )


async def _seed() -> None:
    _guard_non_production()

    try:
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
        from app.infrastructure.repositories.sqlalchemy import SqlAlchemyUnitOfWork
        from app.infrastructure.models import Base
    except ImportError as exc:
        logger.error("SQLAlchemy or asyncpg not installed: %s", exc)
        sys.exit(1)

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        uow = SqlAlchemyUnitOfWork(session)

        # ----- Organization -----
        from app.schemas.core import OrganizationCreate
        org = await uow.organizations.create(OrganizationCreate(name="Kalvium", slug="kalvium"))
        logger.info("Created organization: %s (%s)", org.name, org.id)

        # ----- Users -----
        from app.schemas.auth import UserCreate
        from app.domain.enums import UserRole

        admin = await uow.users.create(UserCreate(
            email="admin@kalvium.dev",
            hashed_password=security.hash_password("admin1234"),
            full_name="Platform Admin",
            role=UserRole.SUPER_ADMIN,
            organization_id=org.id,
        ))
        logger.info("Created admin: %s (%s)", admin.email, admin.id)

        mentor = await uow.users.create(UserCreate(
            email="mentor@kalvium.dev",
            hashed_password=security.hash_password("mentor1234"),
            full_name="Demo Mentor",
            role=UserRole.MENTOR,
            organization_id=org.id,
        ))
        logger.info("Created mentor: %s (%s)", mentor.email, mentor.id)

        student_user = await uow.users.create(UserCreate(
            email="student@kalvium.dev",
            hashed_password=security.hash_password("student1234"),
            full_name="Demo Student",
            role=UserRole.STUDENT,
            organization_id=org.id,
        ))
        logger.info("Created student user: %s (%s)", student_user.email, student_user.id)

        # ----- Batch -----
        from app.schemas.core import BatchCreate
        today = date.today()
        batch = await uow.batches.create(BatchCreate(
            organization_id=org.id,
            name="Batch 2026-A",
            starts_on=today,
            ends_on=today + timedelta(days=90),
        ))
        logger.info("Created batch: %s (%s)", batch.name, batch.id)

        # ----- Student profile -----
        from app.schemas.core import StudentCreate
        from app.domain.enums import Track
        student = await uow.students.create(StudentCreate(
            organization_id=org.id,
            batch_id=batch.id,
            full_name="Demo Student",
            email="student@kalvium.dev",
            track=Track.TRACK_A,
        ))
        logger.info("Created student profile: %s (%s)", student.full_name, student.id)

        # ----- Project -----
        from app.schemas.core import ProjectCreate
        project = await uow.projects.create(ProjectCreate(
            organization_id=org.id,
            student_id=student.id,
            name="Project Defense Demo",
            repository_url="https://github.com/demo/project-defense-demo",
        ))
        logger.info("Created project: %s (%s)", project.name, project.id)

        # ----- Task -----
        from app.schemas.core import TaskCreate
        from app.domain.enums import TaskType
        task = await uow.tasks.create(TaskCreate(
            organization_id=org.id,
            batch_id=batch.id,
            student_id=student.id,
            project_id=project.id,
            task_type=TaskType.CODING,
            title="Build a REST API health-check endpoint",
            problem_statement=(
                "Your FastAPI application must expose a GET /health endpoint that returns "
                "HTTP 200 with a JSON body containing {\"status\": \"ok\"}. "
                "The endpoint must not require authentication."
            ),
            acceptance_criteria=[
                "GET /health returns HTTP 200.",
                "Response body contains {\"status\": \"ok\"}.",
                "No authentication header is required.",
            ],
            expected_concepts=["REST", "FastAPI", "HTTP status codes"],
            due_on=today + timedelta(days=1),
        ))
        logger.info("Created task: %s (%s)", task.title, task.id)

        await uow.commit()

    await engine.dispose()

    print("\n=== Seed complete ===")
    print(f"Organization : {org.name}  id={org.id}")
    print(f"Admin        : {admin.email}  password=admin1234")
    print(f"Mentor       : {mentor.email}  password=mentor1234")
    print(f"Student      : {student_user.email}  password=student1234")
    print(f"Batch        : {batch.name}  id={batch.id}")
    print(f"Task         : {task.title}  id={task.id}")
    print()
    print("Login via:  POST http://localhost:8000/auth/token")
    print('Body:       {"email": "admin@kalvium.dev", "password": "admin1234"}')


if __name__ == "__main__":
    logging.basicConfig(level="INFO")
    asyncio.run(_seed())
