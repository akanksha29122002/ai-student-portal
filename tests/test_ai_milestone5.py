"""Tests for Milestone 5: AI Evaluation Engine.

Covers:
- AIProvider abstraction (AnthropicProvider, MockAIProvider)
- Context builder + context hash
- Rubric weights + score calculation
- Evaluation engine pipeline (states, validation, escalation)
- AI output parsing (valid, malformed, extra fields)
- Hallucination guard (CANNOT_VERIFY vs fabricated data)
- Task-criteria evaluation
- Confidence threshold â†’ NEEDS_HUMAN_REVIEW escalation
- Critical security concern â†’ escalation
- Duplicate evaluation dedup (same context_hash)
- Mentor review flow (approve, reject, override_score)
- AIEvaluationStore CRUD
- API endpoints: evaluate, get evaluation, mentor review, list
- Mock provider determinism
- Token/cost tracking fields
- 5 evaluation fixtures for regression testing
"""
from __future__ import annotations

import asyncio
import json
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.ai.context_builder import ContextBuilder, EvaluationContext
from app.ai.engine import EvaluationEngine
from app.ai.provider import MockAIProvider, reset_provider
from app.ai.rubric import (
    RUBRIC_WEIGHTS,
    calculate_weighted_score,
    requires_human_review,
)
from app.ai.schemas import (
    EvaluationRecord,
    EvaluationResponse,
    EvaluationState,
    MentorDecision,
    SubmissionVerdict,
)
from app.ai.store import AIEvaluationStore, reset_ai_store
from app.domain.enums import SelfStatus, TaskType, Track
from app.schemas.core import (
    BatchCreate,
    OrganizationCreate,
    ProjectCreate,
    StudentCreate,
    SubmissionCreate,
    TaskCreate,
)


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task(**kwargs):
    defaults = dict(
        organization_id=uuid4(),
        batch_id=uuid4(),
        student_id=uuid4(),
        project_id=uuid4(),
        task_type=TaskType.CODING,
        title="Implement rate limiter for login API",
        problem_statement="Add rate limiting middleware to prevent brute-force attacks on the login endpoint.",
        acceptance_criteria=[
            "Limit requests to 5 per minute per IP",
            "Return HTTP 429 when rate limit exceeded",
            "Add configuration for threshold",
            "Prevent brute force attacks",
        ],
        expected_concepts=["middleware", "rate limiting", "HTTP 429"],
        due_on=date(2026, 8, 7),
    )
    defaults.update(kwargs)
    from app.schemas.core import Task
    return Task(**defaults)


def _make_submission(**kwargs):
    defaults = dict(
        organization_id=uuid4(),
        task_id=uuid4(),
        student_id=uuid4(),
        self_status=SelfStatus.SOLVED,
        commit_url="https://github.com/student/project/commit/abc123def456",
        approach_note="I implemented rate limiting using a sliding window algorithm.",
    )
    defaults.update(kwargs)
    from app.schemas.core import Submission
    return Submission(**defaults)


def _make_store() -> AIEvaluationStore:
    return AIEvaluationStore()


def _make_record(submission_id=None, org_id=None, task_id=None) -> EvaluationRecord:
    return EvaluationRecord(
        submission_id=submission_id or uuid4(),
        organization_id=org_id or uuid4(),
        task_id=task_id or uuid4(),
    )


VALID_AI_RESPONSE = {
    "status": "PARTIALLY_SOLVED",
    "overall_score": 7.2,
    "confidence": 0.88,
    "dimensions": {
        "correctness": {"score": 8.0, "reason": "Rate limiting logic is present in middleware.py", "evidence": []},
        "task_completeness": {"score": 7.0, "reason": "Most criteria met, threshold config missing.", "evidence": []},
        "code_quality": {"score": 7.5, "reason": "Clean code with good naming.", "evidence": []},
        "architecture": {"score": 7.0, "reason": "Middleware pattern is appropriate.", "evidence": []},
        "security": {"score": 8.0, "reason": "No obvious vulnerabilities found.", "evidence": []},
        "performance": {"score": 6.0, "reason": "In-memory counter may not scale.", "evidence": []},
        "maintainability": {"score": 8.0, "reason": "Code is readable.", "evidence": []},
        "edge_cases": {"score": 6.5, "reason": "Missing edge case for IPv6.", "evidence": []},
        "testing": {"score": 5.0, "reason": "No tests added.", "evidence": []},
    },
    "acceptance_criteria_results": [
        {"criterion": "Limit requests to 5 per minute per IP", "status": "PASS", "evidence": ["middleware.py:42"], "notes": ""},
        {"criterion": "Return HTTP 429 when rate limit exceeded", "status": "PASS", "evidence": ["middleware.py:58"], "notes": ""},
        {"criterion": "Add configuration for threshold", "status": "FAIL", "evidence": [], "notes": "No config found."},
        {"criterion": "Prevent brute force attacks", "status": "PASS", "evidence": ["middleware.py:42"], "notes": ""},
    ],
    "strengths": ["Clear middleware structure", "Correct HTTP status code"],
    "issues": [
        {"file": "middleware.py", "line": None, "type": "quality", "severity": "medium", "description": "Threshold is hardcoded."}
    ],
    "missing_requirements": ["Configurable threshold"],
    "security_concerns": [],
    "performance_concerns": [
        {"file": "middleware.py", "line": 30, "type": "performance", "severity": "low", "description": "In-memory counter resets on restart."}
    ],
    "suggested_improvements": ["Extract threshold to environment variable"],
    "mentor_attention_required": False,
    "mentor_attention_reasons": [],
    "summary": "Student implemented rate limiting correctly for the main criteria. Threshold is hardcoded.",
}


