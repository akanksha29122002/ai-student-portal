"""GitHub OAuth service.

Supports real GitHub OAuth (when GITHUB_CLIENT_ID/SECRET are set)
and a safe mock mode (GITHUB_MOCK_MODE=true) for local development.

NEVER enable mock mode in production — the startup guard in main.py enforces this.
"""
from __future__ import annotations

import logging
from uuid import UUID

from app.integrations.github.store import GitHubMemoryStore
from app.schemas.github import (
    GitHubConnection,
    GitHubConnectionCreate,
    GitHubStatusResponse,
    MockRepositoryInfo,
)
from app.shared.exceptions import ForbiddenException, InfrastructureException

logger = logging.getLogger("project_defense.integrations.github.oauth")

_MOCK_USER_LOGIN = "mock-github-user"
_MOCK_USER_ID = 12345678
_MOCK_REPOS: list[dict] = [
    {
        "id": 100001,
        "name": "my-project",
        "full_name": "mock-github-user/my-project",
        "private": False,
        "default_branch": "main",
        "html_url": "https://github.com/mock-github-user/my-project",
        "clone_url": "https://github.com/mock-github-user/my-project.git",
    },
    {
        "id": 100002,
        "name": "student-portal",
        "full_name": "mock-github-user/student-portal",
        "private": True,
        "default_branch": "main",
        "html_url": "https://github.com/mock-github-user/student-portal",
        "clone_url": "https://github.com/mock-github-user/student-portal.git",
    },
]


class GitHubOAuthService:
    """Manages GitHub OAuth connections for organisations."""

    def __init__(self, store: GitHubMemoryStore, mock_mode: bool = False) -> None:
        self._store = store
        self._mock_mode = mock_mode

    # ------------------------------------------------------------------
    # Connect / Disconnect
    # ------------------------------------------------------------------

    def get_authorization_url(self, state: str) -> str:
        """Return GitHub OAuth authorisation URL (or mock redirect)."""
        if self._mock_mode:
            return (
                "http://localhost:8000/integrations/github/callback"
                f"?code=mock_code&state={state}"
            )
        from app.core.config import settings
        client_id = getattr(settings, "github_client_id", "")
        if not client_id:
            raise InfrastructureException(
                "GITHUB_CLIENT_ID is not configured. "
                "Set PROJECT_DEFENSE_GITHUB_CLIENT_ID or enable GITHUB_MOCK_MODE."
            )
        return (
            f"https://github.com/login/oauth/authorize"
            f"?client_id={client_id}&scope=repo,read:user&state={state}"
        )

    async def handle_callback(
        self,
        code: str,
        organization_id: UUID,
        user_id: UUID,
    ) -> GitHubConnection:
        """Exchange OAuth code for token and persist the connection."""
        if self._mock_mode:
            logger.info("Mock OAuth callback for org=%s", organization_id)
            return self._store.save_connection(GitHubConnectionCreate(
                organization_id=organization_id,
                user_id=user_id,
                github_user_login=_MOCK_USER_LOGIN,
                github_user_id=_MOCK_USER_ID,
                access_token="mock_token_do_not_use_in_production",
                token_scope="repo,read:user",
            ))

        access_token, scope = await self._exchange_code(code)
        user_info = await self._fetch_github_user(access_token)
        return self._store.save_connection(GitHubConnectionCreate(
            organization_id=organization_id,
            user_id=user_id,
            github_user_login=user_info["login"],
            github_user_id=user_info["id"],
            access_token=access_token,
            token_scope=scope,
        ))

    def disconnect(self, organization_id: UUID) -> None:
        """Remove the GitHub connection for an organisation."""
        self._store.remove_connection(organization_id)
        logger.info("GitHub connection removed for org=%s", organization_id)

    # ------------------------------------------------------------------
    # Status / Repositories
    # ------------------------------------------------------------------

    def get_status(self, organization_id: UUID) -> GitHubStatusResponse:
        connection = self._store.get_connection(organization_id)
        if connection is None:
            return GitHubStatusResponse(connected=False, mock_mode=self._mock_mode)
        return GitHubStatusResponse(
            connected=True,
            github_user_login=connection.github_user_login,
            token_scope=connection.token_scope,
            mock_mode=self._mock_mode,
        )

    def list_repositories(self, organization_id: UUID) -> list[MockRepositoryInfo]:
        """List repositories accessible via the org's GitHub connection."""
        connection = self._store.get_connection(organization_id)
        if connection is None:
            raise ForbiddenException("GitHub is not connected for this organisation")
        if self._mock_mode:
            return [MockRepositoryInfo(**r) for r in _MOCK_REPOS]
        # TODO: fetch from GitHub API using stored token
        return [MockRepositoryInfo(**r) for r in _MOCK_REPOS]

    # ------------------------------------------------------------------
    # Internal — real OAuth helpers
    # ------------------------------------------------------------------

    async def _exchange_code(self, code: str) -> tuple[str, str]:
        try:
            import httpx
        except ImportError:
            raise InfrastructureException("httpx is required for OAuth token exchange")

        from app.core.config import settings
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://github.com/login/oauth/access_token",
                json={
                    "client_id": settings.github_client_id,
                    "client_secret": settings.github_client_secret,
                    "code": code,
                },
                headers={"Accept": "application/json"},
                timeout=15.0,
            )
        data = resp.json()
        token = data.get("access_token", "")
        scope = data.get("scope", "")
        if not token:
            raise InfrastructureException(
                f"GitHub token exchange failed: {data.get('error', 'unknown error')}"
            )
        return token, scope

    async def _fetch_github_user(self, token: str) -> dict:
        try:
            import httpx
        except ImportError:
            raise InfrastructureException("httpx is required for GitHub API calls")

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                timeout=10.0,
            )
        if resp.is_error:
            raise InfrastructureException(f"GitHub API error: {resp.status_code}")
        return resp.json()
