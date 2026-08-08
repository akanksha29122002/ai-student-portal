"""GitHub integration service — business logic over the raw API client.

Provides URL parsing utilities and higher-level operations used by event
handlers and API routes.
"""
from __future__ import annotations

import logging
from datetime import datetime
from urllib.parse import urlparse

from app.integrations.github.client import GitHubClient
from app.integrations.github.schemas import CommitInfo, RepositoryInfo
from app.shared.exceptions import InfrastructureException

logger = logging.getLogger("project_defense.integrations.github.service")

_github_service: "GitHubService | None" = None


def parse_commit_url(url: str) -> tuple[str, str, str]:
    """Return ``(owner, repo, sha)`` from a GitHub commit URL.

    Accepts:
    - ``https://github.com/owner/repo/commit/<sha>``
    - ``https://github.com/owner/repo/commit/<sha>/files``

    Raises ``ValueError`` for unrecognisable URLs.
    """
    parsed = urlparse(str(url))
    segments = [s for s in parsed.path.split("/") if s]
    try:
        idx = segments.index("commit")
    except ValueError:
        raise ValueError(f"Cannot parse GitHub commit URL (no 'commit' segment): {url}")
    if idx < 2 or idx + 1 >= len(segments):
        raise ValueError(f"Unexpected GitHub commit URL structure: {url}")
    return segments[idx - 2], segments[idx - 1], segments[idx + 1]


def parse_repo_url(url: str) -> tuple[str, str]:
    """Return ``(owner, repo)`` from a GitHub repository URL.

    Strips a trailing ``.git`` suffix if present.
    """
    parsed = urlparse(str(url))
    segments = [s for s in parsed.path.split("/") if s]
    if len(segments) < 2:
        raise ValueError(f"Cannot parse GitHub repo URL: {url}")
    repo = segments[1].removesuffix(".git")
    return segments[0], repo


class GitHubService:
    """Domain-level service wrapping ``GitHubClient``.

    All methods accept raw URL strings (as stored in domain schemas) and
    return typed value objects.
    """

    def __init__(self, client: GitHubClient) -> None:
        self._client = client

    async def get_commit(self, commit_url: str) -> CommitInfo:
        """Fetch and validate a commit by its HTML URL."""
        owner, repo, sha = parse_commit_url(commit_url)
        logger.debug("Fetching commit", extra={"owner": owner, "repo": repo, "sha": sha[:8]})
        return await self._client.get_commit(owner, repo, sha)

    async def get_repository(self, repo_url: str) -> RepositoryInfo:
        """Fetch repository metadata by its HTML URL."""
        owner, repo = parse_repo_url(repo_url)
        logger.debug("Fetching repo", extra={"owner": owner, "repo": repo})
        return await self._client.get_repository(owner, repo)

    async def list_recent_commits(
        self, repo_url: str, since: datetime | None = None, per_page: int = 30
    ) -> list[CommitInfo]:
        """List the most recent commits from a repository."""
        owner, repo = parse_repo_url(repo_url)
        return await self._client.list_commits(owner, repo, since=since, per_page=per_page)

    async def close(self) -> None:
        await self._client.close()


def get_github_service() -> GitHubService | None:
    """Return the singleton GitHubService, or ``None`` if not configured.

    Lazily initialises on first call using ``settings.github_token``.
    Returns ``None`` when the token is not set so callers can skip
    GitHub-dependent work gracefully.
    """
    global _github_service
    if _github_service is not None:
        return _github_service

    from app.core.config import settings
    token = getattr(settings, "github_token", None)
    if not token:
        return None

    _github_service = GitHubService(GitHubClient(token=token))
    return _github_service