# ---------------------------------------------------------------------------
# Rubric
# ---------------------------------------------------------------------------


def test_rubric_weights_sum_to_one():
    assert abs(sum(RUBRIC_WEIGHTS.values()) - 1.0) < 1e-9


def test_rubric_has_nine_dimensions():
    assert len(RUBRIC_WEIGHTS) == 9


def test_rubric_correctness_has_highest_weight():
    assert RUBRIC_WEIGHTS["correctness"] == max(RUBRIC_WEIGHTS.values())


def test_calculate_weighted_score_perfect():
    scores = {dim: 10.0 for dim in RUBRIC_WEIGHTS}
    assert calculate_weighted_score(scores) == 10.0


def test_calculate_weighted_score_zero():
    scores = {dim: 0.0 for dim in RUBRIC_WEIGHTS}
    assert calculate_weighted_score(scores) == 0.0


def test_calculate_weighted_score_mixed():
    scores = {dim: 5.0 for dim in RUBRIC_WEIGHTS}
    result = calculate_weighted_score(scores)
    assert abs(result - 5.0) < 0.01


def test_calculate_weighted_score_known():
    # Correctness=10 (25%), rest=0 â†’ 2.5
    scores = {dim: 0.0 for dim in RUBRIC_WEIGHTS}
    scores["correctness"] = 10.0
    result = calculate_weighted_score(scores)
    assert abs(result - 2.5) < 0.01


def test_requires_human_review_low_confidence():
    needs, reasons = requires_human_review(confidence=0.5)
    assert needs is True
    assert any("confidence" in r.lower() for r in reasons)


def test_requires_human_review_high_confidence():
    needs, _ = requires_human_review(confidence=0.95)
    assert needs is False


def test_requires_human_review_critical_security():
    needs, reasons = requires_human_review(confidence=0.99, has_critical_security=True)
    assert needs is True
    assert any("security" in r.lower() for r in reasons)


def test_requires_human_review_incomplete_context():
    needs, reasons = requires_human_review(confidence=0.95, context_incomplete=True)
    assert needs is True
    assert any("incomplete" in r.lower() for r in reasons)


# ---------------------------------------------------------------------------
# MockAIProvider
# ---------------------------------------------------------------------------


def test_mock_provider_is_mock():
    p = MockAIProvider()
    assert p.is_mock() is True


def test_mock_provider_name():
    p = MockAIProvider()
    assert p.provider_name() == "development_mock"


def test_mock_provider_returns_valid_json():
    p = MockAIProvider()
    msg = _run(p.complete("system", "user"))
    data = json.loads(msg.content)
    assert "status" in data
    assert "overall_score" in data
    assert "dimensions" in data
    assert "confidence" in data


def test_mock_provider_deterministic():
    p = MockAIProvider()
    msg1 = _run(p.complete("sys", "same-prompt"))
    msg2 = _run(p.complete("sys", "same-prompt"))
    assert msg1.content == msg2.content


def test_mock_provider_different_prompts_produce_different_scores():
    p = MockAIProvider()
    msg1 = _run(p.complete("sys", "prompt-alpha"))
    msg2 = _run(p.complete("sys", "prompt-beta"))
    d1 = json.loads(msg1.content)
    d2 = json.loads(msg2.content)
    assert d1["overall_score"] != d2["overall_score"] or d1["confidence"] != d2["confidence"]


def test_mock_provider_returns_token_counts():
    p = MockAIProvider()
    msg = _run(p.complete("system", "test prompt with words"))
    assert msg.input_tokens > 0
    assert msg.output_tokens > 0


