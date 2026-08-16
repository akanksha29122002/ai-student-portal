"""Milestone 7 tests — Learning Plans, Profile Analysis, Verification, Import."""
from __future__ import annotations

import asyncio
import csv
import io
import json
from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.enums import (
    LearningPlanStatus,
    PlanDayStatus,
    ProfileAnalysisStatus,
    SkillConfidence,
    VerificationStatus,
)
from app.schemas.m7 import (
    AIInteractionLogCreate,
    DailyAutomationRunCreate,
    LearningPlanCreate,
    LearningPlanDayCreate,
    SkillAssessmentCreate,
    StudentProfileAnalysisCreate,
    StudentProgressCreate,
    SubmissionEvidenceCreate,
    TaskDependencyCreate,
    VerificationEvidenceCreate,
    VerificationResultCreate,
)
from app.services.import_service import (
    _map_headers,
    _map_row,
    _parse_csv,
    _parse_json,
    _random_password,
)
from app.services.plan_service import LearningPlanService, _reorder_days_by_weakness
from app.services.store import InMemoryStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_org(store: InMemoryStore):
    from app.schemas.core import OrganizationCreate
    return store.create_organization(OrganizationCreate(name="Test Org", slug="test-org"))


def make_batch(store: InMemoryStore, org_id):
    from app.schemas.core import BatchCreate
    return store.create_batch(BatchCreate(
        organization_id=org_id,
        name="Batch 2026",
        starts_on=date(2026, 1, 1),
        ends_on=date(2026, 12, 31),
    ))


def make_student(store: InMemoryStore, org_id, batch_id):
    from app.schemas.core import StudentCreate
    return store.create_student(StudentCreate(
        organization_id=org_id,
        batch_id=batch_id,
        full_name="Test Student",
        email=f"test_{uuid4().hex[:8]}@example.com",
    ))


# ---------------------------------------------------------------------------
# Phase 1 — Enums and Schemas
# ---------------------------------------------------------------------------


class TestM7Enums:
    def test_plan_day_status_values(self):
        assert PlanDayStatus.LOCKED == "locked"
        assert PlanDayStatus.AVAILABLE == "available"
        assert PlanDayStatus.COMPLETED == "completed"

    def test_learning_plan_status_values(self):
        assert LearningPlanStatus.ACTIVE == "active"
        assert LearningPlanStatus.DRAFT == "draft"

    def test_skill_confidence_values(self):
        assert SkillConfidence.OBSERVED == "observed"
        assert SkillConfidence.INFERRED == "inferred"
        assert SkillConfidence.UNKNOWN == "unknown"

    def test_verification_status_values(self):
        assert VerificationStatus.PASSED == "passed"
        assert VerificationStatus.NEEDS_HUMAN_REVIEW == "needs_human_review"


class TestM7Schemas:
    def test_learning_plan_create(self):
        payload = LearningPlanCreate(
            student_id=uuid4(),
            organization_id=uuid4(),
            batch_id=uuid4(),
            start_date=date.today(),
            end_date=date.today() + timedelta(days=13),
        )
        assert payload.total_days == 14
        assert payload.status == LearningPlanStatus.DRAFT

    def test_skill_assessment_score_bounds(self):
        with pytest.raises(Exception):
            SkillAssessmentCreate(
                student_id=uuid4(),
                organization_id=uuid4(),
                dimension="testing",
                score=150,  # out of bounds
                confidence=SkillConfidence.OBSERVED,
                assessed_at=datetime.utcnow(),
            )

    def test_verification_result_create(self):
        vr = VerificationResultCreate(
            submission_id=uuid4(),
            organization_id=uuid4(),
        )
        assert vr.status == VerificationStatus.PENDING
        assert vr.escalate_to_mentor is False


# ---------------------------------------------------------------------------
# Phase 1 — InMemoryStore M7 collections
# ---------------------------------------------------------------------------


