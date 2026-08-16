"""Demo seed script — creates rich in-memory demo data for the UI demo.

Run manually:   python -m app.scripts.seed_demo
Or auto-seeded: set PROJECT_DEFENSE_DEMO_MODE=true

Creates:
  - Org: Kalvium Demo
  - 1 Mentor : mentor@demo.projectdefense.ai / demo1234
  - 10 Students: student1–10@demo.projectdefense.ai / demo1234
  - Batch: Project Defense — Demo Batch 2026
  - Tasks + Submissions + AI Evaluations with varied states
  - Milestone 7 data: skill assessments, learning plans, plan days,
    profile analyses, progress snapshots
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from uuid import uuid4

logger = logging.getLogger("seed_demo")

DEMO_PASSWORD = "demo1234"
DEMO_STUDENTS = [
    {"name": "Aarav Sharma",    "email": "student1@demo.projectdefense.ai",  "profile": {"python_experience": "2 years", "built": "REST API, Flask app", "strengths": "algorithms"}},
    {"name": "Priya Nair",      "email": "student2@demo.projectdefense.ai",  "profile": {"python_experience": "1 year", "built": "Django blog", "weakness": "testing"}},
    {"name": "Rahul Verma",     "email": "student3@demo.projectdefense.ai",  "profile": {"python_experience": "3 years", "built": "FastAPI services", "strengths": "system design"}},
    {"name": "Sneha Patel",     "email": "student4@demo.projectdefense.ai",  "profile": {"python_experience": "6 months", "built": "CLI tools", "weakness": "architecture"}},
    {"name": "Arjun Kumar",     "email": "student5@demo.projectdefense.ai",  "profile": {"python_experience": "1.5 years", "built": "data pipelines", "strengths": "debugging"}},
    {"name": "Kavya Reddy",     "email": "student6@demo.projectdefense.ai",  "profile": {"python_experience": "2 years", "built": "ML models", "weakness": "web APIs"}},
    {"name": "Dev Mehta",       "email": "student7@demo.projectdefense.ai",  "profile": {"python_experience": "1 year", "built": "automation scripts", "strengths": "testing"}},
    {"name": "Ananya Iyer",     "email": "student8@demo.projectdefense.ai",  "profile": {"python_experience": "3 years", "built": "microservices", "strengths": "architecture"}},
    {"name": "Rohan Gupta",     "email": "student9@demo.projectdefense.ai",  "profile": {"python_experience": "8 months", "built": "TODO app", "weakness": "system design"}},
    {"name": "Lakshmi Pillai",  "email": "student10@demo.projectdefense.ai", "profile": {"python_experience": "2 years", "built": "e-commerce backend", "strengths": "code quality"}},
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
    {
        "title": "Build a Caching Layer with Redis",
        "problem_statement": (
            "Add a Redis-based caching layer to a FastAPI application. "
            "Cache expensive database queries with configurable TTL and cache invalidation."
        ),
        "acceptance_criteria": [
            "Cache decorator wraps async functions transparently",
            "TTL is configurable per cache key prefix",
            "Cache invalidation clears all keys for a given prefix",
            "Cache miss falls through to the underlying function",
            "Include integration tests with a real Redis instance",
        ],
        "expected_concepts": ["Redis", "caching", "TTL", "cache invalidation", "decorators"],
    },
    {
        "title": "Implement WebSocket Real-Time Notifications",
        "problem_statement": (
            "Add WebSocket support to a FastAPI application for real-time "
            "push notifications. Users must receive notifications when their "
            "submission is evaluated."
        ),
        "acceptance_criteria": [
            "WebSocket endpoint authenticates via JWT in query parameter",
            "Clients receive JSON notification when evaluation completes",
            "Multiple clients per user are supported",
            "Disconnected clients are cleaned up",
            "Fallback to polling if WebSocket is not supported",
        ],
        "expected_concepts": ["WebSocket", "async", "JWT", "push notifications"],
    },
    {
        "title": "Design Event-Driven Architecture",
        "problem_statement": (
            "Refactor a monolithic service into an event-driven architecture "
            "using an in-process event bus. Domain events should decouple "
            "services from each other."
        ),
        "acceptance_criteria": [
            "Define at least 3 domain events as dataclasses",
            "Event bus supports subscribe and publish operations",
            "Handlers are registered via decorator",
            "Events are published after successful database commit",
            "Failed handlers do not roll back the original transaction",
        ],
        "expected_concepts": ["event-driven", "domain events", "decoupling", "publish-subscribe"],
    },
    {
        "title": "Implement Background Task Queue",
        "problem_statement": (
            "Add a background task queue to process expensive AI evaluations "
            "asynchronously. The queue must support retries, dead-letter handling, "
            "and task status tracking."
        ),
        "acceptance_criteria": [
            "Tasks are enqueued and picked up by a worker",
            "Failed tasks are retried up to 3 times with exponential backoff",
            "Tasks that exceed retry limit move to dead-letter queue",
            "GET /tasks/{id}/status returns current task state",
            "Worker can be scaled horizontally without duplicate processing",
        ],
        "expected_concepts": ["task queue", "retry", "dead-letter", "async workers", "idempotency"],
    },
]

# Which students get full evaluations and what commit info
# (student index, task index, commit_url, approach_note, eval_state)
SUBMISSION_CONFIGS = [
    (0, 0, "https://github.com/aarav/project/commit/a1b2c3d4e5f6", "Implemented sliding window using Redis with Lua scripting.", "complete"),
    (1, 1, "https://github.com/priya/project/commit/b2c3d4e5f6a1", "Used PyJWT library. Refresh tokens stored in database.", "needs_review"),
    (2, 2, "https://github.com/rahul/project/commit/c3d4e5f6a1b2", "Cursor-based pagination with keyset approach. Full CRUD.", "approved"),
    (3, 3, "https://github.com/sneha/project/commit/d4e5f6a1b2c3", "Basic Alembic setup. Used autogenerate for migrations.", "needs_review"),
    (5, 4, "https://github.com/kavya/project/commit/e5f6a1b2c3d4", "Added middleware logging. Structured JSON with request_id.", "complete"),
    (6, 0, "https://github.com/dev/project/commit/f6a1b2c3d4e5", "Implemented token bucket algorithm with in-memory dict.", "approved"),
    # Arjun (4), Ananya (7), Rohan (8), Lakshmi (9) have no submission yet
]

# Skill dimension baseline scores for demo (per student index, seeded deterministically)
# Format: [problem_solving, code_quality, system_design, testing, debugging,
#          communication, algorithms, architecture, project_management, domain_knowledge]
DEMO_SKILL_SCORES = [
    [80, 75, 65, 70, 85, 60, 88, 60, 55, 70],   # Aarav — strong algorithms
    [60, 55, 50, 40, 58, 65, 55, 45, 50, 60],   # Priya — weak testing
    [78, 80, 88, 72, 75, 70, 70, 85, 65, 75],   # Rahul — strong system design
    [45, 50, 30, 48, 52, 55, 42, 28, 45, 50],   # Sneha — weak architecture
    [65, 60, 55, 60, 90, 58, 68, 52, 48, 62],   # Arjun — strong debugging
    [55, 60, 48, 52, 58, 62, 50, 45, 50, 55],   # Kavya — needs web APIs
    [60, 58, 50, 85, 62, 55, 55, 48, 52, 60],   # Dev — strong testing
    [80, 82, 85, 78, 75, 70, 72, 90, 72, 78],   # Ananya — strong architecture
    [42, 45, 30, 40, 48, 50, 38, 28, 42, 45],   # Rohan — weak system design
    [72, 88, 70, 75, 68, 65, 65, 68, 62, 72],   # Lakshmi — strong code quality
]

SKILL_DIMENSIONS = [
    "problem_solving", "code_quality", "system_design", "testing",
    "debugging", "communication", "algorithms", "architecture",
    "project_management", "domain_knowledge",
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

        task_cfg = DEMO_TASKS[i % len(DEMO_TASKS)]
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

    # --- Milestone 7: Skill Assessments, Profile Analyses, Learning Plans ---
    await _seed_m7_data(store, org, batch, student_profiles, tasks, today)

    logger.info("Demo seed complete — org=%s batch=%s", org.id, batch.id)
    print("\n=== Demo Seed Complete ===")
    print(f"Mentor:   {mentor_email} / {DEMO_PASSWORD}")
    for i, s in enumerate(DEMO_STUDENTS):
        print(f"Student {i+1:2d}: {s['email']} / {DEMO_PASSWORD}  ({s['name']})")
    print("\nLogin:  POST http://localhost:8000/auth/token")


async def _seed_m7_data(store, org, batch, student_profiles, tasks, today) -> None:
    """Seed Milestone 7 demo data: skill assessments, profiles, and learning plans."""
    from datetime import UTC, datetime, timedelta
    from app.domain.enums import (
        LearningPlanStatus, PlanDayStatus, ProfileAnalysisStatus, SkillConfidence,
    )
    from app.schemas.m7 import (
        LearningPlanCreate, LearningPlanDayCreate,
        SkillAssessmentCreate, StudentProfileAnalysisCreate, StudentProgressCreate,
    )

    for i, student in enumerate(student_profiles):
        scores = DEMO_SKILL_SCORES[i] if i < len(DEMO_SKILL_SCORES) else [50] * 10
        profile_data = DEMO_STUDENTS[i].get("profile", {})

        # Profile analysis (pre-computed for demo)
        analysis = store.create_student_profile_analysis(
            StudentProfileAnalysisCreate(
                student_id=student.id,
                organization_id=org.id,
                status=ProfileAnalysisStatus.COMPLETE,
                raw_profile=profile_data,
                observed_skills=[
                    {"name": "Python", "level": "intermediate", "evidence": profile_data.get("python_experience", "N/A")},
                ],
                inferred_skills=[
                    {"name": k, "level": "intermediate", "reasoning": "Demo inferred skill"}
                    for k in (profile_data.get("strengths", "").split(",") if profile_data.get("strengths") else [])
                ],
                unknown_areas=["cloud_deployment", "microservices"] if i % 3 == 0 else ["advanced_algorithms"],
                learning_style=["hands-on", "visual", "reading", "collaborative"][i % 4],
                risk_factors=[{"factor": "weak_" + (profile_data.get("weakness", "none")), "description": "Demo risk factor"}] if profile_data.get("weakness") else [],
                strengths=[f"Strong in {profile_data.get('strengths', 'general programming')}", "Consistent learner"],
                ai_model="mock-v1",
                confidence=0.75,
                generated_at=datetime.now(UTC),
            )
        )

        # Skill assessments per dimension
        for j, dim in enumerate(SKILL_DIMENSIONS):
            score = scores[j] if j < len(scores) else 50
            conf = SkillConfidence.OBSERVED if score >= 70 else SkillConfidence.INFERRED if score >= 40 else SkillConfidence.UNKNOWN
            store.upsert_skill_assessment(
                SkillAssessmentCreate(
                    student_id=student.id,
                    organization_id=org.id,
                    profile_analysis_id=analysis.id,
                    dimension=dim,
                    score=score,
                    evidence_sources=[{"rationale": f"Demo baseline for {dim}: {score}/100"}],
                    confidence=conf,
                    assessed_at=datetime.now(UTC),
                )
            )

        # Learning plan: students 0–4 have active plans with varying progress
        days_completed = [7, 3, 10, 1, 0, 5, 8, 2, 0, 4][i] if i < 10 else 0
        plan_start = today - timedelta(days=days_completed)
        plan = store.create_learning_plan(
            LearningPlanCreate(
                student_id=student.id,
                organization_id=org.id,
                batch_id=batch.id,
                status=LearningPlanStatus.ACTIVE,
                start_date=plan_start,
                end_date=plan_start + timedelta(days=13),
                total_days=14,
                ai_model="mock-v1",
            )
        )

        # Plan days
        for day_num in range(1, 15):
            scheduled = plan_start + timedelta(days=day_num - 1)
            is_past = scheduled < today
            is_today = scheduled == today

            if day_num <= days_completed:
                status = PlanDayStatus.COMPLETED
                score = scores[day_num % len(scores)] if day_num <= days_completed else None
                completed_at = datetime.now(UTC) - timedelta(days=days_completed - day_num)
            elif is_today or day_num == days_completed + 1:
                status = PlanDayStatus.AVAILABLE
                score = None
                completed_at = None
            else:
                status = PlanDayStatus.LOCKED
                score = None
                completed_at = None

            # Assign the student's task to day 1 (if available)
            task_id = None
            if day_num == days_completed + 1 and i < len(tasks):
                task_id = tasks[i].id if i < len(tasks) else None

            focus_dims = [SKILL_DIMENSIONS[(day_num - 1) % len(SKILL_DIMENSIONS)], SKILL_DIMENSIONS[day_num % len(SKILL_DIMENSIONS)]]
            store.create_learning_plan_day(
                LearningPlanDayCreate(
                    plan_id=plan.id,
                    student_id=student.id,
                    organization_id=org.id,
                    day_number=day_num,
                    scheduled_date=scheduled,
                    status=status,
                    task_id=task_id,
                    target_skills=focus_dims,
                    unlock_condition={"requires_day_completed": day_num - 1} if day_num > 1 else None,
                    completed_at=completed_at,
                    score=score,
                )
            )

        # Progress snapshot
        scored_days = days_completed
        avg_score = sum(scores[:days_completed]) / days_completed if days_completed else None
        store.upsert_student_progress(
            StudentProgressCreate(
                student_id=student.id,
                organization_id=org.id,
                plan_id=plan.id,
                snapshot_date=today,
                day_number=days_completed + 1,
                days_completed=days_completed,
                days_remaining=14 - days_completed,
                current_streak=min(days_completed, 3),
                longest_streak=min(days_completed, 5),
                average_score=round(avg_score, 1) if avg_score else None,
                skill_velocity={dim: 2.0 for dim in SKILL_DIMENSIONS[:3]},
                completed_task_ids=[],
            )
        )

        logger.info(
            "M7 data seeded for %s — %d days completed, avg score %.0f",
            student.full_name, days_completed, avg_score or 0
        )



if __name__ == "__main__":
    logging.basicConfig(level="INFO")
    asyncio.run(seed_demo())