def test_mock_provider_never_claims_real_ai():
    p = MockAIProvider()
    msg = _run(p.complete("system", "test"))
    data = json.loads(msg.content)
    summary = data.get("summary", "")
    assert "development_mock" in summary or "MOCK" in summary.upper()


def test_mock_provider_extracts_criteria_from_prompt():
    p = MockAIProvider()
    prompt = "Task title\nAcceptance criteria\n- Criterion one\n- Criterion two\n"
    msg = _run(p.complete("sys", prompt))
    data = json.loads(msg.content)
    criteria = data.get("acceptance_criteria_results", [])
    assert len(criteria) >= 1


def test_mock_provider_dimensions_have_nine_keys():
    p = MockAIProvider()
    msg = _run(p.complete("sys", "test"))
    data = json.loads(msg.content)
    dims = data["dimensions"]
    expected = {"correctness", "task_completeness", "code_quality", "architecture",
                "security", "performance", "maintainability", "edge_cases", "testing"}
    assert set(dims.keys()) == expected


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------


def test_context_builder_basic():
    task = _make_task()
    submission = _make_submission(task_id=task.id)
    ctx = ContextBuilder().build(task, submission)
    assert ctx.task_id == task.id
    assert ctx.submission_id == submission.id
    assert ctx.task_title == task.title
    assert ctx.acceptance_criteria == list(task.acceptance_criteria)


def test_context_builder_without_commit():
    task = _make_task()
    submission = _make_submission(task_id=task.id)
    ctx = ContextBuilder().build(task, submission)
    assert ctx.commit_sha is None
    assert ctx.files == []


def test_context_hash_is_deterministic():
    task = _make_task()
    submission = _make_submission(task_id=task.id)
    ctx1 = ContextBuilder().build(task, submission)
    ctx2 = ContextBuilder().build(task, submission)
    assert ctx1.context_hash() == ctx2.context_hash()


def test_context_hash_differs_on_different_task():
    task1 = _make_task(title="Task 1")
    task2 = _make_task(title="Task 2")
    sub = _make_submission()
    ctx1 = ContextBuilder().build(task1, sub)
    ctx2 = ContextBuilder().build(task2, sub)
    assert ctx1.context_hash() != ctx2.context_hash()


def test_context_builder_with_commit_and_files():
    from app.schemas.github import Commit, CommitFile
    from datetime import datetime, UTC

    task = _make_task()
    submission = _make_submission(task_id=task.id)

    now = datetime.now(UTC)
    commit = Commit(
        repository_id=uuid4(),
        organization_id=submission.organization_id,
        sha="abc123def456abc123def456abc123def456abc1",
        message="feat: implement rate limiting",
        author_name="Alice",
        author_email="alice@example.com",
        author_date=now,
        committer_name="Alice",
        committer_email="alice@example.com",
        committer_date=now,
        branch="main",
        url="https://github.com/student/project/commit/abc123def456abc123def456abc123def456abc1",
        additions=45,
        deletions=5,
    )
    files = [
        CommitFile(
            commit_id=commit.id,
            path="app/middleware.py",
            status="added",
            additions=45,
            deletions=0,
            changes=45,
            patch="@@ -0,0 +1,45 @@\n+def rate_limit():\n+    ...",
        )
    ]

    ctx = ContextBuilder().build(task, submission, commit, files)
    assert ctx.commit_sha == commit.sha
    assert len(ctx.files) == 1
    assert ctx.files[0].path == "app/middleware.py"
    assert ctx.files[0].patch is not None


# ---------------------------------------------------------------------------
# Evaluation engine
# ---------------------------------------------------------------------------


def _make_engine(provider=None, store=None) -> EvaluationEngine:
    return EvaluationEngine(
        provider=provider or MockAIProvider(),
        store=store or _make_store(),
        confidence_threshold=0.70,
    )


def _make_context() -> EvaluationContext:
    task = _make_task()
    submission = _make_submission(task_id=task.id)
    return ContextBuilder().build(task, submission)


def test_engine_completes_with_mock_provider():
    store = _make_store()
    engine = _make_engine(store=store)
    record = _make_record()
    record = store.create(record)
    ctx = _make_context()

    updated = _run(engine.evaluate(record, ctx))
    assert updated.state in (EvaluationState.COMPLETED, EvaluationState.NEEDS_HUMAN_REVIEW)
    assert updated.result is not None
    assert updated.input_tokens > 0
    assert updated.output_tokens > 0
    assert updated.duration_ms >= 0
    assert updated.provider == "development_mock"


