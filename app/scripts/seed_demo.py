"""Demo seed script — creates rich in-memory demo data for the UI demo.

Run manually:   python -m app.scripts.seed_demo
Or auto-seeded: set PROJECT_DEFENSE_DEMO_MODE=true

Creates:
  - Org: Kalvium Demo
  - 1 Mentor  : mentor@demo.projectdefense.ai / demo1234
  - 5 Students: student1–5@demo.projectdefense.ai / demo1234
  - Batch: Project Defense — Demo Batch 2026
  - Tasks + Submissions + AI Evaluations with varied states
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from uuid import uuid4

logger = logging.getLogger("seed_demo")

DEMO_PASSWORD = "demo1234"
DEMO_STUDENTS = [
    {"name": "Aarav Sharma",  "email": "student1@demo.projectdefense.ai"},
    {"name": "Priya Nair",    "email": "student2@demo.projectdefense.ai"},
    {"name": "Rahul Verma",   "email": "student3@demo.projectdefense.ai"},
    {"name": "Sneha Patel",   "email": "student4@demo.projectdefense.ai"},
    {"name": "Arjun Kumar",   "email": "student5@demo.projectdefense.ai"},
]

DEMO_TASKS = [
    {
        "title": "Implement Rate Limiting for Login API",
        "problem_statement": (
            "Add rate limiting middleware to the FastAPI application to prevent brute-force "
            "attacks on the login endpoint. The middleware must track request counts per IP "
            "address using a configurable sliding window algorithm."
        ),
        "acceptance_criteria": [
            "Limit requests to 5 per minute per IP address",
            "Return HTTP 429 with Retry-After header when rate limit is exceeded",
            "Rate limit threshold must be configurable via environment variable",
            "Rate limit state must not use global in-process memory (must support multiple instances)",
            "Include unit tests for the rate limiting logic",
        ],
        "expected_concepts": ["middleware", "rate limiting", "HTTP 429", "Redis", "sliding window"],
    },
    {
        "title": "Build JWT Authentication System",
        "problem_statement": (
            "Implement a complete JWT authentication system with access tokens and refresh tokens. "
            "The system must support token expiry, refresh, and revocation."
        ),
        "acceptance_criteria": [
            "POST /auth/token returns access_token and refresh_token",
            "Access token expires in 15 minutes",
            "Refresh token can be used to obtain a new access token",
            "Revoked tokens are rejected",
            "Passwords are hashed with bcrypt",
        ],
        "expected_concepts": ["JWT", "bcrypt", "refresh tokens", "token revocation"],
    },
    {
        "title": "Design RESTful API for Task Management",
        "problem_statement": (
            "Design and implement a RESTful API for a task management system. "
            "The API should support CRUD operations, filtering, and pagination."
        ),
        "acceptance_criteria": [
            "GET /tasks returns paginated list with cursor-based pagination",
            "POST /tasks creates a task and returns HTTP 201",
            "PATCH /tasks/{id} supports partial updates",
            "DELETE /tasks/{id} returns HTTP 204",
            "GET /tasks?status=pending filters by status",
        ],
        "expected_concepts": ["REST", "pagination", "HTTP verbs", "status codes"],
    },
    {
        "title": "Implement Database Migration System",
        "problem_statement": (
            "Set up Alembic for database migrations in a FastAPI application. "
            "Create initial migration, add a users table, and write rollback support."
        ),
        "acceptance_criteria": [
            "Alembic is configured and migrations directory exists",
            "Initial migration creates the schema",
            "Users table migration adds id, email, hashed_password, created_at",
            "alembic downgrade -1 reverts the latest migration cleanly",
            "Migration is idempotent — running twice does not fail",
        ],
        "expected_concepts": ["Alembic", "SQLAlchemy", "migrations", "rollback"],
    },
    {
        "title": "Add Observability to FastAPI Service",
        "problem_statement": (
            "Add structured logging and request tracing to a FastAPI application. "
            "Every request should produce a structured log entry with request_id, "
            "duration, status_code, and path."
        ),
        "acceptance_criteria": [
            "Every HTTP request produces a structured JSON log entry",
            "Log entry contains: request_id, method, path, status_code, duration_ms",
            "request_id is propagated in the X-Request-ID response header",
            "Log level is configurable via environment variable",
            "Errors include stack traces in structured form",
        ],
        "expected_concepts": ["structured logging", "middleware", "tracing", "observability"],
    },
]

# Which students get full evaluations and what commit info
SUBMISSION_CONFIGS = [
    # (student index, task index, commit_url, approach_note, eval_state)
    (0, 0, "https://github.com/aarav/project/commit/a1b2c3d4e5f6", "Implemented sliding window using Redis with Lua scripting.", "complete"),
    (1, 1, "https://github.com/priya/project/commit/b2c3d4e5f6a1", "Used PyJWT library. Refresh tokens stored in database.", "needs_review"),
    (2, 2, "https://github.com/rahul/project/commit/c3d4e5f6a1b2", "Cursor-based pagination with keyset approach. Full CRUD.", "approved"),
    (3, 3, "https://github.com/sneha/project/commit/d4e5f6a1b2c3", "Basic Alembic setup. Used autogenerate for migrations.", "needs_review"),
    # Arjun (index 4) has no submission
]


async def seed_demo() -> None:
    """Seed demo data into the in-memory store. Idempotent — skips if already seeded."""
    from app.api.dependencies import _dev_store as store
    from app.core.security import security
    from app.domain.enums import UserRole, Track, TaskType, SelfStatus
    from app.schemas.auth import UserCreate
    from app.schemas.core import (
        OrganizationCreate, BatchCreate, StudentCreate,
        ProjectCreate, TaskCreate, SubmissionCreate,
    )

    # Idempotency guard — check if already seeded
    mentor_email = "mentor@demo.projectdefense.ai"
    if store.get_user_by_email(mentor_email) is not None:
        logger.info("Demo data already seeded — skipping")
        return

    logger.info("Seeding demo data…")
    today = date.today()

    # --- Organization ---
    org = store.create_organization(OrganizationCreate(name="Kalvium Demo", slug="kalvium-demo"))

    # --- Batch ---
    batch = store.create_batch(BatchCreate(
        organization_id=org.id,
        name="Project Defense — Demo Batch 2026",
        starts_on=today - timedelta(days=30),
        ends_on=today + timedelta(days=60),
    ))

    # --- Mentor user ---
    mentor_user = store.create_user(UserCreate(
        email=mentor_email,
        hashed_password=security.hash_password(DEMO_PASSWORD),
        full_name="Demo Mentor",
        role=UserRole.MENTOR,
        organization_id=org.id,
    ))
    logger.info("Created mentor: %s", mentor_email)

    # --- Student users + profiles + projects + tasks ---
    student_users = []
    student_profiles = []
    projects = []
    tasks = []

    for i, s in enumerate(DEMO_STUDENTS):
        user = store.create_user(UserCreate(
            email=s["email"],
            hashed_password=security.hash_password(DEMO_PASSWORD),
            full_name=s["name"],
            role=UserRole.STUDENT,
            organization_id=org.id,
        ))
        student_users.append(user)

        profile = store.create_student(StudentCreate(
            organization_id=org.id,
            batch_id=batch.id,
            full_name=s["name"],
            email=s["email"],
            track=Track.TRACK_A,
            mentor_id=mentor_user.id,
        ))
        student_profiles.append(profile)

        project = store.create_project(ProjectCreate(
            organization_id=org.id,
            student_id=profile.id,
            name=f"{s['name']}'s Project",
            repository_url=f"https://github.com/demo/{s['name'].lower().replace(' ', '-')}",
        ))
        projects.append(project)

        task_cfg = DEMO_TASKS[i]
        task = store.create_task(TaskCreate(
            organization_id=org.id,
            batch_id=batch.id,
            student_id=profile.id,
            project_id=project.id,
            task_type=TaskType.CODING,
            title=task_cfg["title"],
            problem_statement=task_cfg["problem_statement"],
            acceptance_criteria=task_cfg["acceptance_criteria"],
            expected_concepts=task_cfg["expected_concepts"],
            due_on=today,
        ))
        tasks.append(task)
        logger.info("Created student %s with task: %s", s["name"], task.title)

    # --- Submissions + AI Evaluations ---
    from app.ai.context_builder import ContextBuilder
    from app.ai.engine import EvaluationEngine
    from app.ai.provider import MockAIProvider
    from app.ai.schemas import EvaluationRecord, EvaluationState, MentorDecision
    from app.ai.store import get_ai_store
    from app.domain.enums import SelfStatus

    ai_store = get_ai_store()
    provider = MockAIProvider()
    engine = EvaluationEngine(provider=provider, store=ai_store, confidence_threshold=0.70)

    for student_idx, task_idx, commit_url, approach_note, eval_state in SUBMISSION_CONFIGS:
        student_profile = student_profiles[student_idx]
        task = tasks[task_idx]

        submission = store.create_submission(SubmissionCreate(
            organization_id=org.id,
            task_id=task.id,
            student_id=student_profile.id,
            self_status=SelfStatus.SOLVED,
            commit_url=commit_url,
            approach_note=approach_note,
        ))
        logger.info("Created submission for %s", student_profile.full_name)

        # Build context and run AI evaluation
        from app.schemas.core import Task as TaskSchema, Submission as SubmissionSchema
        context = ContextBuilder().build(task, submission)

        record = EvaluationRecord(
            submission_id=submission.id,
            organization_id=org.id,
            task_id=task.id,
            provider=provider.provider_name(),
            model=provider.model_name(),
            context_hash=context.context_hash(),
        )
        record = ai_store.create(record)
        record = await engine.evaluate(record, context)

        # Apply mentor actions for specific states
        if eval_state == "approved":
            record = record.model_copy(update={
                "mentor_decision": MentorDecision.APPROVED,
                "mentor_feedback": "Excellent implementation! Clean code with proper separation of concerns.",
                "mentor_id": mentor_user.id,
            })
            ai_store.update(record)
        elif eval_state == "needs_review":
            # Engine may have already set NEEDS_HUMAN_REVIEW; ensure it is
            if record.state == EvaluationState.COMPLETED:
                record = record.model_copy(update={"state": EvaluationState.NEEDS_HUMAN_REVIEW})
                ai_store.update(record)

        logger.info(
            "Evaluation for %s: state=%s score=%.1f",
            student_profile.full_name,
            record.state,
            record.result.overall_score if record.result else 0,
        )

    logger.info("Demo seed complete — org=%s batch=%s", org.id, batch.id)
    print("\n=== Demo Seed Complete ===")
    print(f"Mentor:   {mentor_email} / {DEMO_PASSWORD}")
    for i, s in enumerate(DEMO_STUDENTS):
        print(f"Student {i+1}: {s['email']} / {DEMO_PASSWORD}  ({s['name']})")
    print("\nLogin:  POST http://localhost:8000/auth/token")


if __name__ == "__main__":
    logging.basicConfig(level="INFO")
    asyncio.run(seed_demo())
