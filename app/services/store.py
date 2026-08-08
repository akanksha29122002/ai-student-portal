from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.schemas.auth import RefreshTokenCreate, RefreshTokenRecord, User, UserCreate
from app.schemas.base import EventEnvelope
from app.schemas.core import (
    Batch,
    BatchCreate,
    Evaluation,
    EvaluationCreate,
    MentorReview,
    MentorReviewCreate,
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
from app.domain.enums import SubmissionStatus


class InMemoryStore:
    def __init__(self) -> None:
        self.organizations: dict[UUID, Organization] = {}
        self.batches: dict[UUID, Batch] = {}
        self.students: dict[UUID, Student] = {}
        self.projects: dict[UUID, Project] = {}
        self.tasks: dict[UUID, Task] = {}
        self.submissions: dict[UUID, Submission] = {}
        self.evaluations: dict[UUID, Evaluation] = {}
        self.mentor_reviews: dict[UUID, MentorReview] = {}
        self.events: list[EventEnvelope] = []
        self.users: dict[UUID, User] = {}
        self._users_by_email: dict[str, UUID] = {}
        self.refresh_tokens: dict[UUID, RefreshTokenRecord] = {}
        self._refresh_tokens_by_hash: dict[str, UUID] = {}

    def create_organization(self, payload: OrganizationCreate) -> Organization:
        entity = Organization(**payload.model_dump())
        self.organizations[entity.id] = entity
        return entity

    def create_batch(self, payload: BatchCreate) -> Batch:
        entity = Batch(**payload.model_dump())
        self.batches[entity.id] = entity
        return entity

    def create_student(self, payload: StudentCreate) -> Student:
        entity = Student(**payload.model_dump())
        self.students[entity.id] = entity
        return entity

    def get_student(self, student_id: UUID) -> Student | None:
        return self.students.get(student_id)

    def create_project(self, payload: ProjectCreate) -> Project:
        data = payload.model_dump()
        data["repository_url"] = str(data["repository_url"])
        entity = Project(**data)
        self.projects[entity.id] = entity
        return entity

    def get_project(self, project_id: UUID) -> Project | None:
        return self.projects.get(project_id)

    def create_task(self, payload: TaskCreate) -> Task:
        entity = Task(**payload.model_dump())
        self.tasks[entity.id] = entity
        return entity

    def get_task(self, task_id: UUID) -> Task | None:
        return self.tasks.get(task_id)

    def list_student_tasks(self, student_id: UUID) -> list[Task]:
        return [t for t in self.tasks.values() if t.student_id == student_id]

    def create_submission(self, payload: SubmissionCreate) -> Submission:
        data = payload.model_dump()
        for field in ("repository_url", "commit_url", "transcript_url"):
            if data.get(field) is not None:
                data[field] = str(data[field])
        entity = Submission(**data)
        self.submissions[entity.id] = entity
        return entity

    def get_submission(self, submission_id: UUID) -> Submission | None:
        return self.submissions.get(submission_id)

    def update_submission_status(self, submission_id: UUID, new_status: SubmissionStatus) -> None:
        submission = self.submissions[submission_id]
        self.submissions[submission_id] = submission.model_copy(
            update={"status": new_status, "updated_at": datetime.now(UTC)}
        )

    def create_evaluation(self, payload: EvaluationCreate) -> Evaluation:
        entity = Evaluation(**payload.model_dump())
        self.evaluations[entity.id] = entity
        return entity

    def get_evaluation(self, evaluation_id: UUID) -> Evaluation | None:
        return self.evaluations.get(evaluation_id)

    def create_mentor_review(self, payload: MentorReviewCreate) -> MentorReview:
        entity = MentorReview(**payload.model_dump())
        self.mentor_reviews[entity.id] = entity
        return entity

    def list_students_for_org(self, org_id: UUID) -> list[Student]:
        return [s for s in self.students.values() if s.organization_id == org_id]

    def get_student_by_email(self, email: str) -> Student | None:
        email_lower = email.lower()
        return next((s for s in self.students.values() if s.email.lower() == email_lower), None)

    def list_submissions_for_student(self, student_id: UUID) -> list[Submission]:
        return [s for s in self.submissions.values() if s.student_id == student_id]

    def list_batches_for_org(self, org_id: UUID) -> list:
        from app.schemas.core import Batch
        return [b for b in self.batches.values() if b.organization_id == org_id]

    def list_batch_submissions(self, batch_id: UUID) -> list[Submission]:
        task_ids = {task.id for task in self.tasks.values() if task.batch_id == batch_id}
        return [submission for submission in self.submissions.values() if submission.task_id in task_ids]

    def list_submission_evaluations(self, submission_id: UUID) -> list[Evaluation]:
        return [evaluation for evaluation in self.evaluations.values() if evaluation.submission_id == submission_id]

    def create_refresh_token(self, payload: RefreshTokenCreate) -> RefreshTokenRecord:
        record = RefreshTokenRecord(**payload.model_dump())
        self.refresh_tokens[record.id] = record
        self._refresh_tokens_by_hash[record.token_hash] = record.id
        return record

    def get_refresh_token_by_hash(self, token_hash: str) -> RefreshTokenRecord | None:
        token_id = self._refresh_tokens_by_hash.get(token_hash)
        return self.refresh_tokens.get(token_id) if token_id else None

    def mark_refresh_token_used(self, token_id: UUID) -> None:
        record = self.refresh_tokens.get(token_id)
        if record:
            self.refresh_tokens[token_id] = record.model_copy(update={"used_at": datetime.now(UTC)})

    def revoke_refresh_token(self, token_id: UUID) -> None:
        record = self.refresh_tokens.get(token_id)
        if record:
            self.refresh_tokens[token_id] = record.model_copy(update={"revoked_at": datetime.now(UTC)})

    def revoke_all_refresh_tokens_for_user(self, user_id: UUID) -> None:
        now = datetime.now(UTC)
        for tid, record in self.refresh_tokens.items():
            if record.user_id == user_id and record.revoked_at is None:
                self.refresh_tokens[tid] = record.model_copy(update={"revoked_at": now})

    def update_user_password(self, user_id: UUID, new_hashed_password: str) -> None:
        user = self.users.get(user_id)
        if user:
            self.users[user_id] = user.model_copy(update={"hashed_password": new_hashed_password})

    def create_user(self, payload: UserCreate) -> User:
        entity = User(**payload.model_dump())
        self.users[entity.id] = entity
        self._users_by_email[entity.email.lower()] = entity.id
        return entity

    def get_user_by_id(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)

    def get_user_by_email(self, email: str) -> User | None:
        user_id = self._users_by_email.get(email.lower())
        return self.users.get(user_id) if user_id else None

    def record_event(self, event_type: str, organization_id: UUID, actor_type: str, actor_id: UUID, payload: dict) -> EventEnvelope:
        event = EventEnvelope(
            id=uuid4(),
            event_type=event_type,
            organization_id=organization_id,
            actor_type=actor_type,
            actor_id=actor_id,
            payload=payload,
        )
        self.events.append(event)
        return event


store = InMemoryStore()