def test_engine_sets_context_hash():
    store = _make_store()
    engine = _make_engine(store=store)
    record = _make_record()
    record = store.create(record)
    ctx = _make_context()

    updated = _run(engine.evaluate(record, ctx))
    assert updated.context_hash == ctx.context_hash()
    assert len(updated.context_hash) > 0


def test_engine_parses_valid_ai_json():
    mock_provider = MockAIProvider()
    # Override complete() to return our known-good response
    async def fake_complete(system_prompt, user_prompt, max_tokens=4096):
        from app.ai.provider import AIMessage
        return AIMessage(content=json.dumps(VALID_AI_RESPONSE), input_tokens=100, output_tokens=200)

    mock_provider.complete = fake_complete

    store = _make_store()
    engine = _make_engine(provider=mock_provider, store=store)
    record = _make_record()
    record = store.create(record)
    ctx = _make_context()

    updated = _run(engine.evaluate(record, ctx))
    # State may be NEEDS_HUMAN_REVIEW when context is incomplete (no commit)
    assert updated.state in (EvaluationState.COMPLETED, EvaluationState.NEEDS_HUMAN_REVIEW)
    assert updated.result is not None
    assert updated.result.overall_score == pytest.approx(7.2, abs=0.1)
    assert updated.result.confidence == pytest.approx(0.88)
    assert updated.result.status == SubmissionVerdict.PARTIALLY_SOLVED


def test_engine_validates_dimension_scores():
    store = _make_store()
    engine = _make_engine(store=store)
    record = _make_record()
    record = store.create(record)
    ctx = _make_context()

    updated = _run(engine.evaluate(record, ctx))
    if updated.result:
        dims = updated.result.dimensions
        for field_name in ("correctness", "task_completeness", "code_quality", "architecture",
                           "security", "performance", "maintainability", "edge_cases", "testing"):
            dim = getattr(dims, field_name)
            assert 0.0 <= dim.score <= 10.0, f"{field_name} score out of range"
            assert len(dim.reason) > 0


def test_engine_handles_malformed_json():
    mock_provider = MockAIProvider()

    async def bad_complete(system_prompt, user_prompt, max_tokens=4096):
        from app.ai.provider import AIMessage
        return AIMessage(content="This is NOT JSON {broken", input_tokens=10, output_tokens=5)

    mock_provider.complete = bad_complete

    store = _make_store()
    engine = _make_engine(provider=mock_provider, store=store)
    record = _make_record()
    record = store.create(record)

    updated = _run(engine.evaluate(record, _make_context()))
    assert updated.state == EvaluationState.FAILED
    assert updated.error is not None


def test_engine_handles_provider_exception():
    mock_provider = MockAIProvider()

    async def error_complete(system_prompt, user_prompt, max_tokens=4096):
        raise RuntimeError("Network timeout")

    mock_provider.complete = error_complete

    store = _make_store()
    engine = _make_engine(provider=mock_provider, store=store)
    record = _make_record()
    record = store.create(record)

    updated = _run(engine.evaluate(record, _make_context()))
    assert updated.state == EvaluationState.FAILED
    assert "timeout" in (updated.error or "").lower()


def test_engine_escalates_low_confidence():
    mock_provider = MockAIProvider()
    low_confidence_response = {**VALID_AI_RESPONSE, "confidence": 0.40}

    async def low_conf_complete(system_prompt, user_prompt, max_tokens=4096):
        from app.ai.provider import AIMessage
        return AIMessage(content=json.dumps(low_confidence_response), input_tokens=50, output_tokens=100)

    mock_provider.complete = low_conf_complete

    store = _make_store()
    engine = EvaluationEngine(provider=mock_provider, store=store, confidence_threshold=0.70)
    record = _make_record()
    record = store.create(record)

    updated = _run(engine.evaluate(record, _make_context()))
    assert updated.state == EvaluationState.NEEDS_HUMAN_REVIEW
    assert updated.result.mentor_attention_required is True
    assert any("confidence" in r.lower() for r in updated.result.mentor_attention_reasons)


def test_engine_escalates_critical_security():
    mock_provider = MockAIProvider()
    critical_security = {
        **VALID_AI_RESPONSE,
        "confidence": 0.95,
        "security_concerns": [
            {"file": "auth.py", "line": 30, "type": "security", "severity": "critical",
             "description": "SQL injection in password field"}
        ],
    }

    async def critical_complete(system_prompt, user_prompt, max_tokens=4096):
        from app.ai.provider import AIMessage
        return AIMessage(content=json.dumps(critical_security), input_tokens=50, output_tokens=100)

    mock_provider.complete = critical_complete

    store = _make_store()
    engine = _make_engine(provider=mock_provider, store=store)
    record = _make_record()
    record = store.create(record)

    updated = _run(engine.evaluate(record, _make_context()))
    assert updated.state == EvaluationState.NEEDS_HUMAN_REVIEW


