"""Async GitHub REST API client.

Wraps ``httpx.AsyncClient`` and maps raw responses to typed schemas.
Raises ``InfrastructureException`` on non-2xx status codes.

Requires ``httpx>=0.27``.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from app.integrations.github.schemas import CommitInfo, RepositoryInfo
from app.shared.exceptions import InfrastructureException

try:
    import httpx
    _HTTPX_AVAILABLE = True
except ImportError:
    httpx = None  # type: ignore[assignment]
    _HTTPX_AVAILABLE = False

logger = logging.getLogger("project_defense.integrations.github.client")

_GITHUB_API_BASE = "https://api.github.com"
_DEFAULT_TIMEOUT = 10.0
_API_VERSION_HEADER = "application/vnd.github.v3+json"


class GitHubClient:
    """Async client for the GitHub REST API.

    Parameters
    ----------
    token:
        Personal Access Token or GitHub App installation token.  If ``None``
        the client uses unauthenticated requests (60 req/h rate limit).
    base_url:
        Override the API base URL — useful for GitHub Enterprise or testing.
    """

    def __init__(self, token: str | None = None, base_url: str = _GITHUB_API_BASE) -> None:
        if not _HTTPX_AVAILABLE:
            raise InfrastructureException("httpx is required — run: pip install httpx")
        headers: dict[str, str] = {"Accept": _API_VERSION_HEADER}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers=headers,
            timeout=_DEFAULT_TIMEOUT,
            follow_redirects=True,
        )

    async def get_commit(self, owner: str, repo: str, sha: str) -> CommitInfo:
        """Fetch a single commit by SHA."""
        response = await self._request("GET", f"/repos/{owner}/{repo}/commits/{sha}")
        return CommitInfo.from_api_response(response)

    async def get_repository(self, owner: str, repo: str) -> RepositoryInfo:
        """Fetch repository metadata."""
        response = await self._request("GET", f"/repos/{owner}/{repo}")
        return RepositoryInfo.from_api_response(response)

    async def list_commits(
        self,
        owner: str,
        repo: str,
        since: datetime | None = None,
        per_page: int = 30,
    ) -> list[CommitInfo]:
        """List recent commits for a repository branch."""
        params: dict[str, Any] = {"per_page": per_page}
        if since is not None:
            params["since"] = since.isoformat()
        items = await self._request("GET", f"/repos/{owner}/{repo}/commits", params=params)
        return [CommitInfo.from_api_response(c) for c in items]

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "GitHubClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def _request(self, method: str, path: str, params: dict | None = None) -> Any:
        response = await self._client.request(method, path, params=params)
        self._raise_for_status(response)
        return response.json()

    def _raise_for_status(self, response: "httpx.Response") -> None:
        if response.status_code == 404:
            raise InfrastructureException(f"GitHub resource not found: {response.url}")
        if response.status_code == 403:
            raise InfrastructureException(
                "GitHub API rate limit exceeded or forbidden — check token permissions"
            )
        if response.status_code == 401:
            raise InfrastructureException("GitHub authentication failed — invalid token")
        if response.is_error:
            raise InfrastructureException(
                f"GitHub API error {response.status_code}: {response.text[:200]}"
            )
