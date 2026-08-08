"""GitHub integration routes.

Existing endpoints (unchanged):
- POST /webhooks/github       — receive GitHub push / PR events
- GET  /github/commit         — fetch commit metadata by URL (staff+)
- GET  /github/repository     — fetch repository metadata by URL

New endpoints (Milestone 4):
- GET  /integrations/github/connect          — begin OAuth flow
- GET  /integrations/github/callback         — handle OAuth callback
- POST /integrations/github/disconnect       — remove GitHub connection
- GET  /integrations/github/status           — connection status
- GET  /integrations/github/repositories     — list accessible repositories
- POST /projects/{project_id}/repository     — link a repository to a project
"""
from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request, status
from uuid import uuid4 as _uuid4

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.domain.enums import UserRole
from app.integrations.github.ingestion import CommitIngestionService
from app.integrations.github.oauth import GitHubOAuthService
from app.integrations.github.schemas import CommitInfo, PushEvent, RepositoryInfo
from app.integrations.github.store import GitHubMemoryStore
from app.integrations.github.webhook import parse_push_event, verify_signature
from app.schemas.auth import CurrentUser
from app.schemas.github import (
    GitHubConnection,
    GitHubStatusResponse,
    MockRepositoryInfo,
    RepositoryCreate,
    RepositoryLinkRequest,
    RepositoryRecord,
    WebhookEventCreate,
)
from app.shared.exceptions import (
    ConflictException,
    ForbiddenException,
    InfrastructureException,
    NotFoundException,
    UnauthorizedException,
)

logger = logging.getLogger("project_defense.api.github_router")

router = APIRouter(tags=["github"])

_CurrentUser = Annotated[CurrentUser, Depends(get_current_user)]

# ---------------------------------------------------------------------------
# Module-level singletons (injected / overridden in tests)
# ---------------------------------------------------------------------------

_github_store = GitHubMemoryStore()


def _get_store() -> GitHubMemoryStore:
    return _github_store


def _get_oauth_service() -> GitHubOAuthService:
    mock_mode = getattr(settings, "github_mock_mode", False)
    return GitHubOAuthService(store=_github_store, mock_mode=mock_mode)


def _get_ingestion_service() -> CommitIngestionService:
    return CommitIngestionService(store=_github_store)


_Store = Annotated[GitHubMemoryStore, Depends(_get_store)]
_OAuth = Annotated[GitHubOAuthService, Depends(_get_oauth_service)]
_Ingestion = Annotated[CommitIngestionService, Depends(_get_ingestion_service)]

# ---------------------------------------------------------------------------
# Existing endpoints — Webhook + commit/repo info
# ---------------------------------------------------------------------------


@router.post("/webhooks/github", status_code=status.HTTP_200_OK)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    store: _Store,
    ingestion: _Ingestion,
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str = Header(default="push"),
    x_github_delivery: str | None = Header(default=None),
) -> dict:
    """Receive GitHub webhook events.

    - Validates HMAC-SHA256 signature
    - Deduplicates by X-GitHub-Delivery ID
    - Persists webhook event immediately
    - Processes push events asynchronously in background
    """
    body = await request.body()

    if not verify_signature(body, x_hub_signature_256, settings.github_webhook_secret):
        raise UnauthorizedException("Invalid webhook signature")

    # Idempotency: only deduplicate when GitHub provides a delivery ID
    if x_github_delivery and store.is_duplicate_delivery(x_github_delivery):
        logger.debug("Duplicate webhook delivery %s — ignored", x_github_delivery)
        return {"received": True, "event": x_github_event, "duplicate": True}

    delivery_id = x_github_delivery or str(_uuid4())

    if x_github_event == "ping":
        store.record_webhook_event(WebhookEventCreate(
            delivery_id=delivery_id,
            event_type="ping",
            repository_full_name="",
            payload={},
        ))
        return {"received": True, "event": "ping"}

    if x_github_event == "push":
        push = parse_push_event(body)
        webhook_event = store.record_webhook_event(WebhookEventCreate(
            delivery_id=delivery_id,
            event_type="push",
            repository_full_name=push.repo_full_name,
            payload={"ref": push.ref, "after": push.after, "commits": len(push.commits)},
        ))
        logger.info(
            "GitHub push event received",
            extra={
                "delivery_id": delivery_id,
                "repo": push.repo_full_name,
                "branch": push.branch,
                "commits": len(push.commits),
                "after": push.after[:8] if push.after else "",
            },
        )
        background_tasks.add_task(
            _ingest_push,
            ingestion,
            webhook_event.id,
            push,
            None,
        )
        return {
            "received": True,
            "event": x_github_event,
            "repo": push.repo_full_name,
            "branch": push.branch,
            "commits": len(push.commits),
        }

    # Unknown / other events — acknowledge safely
    store.record_webhook_event(WebhookEventCreate(
        delivery_id=delivery_id,
        event_type=x_github_event,
        repository_full_name="",
        payload={},
    ))
    logger.debug("Unhandled GitHub event type: %s", x_github_event)
    return {"received": True, "event": x_github_event}


