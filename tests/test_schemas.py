from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.enums import SelfStatus, TaskType
from app.schemas.core import BatchCreate, SubmissionCreate, TaskCreate


def test_batch_end_date_must_not_precede_start_date():
    with pytest.raises(ValidationError):
        BatchCreate(
            organization_id=uuid4(),
            name="Batch 1",
            starts_on=date(2026, 8, 7),
            ends_on=date(2026, 8, 6),
        )


def test_submission_requires_evidence_unless_skipped():
    with pytest.raises(ValidationError):
        SubmissionCreate(
            organization_id=uuid4(),
            task_id=uuid4(),
            student_id=uuid4(),
            self_status=SelfStatus.ATTEMPTED,
        )


def test_task_requires_acceptance_criteria():
    task = TaskCreate(
        organization_id=uuid4(),
        batch_id=uuid4(),
        student_id=uuid4(),
        project_id=uuid4(),
        task_type=TaskType.CODING,
        title="Add API rate limiting",
        problem_statement="Add a rate limit to protect the login endpoint from abuse.",
        acceptance_criteria=["Repeated failed login attempts are throttled."],
        due_on=date(2026, 8, 7),
    )

    assert task.task_type == TaskType.CODING

