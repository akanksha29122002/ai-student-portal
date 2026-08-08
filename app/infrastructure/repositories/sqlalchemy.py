from datetime import UTC, datetime
from uuid import UUID

from app.domain.enums import SubmissionStatus
from app.domain.events import DomainEvent
from app.infrastructure.models import (
    BatchModel,
    DailyTaskModel,
    EvaluationModel,
    MentorReviewModel,
    OrganizationModel,
    ProjectModel,
    RefreshTokenModel,
    StudentModel,
    SubmissionModel,
    SystemEventModel,
    UserModel,
)
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
from app.shared.exceptions import InfrastructureException

try:
    from sqlalchemy import select, update as sa_update
    from sqlalchemy.ext.asyncio import AsyncSession
except ModuleNotFoundError:
    AsyncSession = None
    select = None
    sa_update = None


class SqlAlchemyRepository:
    def __init__(self, session: "AsyncSession") -> None:
        if AsyncSession is None:
            raise InfrastructureException("SQLAlchemy is not installed.")
        self.session = session


class SqlAlchemyOrganizationRepository(SqlAlchemyRepository):
    async def create(self, payload: OrganizationCreate) -> Organization:
        model = OrganizationModel(**payload.model_dump())
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return Organization.model_validate(model, from_attributes=True)


class SqlAlchemyBatchRepository(SqlAlchemyRepository):
    async def create(self, payload: BatchCreate) -> Batch:
        model = BatchModel(**payload.model_dump())
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return Batch.model_validate(model, from_attributes=True)