class TestM7Store:
    def setup_method(self):
        self.store = InMemoryStore()
        org = make_org(self.store)
        batch = make_batch(self.store, org.id)
        self.student = make_student(self.store, org.id, batch.id)
        self.org_id = org.id
        self.batch_id = batch.id

    def test_skill_assessments(self):
        payload = SkillAssessmentCreate(
            student_id=self.student.id,
            organization_id=self.org_id,
            dimension="problem_solving",
            score=75,
            confidence=SkillConfidence.OBSERVED,
            assessed_at=datetime.utcnow(),
        )
        created = self.store.upsert_skill_assessment(payload)
        assert created.score == 75
        assert created.dimension == "problem_solving"

        # Upsert updates existing
        payload2 = payload.model_copy(update={"score": 80})
        updated = self.store.upsert_skill_assessment(payload2)
        assert updated.score == 80
        assert len(self.store.list_skill_assessments(self.student.id)) == 1

    def test_learning_plan_crud(self):
        plan = self.store.create_learning_plan(LearningPlanCreate(
            student_id=self.student.id,
            organization_id=self.org_id,
            batch_id=self.batch_id,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=13),
            status=LearningPlanStatus.ACTIVE,
        ))
        assert plan.status == LearningPlanStatus.ACTIVE

        active = self.store.get_active_plan(self.student.id)
        assert active is not None
        assert active.id == plan.id

        self.store.update_learning_plan(plan.id, status=LearningPlanStatus.COMPLETED)
        updated = self.store.get_learning_plan(plan.id)
        assert updated.status == LearningPlanStatus.COMPLETED
        assert self.store.get_active_plan(self.student.id) is None

    def test_learning_plan_days_ordered(self):
        plan = self.store.create_learning_plan(LearningPlanCreate(
            student_id=self.student.id,
            organization_id=self.org_id,
            batch_id=self.batch_id,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=13),
            status=LearningPlanStatus.ACTIVE,
        ))
        for day_num in [3, 1, 2]:
            self.store.create_learning_plan_day(LearningPlanDayCreate(
                plan_id=plan.id,
                student_id=self.student.id,
                organization_id=self.org_id,
                day_number=day_num,
                scheduled_date=date.today() + timedelta(days=day_num - 1),
                status=PlanDayStatus.LOCKED,
            ))
        days = self.store.list_plan_days(plan.id)
        assert [d.day_number for d in days] == [1, 2, 3]

    def test_student_progress_upsert(self):
        today = date.today()
        payload = StudentProgressCreate(
            student_id=self.student.id,
            organization_id=self.org_id,
            snapshot_date=today,
            days_completed=3,
            days_remaining=11,
            current_streak=3,
            longest_streak=3,
        )
        p1 = self.store.upsert_student_progress(payload)
        assert p1.days_completed == 3

        p2 = self.store.upsert_student_progress(payload.model_copy(update={"days_completed": 5}))
        assert p2.days_completed == 5
        assert len(self.store.get_student_progress(self.student.id)) == 1

    def test_ai_interaction_log(self):
        from app.domain.enums import AIInteractionType
        self.store.log_ai_interaction(AIInteractionLogCreate(
            organization_id=self.org_id,
            student_id=self.student.id,
            interaction_type=AIInteractionType.PROFILE_ANALYSIS,
            ai_model="mock-v1",
            prompt_tokens=100,
            completion_tokens=200,
            success=True,
        ))
        logs = self.store.list_ai_interactions(student_id=self.student.id)
        assert len(logs) == 1
        assert logs[0].interaction_type == AIInteractionType.PROFILE_ANALYSIS


# ---------------------------------------------------------------------------
# Phase 2 — Import Service
# ---------------------------------------------------------------------------


class TestStudentImport:
    def test_csv_parse_standard_headers(self):
        content = b"full_name,email,track\nAlice,alice@test.com,track_a\nBob,bob@test.com,b"
        rows = _parse_csv(content)
        header_map = _map_headers(list(rows[0].keys()))
        mapped = [_map_row(r, header_map) for r in rows]
        assert mapped[0]["full_name"] == "Alice"
        assert mapped[0]["email"] == "alice@test.com"
        assert mapped[0]["track"] == "track_a"

    def test_csv_parse_alias_headers(self):
        content = b"student_name,emailaddress\nCharlie,charlie@test.com"
        rows = _parse_csv(content)
        header_map = _map_headers(list(rows[0].keys()))
        assert "student_name" in header_map
        assert header_map["student_name"] == "full_name"
        assert "emailaddress" in header_map
        assert header_map["emailaddress"] == "email"

    def test_json_parse_list(self):
        data = [{"name": "Diana", "email": "diana@test.com"}]
        rows = _parse_json(json.dumps(data).encode())
        header_map = _map_headers(list(rows[0].keys()))
        mapped = [_map_row(r, header_map) for r in rows]
        assert mapped[0]["full_name"] == "Diana"
        assert mapped[0]["email"] == "diana@test.com"

    def test_json_parse_wrapped(self):
        data = {"students": [{"full_name": "Eve", "email": "eve@test.com"}]}
        rows = _parse_json(json.dumps(data).encode())
        assert rows[0]["full_name"] == "Eve"

    def test_csv_utf8_bom(self):
        # Excel often adds BOM to CSV
        content = "﻿email,full_name\nalice@test.com,Alice".encode("utf-8-sig")
        rows = _parse_csv(content)
        header_map = _map_headers(list(rows[0].keys()))
        assert "email" in header_map

    def test_random_password_length(self):
        pw = _random_password()
        assert len(pw) == 16
        pw2 = _random_password(24)
        assert len(pw2) == 24
        assert pw != pw2  # astronomically unlikely to collide

    def test_missing_required_fields_skipped(self):
        content = b"email\nalice@test.com"  # no full_name column
        rows = _parse_csv(content)
        header_map = _map_headers(list(rows[0].keys()))
        mapped = [_map_row(r, header_map) for r in rows]
        assert "full_name" not in mapped[0]


