"""Tests for the GitHub Integration milestone.

Covers:
- parse_commit_url / parse_repo_url URL parsing utilities
- verify_signature HMAC webhook verification
- parse_push_event webhook body parsing
- GitHubService: delegates to GitHubClient with parsed coordinates
- GitHubValidationHandler: no-op paths and service integration
- GitHub webhook and REST API endpoints via TestClient
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.domain.events import DomainEvent, SubmissionReceived
from app.integrations.github.event_handler import GitHubValidationHandler
from app.integrations.github.schemas import (
    CommitAuthor,
    CommitInfo,
    CommitStats,
    PushEvent,
    RepositoryInfo,
)
from app.integrations.github.service import GitHubService, parse_commit_url, parse_repo_url
from app.integrations.github.webhook import parse_push_event, verify_signature


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Fixtures — reusable test data
# ---------------------------------------------------------------------------


def _commit_author() -> CommitAuthor:
    return CommitAuthor(
        name="Alice",
        email="alice@example.com",
        date=datetime(2026, 8, 7, 10, 0, 0, tzinfo=timezone.utc),
    )


def _commit_info(sha: str = "abc123def456abc123def456abc123def456abc1") -> CommitInfo:
    author = _commit_author()
    return CommitInfo(
        sha=sha,
        url=f"https://github.com/octocat/hello-world/commit/{sha}",
        message="feat: add rate limiting",
        author=author,
        committer=author,
        stats=CommitStats(additions=10, deletions=2, total=12),
        files=[],
    )


def _repo_info() -> RepositoryInfo:
    return RepositoryInfo.model_validate({
        "id": 1296269,
        "name": "hello-world",
        "full_name": "octocat/hello-world",
        "description": "A test repo",
        "private": False,
        "default_branch": "main",
        "language": "Python",
        "stargazers_count": 42,
        "forks_count": 7,
        "html_url": "https://github.com/octocat/hello-world",
    })


# ---------------------------------------------------------------------------
# parse_commit_url
# ---------------------------------------------------------------------------


def test_parse_commit_url_standard():
    owner, repo, sha = parse_commit_url("https://github.com/octocat/hello-world/commit/abc123")
    assert owner == "octocat"
    assert repo == "hello-world"
    assert sha == "abc123"


def test_parse_commit_url_with_trailing_path():
    owner, repo, sha = parse_commit_url(
        "https://github.com/octocat/hello-world/commit/abc123/files"
    )
    assert owner == "octocat"
    assert repo == "hello-world"
    assert sha == "abc123"


def test_parse_commit_url_full_sha():
    sha = "abc123def456abc123def456abc123def456abc1"
    owner, repo, result_sha = parse_commit_url(
        f"https://github.com/myorg/my-repo/commit/{sha}"
    )
    assert owner == "myorg"
    assert repo == "my-repo"
    assert result_sha == sha


def test_parse_commit_url_raises_on_missing_commit_segment():
    with pytest.raises(ValueError, match="commit"):
        parse_commit_url("https://github.com/octocat/hello-world/tree/main")


def test_parse_commit_url_raises_on_too_few_segments():
    with pytest.raises(ValueError):
        parse_commit_url("https://github.com/octocat/commit/abc123")


# ---------------------------------------------------------------------------
# parse_repo_url
# ---------------------------------------------------------------------------


def test_parse_repo_url_standard():
    owner, repo = parse_repo_url("https://github.com/octocat/hello-world")
    assert owner == "octocat"
    assert repo == "hello-world"


def test_parse_repo_url_strips_git_suffix():
    owner, repo = parse_repo_url("https://github.com/octocat/hello-world.git")
    assert owner == "octocat"
    assert repo == "hello-world"


def test_parse_repo_url_raises_on_too_few_segments():
    with pytest.raises(ValueError):
        parse_repo_url("https://github.com/octocat")


def test_parse_repo_url_org_with_hyphen():
    owner, repo = parse_repo_url("https://github.com/my-org/my-repo")
    assert owner == "my-org"
    assert repo == "my-repo"


# ---------------------------------------------------------------------------
# verify_signature
# ---------------------------------------------------------------------------


def _make_signature(body: bytes, secret: str) -> str:
    mac = hmac.new(secret.encode(), body, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


def test_verify_signature_valid():
    body = b'{"ref": "refs/heads/main"}'
    secret = "my-webhook-secret"
    sig = _make_signature(body, secret)
    assert verify_signature(body, sig, secret) is True


def test_verify_signature_wrong_secret():
    body = b'{"ref": "refs/heads/main"}'
    sig = _make_signature(body, "real-secret")
    assert verify_signature(body, sig, "wrong-secret") is False


def test_verify_signature_tampered_body():
    body = b'{"ref": "refs/heads/main"}'
    secret = "my-webhook-secret"
    sig = _make_signature(body, secret)
    tampered = b'{"ref": "refs/heads/evil"}'
    assert verify_signature(tampered, sig, secret) is False


def test_verify_signature_missing_header():
    body = b'{"ref": "refs/heads/main"}'
    assert verify_signature(body, None, "secret") is False


def test_verify_signature_empty_secret():
    body = b'{"ref": "refs/heads/main"}'
    sig = _make_signature(body, "secret")
    assert verify_signature(body, sig, "") is False


def test_verify_signature_empty_header():
    body = b'{"ref": "refs/heads/main"}'
    assert verify_signature(body, "", "secret") is False


# ---------------------------------------------------------------------------
# parse_push_event
# ---------------------------------------------------------------------------


def _push_body(ref: str = "refs/heads/main", num_commits: int = 1) -> bytes:
    commits = [
        {
            "id": f"sha{i}",
            "message": f"commit {i}",
            "url": f"https://github.com/octocat/hello/commit/sha{i}",
            "added": [],
            "removed": [],
            "modified": ["app/main.py"],
            "author": {"name": "Alice", "email": "alice@example.com"},
        }
        for i in range(num_commits)
    ]
    return json.dumps({
        "ref": ref,
        "before": "0000000000000000000000000000000000000000",
        "after": "abc123def456abc123def456abc123def456abc1",
        "repository": {
            "id": 1,
            "name": "hello",
            "full_name": "octocat/hello",
            "html_url": "https://github.com/octocat/hello",
        },
        "commits": commits,
        "pusher": {"name": "Alice", "email": "alice@example.com"},
    }).encode()


def test_parse_push_event_branch_property():
    event = parse_push_event(_push_body("refs/heads/feature/auth"))
    assert event.branch == "feature/auth"


def test_parse_push_event_main_branch():
    event = parse_push_event(_push_body("refs/heads/main"))
    assert event.branch == "main"


def test_parse_push_event_repo_full_name():
    event = parse_push_event(_push_body())
    assert event.repo_full_name == "octocat/hello"


def test_parse_push_event_commit_count():
    event = parse_push_event(_push_body(num_commits=3))
    assert len(event.commits) == 3


def test_parse_push_event_extra_fields_ignored():
    body = json.dumps({
        "ref": "refs/heads/main",
        "repository": {"full_name": "o/r", "html_url": "https://github.com/o/r"},
        "commits": [],
        "some_unknown_future_field": "should_be_ignored",
        "nested_unknown": {"a": 1},
    }).encode()
    event = parse_push_event(body)
    assert isinstance(event, PushEvent)


# ---------------------------------------------------------------------------
# GitHubService (mocked client)
# ---------------------------------------------------------------------------


def test_github_service_get_commit_delegates_to_client():
    client = AsyncMock()
    client.get_commit = AsyncMock(return_value=_commit_info())
    service = GitHubService(client)

    result = _run(service.get_commit("https://github.com/octocat/hello-world/commit/abc123"))

    client.get_commit.assert_called_once_with("octocat", "hello-world", "abc123")
    assert result.sha == _commit_info().sha


def test_github_service_get_repository_delegates_to_client():
    client = AsyncMock()
    client.get_repository = AsyncMock(return_value=_repo_info())
    service = GitHubService(client)

    result = _run(service.get_repository("https://github.com/octocat/hello-world"))

    client.get_repository.assert_called_once_with("octocat", "hello-world")
    assert result.name == "hello-world"


def test_github_service_list_recent_commits_delegates_to_client():
    client = AsyncMock()
    commits = [_commit_info(f"sha{i}" * 5) for i in range(3)]
    client.list_commits = AsyncMock(return_value=commits)
    service = GitHubService(client)

    result = _run(service.list_recent_commits("https://github.com/octocat/hello-world"))

    client.list_commits.assert_called_once_with(
        "octocat", "hello-world", since=None, per_page=30
    )
    assert len(result) == 3


def test_github_service_get_commit_raises_on_invalid_url():
    client = AsyncMock()
    service = GitHubService(client)

    with pytest.raises(ValueError):
        _run(service.get_commit("https://github.com/octocat/hello-world/tree/main"))


def test_github_service_get_repository_raises_on_invalid_url():
    client = AsyncMock()
    service = GitHubService(client)

    with pytest.raises(ValueError):
        _run(service.get_repository("https://github.com/octocat"))


# ---------------------------------------------------------------------------
# GitHubValidationHandler
# ---------------------------------------------------------------------------


def _submission_event(commit_url: str | None = None) -> SubmissionReceived:
    payload: dict = {"task_id": str(uuid4())}
    if commit_url:
        payload["commit_url"] = commit_url
    return SubmissionReceived(aggregate_id=uuid4(), payload=payload)


def test_validation_handler_noop_when_no_commit_url():
    handler = GitHubValidationHandler()
    event = _submission_event(commit_url=None)
    _run(handler.handle(event))  # should not raise


def test_validation_handler_noop_when_github_not_configured():
    handler = GitHubValidationHandler()
    event = _submission_event(commit_url="https://github.com/o/r/commit/abc")

    with patch(
        "app.integrations.github.service.get_github_service", return_value=None
    ):
        _run(handler.handle(event))  # should not raise


def test_validation_handler_calls_service_on_valid_event():
    handler = GitHubValidationHandler()
    event = _submission_event(commit_url="https://github.com/o/r/commit/abc123")

    mock_service = AsyncMock()
    mock_service.get_commit = AsyncMock(return_value=_commit_info("abc123"))

    with patch(
        "app.integrations.github.service.get_github_service",
        return_value=mock_service,
    ):
        _run(handler.handle(event))

    mock_service.get_commit.assert_called_once_with("https://github.com/o/r/commit/abc123")


def test_validation_handler_swallows_service_exceptions():
    handler = GitHubValidationHandler()
    event = _submission_event(commit_url="https://github.com/o/r/commit/abc")

    mock_service = AsyncMock()
    mock_service.get_commit = AsyncMock(side_effect=Exception("network timeout"))

    with patch(
        "app.integrations.github.service.get_github_service",
        return_value=mock_service,
    ):
        _run(handler.handle(event))  # must not propagate the exception


def test_validation_handler_event_type_is_submission_received():
    assert GitHubValidationHandler.event_type == "SubmissionReceived"


# ---------------------------------------------------------------------------
# Webhook endpoint — TestClient
# ---------------------------------------------------------------------------


def _make_client() -> TestClient:
    from app.main import create_app
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


def _signed_push_request(
    client: TestClient,
    body: bytes,
    secret: str,
    event_type: str = "push",
):
    sig = _make_signature(body, secret)
    return client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-Hub-Signature-256": sig,
            "X-GitHub-Event": event_type,
            "Content-Type": "application/json",
        },
    )


def test_webhook_valid_push_event_returns_200():
    client = _make_client()
    body = _push_body()
    secret = "test-webhook-secret"

    with patch("app.api.github_router.settings") as mock_settings:
        mock_settings.github_webhook_secret = secret
        response = _signed_push_request(client, body, secret)

    assert response.status_code == 200
    data = response.json()
    assert data["received"] is True
    assert data["event"] == "push"


def test_webhook_invalid_signature_returns_401():
    client = _make_client()
    body = _push_body()

    with patch("app.api.github_router.settings") as mock_settings:
        mock_settings.github_webhook_secret = "real-secret"
        response = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-Hub-Signature-256": "sha256=deadbeef",
                "X-GitHub-Event": "push",
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == 401


def test_webhook_missing_signature_returns_401():
    client = _make_client()
    body = _push_body()

    with patch("app.api.github_router.settings") as mock_settings:
        mock_settings.github_webhook_secret = "real-secret"
        response = client.post(
            "/webhooks/github",
            content=body,
            headers={"X-GitHub-Event": "push", "Content-Type": "application/json"},
        )

    assert response.status_code == 401


def test_webhook_non_push_event_acknowledged():
    client = _make_client()
    body = json.dumps({"action": "opened"}).encode()
    secret = "test-secret"

    with patch("app.api.github_router.settings") as mock_settings:
        mock_settings.github_webhook_secret = secret
        response = _signed_push_request(client, body, secret, event_type="pull_request")

    assert response.status_code == 200
    assert response.json()["received"] is True
    assert response.json()["event"] == "pull_request"


def test_webhook_push_event_includes_repo_and_branch():
    client = _make_client()
    body = _push_body("refs/heads/feature/auth", num_commits=2)
    secret = "test-secret"

    with patch("app.api.github_router.settings") as mock_settings:
        mock_settings.github_webhook_secret = secret
        response = _signed_push_request(client, body, secret)

    assert response.status_code == 200
    data = response.json()
    assert data["branch"] == "feature/auth"
    assert data["commits"] == 2
    assert data["repo"] == "octocat/hello"