class SqlAlchemyStudentRepository(SqlAlchemyRepository):
    async def create(self, payload: StudentCreate) -> Student:
        model = StudentModel(**payload.model_dump())
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return Student.model_validate(model, from_attributes=True)

    async def get(self, student_id: UUID) -> Student | None:
        result = await self.session.execute(
            select(StudentModel).where(
                StudentModel.id == student_id,
                StudentModel.deleted_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()
        return Student.model_validate(model, from_attributes=True) if model else None


class SqlAlchemyProjectRepository(SqlAlchemyRepository):
    async def create(self, payload: ProjectCreate) -> Project:
        data = payload.model_dump()
        data["repository_url"] = str(data["repository_url"])
        model = ProjectModel(**data)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return Project.model_validate(model, from_attributes=True)

    async def get(self, project_id: UUID) -> Project | None:
        result = await self.session.execute(
            select(ProjectModel).where(
                ProjectModel.id == project_id,
                ProjectModel.deleted_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()
        return Project.model_validate(model, from_attributes=True) if model else None


class SqlAlchemyTaskRepository(SqlAlchemyRepository):
    async def create(self, payload: TaskCreate) -> Task:
        model = DailyTaskModel(**payload.model_dump())
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return Task.model_validate(model, from_attributes=True)

    async def get(self, task_id: UUID) -> Task | None:
        result = await self.session.execute(
            select(DailyTaskModel).where(
                DailyTaskModel.id == task_id,
                DailyTaskModel.deleted_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()
        return Task.model_validate(model, from_attributes=True) if model else None

    async def list_student_ids_for_batch(self, batch_id: UUID) -> set[UUID]:
        result = await self.session.execute(
            select(DailyTaskModel.student_id).where(
                DailyTaskModel.batch_id == batch_id,
                DailyTaskModel.deleted_at.is_(None),
            )
        )
        return {row[0] for row in result.all()}

    async def list_for_student(self, student_id: UUID) -> list[Task]:
        result = await self.session.execute(
            select(DailyTaskModel).where(
                DailyTaskModel.student_id == student_id,
                DailyTaskModel.deleted_at.is_(None),
            )
        )
        return [Task.model_validate(m, from_attributes=True) for m in result.scalars().all()]


class SqlAlchemySubmissionRepository(SqlAlchemyRepository):
    async def create(self, payload: SubmissionCreate) -> Submission:
        data = payload.model_dump()
        for field in ("repository_url", "commit_url", "transcript_url"):
            if data.get(field) is not None:
                data[field] = str(data[field])
        data["status"] = SubmissionStatus.RECEIVED
        model = SubmissionModel(**data)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return Submission.model_validate(model, from_attributes=True)

    async def get(self, submission_id: UUID) -> Submission | None:
        result = await self.session.execute(
            select(SubmissionModel).where(
                SubmissionModel.id == submission_id,
                SubmissionModel.deleted_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()
        return Submission.model_validate(model, from_attributes=True) if model else None

    async def update_status(self, submission_id: UUID, new_status: SubmissionStatus) -> None:
        await self.session.execute(
            sa_update(SubmissionModel)
            .where(SubmissionModel.id == submission_id)
            .values(status=str(new_status), updated_at=datetime.now(UTC))
        )

    async def list_for_batch(self, batch_id: UUID) -> list[Submission]:
        result = await self.session.execute(
            select(SubmissionModel)
            .join(DailyTaskModel, SubmissionModel.task_id == DailyTaskModel.id)
            .where(
                DailyTaskModel.batch_id == batch_id,
                SubmissionModel.deleted_at.is_(None),
            )
        )
        return [Submission.model_validate(m, from_attributes=True) for m in result.scalars().all()]


class SqlAlchemyEvaluationRepository(SqlAlchemyRepository):
    async def create(self, payload: EvaluationCreate) -> Evaluation:
        data = payload.model_dump()
        data["evidence"] = [e.model_dump() for e in payload.evidence]
        model = EvaluationModel(**data)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self._to_evaluation(model)

    async def get(self, evaluation_id: UUID) -> Evaluation | None:
        result = await self.session.execute(
            select(EvaluationModel).where(
                EvaluationModel.id == evaluation_id,
                EvaluationModel.deleted_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()
        return self._to_evaluation(model) if model else None

    async def list_for_submission(self, submission_id: UUID) -> list[Evaluation]:
        result = await self.session.execute(
            select(EvaluationModel).where(
                EvaluationModel.submission_id == submission_id,
                EvaluationModel.deleted_at.is_(None),
            )
        )
        return [self._to_evaluation(m) for m in result.scalars().all()]

    def _to_evaluation(self, model: EvaluationModel) -> Evaluation:
        return Evaluation(
            id=model.id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            organization_id=model.organization_id,
            submission_id=model.submission_id,
            kind=model.kind,
            verdict=model.verdict,
            score=model.score,
            confidence=float(model.confidence),
            evidence=model.evidence,
            flags=model.flags,
            mentor_note=model.mentor_note,
            student_feedback_draft=model.student_feedback_draft,
            recommended_next_action=model.recommended_next_action,
            prompt_version=model.prompt_version,
        )


class SqlAlchemyMentorReviewRepository(SqlAlchemyRepository):
    async def create(self, payload: MentorReviewCreate) -> MentorReview:
        model = MentorReviewModel(**payload.model_dump())
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return MentorReview.model_validate(model, from_attributes=True)


class SqlAlchemyEventStore(SqlAlchemyRepository):
    async def append(self, event: DomainEvent) -> DomainEvent:
        model = SystemEventModel(
            id=event.event_id,
            aggregate_id=event.aggregate_id,
            aggregate_type=event.aggregate_type,
            event_type=event.event_type,
            payload=event.payload,
            occurred_at=event.occurred_at,
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
            user_id=event.user_id,
            metadata_json=event.metadata,
        )
        self.session.add(model)
        await self.session.flush()
        return event

    async def list_by_aggregate(self, aggregate_id: UUID) -> list[DomainEvent]:
        result = await self.session.execute(
            select(SystemEventModel).where(SystemEventModel.aggregate_id == aggregate_id)
        )
        return [self._to_domain_event(m) for m in result.scalars().all()]

    def _to_domain_event(self, model: SystemEventModel) -> DomainEvent:
        return DomainEvent(
            event_id=model.id,
            aggregate_id=model.aggregate_id,
            aggregate_type=model.aggregate_type,
            event_type=model.event_type,
            payload=model.payload,
            occurred_at=model.occurred_at,
            correlation_id=model.correlation_id,
            causation_id=model.causation_id,
            user_id=model.user_id,
            metadata=model.metadata_json,
        )


class SqlAlchemyRefreshTokenRepository(SqlAlchemyRepository):
    async def create(self, payload: RefreshTokenCreate) -> RefreshTokenRecord:
        model = RefreshTokenModel(**payload.model_dump())
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return RefreshTokenRecord.model_validate(model, from_attributes=True)

    async def get_by_hash(self, token_hash: str) -> RefreshTokenRecord | None:
        result = await self.session.execute(
            select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash)
        )
        model = result.scalar_one_or_none()
        return RefreshTokenRecord.model_validate(model, from_attributes=True) if model else None

    async def mark_used(self, token_id: UUID) -> None:
        await self.session.execute(
            sa_update(RefreshTokenModel)
            .where(RefreshTokenModel.id == token_id)
            .values(used_at=datetime.now(UTC))
        )

    async def revoke(self, token_id: UUID) -> None:
        await self.session.execute(
            sa_update(RefreshTokenModel)
            .where(RefreshTokenModel.id == token_id)
            .values(revoked_at=datetime.now(UTC))
        )

    async def revoke_all_for_user(self, user_id: UUID) -> None:
        await self.session.execute(
            sa_update(RefreshTokenModel)
            .where(RefreshTokenModel.user_id == user_id, RefreshTokenModel.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )


class SqlAlchemyUserRepository(SqlAlchemyRepository):
    async def create(self, payload: UserCreate) -> User:
        model = UserModel(**payload.model_dump())
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return User.model_validate(model, from_attributes=True)

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self.session.execute(
            select(UserModel).where(
                UserModel.id == user_id,
                UserModel.deleted_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()
        return User.model_validate(model, from_attributes=True) if model else None

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(UserModel).where(
                UserModel.email == email.lower(),
                UserModel.deleted_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()
        return User.model_validate(model, from_attributes=True) if model else None

    async def update_password(self, user_id: UUID, new_hashed_password: str) -> None:
        await self.session.execute(
            sa_update(UserModel)
            .where(UserModel.id == user_id)
            .values(hashed_password=new_hashed_password, updated_at=datetime.now(UTC))
        )


class SqlAlchemyUnitOfWork:
    def __init__(self, session: "AsyncSession") -> None:
        if AsyncSession is None:
            raise InfrastructureException("SQLAlchemy is not installed.")
        self.session = session
        self.organizations = SqlAlchemyOrganizationRepository(session)
        self.batches = SqlAlchemyBatchRepository(session)
        self.students = SqlAlchemyStudentRepository(session)
        self.projects = SqlAlchemyProjectRepository(session)
        self.tasks = SqlAlchemyTaskRepository(session)
        self.submissions = SqlAlchemySubmissionRepository(session)
        self.evaluations = SqlAlchemyEvaluationRepository(session)
        self.mentor_reviews = SqlAlchemyMentorReviewRepository(session)
        self.events = SqlAlchemyEventStore(session)
        self.users = SqlAlchemyUserRepository(session)
        self.refresh_tokens = SqlAlchemyRefreshTokenRepository(session)

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def begin_nested(self):
        return await self.session.begin_nested()
