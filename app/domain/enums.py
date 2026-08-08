from enum import StrEnum


class UserRole(StrEnum):
    SUPER_ADMIN = "super_admin"
    ORGANIZATION_ADMIN = "organization_admin"
    PROGRAM_MANAGER = "program_manager"
    MENTOR = "mentor"
    REVIEWER = "reviewer"
    STUDENT = "student"
    AI_AGENT = "ai_agent"
    SYSTEM = "system"


class Track(StrEnum):
    TRACK_A = "track_a"
    TRACK_B = "track_b"


class TaskType(StrEnum):
    CODING = "coding"
    SPOKEN_QUESTION = "spoken_question"


class SubmissionStatus(StrEnum):
    RECEIVED = "received"
    QUEUED = "queued"
    PROCESSING = "processing"
    EVALUATED = "evaluated"
    MENTOR_REVIEW_PENDING = "mentor_review_pending"
    FEEDBACK_RELEASED = "feedback_released"
    FAILED = "failed"


class SelfStatus(StrEnum):
    SOLVED = "solved"
    PARTIALLY_SOLVED = "partially_solved"
    NOT_SOLVED = "not_solved"
    ATTEMPTED = "attempted"
    SKIPPED = "skipped"


class EvaluationKind(StrEnum):
    GITHUB_COMMIT = "github_commit"
    TRANSCRIPT = "transcript"


class EvaluationVerdict(StrEnum):
    CORRECT = "correct"
    PARTIALLY_CORRECT = "partially_correct"
    INCORRECT = "incorrect"
    NO_VALID_SUBMISSION = "no_valid_submission"
    NEEDS_HUMAN_REVIEW = "needs_human_review"
    STRONG = "strong"
    ACCEPTABLE = "acceptable"
    PARTIAL = "partial"
    WEAK = "weak"


class MentorReviewDecision(StrEnum):
    APPROVED = "approved"
    EDITED = "edited"
    OVERRIDDEN = "overridden"
    RETURNED_FOR_REVISION = "returned_for_revision"


class SubmissionState(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    VALIDATING = "validating"
    VALIDATED = "validated"
    READY_FOR_EVALUATION = "ready_for_evaluation"
    EVALUATING = "evaluating"
    EVALUATED = "evaluated"
    MENTOR_REVIEW = "mentor_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WebhookEventStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    DUPLICATE = "duplicate"