# ---------------------------------------------------------------------------
# Phase 5 — Learning Plan Generator
# ---------------------------------------------------------------------------


class TestLearningPlanService:
    def setup_method(self):
        self.store = InMemoryStore()
        org = make_org(self.store)
        batch = make_batch(self.store, org.id)
        self.student = make_student(self.store, org.id, batch.id)
        self.org_id = org.id
        self.batch_id = batch.id
        self.svc = LearningPlanService(self.store)

    def test_generates_14_days(self):
        result = asyncio.run(self.svc.generate_plan(
            student_id=self.student.id,
            student=self.student,
        ))
        assert len(result["days"]) == 14

    def test_day_1_is_available(self):
        result = asyncio.run(self.svc.generate_plan(
            student_id=self.student.id,
            student=self.student,
        ))
        assert result["days"][0].status == PlanDayStatus.AVAILABLE
        assert result["days"][0].day_number == 1

    def test_remaining_days_locked(self):
        result = asyncio.run(self.svc.generate_plan(
            student_id=self.student.id,
            student=self.student,
        ))
        for day in result["days"][1:]:
            assert day.status == PlanDayStatus.LOCKED

    def test_plan_start_is_today(self):
        result = asyncio.run(self.svc.generate_plan(
            student_id=self.student.id,
            student=self.student,
        ))
        assert result["plan"].start_date == date.today()

    def test_plan_end_is_13_days_ahead(self):
        result = asyncio.run(self.svc.generate_plan(
            student_id=self.student.id,
            student=self.student,
        ))
        assert result["plan"].end_date == date.today() + timedelta(days=13)

    def test_plan_stored_in_store(self):
        asyncio.run(self.svc.generate_plan(
            student_id=self.student.id,
            student=self.student,
        ))
        active = self.store.get_active_plan(self.student.id)
        assert active is not None

    def test_reorder_days_by_weakness(self):
        skills = {"problem_solving": 30, "testing": 20, "code_quality": 80, "algorithms": 60}
        reordered = _reorder_days_by_weakness(skills)
        assert len(reordered) == 14
        # Each entry has 2 dimensions
        assert all(len(day) == 2 for day in reordered)

    def test_reorder_empty_skills(self):
        from app.services.plan_service import _DAY_FOCUS
        reordered = _reorder_days_by_weakness({})
        assert reordered == _DAY_FOCUS

    def test_target_skills_populated(self):
        result = asyncio.run(self.svc.generate_plan(
            student_id=self.student.id,
            student=self.student,
        ))
        for day in result["days"]:
            assert len(day.target_skills) > 0


# ---------------------------------------------------------------------------
# Phase 8 — Verification Service
# ---------------------------------------------------------------------------


class TestVerificationService:
    def setup_method(self):
        self.store = InMemoryStore()
        org = make_org(self.store)
        batch = make_batch(self.store, org.id)
        student = make_student(self.store, org.id, batch.id)
        self.org_id = org.id
        from app.schemas.core import TaskCreate, TaskType, ProjectCreate, SubmissionCreate, SelfStatus
        proj = self.store.create_project(ProjectCreate(
            organization_id=org.id,
            student_id=student.id,
            name="Test Project",
            repository_url="https://github.com/test/proj",
        ))
        task = self.store.create_task(TaskCreate(
            organization_id=org.id,
            batch_id=batch.id,
            student_id=student.id,
            project_id=proj.id,
            task_type=TaskType.CODING,
            title="Test task",
            problem_statement="Build something",
            acceptance_criteria=["It works"],
            due_on=date.today(),
        ))
        self.submission = self.store.create_submission(SubmissionCreate(
            organization_id=org.id,
            task_id=task.id,
            student_id=student.id,
            self_status="solved",
            commit_url="https://github.com/test/proj/commit/abc123",
            approach_note="I implemented it using a simple approach.",
        ))

    def test_verify_creates_result(self):
        from app.services.verification_service import VerificationService
        svc = VerificationService(self.store)
        result = asyncio.run(svc.verify(
            submission_id=self.submission.id,
            submission=self.submission,
        ))
        assert "result" in result
        assert result["result"].status in (VerificationStatus.PASSED, VerificationStatus.FAILED)

    def test_verify_stores_in_store(self):
        from app.services.verification_service import VerificationService
        svc = VerificationService(self.store)
        asyncio.run(svc.verify(
            submission_id=self.submission.id,
            submission=self.submission,
        ))
        stored = self.store.get_latest_verification(self.submission.id)
        assert stored is not None
        assert stored.submission_id == self.submission.id

    def test_verify_collects_commit_evidence(self):
        from app.services.verification_service import VerificationService
        svc = VerificationService(self.store)
        asyncio.run(svc.verify(
            submission_id=self.submission.id,
            submission=self.submission,
        ))
        result = self.store.get_latest_verification(self.submission.id)
        evidences = self.store.list_verification_evidences(result.id)
        # commit_url is present → at least 1 evidence from submission fields
        sources = [e.source for e in evidences]
        assert any("submission" in s or "github" in s for s in sources)

    def test_escalation_logic(self):
        from app.services.verification_service import VerificationService, _quality_from_score
        from app.domain.enums import EvidenceQuality
        assert _quality_from_score(80) == EvidenceQuality.STRONG
        assert _quality_from_score(55) == EvidenceQuality.MODERATE
        assert _quality_from_score(20) == EvidenceQuality.WEAK
        assert _quality_from_score(None) == EvidenceQuality.MISSING


