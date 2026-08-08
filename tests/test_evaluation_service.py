from datetime import date

from app.domain.enums import EvaluationVerdict, SelfStatus, TaskType
from app.schemas.core import (
    BatchCreate,
    OrganizationCreate,
    ProjectCreate,
    StudentCreate,
    SubmissionCreate,
    TaskCreate,
)
from app.services.evaluation_service import EvaluationService
from app.services.store import InMemoryStore


def test_evaluate_commit_submission_creates_auditable_needs_review_record():
    store = InMemoryStore()
    service = EvaluationService(store)
    org = store.create_organization(OrganizationCreate(name="Acme University", slug="acme-university"))
    batch = store.create_batch(BatchCreate(organization_id=org.id, name="Track A Batch", starts_on=date(2026, 8, 7), ends_on=date(2026, 8, 14)))
    student = store.create_student(StudentCreate(organization_id=org.id, batch_id=batch.id, full_name="Asha Kumar", email="asha@example.com"))
    project = store.create_project(ProjectCreate(organization_id=org.id, student_id=student.id, name="Student Portal", repository_url="https://github.com/example/student-portal"))
    task = store.create_task(
        TaskCreate(
            organization_id=org.id,
            batch_id=batch.id,
            student_id=student.id,
            project_id=project.id,
            task_type=TaskType.CODING,
            title="Add rate limiting",
            problem_statement="Add rate limiting to the login endpoint to reduce brute force risk.",
            acceptance_criteria=["Login attempts are throttled by identity and IP."],
            due_on=date(2026, 8, 7),
        )
    )
    submission = store.create_submission(
        SubmissionCreate(
            organization_id=org.id,
            task_id=task.id,
            student_id=student.id,
            self_status=SelfStatus.SOLVED,
            commit_url="https://github.com/example/student-portal/commit/abc123",
            approach_note="Added middleware for login throttling.",
        )
    )

    evaluation = service.evaluate_submission(submission)

    assert evaluation.verdict == EvaluationVerdict.NEEDS_HUMAN_REVIEW
    assert evaluation.confidence == 0.45
    assert evaluation.evidence[0].type == "commit_url"


def test_daily_summary_counts_needs_review_submission():
    store = InMemoryStore()
    service = EvaluationService(store)
    org = store.create_organization(OrganizationCreate(name="Acme University", slug="acme-university"))
    batch = store.create_batch(BatchCreate(organization_id=org.id, name="Track A Batch", starts_on=date(2026, 8, 7), ends_on=date(2026, 8, 14)))
    student = store.create_student(StudentCreate(organization_id=org.id, batch_id=batch.id, full_name="Asha Kumar", email="asha@example.com"))
    project = store.create_project(ProjectCreate(organization_id=org.id, student_id=student.id, name="Student Portal", repository_url="https://github.com/example/student-portal"))
    task = store.create_task(
        TaskCreate(
            organization_id=org.id,
            batch_id=batch.id,
            student_id=student.id,
            project_id=project.id,
            task_type=TaskType.SPOKEN_QUESTION,
            title="Explain authentication",
            problem_statement="Explain how authentication works in your project.",
            acceptance_criteria=["Mentions identity, session/token, authorization, and failure handling."],
            due_on=date(2026, 8, 7),
        )
    )
    submission = store.create_submission(
        SubmissionCreate(
            organization_id=org.id,
            task_id=task.id,
            student_id=student.id,
            self_status=SelfStatus.ATTEMPTED,
            transcript_text="My project uses JWT tokens after login and protects dashboard routes.",
        )
    )
    service.evaluate_submission(submission)

    summary = service.build_daily_summary(batch.id)

    assert summary["totals"]["students_expected"] == 1
    assert summary["totals"]["submitted"] == 1
    assert summary["totals"]["needs_human_review"] == 1
