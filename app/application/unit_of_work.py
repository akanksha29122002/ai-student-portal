from typing import Protocol

from app.application.repositories import (
    AsyncBatchRepository,
    AsyncEvaluationRepository,
    AsyncEventStore,
    AsyncMentorReviewRepository,
    AsyncOrganizationRepository,
    AsyncProjectRepository,
    AsyncProjectProfileRepository,
    AsyncStudentRepository,
    AsyncSubmissionRepository,
    AsyncTaskRepository,
    AsyncTaskAssignmentRepository,
    AsyncUserRepository,
    BatchRepository,
    EvaluationRepository,
    EventStore,
    MentorReviewRepository,
    OrganizationRepository,
    ProjectRepository,
    ProjectProfileRepository,
    StudentRepository,
    SubmissionRepository,
    TaskRepository,
    TaskAssignmentRepository,
    UserRepository,
)


class UnitOfWork(Protocol):
    organizations: OrganizationRepository
    batches: BatchRepository
    students: StudentRepository
    projects: ProjectRepository
    project_profiles: ProjectProfileRepository
    tasks: TaskRepository
    task_assignments: TaskAssignmentRepository
    submissions: SubmissionRepository
    evaluations: EvaluationRepository
    mentor_reviews: MentorReviewRepository
    events: EventStore
    users: UserRepository

    def __enter__(self) -> "UnitOfWork": ...
    def __exit__(self, exc_type, exc, traceback) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def begin_nested(self) -> "UnitOfWork": ...


class AsyncUnitOfWork(Protocol):
    organizations: AsyncOrganizationRepository
    batches: AsyncBatchRepository
    students: AsyncStudentRepository
    projects: AsyncProjectRepository
    project_profiles: AsyncProjectProfileRepository
    tasks: AsyncTaskRepository
    task_assignments: AsyncTaskAssignmentRepository
    submissions: AsyncSubmissionRepository
    evaluations: AsyncEvaluationRepository
    mentor_reviews: AsyncMentorReviewRepository
    events: AsyncEventStore
    users: AsyncUserRepository

    async def __aenter__(self) -> "AsyncUnitOfWork": ...
    async def __aexit__(self, exc_type, exc, traceback) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
    async def begin_nested(self): ...