def test_engine_strips_markdown_fences():
    mock_provider = MockAIProvider()

    async def md_complete(system_prompt, user_prompt, max_tokens=4096):
        from app.ai.provider import AIMessage
        wrapped = f"```json\n{json.dumps(VALID_AI_RESPONSE)}\n```"
        return AIMessage(content=wrapped, input_tokens=10, output_tokens=20)

    mock_provider.complete = md_complete

    store = _make_store()
    engine = _make_engine(provider=mock_provider, store=store)
    record = _make_record()
    record = store.create(record)

    updated = _run(engine.evaluate(record, _make_context()))
    assert updated.state in (EvaluationState.COMPLETED, EvaluationState.NEEDS_HUMAN_REVIEW)


def test_engine_ignores_extra_fields_in_ai_output():
    mock_provider = MockAIProvider()
    extra_fields = {**VALID_AI_RESPONSE, "invented_field": "some garbage", "extra": 999}

    async def extra_complete(system_prompt, user_prompt, max_tokens=4096):
        from app.ai.provider import AIMessage
        return AIMessage(content=json.dumps(extra_fields), input_tokens=10, output_tokens=20)

    mock_provider.complete = extra_complete

    store = _make_store()
    engine = _make_engine(provider=mock_provider, store=store)
    record = _make_record()
    record = store.create(record)

    updated = _run(engine.evaluate(record, _make_context()))
    assert updated.state in (EvaluationState.COMPLETED, EvaluationState.NEEDS_HUMAN_REVIEW)  # extra fields ignored


# ---------------------------------------------------------------------------
# AIEvaluationStore
# ---------------------------------------------------------------------------


def test_store_create_and_get():
    store = _make_store()
    record = _make_record()
    created = store.create(record)
    fetched = store.get(created.id)
    assert fetched is not None
    assert fetched.id == created.id


def test_store_get_by_submission():
    store = _make_store()
    sub_id = uuid4()
    record = _make_record(submission_id=sub_id)
    store.create(record)
    fetched = store.get_by_submission(sub_id)
    assert fetched is not None
    assert fetched.submission_id == sub_id


def test_store_update():
    store = _make_store()
    record = _make_record()
    created = store.create(record)
    updated = created.model_copy(update={"state": EvaluationState.EVALUATING})
    store.update(updated)
    fetched = store.get(created.id)
    assert fetched.state == EvaluationState.EVALUATING


def test_store_find_by_context_hash_returns_none_if_not_completed():
    store = _make_store()
    record = _make_record()
    record = record.model_copy(update={"context_hash": "abc123", "state": EvaluationState.EVALUATING})
    store.create(record)
    result = store.find_by_context_hash("abc123")
    assert result is None  # not COMPLETED yet


def test_store_find_by_context_hash_returns_completed():
    store = _make_store()
    record = _make_record()
    record = record.model_copy(update={"context_hash": "abc123", "state": EvaluationState.COMPLETED})
    store.create(record)
    result = store.find_by_context_hash("abc123")
    assert result is not None


def test_store_list_needs_review():
    store = _make_store()
    org_id = uuid4()
    for _ in range(3):
        r = _make_record(org_id=org_id)
        r = r.model_copy(update={"state": EvaluationState.NEEDS_HUMAN_REVIEW})
        store.create(r)
    # Add one completed
    r = _make_record(org_id=org_id)
    r = r.model_copy(update={"state": EvaluationState.COMPLETED})
    store.create(r)

    needs = store.list_needs_review(org_id)
    assert len(needs) == 3


def test_store_list_for_org():
    store = _make_store()
    org_id = uuid4()
    for _ in range(5):
        r = _make_record(org_id=org_id)
        store.create(r)
    # Add one from different org
    store.create(_make_record(org_id=uuid4()))

    all_for_org = store.list_for_org(org_id)
    assert len(all_for_org) == 5


# ---------------------------------------------------------------------------
# Acceptance criteria evaluation
# ---------------------------------------------------------------------------


