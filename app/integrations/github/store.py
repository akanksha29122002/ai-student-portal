"""In-memory store for GitHub integration entities.

Used in tests and mock mode.  Does NOT extend InMemoryStore so it stays
isolated — the GitHub integration can be tested independently.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.domain.enums import WebhookEventStatus
from app.schemas.github import (
    Commit,
    CommitCreate,
    CommitFile,
    GitHubConnection,
    GitHubConnectionCreate,
    RepositoryCreate,
    RepositoryRecord,
    WebhookEvent,
    WebhookEventCreate,
)


class GitHubMemoryStore:
    def __init__(self) -> None:
        # GitHub OAuth connections per org (one per org)
        self._connections: dict[UUID, GitHubConnection] = {}
        self._tokens: dict[UUID, str] = {}  # org_id → access_token (never in API responses)

        # Webhook events (for idempotency + status tracking)
        self._webhook_events: dict[UUID, WebhookEvent] = {}
        self._webhook_by_delivery: dict[str, UUID] = {}  # delivery_id → event_id

        # Repositories
        self._repositories: dict[UUID, RepositoryRecord] = {}
        self._repos_by_project: dict[UUID, UUID] = {}   # project_id → repo_id
        self._repos_by_fullname: dict[str, UUID] = {}   # full_name → repo_id

        # Commits
        self._commits: dict[UUID, Commit] = {}
        self._commits_by_sha: dict[tuple[UUID, str], UUID] = {}  # (repo_id, sha) → commit_id

        # Commit files
        self._commit_files: dict[UUID, list[CommitFile]] = {}  # commit_id → files

    # ------------------------------------------------------------------
    # Connections
    # ------------------------------------------------------------------

    def save_connection(self, payload: GitHubConnectionCreate) -> GitHubConnection:
        connection = GitHubConnection(
            organization_id=payload.organization_id,
            user_id=payload.user_id,
            github_user_login=payload.github_user_login,
            github_user_id=payload.github_user_id,
            token_scope=payload.token_scope,
        )
        self._connections[payload.organization_id] = connection
        self._tokens[payload.organization_id] = payload.access_token
        return connection

    def get_connection(self, organization_id: UUID) -> GitHubConnection | None:
        return self._connections.get(organization_id)

    def get_access_token(self, organization_id: UUID) -> str | None:
        return self._tokens.get(organization_id)

    def remove_connection(self, organization_id: UUID) -> None:
        self._connections.pop(organization_id, None)
        self._tokens.pop(organization_id, None)

    # ------------------------------------------------------------------
    # Webhook events (idempotency)
    # ------------------------------------------------------------------

    def is_duplicate_delivery(self, delivery_id: str) -> bool:
        return delivery_id in self._webhook_by_delivery

    def record_webhook_event(self, payload: WebhookEventCreate) -> WebhookEvent:
        event = WebhookEvent(**payload.model_dump(exclude={"payload"}))
        self._webhook_events[event.id] = event
        self._webhook_by_delivery[payload.delivery_id] = event.id
        return event

    def get_webhook_event(self, event_id: UUID) -> WebhookEvent | None:
        return self._webhook_events.get(event_id)

    def mark_webhook_processed(self, event_id: UUID) -> None:
        event = self._webhook_events.get(event_id)
        if event:
            self._webhook_events[event_id] = event.model_copy(update={
                "status": WebhookEventStatus.PROCESSED,
                "processed_at": datetime.now(UTC),
            })

    def mark_webhook_failed(self, event_id: UUID, error: str) -> None:
        event = self._webhook_events.get(event_id)
        if event:
            self._webhook_events[event_id] = event.model_copy(update={
                "status": WebhookEventStatus.FAILED,
                "error_message": error,
            })

    # ------------------------------------------------------------------
    # Repositories
    # ------------------------------------------------------------------

    def save_repository(self, payload: RepositoryCreate) -> RepositoryRecord:
        repo = RepositoryRecord(**payload.model_dump())
        self._repositories[repo.id] = repo
        self._repos_by_project[payload.project_id] = repo.id
        self._repos_by_fullname[payload.full_name] = repo.id
        return repo

    def get_repository(self, repo_id: UUID) -> RepositoryRecord | None:
        return self._repositories.get(repo_id)

    def get_repository_by_project(self, project_id: UUID) -> RepositoryRecord | None:
        repo_id = self._repos_by_project.get(project_id)
        return self._repositories.get(repo_id) if repo_id else None

    def get_repository_by_fullname(self, full_name: str) -> RepositoryRecord | None:
        repo_id = self._repos_by_fullname.get(full_name)
        return self._repositories.get(repo_id) if repo_id else None

    def is_fullname_taken_by_other_org(self, full_name: str, organization_id: UUID) -> bool:
        repo_id = self._repos_by_fullname.get(full_name)
        if repo_id is None:
            return False
        repo = self._repositories[repo_id]
        return repo.organization_id != organization_id

    # ------------------------------------------------------------------
    # Commits
    # ------------------------------------------------------------------

    def save_commit(
        self,
        payload: CommitCreate,
        file_payloads: list[dict],
        diff_truncated: bool = False,
    ) -> Commit:
        commit = Commit(**payload.model_dump(), diff_truncated=diff_truncated)
        self._commits[commit.id] = commit
        self._commits_by_sha[(payload.repository_id, payload.sha)] = commit.id
        files: list[CommitFile] = []
        for fp in file_payloads:
            cf = CommitFile(commit_id=commit.id, **fp)
            files.append(cf)
        self._commit_files[commit.id] = files
        return commit

    def get_commit(self, commit_id: UUID) -> Commit | None:
        return self._commits.get(commit_id)

    def get_commit_by_sha(self, repo_id: UUID, sha: str) -> Commit | None:
        commit_id = self._commits_by_sha.get((repo_id, sha))
        return self._commits.get(commit_id) if commit_id else None

    def get_commit_files(self, commit_id: UUID) -> list[CommitFile]:
        return self._commit_files.get(commit_id, [])

    def list_commits_for_repository(self, repo_id: UUID) -> list[Commit]:
        return [c for c in self._commits.values() if c.repository_id == repo_id]
