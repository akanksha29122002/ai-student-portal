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
from app.schemas.m7 import (
    AIInteractionLog,
    AIInteractionLogCreate,
    DailyAutomationRun,
    DailyAutomationRunCreate,
    LearningPlan,
    LearningPlanCreate,
    LearningPlanDay,
    LearningPlanDayCreate,
    SkillAssessment,
    SkillAssessmentCreate,
    StudentProfileAnalysis,
    StudentProfileAnalysisCreate,
    StudentProgress,
    StudentProgressCreate,
    StudentProjectProfile,
    StudentProjectProfileCreate,
    StudentProjectProfileUpdate,
    SubmissionEvidence,
    SubmissionEvidenceCreate,
    TaskDependency,
    TaskDependencyCreate,
    TaskAssignment,
    TaskAssignmentCreate,
    VerificationEvidence,
    VerificationEvidenceCreate,
    VerificationResult,
    VerificationResultCreate,
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
        # Milestone 7 collections
        self.student_profile_analyses: dict[UUID, StudentProfileAnalysis] = {}
        self.skill_assessments: dict[UUID, SkillAssessment] = {}
        self.learning_plans: dict[UUID, LearningPlan] = {}
        self.learning_plan_days: dict[UUID, LearningPlanDay] = {}
        self.task_dependencies: dict[UUID, TaskDependency] = {}
        self.task_assignments: dict[UUID, TaskAssignment] = {}
        self.submission_evidences: dict[UUID, SubmissionEvidence] = {}
        self.verification_results: dict[UUID, VerificationResult] = {}
        self.verification_evidences: dict[UUID, VerificationEvidence] = {}
        self.student_progress: dict[UUID, StudentProgress] = {}
        self.student_project_profiles: dict[UUID, StudentProjectProfile] = {}
        self.daily_automation_runs: dict[UUID, DailyAutomationRun] = {}
        self.ai_interaction_logs: list[AIInteractionLog] = []

    def create_organization(self, payload: OrganizationCreate) -> Organization:
        entity = Organization(**payload.model_dump())
        self.organizations[entity.id] = entity
        return entity

    def get_organization_by_slug(self, slug: str) -> Organization | None:
        slug_lower = slug.lower()
        return next((o for o in self.organizations.values() if o.slug.lower() == slug_lower), None)

    def list_organizations(self) -> list[Organization]:
        return list(self.organizations.values())

    def create_batch(self, payload: BatchCreate) -> Batch:
        entity = Batch(**payload.model_dump())
        self.batches[entity.id] = entity
        return entity

    def get_batch_by_name(self, organization_id: UUID, name: str) -> Batch | None:
        name_lower = name.lower()
        return next(
            (
                b
                for b in self.batches.values()
                if b.organization_id == organization_id and b.name.lower() == name_lower
            ),
            None,
        )

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

    def create_student_project_profile(self, payload: StudentProjectProfileCreate) -> StudentProjectProfile:
        existing = self.get_student_project_profile(payload.student_id)
        if existing:
            raise ValueError("student project profile already exists")
        entity = StudentProjectProfile(**payload.model_dump())
        self.student_project_profiles[entity.id] = entity
        return entity

    def get_student_project_profile(self, student_id: UUID) -> StudentProjectProfile | None:
        return next(
            (profile for profile in self.student_project_profiles.values() if profile.student_id == student_id),
            None,
        )

    def update_student_project_profile(
        self,
        student_id: UUID,
        payload: StudentProjectProfileUpdate,
    ) -> StudentProjectProfile | None:
        existing = self.get_student_project_profile(student_id)
        if existing is None:
            return None
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return existing
        updated = existing.model_copy(update={**updates, "updated_at": datetime.now(UTC)})
        self.student_project_profiles[existing.id] = updated
        return updated

    def get_project(self, project_id: UUID) -> Project | None:
        return self.projects.get(project_id)

    def create_task(self, payload: TaskCreate) -> Task:
        entity = Task(**payload.model_dump())
        self.tasks[entity.id] = entity
        return entity

    def create_task_assignment(self, payload: TaskAssignmentCreate) -> TaskAssignment:
        existing = self.get_task_assignment_for_student_on(payload.student_id, payload.assigned_on)
        if existing:
            raise ValueError("task assignment already exists for this student/day")
        entity = TaskAssignment(**payload.model_dump())
        self.task_assignments[entity.id] = entity
        return entity

    def get_task_assignment_for_student_on(self, student_id: UUID, assigned_on) -> TaskAssignment | None:
        return next(
            (
                assignment
                for assignment in self.task_assignments.values()
                if assignment.student_id == student_id and assignment.assigned_on == assigned_on
            ),
            None,
        )

    def list_task_assignments_for_student(self, student_id: UUID) -> list[TaskAssignment]:
        return sorted(
            [assignment for assignment in self.task_assignments.values() if assignment.student_id == student_id],
            key=lambda assignment: assignment.assigned_on,
        )

    def list_task_assignments_for_batch_on(self, batch_id: UUID, assigned_on) -> list[TaskAssignment]:
        return [
            assignment
            for assignment in self.task_assignments.values()
            if assignment.batch_id == batch_id and assignment.assigned_on == assigned_on
        ]

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

    # ------------------------------------------------------------------
    # Milestone 7 — Learning Plans
    # ------------------------------------------------------------------

    def create_student_profile_analysis(self, payload: StudentProfileAnalysisCreate) -> StudentProfileAnalysis:
        entity = StudentProfileAnalysis(**payload.model_dump())
        self.student_profile_analyses[entity.id] = entity
        return entity

    def get_student_profile_analysis(self, analysis_id: UUID) -> StudentProfileAnalysis | None:
        return self.student_profile_analyses.get(analysis_id)

    def get_latest_profile_analysis(self, student_id: UUID) -> StudentProfileAnalysis | None:
        analyses = [a for a in self.student_profile_analyses.values() if a.student_id == student_id]
        return max(analyses, key=lambda a: a.created_at) if analyses else None

    def update_profile_analysis(self, analysis_id: UUID, **updates) -> StudentProfileAnalysis | None:
        entity = self.student_profile_analyses.get(analysis_id)
        if entity:
            self.student_profile_analyses[analysis_id] = entity.model_copy(
                update={**updates, "updated_at": datetime.now(UTC)}
            )
        return self.student_profile_analyses.get(analysis_id)

    def create_skill_assessment(self, payload: SkillAssessmentCreate) -> SkillAssessment:
        entity = SkillAssessment(**payload.model_dump())
        self.skill_assessments[entity.id] = entity
        return entity

    def list_skill_assessments(self, student_id: UUID) -> list[SkillAssessment]:
        return [a for a in self.skill_assessments.values() if a.student_id == student_id]

    def upsert_skill_assessment(self, payload: SkillAssessmentCreate) -> SkillAssessment:
        existing = next(
            (a for a in self.skill_assessments.values()
             if a.student_id == payload.student_id and a.dimension == payload.dimension),
            None,
        )
        if existing:
            updated = existing.model_copy(update={**payload.model_dump(), "updated_at": datetime.now(UTC)})
            self.skill_assessments[existing.id] = updated
            return updated
        return self.create_skill_assessment(payload)

    def create_learning_plan(self, payload: LearningPlanCreate) -> LearningPlan:
        entity = LearningPlan(**payload.model_dump())
        self.learning_plans[entity.id] = entity
        return entity

    def get_learning_plan(self, plan_id: UUID) -> LearningPlan | None:
        return self.learning_plans.get(plan_id)

    def get_active_plan(self, student_id: UUID) -> LearningPlan | None:
        return next(
            (p for p in self.learning_plans.values()
             if p.student_id == student_id and p.status == "active"),
            None,
        )

    def list_learning_plans(self, student_id: UUID) -> list[LearningPlan]:
        return [p for p in self.learning_plans.values() if p.student_id == student_id]

    def update_learning_plan(self, plan_id: UUID, **updates) -> LearningPlan | None:
        entity = self.learning_plans.get(plan_id)
        if entity:
            self.learning_plans[plan_id] = entity.model_copy(
                update={**updates, "updated_at": datetime.now(UTC)}
            )
        return self.learning_plans.get(plan_id)

    def create_learning_plan_day(self, payload: LearningPlanDayCreate) -> LearningPlanDay:
        entity = LearningPlanDay(**payload.model_dump())
        self.learning_plan_days[entity.id] = entity
        return entity

    def get_learning_plan_day(self, day_id: UUID) -> LearningPlanDay | None:
        return self.learning_plan_days.get(day_id)

    def list_plan_days(self, plan_id: UUID) -> list[LearningPlanDay]:
        return sorted(
            [d for d in self.learning_plan_days.values() if d.plan_id == plan_id],
            key=lambda d: d.day_number,
        )

    def get_plan_day_by_number(self, plan_id: UUID, day_number: int) -> LearningPlanDay | None:
        return next(
            (d for d in self.learning_plan_days.values()
             if d.plan_id == plan_id and d.day_number == day_number),
            None,
        )

    def update_plan_day(self, day_id: UUID, **updates) -> LearningPlanDay | None:
        entity = self.learning_plan_days.get(day_id)
        if entity:
            self.learning_plan_days[day_id] = entity.model_copy(
                update={**updates, "updated_at": datetime.now(UTC)}
            )
        return self.learning_plan_days.get(day_id)

    def create_task_dependency(self, payload: TaskDependencyCreate) -> TaskDependency:
        entity = TaskDependency(**payload.model_dump())
        self.task_dependencies[entity.id] = entity
        return entity

    def list_task_dependencies(self, task_id: UUID) -> list[TaskDependency]:
        return [d for d in self.task_dependencies.values() if d.task_id == task_id]

    def create_submission_evidence(self, payload: SubmissionEvidenceCreate) -> SubmissionEvidence:
        entity = SubmissionEvidence(**payload.model_dump())
        self.submission_evidences[entity.id] = entity
        return entity

    def list_submission_evidences(self, submission_id: UUID) -> list[SubmissionEvidence]:
        return [e for e in self.submission_evidences.values() if e.submission_id == submission_id]

    def create_verification_result(self, payload: VerificationResultCreate) -> VerificationResult:
        entity = VerificationResult(**payload.model_dump())
        self.verification_results[entity.id] = entity
        return entity

    def get_verification_result(self, result_id: UUID) -> VerificationResult | None:
        return self.verification_results.get(result_id)

    def get_latest_verification(self, submission_id: UUID) -> VerificationResult | None:
        results = [r for r in self.verification_results.values() if r.submission_id == submission_id]
        return max(results, key=lambda r: r.created_at) if results else None

    def update_verification_result(self, result_id: UUID, **updates) -> VerificationResult | None:
        entity = self.verification_results.get(result_id)
        if entity:
            self.verification_results[result_id] = entity.model_copy(
                update={**updates, "updated_at": datetime.now(UTC)}
            )
        return self.verification_results.get(result_id)

    def create_verification_evidence(self, payload: VerificationEvidenceCreate) -> VerificationEvidence:
        entity = VerificationEvidence(**payload.model_dump())
        self.verification_evidences[entity.id] = entity
        return entity

    def list_verification_evidences(self, result_id: UUID) -> list[VerificationEvidence]:
        return [e for e in self.verification_evidences.values() if e.verification_result_id == result_id]

    def upsert_student_progress(self, payload: StudentProgressCreate) -> StudentProgress:
        existing = next(
            (p for p in self.student_progress.values()
             if p.student_id == payload.student_id and p.snapshot_date == payload.snapshot_date),
            None,
        )
        if existing:
            updated = existing.model_copy(update={**payload.model_dump(), "updated_at": datetime.now(UTC)})
            self.student_progress[existing.id] = updated
            return updated
        entity = StudentProgress(**payload.model_dump())
        self.student_progress[entity.id] = entity
        return entity

    def get_student_progress(self, student_id: UUID) -> list[StudentProgress]:
        return sorted(
            [p for p in self.student_progress.values() if p.student_id == student_id],
            key=lambda p: p.snapshot_date,
        )

    def create_daily_automation_run(self, payload: DailyAutomationRunCreate) -> DailyAutomationRun:
        entity = DailyAutomationRun(**payload.model_dump())
        self.daily_automation_runs[entity.id] = entity
        return entity

    def get_daily_automation_run(self, run_id: UUID) -> DailyAutomationRun | None:
        return self.daily_automation_runs.get(run_id)

    def update_daily_automation_run(self, run_id: UUID, **updates) -> DailyAutomationRun | None:
        entity = self.daily_automation_runs.get(run_id)
        if entity:
            self.daily_automation_runs[run_id] = entity.model_copy(
                update={**updates, "updated_at": datetime.now(UTC)}
            )
        return self.daily_automation_runs.get(run_id)

    def log_ai_interaction(self, payload: AIInteractionLogCreate) -> AIInteractionLog:
        entity = AIInteractionLog(**payload.model_dump())
        self.ai_interaction_logs.append(entity)
        return entity

    def list_ai_interactions(self, student_id: UUID | None = None, limit: int = 100) -> list[AIInteractionLog]:
        logs = self.ai_interaction_logs
        if student_id:
            logs = [l for l in logs if l.student_id == student_id]
        return list(reversed(logs))[:limit]


store = InMemoryStore()
