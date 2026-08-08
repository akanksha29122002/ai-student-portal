from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import Field

from app.schemas.base import ApiModel


class DomainEvent(ApiModel):
    event_id: UUID = Field(default_factory=uuid4)
    aggregate_id: UUID
    aggregate_type: str
    event_type: str
    payload: dict[str, Any]
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    correlation_id: UUID = Field(default_factory=uuid4)
    causation_id: UUID | None = None
    user_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StudentRegistered(DomainEvent):
    aggregate_type: Literal["student"] = "student"
    event_type: Literal["StudentRegistered"] = "StudentRegistered"


class ProjectCreated(DomainEvent):
    aggregate_type: Literal["project"] = "project"
    event_type: Literal["ProjectCreated"] = "ProjectCreated"


class TaskAssigned(DomainEvent):
    aggregate_type: Literal["task"] = "task"
    event_type: Literal["TaskAssigned"] = "TaskAssigned"


class SubmissionReceived(DomainEvent):
    aggregate_type: Literal["submission"] = "submission"
    event_type: Literal["SubmissionReceived"] = "SubmissionReceived"


class SubmissionValidated(DomainEvent):
    aggregate_type: Literal["submission"] = "submission"
    event_type: Literal["SubmissionValidated"] = "SubmissionValidated"


class EvaluationStarted(DomainEvent):
    aggregate_type: Literal["evaluation"] = "evaluation"
    event_type: Literal["EvaluationStarted"] = "EvaluationStarted"


class EvaluationCompleted(DomainEvent):
    aggregate_type: Literal["evaluation"] = "evaluation"
    event_type: Literal["EvaluationCompleted"] = "EvaluationCompleted"


class MentorReviewed(DomainEvent):
    aggregate_type: Literal["mentor_review"] = "mentor_review"
    event_type: Literal["MentorReviewed"] = "MentorReviewed"


class ReminderTriggered(DomainEvent):
    aggregate_type: Literal["notification"] = "notification"
    event_type: Literal["ReminderTriggered"] = "ReminderTriggered"


class DailySummaryGenerated(DomainEvent):
    aggregate_type: Literal["daily_summary"] = "daily_summary"
    event_type: Literal["DailySummaryGenerated"] = "DailySummaryGenerated"


class GitHubPushReceived(DomainEvent):
    aggregate_type: Literal["github_push"] = "github_push"
    event_type: Literal["GitHubPushReceived"] = "GitHubPushReceived"


class GitHubConnected(DomainEvent):
    aggregate_type: Literal["github_connection"] = "github_connection"
    event_type: Literal["GitHubConnected"] = "GitHubConnected"


class RepositoryLinked(DomainEvent):
    aggregate_type: Literal["repository"] = "repository"
    event_type: Literal["RepositoryLinked"] = "RepositoryLinked"


class WebhookReceived(DomainEvent):
    aggregate_type: Literal["webhook_event"] = "webhook_event"
    event_type: Literal["WebhookReceived"] = "WebhookReceived"


class CommitIngested(DomainEvent):
    aggregate_type: Literal["commit"] = "commit"
    event_type: Literal["CommitIngested"] = "CommitIngested"


class SubmissionReadyForEvaluation(DomainEvent):
    aggregate_type: Literal["submission"] = "submission"
    event_type: Literal["SubmissionReadyForEvaluation"] = "SubmissionReadyForEvaluation"