async def _ingest_push(
    ingestion: CommitIngestionService,
    webhook_event_id: UUID,
    push: PushEvent,
    organization_id: UUID | None,
) -> None:
    """Background task: ingest commits from a push event."""
    try:
        await ingestion.ingest_push_event(webhook_event_id, push, organization_id)
    except Exception as exc:
        logger.error("Commit ingestion failed for event %s: %s", webhook_event_id, exc)


@router.get("/github/commit", response_model=CommitInfo)
async def get_commit_info(commit_url: str, current_user: _CurrentUser) -> CommitInfo:
    """Fetch commit metadata from GitHub by commit URL (staff+ only)."""
    if not current_user.can(
        UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN,
        UserRole.PROGRAM_MANAGER, UserRole.MENTOR, UserRole.AI_AGENT,
    ):
        raise UnauthorizedException("Insufficient permissions to fetch commit info")

    from app.integrations.github.service import get_github_service
    service = get_github_service()
    if service is None:
        raise InfrastructureException("GitHub integration is not configured")

    return await service.get_commit(commit_url)


@router.get("/github/repository", response_model=RepositoryInfo)
async def get_repository_info(repo_url: str, current_user: _CurrentUser) -> RepositoryInfo:
    """Fetch repository metadata from GitHub by URL (staff+ only)."""
    if not current_user.can(
        UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN,
        UserRole.PROGRAM_MANAGER, UserRole.MENTOR, UserRole.AI_AGENT,
    ):
        raise UnauthorizedException("Insufficient permissions to fetch repository info")

    from app.integrations.github.service import get_github_service
    service = get_github_service()
    if service is None:
        raise InfrastructureException("GitHub integration is not configured")

    return await service.get_repository(repo_url)


# ---------------------------------------------------------------------------
# New endpoints — GitHub OAuth
# ---------------------------------------------------------------------------


@router.get(
    "/integrations/github/connect",
    tags=["github-oauth"],
    summary="Start GitHub OAuth flow",
)
async def github_connect(
    current_user: _CurrentUser,
    oauth: _OAuth,
    state: str = Query(default="default"),
) -> dict:
    """Return the GitHub OAuth authorisation URL.

    The client should redirect the user to this URL.
    """
    url = oauth.get_authorization_url(state=state)
    return {"authorization_url": url, "mock_mode": getattr(settings, "github_mock_mode", False)}


@router.get(
    "/integrations/github/callback",
    response_model=GitHubConnection,
    tags=["github-oauth"],
    summary="Handle GitHub OAuth callback",
)
async def github_callback(
    current_user: _CurrentUser,
    oauth: _OAuth,
    code: str = Query(...),
    state: str = Query(default=""),
) -> GitHubConnection:
    """Handle the OAuth callback from GitHub.

    Exchanges the code for an access token and stores the connection.
    """
    org_id = current_user.organization_id
    if org_id is None:
        raise ForbiddenException("User must belong to an organisation to connect GitHub")

    return await oauth.handle_callback(
        code=code,
        organization_id=org_id,
        user_id=current_user.id,
    )


@router.post(
    "/integrations/github/disconnect",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["github-oauth"],
    summary="Disconnect GitHub from this organisation",
)
async def github_disconnect(
    current_user: _CurrentUser,
    oauth: _OAuth,
) -> None:
    """Remove the GitHub connection for the current user's organisation."""
    if not current_user.can(
        UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.PROGRAM_MANAGER,
    ):
        raise ForbiddenException("Only organisation admins can disconnect GitHub")
    org_id = current_user.organization_id
    if org_id is None:
        raise ForbiddenException("User must belong to an organisation")
    oauth.disconnect(org_id)


