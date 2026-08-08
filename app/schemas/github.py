"""Pydantic schemas for GitHub integration entities."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.domain.enums import SubmissionState, WebhookEventStatus
from app.schemas.base import ApiModel, Entity


# ---------------------------------------------------------------------------
# GitHub OAuth Connection
# ---------------------------------------------------------------------------


class GitHubConnectionCreate(ApiModel):
    organization_id: UUID
    user_id: UUID
    github_user_login: str = Field(min_length=1, max_length=80)
    github_user_id: int
    access_token: str = Field(min_length=1, max_length=500)
    token_scope: str = ""


class GitHubConnection(Entity):
    organization_id: UUID
    user_id: UUID
    github_user_login: str
    github_user_id: int
    token_scope: str = ""
    is_active: bool = True


class GitHubStatusResponse(ApiModel):
    connected: bool
    github_user_login: str | None = None
    token_scope: str | None = None
    mock_mode: bool = False


# ---------------------------------------------------------------------------
# Webhook Events
# ---------------------------------------------------------------------------


class WebhookEventCreate(ApiModel):
    delivery_id: str = Field(min_length=1, max_length=120)
    event_type: str = Field(min_length=1, max_length=80)
    repository_full_name: str = Field(default="", max_length=300)
    organization_id: UUID | None = None
    payload: dict


class WebhookEvent(Entity):
    delivery_id: str
    event_type: str
    repository_full_name: str = ""
    organization_id: UUID | None = None
    status: WebhookEventStatus = WebhookEventStatus.PENDING
    error_message: str | None = None
    processed_at: datetime | None = None


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class RepositoryCreate(ApiModel):
    organization_id: UUID
    project_id: UUID
    provider: str = "github"
    owner: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    full_name: str = Field(min_length=3, max_length=300)
    external_repository_id: int
    default_branch: str = Field(default="main", max_length=120)
    private: bool = False
    html_url: str = Field(max_length=500)
    clone_url: str = Field(default="", max_length=500)


class RepositoryRecord(Entity):
    organization_id: UUID
    project_id: UUID
    provider: str = "github"
    owner: str
    name: str
    full_name: str
    external_repository_id: int
    default_branch: str = "main"
    private: bool = False
    html_url: str
    clone_url: str = ""
    last_synced_at: datetime | None = None


class RepositoryLinkRequest(ApiModel):
    full_name: str = Field(min_length=3, max_length=300, description="owner/repo GitHub format")


# ---------------------------------------------------------------------------
# Commits
# ---------------------------------------------------------------------------


class CommitCreate(ApiModel):
    repository_id: UUID
    organization_id: UUID
    sha: str = Field(min_length=7, max_length=80)
    message: str = Field(max_length=4000)
    author_name: str = Field(max_length=200)
    author_email: str = Field(max_length=254)
    author_date: datetime
    committer_name: str = Field(max_length=200)
    committer_email: str = Field(max_length=254)
    committer_date: datetime
    branch: str = Field(max_length=200)
    url: str = Field(max_length=500)
    parent_shas: list[str] = Field(default_factory=list)
    additions: int = 0
    deletions: int = 0


class Commit(Entity):
    repository_id: UUID
    organization_id: UUID
    sha: str
    message: str
    author_name: str
    author_email: str
    author_date: datetime
    committer_name: str
    committer_email: str
    committer_date: datetime
    branch: str
    url: str
    parent_shas: list[str] = Field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    diff_truncated: bool = False


class CommitFileCreate(ApiModel):
    commit_id: UUID
    path: str = Field(max_length=800)
    status: str = Field(max_length=40)
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    patch: str | None = None
    patch_truncated: bool = False


class CommitFile(Entity):
    commit_id: UUID
    path: str
    status: str
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    patch: str | None = None
    patch_truncated: bool = False


# ---------------------------------------------------------------------------
# Submission state snapshot (returned in API responses)
# ---------------------------------------------------------------------------


class SubmissionStateInfo(ApiModel):
    submission_id: UUID
    state: SubmissionState
    repository_id: UUID | None = None
    commit_ids: list[UUID] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Mock / demo
# ---------------------------------------------------------------------------


class MockRepositoryInfo(ApiModel):
    id: int
    name: str
    full_name: str
    private: bool
    default_branch: str
    html_url: str
    clone_url: str