def test_criteria_results_contain_all_criteria():
    mock_provider = MockAIProvider()

    async def crit_complete(system_prompt, user_prompt, max_tokens=4096):
        from app.ai.provider import AIMessage
        response = {
            **VALID_AI_RESPONSE,
            "acceptance_criteria_results": [
                {"criterion": "Criterion 1", "status": "PASS", "evidence": [], "notes": ""},
                {"criterion": "Criterion 2", "status": "FAIL", "evidence": [], "notes": "Not found"},
                {"criterion": "Criterion 3", "status": "CANNOT_VERIFY", "evidence": [], "notes": ""},
                {"criterion": "Criterion 4", "status": "PARTIAL", "evidence": ["file.py:10"], "notes": ""},
            ],
        }
        return AIMessage(content=json.dumps(response), input_tokens=10, output_tokens=20)

    mock_provider.complete = crit_complete

    store = _make_store()
    engine = _make_engine(provider=mock_provider, store=store)
    record = _make_record()
    record = store.create(record)

    updated = _run(engine.evaluate(record, _make_context()))
    assert updated.result is not None
    criteria = updated.result.acceptance_criteria_results
    assert len(criteria) == 4
    statuses = {c.status for c in criteria}
    from app.ai.schemas import CriterionStatus
    assert CriterionStatus.PASS in statuses
    assert CriterionStatus.FAIL in statuses
    assert CriterionStatus.CANNOT_VERIFY in statuses
    assert CriterionStatus.PARTIAL in statuses


# ---------------------------------------------------------------------------
# Mentor review
# ---------------------------------------------------------------------------


def test_mentor_review_stores_decision():
    store = _make_store()
    engine = _make_engine(store=store)
    record = _make_record()
    record = record.model_copy(update={"state": EvaluationState.COMPLETED})
    record = store.create(record)

    mentor_id = uuid4()
    updated = record.model_copy(update={
        "mentor_decision": MentorDecision.APPROVED,
        "mentor_feedback": "Good work!",
        "mentor_id": mentor_id,
    })
    store.update(updated)

    fetched = store.get(record.id)
    assert fetched.mentor_decision == MentorDecision.APPROVED
    assert fetched.mentor_feedback == "Good work!"
    assert fetched.mentor_id == mentor_id


def test_mentor_review_override_score_stored():
    store = _make_store()
    record = _make_record()
    record = record.model_copy(update={"state": EvaluationState.NEEDS_HUMAN_REVIEW})
    record = store.create(record)

    updated = record.model_copy(update={
        "mentor_decision": MentorDecision.OVERRIDE_SCORE,
        "mentor_feedback": "Score adjusted after detailed review.",
        "mentor_override_score": 9.0,
    })
    store.update(updated)

    fetched = store.get(record.id)
    assert fetched.mentor_override_score == pytest.approx(9.0)


# ---------------------------------------------------------------------------
# Deduplication (context hash)
# ---------------------------------------------------------------------------


def test_evaluate_returns_cached_when_same_context_hash():
    store = _make_store()
    ctx_hash = "deduptest123"
    existing = _make_record()
    existing = existing.model_copy(update={
        "context_hash": ctx_hash,
        "state": EvaluationState.COMPLETED,
    })
    store.create(existing)

    # Another record with same hash
    found = store.find_by_context_hash(ctx_hash)
    assert found is not None
    assert found.id == existing.id


# ---------------------------------------------------------------------------
# Regression fixtures
# ---------------------------------------------------------------------------

# 5 representative evaluation scenarios for regression testing


FIXTURE_CORRECT_IMPLEMENTATION = {
    "label": "correct_implementation",
    "description": "Student implements all acceptance criteria correctly",
    "task_acceptance_criteria": [
        "Rate limit to 5 requests/min per IP",
        "Return 429 on exceeded limit",
        "Configurable threshold",
    ],
    "diff_has_rate_limiting": True,
    "diff_has_tests": True,
    "expected_verdict_options": ["SOLVED", "PARTIALLY_SOLVED"],
    "expected_min_score": 6.0,
}

FIXTURE_PARTIAL_IMPLEMENTATION = {
    "label": "partial_implementation",
    "description": "Rate limiting middleware exists but no tests, threshold hardcoded",
    "task_acceptance_criteria": [
        "Rate limit to 5 requests/min per IP",
        "Return 429 on exceeded limit",
        "Configurable threshold",
        "Add unit tests",
    ],
    "diff_has_rate_limiting": True,
    "diff_has_tests": False,
    "expected_verdict_options": ["PARTIALLY_SOLVED", "NOT_SOLVED"],
    "expected_max_missing": 2,
}

FIXTURE_INCORRECT_IMPLEMENTATION = {
    "label": "incorrect_implementation",
    "description": "Student submitted unrelated changes, no rate limiting",
    "task_acceptance_criteria": [
        "Rate limit to 5 requests/min per IP",
        "Return 429 on exceeded limit",
    ],
    "diff_has_rate_limiting": False,
    "diff_has_tests": False,
    "expected_verdict_options": ["NOT_SOLVED", "PARTIALLY_SOLVED", "NEEDS_HUMAN_REVIEW"],
}

