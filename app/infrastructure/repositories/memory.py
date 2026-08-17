from copy import deepcopy
from uuid import UUID

from app.domain.events import DomainEvent
from app.domain.enums import SubmissionStatus
from app.schemas.auth import RefreshTokenCreate, RefreshTokenRecord, User, UserCreate
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
from app.services.store import InMemoryStore


class MemoryOrganizationRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def create(self, payload: OrganizationCreate) -> Organization:
        return self.store.create_organization(payload)

    def get_by_slug(self, slug: str) -> Organization | None:
        return self.store.get_organization_by_slug(slug)

    def list(self) -> list[Organization]:
        return self.store.list_organizations()


class MemoryBatchRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def create(self, payload: BatchCreate) -> Batch:
        return self.store.create_batch(payload)

    def get_by_name(self, organization_id: UUID, name: str) -> Batch | None:
        return self.store.get_batch_by_name(organization_id, name)

    def list_for_org(self, org_id: UUID) -> list[Batch]:
        return self.store.list_batches_for_org(org_id)


class MemoryStudentRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def create(self, payload: StudentCreate) -> Student:
        return self.store.create_student(payload)

    def get(self, student_id: UUID) -> Student | None:
        return self.store.get_student(student_id)

    def get_by_email(self, email: str, organization_id: UUID | None = None) -> Student | None:
        email_lower = email.lower()
        return next(
            (
                student
                for student in self.store.students.values()
                if student.email.lower() == email_lower
                and (organization_id is None or student.organization_id == organization_id)
            ),
            None,
        )

    def list_for_org(self, org_id: UUID) -> list[Student]:
        return self.store.list_students_for_org(org_id)


class MemoryProjectRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def create(self, payload: ProjectCreate) -> Project:
        return self.store.create_project(payload)

    def get(self, project_id: UUID) -> Project | None:
        return self.store.get_project(project_id)


class MemoryTaskRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def create(self, payload: TaskCreate) -> Task:
        return self.store.create_task(payload)

    def get(self, task_id: UUID) -> Task | None:
        return self.store.get_task(task_id)

    def list_student_ids_for_batch(self, batch_id: UUID) -> set[UUID]:
        return {task.student_id for task in self.store.tasks.values() if task.batch_id == batch_id}

    def list_for_student(self, student_id: UUID) -> list[Task]:
        return self.store.list_student_tasks(student_id)


class MemorySubmissionRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def create(self, payload: SubmissionCreate) -> Submission:
        return self.store.create_submission(payload)

    def get(self, submission_id: UUID) -> Submission | None:
        return self.store.get_submission(submission_id)

    def update_status(self, submission_id: UUID, new_status: SubmissionStatus) -> None:
        self.store.update_submission_status(submission_id, new_status)

    def list_for_batch(self, batch_id: UUID) -> list[Submission]:
        return self.store.list_batch_submissions(batch_id)

    def list_for_student(self, student_id: UUID) -> list[Submission]:
        return self.store.list_submissions_for_student(student_id)


class MemoryEvaluationRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def create(self, payload: EvaluationCreate) -> Evaluation:
        return self.store.create_evaluation(payload)

    def get(self, evaluation_id: UUID) -> Evaluation | None:
        return self.store.get_evaluation(evaluation_id)

    def list_for_submission(self, submission_id: UUID) -> list[Evaluation]:
        return self.store.list_submission_evaluations(submission_id)


class MemoryMentorReviewRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def create(self, payload: MentorReviewCreate) -> MentorReview:
        return self.store.create_mentor_review(payload)


class MemoryEventStore:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store
        if not hasattr(store, "domain_events"):
            store.domain_events = []

    def append(self, event: DomainEvent) -> DomainEvent:
        self.store.domain_events.append(event)
        return event

    def list_by_aggregate(self, aggregate_id: UUID) -> list[DomainEvent]:
        return [event for event in self.store.domain_events if event.aggregate_id == aggregate_id]


class MemoryRefreshTokenRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def create(self, payload: RefreshTokenCreate) -> RefreshTokenRecord:
        return self.store.create_refresh_token(payload)

    def get_by_hash(self, token_hash: str) -> RefreshTokenRecord | None:
        return self.store.get_refresh_token_by_hash(token_hash)

    def mark_used(self, token_id: UUID) -> None:
        self.store.mark_refresh_token_used(token_id)

    def revoke(self, token_id: UUID) -> None:
        self.store.revoke_refresh_token(token_id)

    def revoke_all_for_user(self, user_id: UUID) -> None:
        self.store.revoke_all_refresh_tokens_for_user(user_id)


class MemoryUserRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def create(self, payload: UserCreate) -> User:
        return self.store.create_user(payload)

    def get_by_id(self, user_id: UUID) -> User | None:
        return self.store.get_user_by_id(user_id)

    def get_by_email(self, email: str) -> User | None:
        return self.store.get_user_by_email(email)

    def update_password(self, user_id: UUID, new_hashed_password: str) -> None:
        self.store.update_user_password(user_id, new_hashed_password)


class MemoryUnitOfWork:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store
        self.organizations = MemoryOrganizationRepository(store)
        self.batches = MemoryBatchRepository(store)
        self.students = MemoryStudentRepository(store)
        self.projects = MemoryProjectRepository(store)
        self.tasks = MemoryTaskRepository(store)
        self.submissions = MemorySubmissionRepository(store)
        self.evaluations = MemoryEvaluationRepository(store)
        self.mentor_reviews = MemoryMentorReviewRepository(store)
        self.events = MemoryEventStore(store)
        self.users = MemoryUserRepository(store)
        self.refresh_tokens = MemoryRefreshTokenRepository(store)
        self._snapshot: InMemoryStore | None = None

    def __enter__(self) -> "MemoryUnitOfWork":
        self._snapshot = deepcopy(self.store)
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()

    def commit(self) -> None:
        self._snapshot = None

    def rollback(self) -> None:
        if self._snapshot is None:
            return
        self.store.__dict__.clear()
        self.store.__dict__.update(self._snapshot.__dict__)
        self._snapshot = None

    def begin_nested(self) -> "MemoryUnitOfWork":
        return MemoryUnitOfWork(self.store)


# ---------------------------------------------------------------------------
# Async wrappers — thin async facades over sync memory repos.
# Used by AsyncDailyLoopService in development / test environments where
# PostgreSQL is not available.
# ---------------------------------------------------------------------------


class AsyncMemoryOrganizationRepository:
    def __init__(self, inner: MemoryOrganizationRepository) -> None:
        self._inner = inner

    async def create(self, payload: OrganizationCreate) -> Organization:
        return self._inner.create(payload)

    async def get_by_slug(self, slug: str) -> Organization | None:
        return self._inner.get_by_slug(slug)

    async def list(self) -> list[Organization]:
        return self._inner.list()


class AsyncMemoryBatchRepository:
    def __init__(self, inner: MemoryBatchRepository) -> None:
        self._inner = inner

    async def create(self, payload: BatchCreate) -> Batch:
        return self._inner.create(payload)

    async def get_by_name(self, organization_id: UUID, name: str) -> Batch | None:
        return self._inner.get_by_name(organization_id, name)

    async def list_for_org(self, org_id: UUID) -> list[Batch]:
        return self._inner.list_for_org(org_id)


class AsyncMemoryStudentRepository:
    def __init__(self, inner: MemoryStudentRepository) -> None:
        self._inner = inner

    async def create(self, payload: StudentCreate) -> Student:
        return self._inner.create(payload)

    async def get(self, student_id: UUID) -> Student | None:
        return self._inner.get(student_id)

    async def get_by_email(self, email: str, organization_id: UUID | None = None) -> Student | None:
        return self._inner.get_by_email(email, organization_id)

    async def list_for_org(self, org_id: UUID) -> list[Student]:
        return self._inner.list_for_org(org_id)


class AsyncMemoryProjectRepository:
    def __init__(self, inner: MemoryProjectRepository) -> None:
        self._inner = inner

    async def create(self, payload: ProjectCreate) -> Project:
        return self._inner.create(payload)

    async def get(self, project_id: UUID) -> Project | None:
        return self._inner.get(project_id)


class AsyncMemoryTaskRepository:
    def __init__(self, inner: MemoryTaskRepository) -> None:
        self._inner = inner

    async def create(self, payload: TaskCreate) -> Task:
        return self._inner.create(payload)

    async def get(self, task_id: UUID) -> Task | None:
        return self._inner.get(task_id)

    async def list_student_ids_for_batch(self, batch_id: UUID) -> set[UUID]:
        return self._inner.list_student_ids_for_batch(batch_id)

    async def list_for_student(self, student_id: UUID) -> list[Task]:
        return self._inner.list_for_student(student_id)


class AsyncMemorySubmissionRepository:
    def __init__(self, inner: MemorySubmissionRepository) -> None:
        self._inner = inner

    async def create(self, payload: SubmissionCreate) -> Submission:
        return self._inner.create(payload)

    async def get(self, submission_id: UUID) -> Submission | None:
        return self._inner.get(submission_id)

    async def update_status(self, submission_id: UUID, new_status: SubmissionStatus) -> None:
        self._inner.update_status(submission_id, new_status)

    async def list_for_batch(self, batch_id: UUID) -> list[Submission]:
        return self._inner.list_for_batch(batch_id)

    async def list_for_student(self, student_id: UUID) -> list[Submission]:
        return self._inner.list_for_student(student_id)