# ---------------------------------------------------------------------------
# Phase 9 — Daily Automation
# ---------------------------------------------------------------------------


class TestDailyAutomation:
    def setup_method(self):
        self.store = InMemoryStore()
        org = make_org(self.store)
        self.org_id = org.id
        batch = make_batch(self.store, org.id)
        self.batch_id = batch.id

    def test_run_for_empty_batch(self):
        from app.services.automation_service import DailyAutomationService
        svc = DailyAutomationService(self.store)
        result = asyncio.run(svc.run_for_batch(
            organization_id=self.org_id,
            batch_id=self.batch_id,
        ))
        assert result["students_processed"] == 0
        assert result["run_id"] is not None

    def test_automation_creates_run_record(self):
        from app.services.automation_service import DailyAutomationService
        svc = DailyAutomationService(self.store)
        result = asyncio.run(svc.run_for_batch(
            organization_id=self.org_id,
            batch_id=self.batch_id,
        ))
        run_id = result["run_id"]
        from uuid import UUID
        run = self.store.get_daily_automation_run(UUID(run_id))
        assert run is not None
        assert run.run_date == date.today()

    def test_streak_calculation(self):
        from app.services.automation_service import _compute_streak
        today = date.today()

        class FakeDay:
            def __init__(self, d, s):
                self.scheduled_date = d
                self.status = s

        days = [FakeDay(today - timedelta(days=i), "completed") for i in range(5)]
        assert _compute_streak(days, today) == 5

        # Gap breaks streak
        days_with_gap = [FakeDay(today, "completed"), FakeDay(today - timedelta(days=2), "completed")]
        assert _compute_streak(days_with_gap, today) == 1


# ---------------------------------------------------------------------------
# Phase 14 — Demo Seed
# ---------------------------------------------------------------------------


class TestDemoSeed:
    def test_seed_creates_10_students(self):
        store = InMemoryStore()
        import app.api.dependencies as deps
        original = deps._dev_store
        deps._dev_store = store
        try:
            asyncio.run(__import__("app.scripts.seed_demo", fromlist=["seed_demo"]).seed_demo())
            assert len(store.students) == 10
        finally:
            deps._dev_store = original

    def test_seed_creates_learning_plans(self):
        store = InMemoryStore()
        import app.api.dependencies as deps
        original = deps._dev_store
        deps._dev_store = store
        try:
            asyncio.run(__import__("app.scripts.seed_demo", fromlist=["seed_demo"]).seed_demo())
            assert len(store.learning_plans) == 10
            assert len(store.learning_plan_days) == 140  # 14 × 10
        finally:
            deps._dev_store = original

    def test_seed_creates_skill_assessments(self):
        store = InMemoryStore()
        import app.api.dependencies as deps
        original = deps._dev_store
        deps._dev_store = store
        try:
            asyncio.run(__import__("app.scripts.seed_demo", fromlist=["seed_demo"]).seed_demo())
            assert len(store.skill_assessments) == 100  # 10 dims × 10 students
        finally:
            deps._dev_store = original

    def test_seed_idempotent(self):
        store = InMemoryStore()
        import app.api.dependencies as deps
        original = deps._dev_store
        deps._dev_store = store
        try:
            seed = __import__("app.scripts.seed_demo", fromlist=["seed_demo"]).seed_demo
            asyncio.run(seed())
            asyncio.run(seed())  # second call must be a no-op
            assert len(store.students) == 10  # not 20
        finally:
            deps._dev_store = original