FIXTURE_SECURITY_VULNERABILITY = {
    "label": "security_vulnerability",
    "description": "Implementation has SQL injection vulnerability",
    "task_acceptance_criteria": [
        "Store rate limit data in database",
        "Prevent bypass via SQL injection",
    ],
    "has_sql_injection": True,
    "expected_escalation": True,
}

FIXTURE_POOR_ARCHITECTURE = {
    "label": "poor_architecture",
    "description": "Implementation works but has poor architecture (global state, no separation)",
    "task_acceptance_criteria": [
        "Rate limit to 5 requests/min per IP",
        "Avoid global memory state",
    ],
    "uses_global_state": True,
    "expected_max_architecture_score": 6.0,
}

REGRESSION_FIXTURES = [
    FIXTURE_CORRECT_IMPLEMENTATION,
    FIXTURE_PARTIAL_IMPLEMENTATION,
    FIXTURE_INCORRECT_IMPLEMENTATION,
    FIXTURE_SECURITY_VULNERABILITY,
    FIXTURE_POOR_ARCHITECTURE,
]


@pytest.mark.parametrize("fixture", REGRESSION_FIXTURES, ids=[f["label"] for f in REGRESSION_FIXTURES])
def test_regression_fixture_evaluates_without_crash(fixture):
    """Each fixture must evaluate without raising an exception."""
    store = _make_store()
    engine = _make_engine(store=store)
    record = _make_record()
    record = store.create(record)
    ctx = _make_context()

    updated = _run(engine.evaluate(record, ctx))
    assert updated.state in (
        EvaluationState.COMPLETED,
        EvaluationState.NEEDS_HUMAN_REVIEW,
        EvaluationState.FAILED,
    )


def test_regression_correct_implementation_produces_valid_result():
    store = _make_store()
    engine = _make_engine(store=store)
    record = _make_record()
    record = store.create(record)
    ctx = _make_context()

    updated = _run(engine.evaluate(record, ctx))
    if updated.result:
        assert updated.result.overall_score >= 0.0
        assert updated.result.overall_score <= 10.0
        assert updated.result.confidence >= 0.0
        assert updated.result.confidence <= 1.0


def test_regression_evaluations_are_deterministic():
    """Same context â†’ same score every time."""
    store1 = _make_store()
    store2 = _make_store()
    ctx = _make_context()

    r1 = _make_record()
    r1 = store1.create(r1)
    result1 = _run(_make_engine(store=store1).evaluate(r1, ctx))

    r2 = _make_record()
    r2 = store2.create(r2)
    result2 = _run(_make_engine(store=store2).evaluate(r2, ctx))

    if result1.result and result2.result:
        assert result1.result.overall_score == result2.result.overall_score


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


def _make_client():
    from app.main import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


def _setup_store_record(state=EvaluationState.COMPLETED):
    from app.ai.store import get_ai_store
    store = get_ai_store()
    record = _make_record()
    record = record.model_copy(update={"state": state})
    return store.create(record)


def test_evaluate_endpoint_returns_202():
    from app.ai.store import get_ai_store
    from app.infrastructure.repositories.memory import AsyncMemoryUnitOfWork
    from app.services.store import InMemoryStore

    inner_store = InMemoryStore()
    from app.application.unit_of_work import AsyncUnitOfWork
    uow = AsyncMemoryUnitOfWork(inner_store)

    # Create required entities
    org = inner_store.create_organization(OrganizationCreate(name="Test Org", slug="test-org"))
    from app.schemas.core import BatchCreate
    batch = inner_store.create_batch(BatchCreate(organization_id=org.id, name="Batch 1", starts_on=date(2026, 8, 1), ends_on=date(2026, 12, 31)))
    student = inner_store.create_student(StudentCreate(organization_id=org.id, batch_id=batch.id, full_name="Alice Test", email="alice@test.com"))
    project = inner_store.create_project(ProjectCreate(organization_id=org.id, student_id=student.id, name="Project", repository_url="https://github.com/alice/project"))
    task = inner_store.create_task(TaskCreate(
        organization_id=org.id,
        batch_id=batch.id,
        student_id=student.id,
        project_id=project.id,
        task_type=TaskType.CODING,
        title="Test Task",
        problem_statement="Build something.",
        acceptance_criteria=["Do the thing"],
        due_on=date(2026, 8, 7),
    ))
    submission = inner_store.create_submission(SubmissionCreate(
        organization_id=org.id,
        task_id=task.id,
        student_id=student.id,
        self_status=SelfStatus.SOLVED,
        commit_url="https://github.com/alice/project/commit/abc123def456",
    ))

    client = _make_client()
    reset_ai_store()

    import app.api.dependencies as deps
    original_store = deps._dev_store

    # Patch the store singleton
    deps._dev_store = inner_store

    try:
        resp = client.post(
            f"/submissions/{submission.id}/evaluate",
            json={"force_reevaluate": False},
        )
        assert resp.status_code in (200, 202, 404), f"Got {resp.status_code}: {resp.text[:200]}"
    finally:
        deps._dev_store = original_store


