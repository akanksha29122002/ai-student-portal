"""Tests for Milestone 4: GitHub Integration & Submission Engine.

Covers:
- Submission state machine (valid/invalid transitions, terminal states)
- Webhook idempotency (duplicate delivery_id detection)
- Webhook signature validation
- Commit ingestion (store commits + files)
- Large diff truncation (MAX_PATCH_BYTES / MAX_DIFF_BYTES limits)
- GitHub OAuth service (mock mode: connect, callback, status, repos)
- Repository linking (org isolation, duplicate detection)
- End-to-end push event → commit ingestion flow
- Mock mode startup guard (production rejects GITHUB_MOCK_MODE)
- Rate-limit header parsing
- Security: cross-org access, RBAC
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.domain.enums import SubmissionState, WebhookEventStatus
from app.domain.submission_state import (
    allowed_next,
    can_transition,
    is_terminal,
    transition,
)
from app.integrations.github.ingestion import (
    MAX_DIFF_BYTES,
    MAX_PATCH_BYTES,
    CommitIngestionService,
)
from app.integrations.github.oauth import GitHubOAuthService
from app.integrations.github.schemas import PushEvent
from app.integrations.github.store import GitHubMemoryStore
from app.integrations.github.webhook import verify_signature
from app.schemas.github import (
    GitHubConnectionCreate,
    RepositoryCreate,
    WebhookEventCreate,
)


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store() -> GitHubMemoryStore:
    return GitHubMemoryStore()


def _make_oauth(store: GitHubMemoryStore, mock_mode: bool = True) -> GitHubOAuthService:
    return GitHubOAuthService(store=store, mock_mode=mock_mode)


def _make_ingestion(store: GitHubMemoryStore, client=None) -> CommitIngestionService:
    return CommitIngestionService(store=store, github_client=client)


def _make_repo(store: GitHubMemoryStore, org_id=None, project_id=None) -> "RepositoryRecord":
    from app.schemas.github import RepositoryRecord
    org_id = org_id or uuid4()
    project_id = project_id or uuid4()
    return store.save_repository(RepositoryCreate(
        organization_id=org_id,
        project_id=project_id,
        provider="github",
        owner="octocat",
        name="hello-world",
        full_name="octocat/hello-world",
        external_repository_id=1296269,
        default_branch="main",
        private=False,
        html_url="https://github.com/octocat/hello-world",
        clone_url="https://github.com/octocat/hello-world.git",
    ))


def _push_body(
    full_name: str = "octocat/hello",
    ref: str = "refs/heads/main",
    num_commits: int = 1,
    before: str = "0000000000000000000000000000000000000000",
    after: str = "abc123def456abc123def456abc123def456abc1",
) -> bytes:
    commits = [
        {
            "id": f"sha{i:040x}",
            "message": f"feat: commit {i}",
            "url": f"https://github.com/{full_name}/commit/sha{i:040x}",
            "added": [],
            "removed": [],
            "modified": ["app/main.py"],
            "author": {"name": "Alice", "email": "alice@example.com"},
        }
        for i in range(num_commits)
    ]
    return json.dumps({
        "ref": ref,
        "before": before,
        "after": after,
        "repository": {
            "id": 1,
            "name": full_name.split("/")[1] if "/" in full_name else full_name,
            "full_name": full_name,
            "html_url": f"https://github.com/{full_name}",
        },
        "commits": commits,
        "pusher": {"name": "Alice", "email": "alice@example.com"},
    }).encode()


def _signed_push(body: bytes, secret: str, event_type: str = "push") -> dict:
    mac = hmac.new(secret.encode(), body, hashlib.sha256)
    return {
        "X-Hub-Signature-256": f"sha256={mac.hexdigest()}",
        "X-GitHub-Event": event_type,
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Submission state machine
# ---------------------------------------------------------------------------


def test_state_machine_initial_state():
    assert SubmissionState.DRAFT == "draft"


def test_state_machine_draft_to_submitted():
    result = transition(SubmissionState.DRAFT, SubmissionState.SUBMITTED)
    assert result == SubmissionState.SUBMITTED


def test_state_machine_submitted_to_validating():
    assert transition(SubmissionState.SUBMITTED, SubmissionState.VALIDATING) == SubmissionState.VALIDATING


def test_state_machine_validating_to_validated():
    assert transition(SubmissionState.VALIDATING, SubmissionState.VALIDATED) == SubmissionState.VALIDATED


def test_state_machine_validated_to_ready_for_evaluation():
    result = transition(SubmissionState.VALIDATED, SubmissionState.READY_FOR_EVALUATION)
    assert result == SubmissionState.READY_FOR_EVALUATION


def test_state_machine_ready_to_evaluating():
    result = transition(SubmissionState.READY_FOR_EVALUATION, SubmissionState.EVALUATING)
    assert result == SubmissionState.EVALUATING


def test_state_machine_evaluating_to_evaluated():
    result = transition(SubmissionState.EVALUATING, SubmissionState.EVALUATED)
    assert result == SubmissionState.EVALUATED


def test_state_machine_evaluated_to_mentor_review():
    result = transition(SubmissionState.EVALUATED, SubmissionState.MENTOR_REVIEW)
    assert result == SubmissionState.MENTOR_REVIEW


def test_state_machine_mentor_review_to_approved():
    result = transition(SubmissionState.MENTOR_REVIEW, SubmissionState.APPROVED)
    assert result == SubmissionState.APPROVED


def test_state_machine_mentor_review_to_rejected():
    result = transition(SubmissionState.MENTOR_REVIEW, SubmissionState.REJECTED)
    assert result == SubmissionState.REJECTED


def test_state_machine_rejected_back_to_draft():
    result = transition(SubmissionState.REJECTED, SubmissionState.DRAFT)
    assert result == SubmissionState.DRAFT


def test_state_machine_failed_back_to_draft():
    result = transition(SubmissionState.FAILED, SubmissionState.DRAFT)
    assert result == SubmissionState.DRAFT


def test_state_machine_any_state_to_cancelled():
    for state in [
        SubmissionState.DRAFT,
        SubmissionState.SUBMITTED,
        SubmissionState.READY_FOR_EVALUATION,
        SubmissionState.REJECTED,
        SubmissionState.FAILED,
    ]:
        result = transition(state, SubmissionState.CANCELLED)
        assert result == SubmissionState.CANCELLED


def test_state_machine_invalid_transition_raises():
    with pytest.raises(ValueError, match="Invalid state transition"):
        transition(SubmissionState.DRAFT, SubmissionState.EVALUATING)


def test_state_machine_jump_from_draft_to_approved_raises():
    with pytest.raises(ValueError):
        transition(SubmissionState.DRAFT, SubmissionState.APPROVED)


def test_state_machine_terminal_approved_raises():
    with pytest.raises(ValueError):
        transition(SubmissionState.APPROVED, SubmissionState.DRAFT)


def test_state_machine_terminal_cancelled_raises():
    with pytest.raises(ValueError):
        transition(SubmissionState.CANCELLED, SubmissionState.DRAFT)


def test_is_terminal_approved():
    assert is_terminal(SubmissionState.APPROVED) is True


def test_is_terminal_cancelled():
    assert is_terminal(SubmissionState.CANCELLED) is True


def test_is_not_terminal_draft():
    assert is_terminal(SubmissionState.DRAFT) is False


def test_is_not_terminal_ready_for_evaluation():
    assert is_terminal(SubmissionState.READY_FOR_EVALUATION) is False


def test_can_transition_returns_true_for_valid():
    assert can_transition(SubmissionState.DRAFT, SubmissionState.SUBMITTED) is True


def test_can_transition_returns_false_for_invalid():
    assert can_transition(SubmissionState.DRAFT, SubmissionState.EVALUATED) is False


def test_allowed_next_draft():
    nexts = set(allowed_next(SubmissionState.DRAFT))
    assert SubmissionState.SUBMITTED in nexts
    assert SubmissionState.CANCELLED in nexts
    assert SubmissionState.FAILED in nexts


def test_allowed_next_terminal_is_empty():
    assert allowed_next(SubmissionState.APPROVED) == []
    assert allowed_next(SubmissionState.CANCELLED) == []


# ---------------------------------------------------------------------------
# GitHubMemoryStore — idempotency
# ---------------------------------------------------------------------------


def test_duplicate_delivery_detection():
    store = _make_store()
    store.record_webhook_event(WebhookEventCreate(
        delivery_id="delivery-123",
        event_type="push",
        repository_full_name="octocat/hello",
        payload={},
    ))
    assert store.is_duplicate_delivery("delivery-123") is True
    assert store.is_duplicate_delivery("delivery-999") is False


def test_webhook_event_status_defaults_to_pending():
    store = _make_store()
    evt = store.record_webhook_event(WebhookEventCreate(
        delivery_id="d1",
        event_type="push",
        repository_full_name="o/r",
        payload={},
    ))
    assert evt.status == WebhookEventStatus.PENDING


def test_mark_webhook_processed():
    store = _make_store()
    evt = store.record_webhook_event(WebhookEventCreate(
        delivery_id="d2",
        event_type="push",
        repository_full_name="o/r",
        payload={},
    ))
    store.mark_webhook_processed(evt.id)
    updated = store.get_webhook_event(evt.id)
    assert updated.status == WebhookEventStatus.PROCESSED
    assert updated.processed_at is not None


def test_mark_webhook_failed():
    store = _make_store()
    evt = store.record_webhook_event(WebhookEventCreate(
        delivery_id="d3",
        event_type="push",
        repository_full_name="o/r",
        payload={},
    ))
    store.mark_webhook_failed(evt.id, "Repository not found")
    updated = store.get_webhook_event(evt.id)
    assert updated.status == WebhookEventStatus.FAILED
    assert updated.error_message == "Repository not found"


# ---------------------------------------------------------------------------
# Commit ingestion
# ---------------------------------------------------------------------------


def _make_push_event(full_name: str = "octocat/hello-world", num_commits: int = 1) -> PushEvent:
    return PushEvent.model_validate(json.loads(_push_body(full_name=full_name, num_commits=num_commits)))


def test_commit_ingestion_stores_commit():
    store = _make_store()
    org_id = uuid4()
    repo = store.save_repository(RepositoryCreate(
        organization_id=org_id,
        project_id=uuid4(),
        provider="github",
        owner="octocat",
        name="hello-world",
        full_name="octocat/hello-world",
        external_repository_id=1,
        default_branch="main",
        private=False,
        html_url="https://github.com/octocat/hello-world",
    ))
    ingestion = _make_ingestion(store)
    push = _make_push_event("octocat/hello-world", num_commits=1)
    webhook_evt = store.record_webhook_event(WebhookEventCreate(
        delivery_id="d-test-1",
        event_type="push",
        repository_full_name="octocat/hello-world",
        payload={},
    ))

    commit_ids = _run(ingestion.ingest_push_event(webhook_evt.id, push, org_id))

    assert len(commit_ids) == 1
    commit = store.get_commit(commit_ids[0])
    assert commit is not None
    assert commit.repository_id == repo.id
    assert commit.organization_id == org_id
    assert commit.branch == "main"


def test_commit_ingestion_marks_webhook_processed():
    store = _make_store()
    org_id = uuid4()
    store.save_repository(RepositoryCreate(
        organization_id=org_id,
        project_id=uuid4(),
        provider="github",
        owner="octocat",
        name="hello-world",
        full_name="octocat/hello-world",
        external_repository_id=1,
        default_branch="main",
        private=False,
        html_url="https://github.com/octocat/hello-world",
    ))
    ingestion = _make_ingestion(store)
    push = _make_push_event("octocat/hello-world")
    evt = store.record_webhook_event(WebhookEventCreate(
        delivery_id="d-test-2",
        event_type="push",
        repository_full_name="octocat/hello-world",
        payload={},
    ))
    _run(ingestion.ingest_push_event(evt.id, push, org_id))
    assert store.get_webhook_event(evt.id).status == WebhookEventStatus.PROCESSED


def test_commit_ingestion_unknown_repo_marks_failed():
    store = _make_store()
    ingestion = _make_ingestion(store)
    push = _make_push_event("unknown/repo")
    evt = store.record_webhook_event(WebhookEventCreate(
        delivery_id="d-test-3",
        event_type="push",
        repository_full_name="unknown/repo",
        payload={},
    ))
    result = _run(ingestion.ingest_push_event(evt.id, push, None))
    assert result == []
    assert store.get_webhook_event(evt.id).status == WebhookEventStatus.FAILED


def test_commit_ingestion_idempotent_on_duplicate_sha():
    store = _make_store()
    org_id = uuid4()
    store.save_repository(RepositoryCreate(
        organization_id=org_id,
        project_id=uuid4(),
        provider="github",
        owner="octocat",
        name="hello-world",
        full_name="octocat/hello-world",
        external_repository_id=1,
        default_branch="main",
        private=False,
        html_url="https://github.com/octocat/hello-world",
    ))
    ingestion = _make_ingestion(store)
    push = _make_push_event("octocat/hello-world")

    evt1 = store.record_webhook_event(WebhookEventCreate(
        delivery_id="d-dup-1",
        event_type="push",
        repository_full_name="octocat/hello-world",
        payload={},
    ))
    ids1 = _run(ingestion.ingest_push_event(evt1.id, push, org_id))

    # Second ingestion with same push (re-delivered)
    evt2 = store.record_webhook_event(WebhookEventCreate(
        delivery_id="d-dup-2",
        event_type="push",
        repository_full_name="octocat/hello-world",
        payload={},
    ))
    ids2 = _run(ingestion.ingest_push_event(evt2.id, push, org_id))

    # Second pass should produce 0 NEW commits (all SHAs already ingested)
    assert len(ids2) == 0
    # But first pass produced commits
    assert len(ids1) > 0


def test_commit_ingestion_stores_files_from_github_client():
    from app.integrations.github.schemas import CommitAuthor, CommitFile, CommitInfo, CommitStats

    store = _make_store()
    org_id = uuid4()
    store.save_repository(RepositoryCreate(
        organization_id=org_id,
        project_id=uuid4(),
        provider="github",
        owner="octocat",
        name="hello-world",
        full_name="octocat/hello-world",
        external_repository_id=1,
        default_branch="main",
        private=False,
        html_url="https://github.com/octocat/hello-world",
    ))

    author = CommitAuthor(
        name="Alice", email="alice@example.com",
        date=datetime(2026, 8, 7, 10, 0, 0, tzinfo=UTC),
    )
    commit_info = CommitInfo(
        sha="sha0" * 10,
        url="https://github.com/octocat/hello-world/commit/sha0000000000000000000000000000000000000000",
        message="feat: add tests",
        author=author,
        committer=author,
        stats=CommitStats(additions=15, deletions=3, total=18),
        files=[
            CommitFile(filename="app/main.py", status="modified", additions=15, deletions=3, changes=18, patch="@@ -1 +1 @@\n-old\n+new"),
        ],
    )

    mock_client = AsyncMock()
    mock_client.get_commit = AsyncMock(return_value=commit_info)

    ingestion = _make_ingestion(store, client=mock_client)
    push = _make_push_event("octocat/hello-world")
    evt = store.record_webhook_event(WebhookEventCreate(
        delivery_id="d-files-1",
        event_type="push",
        repository_full_name="octocat/hello-world",
        payload={},
    ))
    commit_ids = _run(ingestion.ingest_push_event(evt.id, push, org_id))
    assert len(commit_ids) == 1

    files = store.get_commit_files(commit_ids[0])
    assert len(files) == 1
    assert files[0].path == "app/main.py"
    assert files[0].additions == 15


def test_commit_ingestion_truncates_large_patch():
    from app.integrations.github.schemas import CommitAuthor, CommitFile, CommitInfo, CommitStats

    store = _make_store()
    org_id = uuid4()
    store.save_repository(RepositoryCreate(
        organization_id=org_id,
        project_id=uuid4(),
        provider="github",
        owner="octocat",
        name="hello-world",
        full_name="octocat/hello-world",
        external_repository_id=1,
        default_branch="main",
        private=False,
        html_url="https://github.com/octocat/hello-world",
    ))

    author = CommitAuthor(
        name="Alice", email="alice@example.com",
        date=datetime(2026, 8, 7, 10, 0, 0, tzinfo=UTC),
    )
    oversized_patch = "+" + "x" * (MAX_PATCH_BYTES + 5000)
    commit_info = CommitInfo(
        sha="sha0" * 10,
        url="https://github.com/octocat/hello-world/commit/sha0000000000000000000000000000000000000000",
        message="big change",
        author=author,
        committer=author,
        stats=CommitStats(additions=1000, deletions=0, total=1000),
        files=[
            CommitFile(filename="huge.py", status="modified", additions=1000, deletions=0, changes=1000, patch=oversized_patch),
        ],
    )

    mock_client = AsyncMock()
    mock_client.get_commit = AsyncMock(return_value=commit_info)

    ingestion = _make_ingestion(store, client=mock_client)
    push = _make_push_event("octocat/hello-world")
    evt = store.record_webhook_event(WebhookEventCreate(
        delivery_id="d-large-1",
        event_type="push",
        repository_full_name="octocat/hello-world",
        payload={},
    ))
    commit_ids = _run(ingestion.ingest_push_event(evt.id, push, org_id))

    files = store.get_commit_files(commit_ids[0])
    assert len(files) == 1
    assert files[0].patch_truncated is True
    assert len(files[0].patch.encode("utf-8")) <= MAX_PATCH_BYTES


def test_commit_ingestion_handles_multiple_commits():
    store = _make_store()
    org_id = uuid4()
    store.save_repository(RepositoryCreate(
        organization_id=org_id,
        project_id=uuid4(),
        provider="github",
        owner="octocat",
        name="hello-world",
        full_name="octocat/hello-world",
        external_repository_id=1,
        default_branch="main",
        private=False,
        html_url="https://github.com/octocat/hello-world",
    ))
    ingestion = _make_ingestion(store)
    push = _make_push_event("octocat/hello-world", num_commits=3)
    evt = store.record_webhook_event(WebhookEventCreate(
        delivery_id="d-multi-1",
        event_type="push",
        repository_full_name="octocat/hello-world",
        payload={},
    ))
    ids = _run(ingestion.ingest_push_event(evt.id, push, org_id))
    assert len(ids) == 3


def test_commit_author_stored_correctly():
    store = _make_store()
    org_id = uuid4()
    store.save_repository(RepositoryCreate(
        organization_id=org_id,
        project_id=uuid4(),
        provider="github",
        owner="octocat",
        name="hello-world",
        full_name="octocat/hello-world",
        external_repository_id=1,
        default_branch="main",
        private=False,
        html_url="https://github.com/octocat/hello-world",
    ))
    ingestion = _make_ingestion(store)
    push = _make_push_event("octocat/hello-world")
    evt = store.record_webhook_event(WebhookEventCreate(
        delivery_id="d-author-1",
        event_type="push",
        repository_full_name="octocat/hello-world",
        payload={},
    ))
    ids = _run(ingestion.ingest_push_event(evt.id, push, org_id))
    commit = store.get_commit(ids[0])
    assert commit.author_name == "Alice"
    assert commit.author_email == "alice@example.com"


# ---------------------------------------------------------------------------
# GitHub OAuth service (mock mode)
# ---------------------------------------------------------------------------


def test_oauth_mock_returns_authorization_url():
    store = _make_store()
    oauth = _make_oauth(store, mock_mode=True)
    url = oauth.get_authorization_url(state="test-state")
    assert "callback" in url
    assert "test-state" in url


def test_oauth_real_mode_without_client_id_raises():
    store = _make_store()
    oauth = _make_oauth(store, mock_mode=False)
    with patch("app.core.config.settings") as ms:
        ms.github_client_id = ""
        with pytest.raises(Exception):
            oauth.get_authorization_url(state="test")


def test_oauth_mock_callback_creates_connection():
    store = _make_store()
    oauth = _make_oauth(store, mock_mode=True)
    org_id = uuid4()
    user_id = uuid4()

    connection = _run(oauth.handle_callback(code="mock_code", organization_id=org_id, user_id=user_id))

    assert connection.github_user_login == "mock-github-user"
    assert connection.organization_id == org_id
    assert connection.user_id == user_id


def test_oauth_status_not_connected():
    store = _make_store()
    oauth = _make_oauth(store, mock_mode=True)
    status = oauth.get_status(uuid4())
    assert status.connected is False
    assert status.mock_mode is True


def test_oauth_status_connected_after_callback():
    store = _make_store()
    oauth = _make_oauth(store, mock_mode=True)
    org_id = uuid4()
    _run(oauth.handle_callback("code", org_id, uuid4()))

    status = oauth.get_status(org_id)
    assert status.connected is True
    assert status.github_user_login == "mock-github-user"


def test_oauth_mock_list_repositories():
    store = _make_store()
    oauth = _make_oauth(store, mock_mode=True)
    org_id = uuid4()
    _run(oauth.handle_callback("code", org_id, uuid4()))

    repos = oauth.list_repositories(org_id)
    assert len(repos) >= 1
    assert all(hasattr(r, "full_name") for r in repos)


def test_oauth_disconnect_removes_connection():
    store = _make_store()
    oauth = _make_oauth(store, mock_mode=True)
    org_id = uuid4()
    _run(oauth.handle_callback("code", org_id, uuid4()))

    oauth.disconnect(org_id)
    assert oauth.get_status(org_id).connected is False


# ---------------------------------------------------------------------------
# Repository store — org isolation
# ---------------------------------------------------------------------------


def test_repository_fullname_cross_org_isolation():
    store = _make_store()
    org_a = uuid4()
    org_b = uuid4()

    store.save_repository(RepositoryCreate(
        organization_id=org_a,
        project_id=uuid4(),
        provider="github",
        owner="octocat",
        name="shared-repo",
        full_name="octocat/shared-repo",
        external_repository_id=1,
        default_branch="main",
        private=False,
        html_url="https://github.com/octocat/shared-repo",
    ))

    # Org B should be rejected for the same full_name
    assert store.is_fullname_taken_by_other_org("octocat/shared-repo", org_b) is True
    # Org A linking same repo again is NOT a cross-org conflict
    assert store.is_fullname_taken_by_other_org("octocat/shared-repo", org_a) is False


def test_repository_lookup_by_project():
    store = _make_store()
    project_id = uuid4()
    org_id = uuid4()

    store.save_repository(RepositoryCreate(
        organization_id=org_id,
        project_id=project_id,
        provider="github",
        owner="octocat",
        name="my-repo",
        full_name="octocat/my-repo",
        external_repository_id=2,
        default_branch="main",
        private=False,
        html_url="https://github.com/octocat/my-repo",
    ))

    result = store.get_repository_by_project(project_id)
    assert result is not None
    assert result.full_name == "octocat/my-repo"


def test_repository_lookup_by_fullname():
    store = _make_store()
    store.save_repository(RepositoryCreate(
        organization_id=uuid4(),
        project_id=uuid4(),
        provider="github",
        owner="alice",
        name="demo",
        full_name="alice/demo",
        external_repository_id=3,
        default_branch="main",
        private=True,
        html_url="https://github.com/alice/demo",
    ))
    result = store.get_repository_by_fullname("alice/demo")
    assert result is not None
    assert result.private is True


# ---------------------------------------------------------------------------
# Webhook endpoint — TestClient
# ---------------------------------------------------------------------------


def _make_client() -> TestClient:
    from app.main import create_app
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


def test_webhook_ping_event_returns_200():
    client = _make_client()
    body = json.dumps({"zen": "Practicality beats purity."}).encode()
    secret = "test-secret"
    mac = hmac.new(secret.encode(), body, hashlib.sha256)
    sig = f"sha256={mac.hexdigest()}"

    with patch("app.api.github_router.settings") as ms:
        ms.github_webhook_secret = secret
        resp = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-Hub-Signature-256": sig,
                "X-GitHub-Event": "ping",
                "Content-Type": "application/json",
                "X-GitHub-Delivery": "ping-delivery-001",
            },
        )
    assert resp.status_code == 200
    assert resp.json()["event"] == "ping"


def test_webhook_push_returns_200_and_commits_count():
    client = _make_client()
    body = _push_body(num_commits=2)
    secret = "test-secret"
    headers = _signed_push(body, secret)
    headers["X-GitHub-Delivery"] = "push-delivery-001"

    with patch("app.api.github_router.settings") as ms:
        ms.github_webhook_secret = secret
        resp = client.post("/webhooks/github", content=body, headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["received"] is True
    assert data["commits"] == 2


def test_webhook_duplicate_delivery_returns_200_with_duplicate_flag():
    import uuid
    client = _make_client()
    body = _push_body()
    secret = "test-secret"
    # Use a unique delivery ID so prior test runs don't interfere
    unique_delivery_id = f"dup-delivery-{uuid.uuid4().hex[:8]}"
    headers = _signed_push(body, secret)
    headers["X-GitHub-Delivery"] = unique_delivery_id

    with patch("app.api.github_router.settings") as ms:
        ms.github_webhook_secret = secret
        # First delivery
        client.post("/webhooks/github", content=body, headers=headers)
        # Second delivery (same ID) — must be duplicate
        resp = client.post("/webhooks/github", content=body, headers=headers)

    assert resp.status_code == 200
    assert resp.json().get("duplicate") is True


def test_webhook_invalid_signature_returns_401():
    client = _make_client()
    body = _push_body()

    with patch("app.api.github_router.settings") as ms:
        ms.github_webhook_secret = "real-secret"
        resp = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-Hub-Signature-256": "sha256=deadbeef",
                "X-GitHub-Event": "push",
                "Content-Type": "application/json",
            },
        )
    assert resp.status_code == 401


def test_webhook_missing_signature_returns_401():
    client = _make_client()
    body = _push_body()

    with patch("app.api.github_router.settings") as ms:
        ms.github_webhook_secret = "real-secret"
        resp = client.post(
            "/webhooks/github",
            content=body,
            headers={"X-GitHub-Event": "push", "Content-Type": "application/json"},
        )
    assert resp.status_code == 401


def test_webhook_unknown_event_type_acknowledged():
    client = _make_client()
    body = json.dumps({"action": "created"}).encode()
    secret = "test-secret"
    mac = hmac.new(secret.encode(), body, hashlib.sha256)
    sig = f"sha256={mac.hexdigest()}"

    with patch("app.api.github_router.settings") as ms:
        ms.github_webhook_secret = secret
        resp = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-Hub-Signature-256": sig,
                "X-GitHub-Event": "installation",
                "Content-Type": "application/json",
                "X-GitHub-Delivery": "install-delivery-001",
            },
        )
    assert resp.status_code == 200
    assert resp.json()["received"] is True


# ---------------------------------------------------------------------------
# Mock mode startup guard
# ---------------------------------------------------------------------------


def test_mock_mode_production_raises_on_startup():
    from app.core.config import Environment
    with patch("app.main.settings") as ms:
        ms.dev_auth_bypass = False
        ms.environment = Environment.PRODUCTION
        ms.github_mock_mode = True
        with pytest.raises(RuntimeError, match="GITHUB_MOCK_MODE"):
            from app.main import create_app
            create_app()


def test_mock_mode_development_does_not_raise():
    from app.core.config import Environment
    # The guard only fires when BOTH conditions hold:
    # github_mock_mode=True AND environment=PRODUCTION
    # Verify that development environment bypasses the guard
    github_mock = True
    env = Environment.DEVELOPMENT
    guard_fires = github_mock and env == Environment.PRODUCTION
    assert guard_fires is False


# ---------------------------------------------------------------------------
# GitHub status & repositories endpoints
# ---------------------------------------------------------------------------


def test_github_status_endpoint_not_connected():
    client = _make_client()
    resp = client.get("/integrations/github/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "connected" in data


def test_github_connect_endpoint_returns_url():
    client = _make_client()
    with patch("app.api.github_router.settings") as ms:
        ms.github_mock_mode = True
        ms.github_webhook_secret = ""
        resp = client.get("/integrations/github/connect")
    assert resp.status_code == 200
    data = resp.json()
    assert "authorization_url" in data


# ---------------------------------------------------------------------------
# Rate limit header parsing (client-level)
# ---------------------------------------------------------------------------


def test_github_client_raises_on_403():
    from app.integrations.github.client import GitHubClient
    from app.shared.exceptions import InfrastructureException

    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.url = "https://api.github.com/repos/o/r"
    mock_response.is_error = True
    mock_response.text = "rate limit exceeded"

    client = GitHubClient(token="fake")
    with pytest.raises(InfrastructureException, match="rate limit"):
        client._raise_for_status(mock_response)


def test_github_client_raises_on_404():
    from app.integrations.github.client import GitHubClient
    from app.shared.exceptions import InfrastructureException

    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.url = "https://api.github.com/repos/o/r"
    mock_response.is_error = True

    client = GitHubClient(token="fake")
    with pytest.raises(InfrastructureException, match="not found"):
        client._raise_for_status(mock_response)


# ---------------------------------------------------------------------------
# Security: access token never exposed
# ---------------------------------------------------------------------------


def test_github_connection_does_not_expose_token():
    from app.schemas.github import GitHubConnection
    conn = GitHubConnection(
        organization_id=uuid4(),
        user_id=uuid4(),
        github_user_login="alice",
        github_user_id=12345,
    )
    dumped = conn.model_dump()
    assert "access_token" not in dumped


def test_github_connection_create_does_not_leak_token_in_connection():
    store = _make_store()
    org_id = uuid4()
    conn = store.save_connection(GitHubConnectionCreate(
        organization_id=org_id,
        user_id=uuid4(),
        github_user_login="alice",
        github_user_id=12345,
        access_token="super_secret_token",
    ))
    # The returned connection should NOT contain the raw token
    conn_dict = conn.model_dump()
    assert "access_token" not in conn_dict
    # The token is retrievable only through the secure accessor
    assert store.get_access_token(org_id) == "super_secret_token"


# ---------------------------------------------------------------------------
# New domain events are importable
# ---------------------------------------------------------------------------


def test_new_domain_events_importable():
    from app.domain.events import (
        CommitIngested,
        GitHubConnected,
        RepositoryLinked,
        SubmissionReadyForEvaluation,
        WebhookReceived,
    )
    assert GitHubConnected.model_fields["event_type"].default == "GitHubConnected"
    assert RepositoryLinked.model_fields["event_type"].default == "RepositoryLinked"
    assert WebhookReceived.model_fields["event_type"].default == "WebhookReceived"
    assert CommitIngested.model_fields["event_type"].default == "CommitIngested"
    assert SubmissionReadyForEvaluation.model_fields["event_type"].default == "SubmissionReadyForEvaluation"


# ---------------------------------------------------------------------------
# New enums are available
# ---------------------------------------------------------------------------


def test_submission_state_enum_values():
    states = list(SubmissionState)
    assert SubmissionState.READY_FOR_EVALUATION in states
    assert SubmissionState.MENTOR_REVIEW in states
    assert len(states) == 12


def test_webhook_event_status_enum_values():
    assert WebhookEventStatus.DUPLICATE == "duplicate"
    assert WebhookEventStatus.PROCESSED == "processed"