class AsyncMemoryEvaluationRepository:
    def __init__(self, inner: MemoryEvaluationRepository) -> None:
        self._inner = inner

    async def create(self, payload: EvaluationCreate) -> Evaluation:
        return self._inner.create(payload)

    async def get(self, evaluation_id: UUID) -> Evaluation | None:
        return self._inner.get(evaluation_id)

    async def list_for_submission(self, submission_id: UUID) -> list[Evaluation]:
        return self._inner.list_for_submission(submission_id)


class AsyncMemoryMentorReviewRepository:
    def __init__(self, inner: MemoryMentorReviewRepository) -> None:
        self._inner = inner

    async def create(self, payload: MentorReviewCreate) -> MentorReview:
        return self._inner.create(payload)


class AsyncMemoryEventStore:
    def __init__(self, inner: MemoryEventStore) -> None:
        self._inner = inner

    async def append(self, event: DomainEvent) -> DomainEvent:
        return self._inner.append(event)

    async def list_by_aggregate(self, aggregate_id: UUID) -> list[DomainEvent]:
        return self._inner.list_by_aggregate(aggregate_id)


class AsyncMemoryRefreshTokenRepository:
    def __init__(self, inner: MemoryRefreshTokenRepository) -> None:
        self._inner = inner

    async def create(self, payload: RefreshTokenCreate) -> RefreshTokenRecord:
        return self._inner.create(payload)

    async def get_by_hash(self, token_hash: str) -> RefreshTokenRecord | None:
        return self._inner.get_by_hash(token_hash)

    async def mark_used(self, token_id: UUID) -> None:
        self._inner.mark_used(token_id)

    async def revoke(self, token_id: UUID) -> None:
        self._inner.revoke(token_id)

    async def revoke_all_for_user(self, user_id: UUID) -> None:
        self._inner.revoke_all_for_user(user_id)


class AsyncMemoryUserRepository:
    def __init__(self, inner: MemoryUserRepository) -> None:
        self._inner = inner

    async def create(self, payload: UserCreate) -> User:
        return self._inner.create(payload)

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self._inner.get_by_id(user_id)

    async def get_by_email(self, email: str) -> User | None:
        return self._inner.get_by_email(email)

    async def update_password(self, user_id: UUID, new_hashed_password: str) -> None:
        self._inner.update_password(user_id, new_hashed_password)


class AsyncMemoryUnitOfWork:
    """Async-compatible UoW backed by in-memory repos.

    Used as the DI fallback when PostgreSQL is unavailable (dev/test).
    Delegates every operation to MemoryUnitOfWork; adds async enter/exit
    so it satisfies the AsyncUnitOfWork protocol.
    """

    def __init__(self, store: InMemoryStore) -> None:
        self._sync_uow = MemoryUnitOfWork(store)
        self.organizations = AsyncMemoryOrganizationRepository(self._sync_uow.organizations)
        self.batches = AsyncMemoryBatchRepository(self._sync_uow.batches)
        self.students = AsyncMemoryStudentRepository(self._sync_uow.students)
        self.projects = AsyncMemoryProjectRepository(self._sync_uow.projects)
        self.tasks = AsyncMemoryTaskRepository(self._sync_uow.tasks)
        self.submissions = AsyncMemorySubmissionRepository(self._sync_uow.submissions)
        self.evaluations = AsyncMemoryEvaluationRepository(self._sync_uow.evaluations)
        self.mentor_reviews = AsyncMemoryMentorReviewRepository(self._sync_uow.mentor_reviews)
        self.events = AsyncMemoryEventStore(self._sync_uow.events)
        self.users = AsyncMemoryUserRepository(self._sync_uow.users)
        self.refresh_tokens = AsyncMemoryRefreshTokenRepository(self._sync_uow.refresh_tokens)

    async def __aenter__(self) -> "AsyncMemoryUnitOfWork":
        self._sync_uow.__enter__()
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        self._sync_uow.__exit__(exc_type, exc, traceback)

    async def commit(self) -> None:
        self._sync_uow.commit()

    async def rollback(self) -> None:
        self._sync_uow.rollback()

    async def begin_nested(self) -> "AsyncMemoryUnitOfWork":
        return AsyncMemoryUnitOfWork(self._sync_uow.store)
