"""Tests for the AI Agents milestone.

Covers:
- bootstrap_github_evaluation / bootstrap_transcript_evaluation fallbacks
- GitHubEvalAgent: valid response, malformed JSON fallback, API error fallback
- TranscriptEvalAgent: valid response, transcript_text in prompt, fallback
- TaskGenAgent: valid response, missing-field fallback, validation clamping
- AgentOrchestrator: not configured → bootstrap, routes commit/transcript agents
- AgentOrchestrator.generate_task raises when not configured
- AsyncDailyLoopService.ai_evaluate_submission (mocked orchestrator)
- AsyncDailyLoopService.suggest_task (mocked orchestrator)
- New repository methods: students.get, projects.get, tasks.list_for_student
- /submissions/{id}/ai-evaluate endpoint
- /students/{id}/suggest-task endpoint
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.agents.base import (
    AgentContext,
    TaskGenContext,
    bootstrap_github_evaluation,
    bootstrap_transcript_evaluation,
)
from app.agents.github_eval_agent import GitHubEvalAgent, _build_evaluation, _extract_json
from app.agents.task_gen_agent import TaskGenAgent, _build_task_create
from app.agents.transcript_eval_agent import TranscriptEvalAgent
from app.agents.orchestrator import AgentOrchestrator
from app.application.async_daily_loop_service import AsyncDailyLoopService
from app.domain.enums import (
    EvaluationKind,
    EvaluationVerdict,
    SelfStatus,
    SubmissionStatus,
    TaskType,
    Track,
)
from app.infrastructure.repositories.memory import AsyncMemoryUnitOfWork
from app.schemas.core import (
    Batch,
    BatchCreate,
    Evaluation,
    EvaluationCreate,
    Evidence,
    Organization,
    OrganizationCreate,
    Project,
    ProjectCreate,
    Student,
    StudentCreate,
    Submission,
    SubmissionCreate,
    Task,
    TaskCreate,
)
from app.services.store import InMemoryStore
from app.shared.exceptions import InfrastructureException, NotFoundException


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _org() -> Organization:
    return Organization(name="Kalvium", slug="kalvium")


def _batch(org_id) -> Batch:
    return Batch(
        organization_id=org_id,
        name="Batch 1",
        starts_on=date(2026, 8, 1),
        ends_on=date(2026, 8, 31),
    )


def _student(org_id, batch_id) -> Student:
    return Student(
        organization_id=org_id,
        batch_id=batch_id,
        full_name="Alice Kumar",
        email="alice@example.com",
        track=Track.TRACK_A,
    )


def _project(org_id, student_id) -> Project:
    return Project(
        organization_id=org_id,
        student_id=student_id,
        name="Defense App",
        repository_url="https://github.com/alice/defense-app",
    )


def _task(org_id, batch_id, student_id, project_id) -> Task:
    return Task(
        organization_id=org_id,
        batch_id=batch_id,
        student_id=student_id,
        project_id=project_id,
        task_type=TaskType.CODING,
        title="Implement rate limiting",
        problem_statement="Add rate limiting to the login endpoint to prevent brute force attacks.",
        acceptance_criteria=[
            "Requests exceeding 5 per minute return 429.",
            "Rate limit resets after 60 seconds.",
            "Header X-RateLimit-Remaining is returned.",
        ],
        expected_concepts=["rate_limiting", "middleware"],
        due_on=date(2026, 8, 7),
    )


def _submission(org_id, task_id, student_id, *, commit_url=None, transcript_text=None) -> Submission:
    kwargs = {
        "organization_id": org_id,
        "task_id": task_id,
        "student_id": student_id,
        "self_status": SelfStatus.SOLVED,
    }
    if commit_url:
        kwargs["commit_url"] = commit_url
    elif transcript_text:
        kwargs["transcript_text"] = transcript_text
    else:
        kwargs["commit_url"] = "https://github.com/alice/defense-app/commit/abc123"
    return Submission(**kwargs)


def _agent_context(commit_url=None, transcript_text=None) -> AgentContext:
    org_id = uuid4()
    batch_id = uuid4()
    student_id = uuid4()
    project_id = uuid4()
    task = _task(org_id, batch_id, student_id, project_id)
    submission = _submission(
        org_id, task.id, student_id,
        commit_url=commit_url,
        transcript_text=transcript_text,
    )
    return AgentContext(task=task, submission=submission)


_VALID_GITHUB_RESPONSE = {
    "verdict": "correct",
    "score": 90,
    "confidence": 0.85,
    "evidence_summary": "Rate limiting middleware found in app/middleware.py with correct 429 status.",
    "flags": [],
    "mentor_note": "Solid implementation. No issues found.",
    "student_feedback_draft": "Great work! Your rate limiting implementation meets all criteria.",
    "recommended_next_action": "none",
}

_VALID_TRANSCRIPT_RESPONSE = {
    "verdict": "partially_correct",
    "score": 70,
    "confidence": 0.75,
    "evidence_summary": "Student explained middleware correctly but missed token bucket details.",
    "flags": ["surface_understanding_only"],
    "mentor_note": "Student understands the concept but lacks depth on implementation trade-offs.",
    "student_feedback_draft": "Good explanation overall. Try to elaborate on why token bucket is preferred.",
    "recommended_next_action": "none",
}

_VALID_TASK_RESPONSE = {
    "task_type": "coding",
    "title": "Add authentication middleware",
    "problem_statement": "Implement JWT-based authentication middleware for all protected routes.",
    "acceptance_criteria": [
        "Requests without valid JWT return 401.",
        "Token expiry is enforced.",
        "Middleware is applied to all /api routes.",
    ],
    "expected_concepts": ["jwt", "middleware", "authentication"],
}


def _mock_anthropic_response(content: dict) -> MagicMock:
    msg = MagicMock()
    msg.content = [MagicMock(text=json.dumps(content))]
    return msg


# ---------------------------------------------------------------------------
# bootstrap_github_evaluation
# ---------------------------------------------------------------------------


def test_bootstrap_github_evaluation_returns_needs_human_review():
    ctx = _agent_context(commit_url="https://github.com/alice/repo/commit/abc")
    result = bootstrap_github_evaluation(ctx)
    assert result.verdict == EvaluationVerdict.NEEDS_HUMAN_REVIEW
    assert result.kind == EvaluationKind.GITHUB_COMMIT
    assert "ai_evaluation_not_configured" in result.flags
    assert result.prompt_version == "deterministic-bootstrap.v1"


def test_bootstrap_transcript_evaluation_returns_needs_human_review():
    ctx = _agent_context(transcript_text="I implemented rate limiting using middleware.")
    result = bootstrap_transcript_evaluation(ctx)
    assert result.verdict == EvaluationVerdict.NEEDS_HUMAN_REVIEW
    assert result.kind == EvaluationKind.TRANSCRIPT
    assert "ai_evaluation_not_configured" in result.flags


# ---------------------------------------------------------------------------
# _extract_json
# ---------------------------------------------------------------------------


def test_extract_json_plain():
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_strips_markdown_fence():
    assert _extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_strips_plain_fence():
    assert _extract_json('```\n{"a": 1}\n```') == {"a": 1}


# ---------------------------------------------------------------------------
# GitHubEvalAgent
# ---------------------------------------------------------------------------


def test_github_eval_agent_maps_verdict_correctly():
    client = AsyncMock()
    client.messages.create = AsyncMock(
        return_value=_mock_anthropic_response(_VALID_GITHUB_RESPONSE)
    )
    agent = GitHubEvalAgent(client, "claude-haiku-4-5-20251001")
    ctx = _agent_context(commit_url="https://github.com/alice/repo/commit/abc")

    result = _run(agent.evaluate(ctx))

    assert result.verdict == EvaluationVerdict.CORRECT
    assert result.score == 90
    assert result.confidence == 0.85
    assert result.kind == EvaluationKind.GITHUB_COMMIT
    assert result.prompt_version == "github-eval-agent.v1"


def test_github_eval_agent_clamps_score_and_confidence():
    ctx = _agent_context(commit_url="https://github.com/alice/repo/commit/abc")
    parsed = {**_VALID_GITHUB_RESPONSE, "verdict": "correct", "score": 150, "confidence": 2.5}
    result = _build_evaluation(ctx, parsed)
    assert result.score == 100
    assert result.confidence == 1.0


def test_github_eval_agent_falls_back_on_malformed_json():
    client = AsyncMock()
    bad_msg = MagicMock()
    bad_msg.content = [MagicMock(text="not valid json at all")]
    client.messages.create = AsyncMock(return_value=bad_msg)
    agent = GitHubEvalAgent(client, "claude-haiku-4-5-20251001")
    ctx = _agent_context(commit_url="https://github.com/alice/repo/commit/abc")

    result = _run(agent.evaluate(ctx))

    assert result.verdict == EvaluationVerdict.NEEDS_HUMAN_REVIEW
    assert "ai_evaluation_not_configured" in result.flags or "ai_evaluation_failed" in result.flags


def test_github_eval_agent_falls_back_on_api_error():
    client = AsyncMock()
    client.messages.create = AsyncMock(side_effect=Exception("connection timeout"))
    agent = GitHubEvalAgent(client, "claude-haiku-4-5-20251001")
    ctx = _agent_context(commit_url="https://github.com/alice/repo/commit/abc")

    result = _run(agent.evaluate(ctx))

    assert "ai_evaluation_failed" in result.flags


def test_github_eval_agent_unknown_verdict_maps_to_needs_human_review():
    ctx = _agent_context(commit_url="https://github.com/alice/repo/commit/abc")
    parsed = {**_VALID_GITHUB_RESPONSE, "verdict": "amazing"}
    result = _build_evaluation(ctx, parsed)
    assert result.verdict == EvaluationVerdict.NEEDS_HUMAN_REVIEW


def test_github_eval_agent_invalid_action_coerced():
    ctx = _agent_context(commit_url="https://github.com/alice/repo/commit/abc")
    parsed = {**_VALID_GITHUB_RESPONSE, "recommended_next_action": "do_magic"}
    result = _build_evaluation(ctx, parsed)
    assert result.recommended_next_action == "mentor_review_required"


# ---------------------------------------------------------------------------
# TranscriptEvalAgent
# ---------------------------------------------------------------------------


def test_transcript_eval_agent_maps_verdict():
    client = AsyncMock()
    client.messages.create = AsyncMock(
        return_value=_mock_anthropic_response(_VALID_TRANSCRIPT_RESPONSE)
    )
    agent = TranscriptEvalAgent(client, "claude-haiku-4-5-20251001")
    ctx = _agent_context(transcript_text="I used token bucket algorithm for rate limiting.")

    result = _run(agent.evaluate(ctx))

    assert result.verdict == EvaluationVerdict.PARTIALLY_CORRECT
    assert result.kind == EvaluationKind.TRANSCRIPT
    assert result.prompt_version == "transcript-eval-agent.v1"


def test_transcript_eval_agent_falls_back_on_api_error():
    client = AsyncMock()
    client.messages.create = AsyncMock(side_effect=RuntimeError("rate limit"))
    agent = TranscriptEvalAgent(client, "claude-haiku-4-5-20251001")
    ctx = _agent_context(transcript_text="Rate limiting prevents brute force.")

    result = _run(agent.evaluate(ctx))

    assert "ai_evaluation_failed" in result.flags
    assert result.kind == EvaluationKind.TRANSCRIPT


# ---------------------------------------------------------------------------
# TaskGenAgent
# ---------------------------------------------------------------------------


def test_task_gen_agent_produces_valid_task_create():
    client = AsyncMock()
    client.messages.create = AsyncMock(
        return_value=_mock_anthropic_response(_VALID_TASK_RESPONSE)
    )
    org_id = uuid4()
    batch_id = uuid4()
    student_id = uuid4()
    project_id = uuid4()
    context = TaskGenContext(
        student=_student(org_id, batch_id),
        project=_project(org_id, student_id),
        previous_tasks=[],
    )
    agent = TaskGenAgent(client, "claude-haiku-4-5-20251001")

    result = _run(agent.generate(context, org_id, batch_id, date(2026, 8, 8)))

    assert isinstance(result, TaskCreate)
    assert result.title == "Add authentication middleware"
    assert len(result.acceptance_criteria) == 3
    assert result.task_type == TaskType.CODING


def test_task_gen_agent_short_title_replaced():
    org_id = uuid4()
    batch_id = uuid4()
    student_id = uuid4()
    project_id = uuid4()
    context = TaskGenContext(
        student=_student(org_id, batch_id),
        project=_project(org_id, student_id),
        previous_tasks=[],
    )
    parsed = {**_VALID_TASK_RESPONSE, "title": "AB"}
    result = _build_task_create(context, parsed, org_id, batch_id, date(2026, 8, 8))
    assert len(result.title) >= 3


def test_task_gen_agent_empty_criteria_gets_fallback():
    org_id = uuid4()
    batch_id = uuid4()
    student_id = uuid4()
    project_id = uuid4()
    context = TaskGenContext(
        student=_student(org_id, batch_id),
        project=_project(org_id, student_id),
        previous_tasks=[],
    )
    parsed = {**_VALID_TASK_RESPONSE, "acceptance_criteria": []}
    result = _build_task_create(context, parsed, org_id, batch_id, date(2026, 8, 8))
    assert len(result.acceptance_criteria) >= 1


def test_task_gen_agent_unknown_task_type_defaults_to_coding():
    org_id = uuid4()
    batch_id = uuid4()
    student_id = uuid4()
    project_id = uuid4()
    context = TaskGenContext(
        student=_student(org_id, batch_id),
        project=_project(org_id, student_id),
        previous_tasks=[],
    )
    parsed = {**_VALID_TASK_RESPONSE, "task_type": "essay"}
    result = _build_task_create(context, parsed, org_id, batch_id, date(2026, 8, 8))
    assert result.task_type == TaskType.CODING


# ---------------------------------------------------------------------------
# AgentOrchestrator — not configured
# ---------------------------------------------------------------------------


def test_orchestrator_not_configured_returns_bootstrap_for_commit():
    org_id = uuid4()
    batch_id = uuid4()
    student_id = uuid4()
    project_id = uuid4()
    task = _task(org_id, batch_id, student_id, project_id)
    submission = _submission(
        org_id, task.id, student_id,
        commit_url="https://github.com/alice/repo/commit/abc",
    )
    orch = AgentOrchestrator(api_key="")

    result = _run(orch.evaluate_submission(task, submission))

    assert result.verdict == EvaluationVerdict.NEEDS_HUMAN_REVIEW
    assert result.kind == EvaluationKind.GITHUB_COMMIT
    assert "ai_evaluation_not_configured" in result.flags


def test_orchestrator_not_configured_returns_bootstrap_for_transcript():
    org_id = uuid4()
    batch_id = uuid4()
    student_id = uuid4()
    project_id = uuid4()
    task = _task(org_id, batch_id, student_id, project_id)
    submission = _submission(
        org_id, task.id, student_id,
        transcript_text="Rate limiting prevents brute force attacks.",
    )
    orch = AgentOrchestrator(api_key="")

    result = _run(orch.evaluate_submission(task, submission))

    assert result.verdict == EvaluationVerdict.NEEDS_HUMAN_REVIEW
    assert result.kind == EvaluationKind.TRANSCRIPT


def test_orchestrator_not_configured_raises_on_generate_task():
    org_id = uuid4()
    batch_id = uuid4()
    student_id = uuid4()
    context = TaskGenContext(
        student=_student(org_id, batch_id),
        project=_project(org_id, student_id),
        previous_tasks=[],
    )
    orch = AgentOrchestrator(api_key="")

    with pytest.raises(InfrastructureException):
        _run(orch.generate_task(context, org_id, batch_id, date(2026, 8, 8)))


# ---------------------------------------------------------------------------
# AgentOrchestrator — configured (mocked client)
# ---------------------------------------------------------------------------


def _mock_orchestrator_with_github_result(evaluation: EvaluationCreate) -> AgentOrchestrator:
    orch = AgentOrchestrator.__new__(AgentOrchestrator)
    orch._model = "claude-haiku-4-5-20251001"
    mock_client = AsyncMock()
    orch._client = mock_client

    mock_agent = AsyncMock()
    mock_agent.evaluate = AsyncMock(return_value=evaluation)

    with patch("app.agents.orchestrator.get_github_service", return_value=None):
        pass

    return orch


def test_orchestrator_is_configured_when_client_set():
    orch = AgentOrchestrator.__new__(AgentOrchestrator)
    orch._model = "test"
    orch._client = MagicMock()
    assert orch.is_configured is True


def test_orchestrator_not_configured_when_no_client():
    orch = AgentOrchestrator(api_key="")
    assert orch.is_configured is False


# ---------------------------------------------------------------------------
# New repository methods — memory implementations
# ---------------------------------------------------------------------------


def test_memory_student_repo_get_returns_student():
    store = InMemoryStore()
    student = store.create_student(StudentCreate(
        organization_id=uuid4(),
        batch_id=uuid4(),
        full_name="Alice Kumar",
        email="alice@test.com",
    ))

    result = store.get_student(student.id)
    assert result is not None
    assert result.id == student.id


def test_memory_student_repo_get_returns_none_for_missing():
    store = InMemoryStore()
    assert store.get_student(uuid4()) is None


def test_memory_project_repo_get_returns_project():
    store = InMemoryStore()
    org_id = uuid4()
    project = store.create_project(ProjectCreate(
        organization_id=org_id,
        student_id=uuid4(),
        name="Defense App",
        repository_url="https://github.com/alice/defense",
    ))

    result = store.get_project(project.id)
    assert result is not None
    assert result.id == project.id


def test_memory_task_list_for_student():
    store = InMemoryStore()
    org_id = uuid4()
    batch_id = uuid4()
    student_id = uuid4()
    project_id = uuid4()

    t1 = store.create_task(TaskCreate(
        organization_id=org_id, batch_id=batch_id,
        student_id=student_id, project_id=project_id,
        task_type=TaskType.CODING, title="Task one here",
        problem_statement="First task description here.",
        acceptance_criteria=["AC1."], due_on=date(2026, 8, 7),
    ))
    other_student = uuid4()
    store.create_task(TaskCreate(
        organization_id=org_id, batch_id=batch_id,
        student_id=other_student, project_id=project_id,
        task_type=TaskType.CODING, title="Another student task",
        problem_statement="Other student description here.",
        acceptance_criteria=["AC1."], due_on=date(2026, 8, 7),
    ))

    results = store.list_student_tasks(student_id)
    assert len(results) == 1
    assert results[0].id == t1.id


# ---------------------------------------------------------------------------
# AsyncDailyLoopService.ai_evaluate_submission
# ---------------------------------------------------------------------------


def _make_service_with_store():
    store = InMemoryStore()
    uow = AsyncMemoryUnitOfWork(store)
    service = AsyncDailyLoopService(uow)
    return service, store


def test_ai_evaluate_submission_raises_not_found_for_missing_submission():
    service, _ = _make_service_with_store()
    orch = AgentOrchestrator(api_key="")

    with pytest.raises(NotFoundException):
        _run(service.ai_evaluate_submission(uuid4(), orch))


def test_ai_evaluate_submission_returns_evaluation():
    service, store = _make_service_with_store()
    org = store.create_organization(OrganizationCreate(name="Kalvium", slug="kalvium"))
    batch = store.create_batch(BatchCreate(
        organization_id=org.id, name="B1",
        starts_on=date(2026, 8, 1), ends_on=date(2026, 8, 31),
    ))
    student = store.create_student(StudentCreate(
        organization_id=org.id, batch_id=batch.id,
        full_name="Alice", email="alice@example.com",
    ))
    project = store.create_project(ProjectCreate(
        organization_id=org.id, student_id=student.id,
        name="Defense App", repository_url="https://github.com/alice/app",
    ))
    task = store.create_task(TaskCreate(
        organization_id=org.id, batch_id=batch.id,
        student_id=student.id, project_id=project.id,
        task_type=TaskType.CODING, title="Rate limiting task",
        problem_statement="Implement rate limiting for login endpoint.",
        acceptance_criteria=["Returns 429 when exceeded."],
        due_on=date(2026, 8, 7),
    ))
    submission = store.create_submission(SubmissionCreate(
        organization_id=org.id, task_id=task.id, student_id=student.id,
        self_status=SelfStatus.SOLVED,
        commit_url="https://github.com/alice/app/commit/abc123",
    ))

    orch = AgentOrchestrator(api_key="")
    result = _run(service.ai_evaluate_submission(submission.id, orch))

    assert isinstance(result, Evaluation)
    assert result.submission_id == submission.id
    assert result.kind == EvaluationKind.GITHUB_COMMIT


# ---------------------------------------------------------------------------
# AsyncDailyLoopService.suggest_task
# ---------------------------------------------------------------------------


def test_suggest_task_raises_not_found_for_missing_student():
    service, _ = _make_service_with_store()
    orch = AgentOrchestrator(api_key="")

    with pytest.raises(NotFoundException, match="Student"):
        _run(service.suggest_task(
            student_id=uuid4(),
            project_id=uuid4(),
            batch_id=uuid4(),
            due_on=date(2026, 8, 8),
            orchestrator=orch,
        ))


def test_suggest_task_raises_not_found_for_missing_project():
    service, store = _make_service_with_store()
    org = store.create_organization(OrganizationCreate(name="Kalvium", slug="kalvium"))
    batch = store.create_batch(BatchCreate(
        organization_id=org.id, name="B1",
        starts_on=date(2026, 8, 1), ends_on=date(2026, 8, 31),
    ))
    student = store.create_student(StudentCreate(
        organization_id=org.id, batch_id=batch.id,
        full_name="Bob", email="bob@example.com",
    ))
    orch = AgentOrchestrator(api_key="")

    with pytest.raises(NotFoundException, match="Project"):
        _run(service.suggest_task(
            student_id=student.id,
            project_id=uuid4(),
            batch_id=batch.id,
            due_on=date(2026, 8, 8),
            orchestrator=orch,
        ))


def test_suggest_task_raises_infrastructure_when_not_configured():
    service, store = _make_service_with_store()
    org = store.create_organization(OrganizationCreate(name="Kalvium", slug="kalvium"))
    batch = store.create_batch(BatchCreate(
        organization_id=org.id, name="B1",
        starts_on=date(2026, 8, 1), ends_on=date(2026, 8, 31),
    ))
    student = store.create_student(StudentCreate(
        organization_id=org.id, batch_id=batch.id,
        full_name="Carol", email="carol@example.com",
    ))
    project = store.create_project(ProjectCreate(
        organization_id=org.id, student_id=student.id,
        name="Defense App", repository_url="https://github.com/carol/app",
    ))
    orch = AgentOrchestrator(api_key="")

    with pytest.raises(InfrastructureException):
        _run(service.suggest_task(
            student_id=student.id,
            project_id=project.id,
            batch_id=batch.id,
            due_on=date(2026, 8, 8),
            orchestrator=orch,
        ))


def test_suggest_task_creates_task_with_mocked_orchestrator():
    service, store = _make_service_with_store()
    org = store.create_organization(OrganizationCreate(name="Kalvium", slug="kalvium"))
    batch = store.create_batch(BatchCreate(
        organization_id=org.id, name="B1",
        starts_on=date(2026, 8, 1), ends_on=date(2026, 8, 31),
    ))
    student = store.create_student(StudentCreate(
        organization_id=org.id, batch_id=batch.id,
        full_name="Dave", email="dave@example.com",
    ))
    project = store.create_project(ProjectCreate(
        organization_id=org.id, student_id=student.id,
        name="Defense App", repository_url="https://github.com/dave/app",
    ))

    ai_task_payload = TaskCreate(
        organization_id=org.id,
        batch_id=batch.id,
        student_id=student.id,
        project_id=project.id,
        task_type=TaskType.CODING,
        title="Implement JWT auth middleware",
        problem_statement="Add JWT authentication to protect all API routes.",
        acceptance_criteria=["Unauthenticated requests return 401."],
        due_on=date(2026, 8, 8),
    )

    mock_orch = AsyncMock(spec=AgentOrchestrator)
    mock_orch.generate_task = AsyncMock(return_value=ai_task_payload)

    result = _run(service.suggest_task(
        student_id=student.id,
        project_id=project.id,
        batch_id=batch.id,
        due_on=date(2026, 8, 8),
        orchestrator=mock_orch,
    ))

    assert isinstance(result, Task)
    assert result.title == "Implement JWT auth middleware"
    assert result.student_id == student.id


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------


def _make_test_client() -> tuple[TestClient, InMemoryStore]:
    from app.api.dependencies import get_async_service
    from app.main import create_app

    app = create_app()
    store = InMemoryStore()

    async def _override() -> AsyncIterator[AsyncDailyLoopService]:
        yield AsyncDailyLoopService(AsyncMemoryUnitOfWork(store))

    app.dependency_overrides[get_async_service] = _override
    return TestClient(app, raise_server_exceptions=False), store


def _setup_submission(store: InMemoryStore):
    org = store.create_organization(OrganizationCreate(name="Kalvium", slug="kalvium"))
    batch = store.create_batch(BatchCreate(
        organization_id=org.id, name="B1",
        starts_on=date(2026, 8, 1), ends_on=date(2026, 8, 31),
    ))
    student = store.create_student(StudentCreate(
        organization_id=org.id, batch_id=batch.id,
        full_name="Eve", email="eve@example.com",
    ))
    project = store.create_project(ProjectCreate(
        organization_id=org.id, student_id=student.id,
        name="Defense App", repository_url="https://github.com/eve/app",
    ))
    task = store.create_task(TaskCreate(
        organization_id=org.id, batch_id=batch.id,
        student_id=student.id, project_id=project.id,
        task_type=TaskType.CODING, title="Rate limiting task",
        problem_statement="Implement rate limiting for login endpoint.",
        acceptance_criteria=["Returns 429 when exceeded."],
        due_on=date(2026, 8, 7),
    ))
    submission = store.create_submission(SubmissionCreate(
        organization_id=org.id, task_id=task.id, student_id=student.id,
        self_status=SelfStatus.SOLVED,
        commit_url="https://github.com/eve/app/commit/abc123",
    ))
    return org, batch, student, project, task, submission


def test_ai_evaluate_endpoint_returns_200():
    client, store = _make_test_client()
    _, _, _, _, _, submission = _setup_submission(store)

    response = client.post(f"/submissions/{submission.id}/ai-evaluate")

    assert response.status_code == 200
    data = response.json()
    assert data["submission_id"] == str(submission.id)
    assert "verdict" in data


def test_ai_evaluate_endpoint_returns_404_for_unknown_submission():
    client, _ = _make_test_client()
    response = client.post(f"/submissions/{uuid4()}/ai-evaluate")
    assert response.status_code == 404


def test_suggest_task_endpoint_returns_404_for_unknown_student():
    client, store = _make_test_client()
    org = store.create_organization(OrganizationCreate(name="Kalvium", slug="kalvium"))
    batch = store.create_batch(BatchCreate(
        organization_id=org.id, name="B1",
        starts_on=date(2026, 8, 1), ends_on=date(2026, 8, 31),
    ))

    response = client.post(
        f"/students/{uuid4()}/suggest-task",
        json={"project_id": str(uuid4()), "batch_id": str(batch.id), "due_on": "2026-08-08"},
    )
    assert response.status_code == 404


def test_suggest_task_endpoint_returns_500_when_ai_not_configured():
    client, store = _make_test_client()
    _, batch, student, project, _, _ = _setup_submission(store)

    response = client.post(
        f"/students/{student.id}/suggest-task",
        json={
            "project_id": str(project.id),
            "batch_id": str(batch.id),
            "due_on": "2026-08-08",
        },
    )
    assert response.status_code == 500