@router.get(
    "/integrations/github/status",
    response_model=GitHubStatusResponse,
    tags=["github-oauth"],
    summary="Get GitHub connection status for this organisation",
)
async def github_status(
    current_user: _CurrentUser,
    oauth: _OAuth,
) -> GitHubStatusResponse:
    """Return whether GitHub is connected for the current user's organisation."""
    org_id = current_user.organization_id
    if org_id is None:
        return GitHubStatusResponse(connected=False, mock_mode=getattr(settings, "github_mock_mode", False))
    return oauth.get_status(org_id)


@router.get(
    "/integrations/github/repositories",
    response_model=list[MockRepositoryInfo],
    tags=["github-oauth"],
    summary="List repositories accessible via this organisation's GitHub connection",
)
async def list_github_repositories(
    current_user: _CurrentUser,
    oauth: _OAuth,
) -> list[MockRepositoryInfo]:
    """Return repositories the connected GitHub account can access."""
    org_id = current_user.organization_id
    if org_id is None:
        raise ForbiddenException("User must belong to an organisation")
    return oauth.list_repositories(org_id)


# ---------------------------------------------------------------------------
# New endpoints — Repository linking
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/repository",
    response_model=RepositoryRecord,
    status_code=status.HTTP_201_CREATED,
    tags=["repositories"],
    summary="Link a GitHub repository to a project",
)
async def link_repository(
    project_id: UUID,
    payload: RepositoryLinkRequest,
    current_user: _CurrentUser,
    store: _Store,
    oauth: _OAuth,
) -> RepositoryRecord:
    """Link a GitHub repository (by full_name) to a project.

    Validates:
    - Project is accessible to the current user's org
    - Repository is not already linked to a different org
    - GitHub is connected for this org
    """
    org_id = current_user.organization_id

    # Org isolation: must belong to an org
    if org_id is None:
        raise ForbiddenException("User must belong to an organisation to link repositories")

    # Check GitHub is connected
    connection = store.get_connection(org_id)
    if connection is None:
        github_mock = getattr(settings, "github_mock_mode", False)
        if not github_mock:
            raise ForbiddenException(
                "GitHub is not connected for this organisation. "
                "Visit /integrations/github/connect first."
            )

    # Org isolation: full_name must not be owned by another org
    if store.is_fullname_taken_by_other_org(payload.full_name, org_id):
        raise ConflictException(
            f"Repository {payload.full_name!r} is already linked to a different organisation"
        )

    # Check for duplicate link on same project
    existing = store.get_repository_by_project(project_id)
    if existing is not None and existing.full_name == payload.full_name:
        raise ConflictException(f"Repository {payload.full_name!r} is already linked to this project")

    # Fetch repo metadata (mock or real)
    try:
        owner, repo_name = payload.full_name.split("/", 1)
    except ValueError:
        raise NotFoundException(f"Invalid repository format: {payload.full_name!r}. Use owner/repo")

    repo_info = await _fetch_repo_info(payload.full_name, store, org_id)

    record = store.save_repository(RepositoryCreate(
        organization_id=org_id,
        project_id=project_id,
        provider="github",
        owner=owner,
        name=repo_name,
        full_name=payload.full_name,
        external_repository_id=repo_info.get("id", 0),
        default_branch=repo_info.get("default_branch", "main"),
        private=repo_info.get("private", False),
        html_url=repo_info.get("html_url", f"https://github.com/{payload.full_name}"),
        clone_url=repo_info.get("clone_url", ""),
    ))

    logger.info(
        "Repository linked",
        extra={
            "project_id": str(project_id),
            "repo_id": str(record.id),
            "full_name": payload.full_name,
            "org_id": str(org_id),
        },
    )
    return record


async def _fetch_repo_info(
    full_name: str,
    store: GitHubMemoryStore,
    org_id: UUID,
) -> dict:
    """Fetch repo metadata from GitHub API or fall back to mock data."""
    from app.integrations.github.service import get_github_service

    service = get_github_service()
    if service is not None:
        try:
            info = await service.get_repository(f"https://github.com/{full_name}")
            owner, repo_name = full_name.split("/", 1)
            return {
                "id": info.github_id,
                "default_branch": info.default_branch,
                "private": info.private,
                "html_url": info.url,
                "clone_url": f"https://github.com/{full_name}.git",
            }
        except Exception as exc:
            logger.warning("Could not fetch repo info for %s: %s", full_name, exc)

    # Fall back to minimal info (mock mode or GitHub not configured)
    owner, repo_name = full_name.split("/", 1)
    return {
        "id": abs(hash(full_name)) % 10_000_000,
        "default_branch": "main",
        "private": False,
        "html_url": f"https://github.com/{full_name}",
        "clone_url": f"https://github.com/{full_name}.git",
    }