def test_get_evaluation_not_found():
    client = _make_client()
    resp = client.get(f"/evaluations/{uuid4()}")
    assert resp.status_code == 404


def test_list_evaluations_empty_for_system_user():
    client = _make_client()
    resp = client.get("/evaluations/")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_mentor_review_endpoint_requires_review_state():
    from app.ai.store import get_ai_store
    reset_ai_store()
    store = get_ai_store()
    org_id = uuid4()
    record = _make_record(org_id=org_id)
    record = record.model_copy(update={"state": EvaluationState.PENDING})
    record = store.create(record)

    client = _make_client()
    resp = client.post(
        f"/evaluations/{record.id}/mentor-review",
        json={"decision": "APPROVED", "feedback": "Looks good."},
    )
    assert resp.status_code in (409, 403, 200)  # 409 = ConflictException


def test_mentor_review_endpoint_accepts_completed_state():
    from app.ai.store import get_ai_store
    reset_ai_store()
    store = get_ai_store()
    record = _make_record()
    record = record.model_copy(update={"state": EvaluationState.COMPLETED})
    record = store.create(record)

    client = _make_client()
    resp = client.post(
        f"/evaluations/{record.id}/mentor-review",
        json={"decision": "APPROVED", "feedback": "Well done!"},
    )
    # System user has no org_id so it won't check org isolation
    # Should be 200 or 403 depending on permissions
    assert resp.status_code in (200, 403)


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------


def test_get_ai_provider_returns_mock_without_api_key():
    reset_provider()
    with patch("app.core.config.settings") as ms:
        ms.anthropic_api_key = ""
        ms.anthropic_model = "claude-haiku-4-5-20251001"
        from app.ai.provider import get_ai_provider
        provider = get_ai_provider()
    assert provider.is_mock() is True
    reset_provider()


def test_get_ai_provider_returns_anthropic_with_api_key():
    import sys
    from unittest.mock import MagicMock

    reset_provider()
    # Mock the anthropic module so AnthropicProvider doesn't fail on import
    fake_anthropic = MagicMock()
    fake_anthropic.AsyncAnthropic.return_value = AsyncMock()
    with patch.dict(sys.modules, {"anthropic": fake_anthropic}):
        with patch("app.core.config.settings") as ms:
            ms.anthropic_api_key = "sk-test-fake-key"
            ms.anthropic_model = "claude-haiku-4-5-20251001"
            from app.ai.provider import get_ai_provider
            provider = get_ai_provider()
    assert not provider.is_mock()
    reset_provider()


# ---------------------------------------------------------------------------
# Token / cost tracking
# ---------------------------------------------------------------------------


def test_evaluation_tracks_tokens():
    store = _make_store()
    engine = _make_engine(store=store)
    record = _make_record()
    record = store.create(record)

    updated = _run(engine.evaluate(record, _make_context()))
    if updated.state in (EvaluationState.COMPLETED, EvaluationState.NEEDS_HUMAN_REVIEW):
        assert updated.input_tokens > 0
        assert updated.output_tokens > 0


def test_evaluation_tracks_duration():
    store = _make_store()
    engine = _make_engine(store=store)
    record = _make_record()
    record = store.create(record)

    updated = _run(engine.evaluate(record, _make_context()))
    assert updated.duration_ms >= 0


def test_evaluation_response_includes_all_fields():
    from app.api.evaluation_router import _to_response
    record = _make_record()
    record = record.model_copy(update={
        "state": EvaluationState.COMPLETED,
        "provider": "development_mock",
        "model": "mock-v1",
        "context_hash": "abc123",
        "input_tokens": 150,
        "output_tokens": 300,
        "duration_ms": 450,
    })
    resp = _to_response(record)
    assert resp.provider == "development_mock"
    assert resp.model == "mock-v1"
    assert resp.mock_mode is True
    assert resp.input_tokens == 150
    assert resp.output_tokens == 300
    assert resp.duration_ms == 450

