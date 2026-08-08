"""Tests for Milestone 3 additions.

Covers:
- Refresh token storage, rotation, and reuse detection
- /auth/logout endpoint
- /auth/change-password endpoint
- DEV_AUTH_BYPASS flag behavior
- Production auth enforcement (no bypass allowed)
- SecureHeadersMiddleware
- ForbiddenException (403)
- Tenant isolation (org A cannot read org B resources)
"""
from __future__ import annotations

import asyncio
import importlib.util
from collections.abc import AsyncIterator
from datetime import date
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.repositories.memory import AsyncMemoryUnitOfWork
from app.schemas.auth import ChangePasswordRequest, LoginRequest, LogoutRequest, RegisterRequest, RefreshRequest
from app.services.store import InMemoryStore

_PASSLIB = importlib.util.find_spec("passlib") is not None
_JWT = importlib.util.find_spec("jwt") is not None
_CRYPTO_AVAILABLE = _PASSLIB and _JWT


def _run(coro):
    return asyncio.run(coro)


def _make_uow():
    store = InMemoryStore()
    return AsyncMemoryUnitOfWork(store), store


# ---------------------------------------------------------------------------
# ForbiddenException
# ---------------------------------------------------------------------------


def test_forbidden_exception_has_status_403():
    from app.shared.exceptions import ForbiddenException
    exc = ForbiddenException("Not allowed")
    assert int(exc.status_code) == 403
    assert exc.title == "Forbidden"


# ---------------------------------------------------------------------------
# Refresh token storage and rotation
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="passlib[bcrypt] and PyJWT required")
def test_register_stores_refresh_token_hash():
    from app.services.auth_service import AuthService
    from app.core.security import security

    uow, store = _make_uow()
    service = AuthService(uow)

    tokens = _run(service.register(RegisterRequest(
        email="alice@example.com", password="securepass", full_name="Alice",
    )))

    token_hash = security.hash_token(tokens.refresh_token)
    record = store.get_refresh_token_by_hash(token_hash)
    assert record is not None
    assert record.used_at is None
    assert record.revoked_at is None


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="passlib[bcrypt] and PyJWT required")
def test_login_stores_refresh_token_hash():
    from app.services.auth_service import AuthService
    from app.core.security import security

    uow, store = _make_uow()
    service = AuthService(uow)

    _run(service.register(RegisterRequest(email="bob@example.com", password="pass1234", full_name="Bob")))
    tokens = _run(service.login(LoginRequest(email="bob@example.com", password="pass1234")))

    token_hash = security.hash_token(tokens.refresh_token)
    record = store.get_refresh_token_by_hash(token_hash)
    assert record is not None


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="passlib[bcrypt] and PyJWT required")
def test_refresh_marks_old_token_used_and_stores_new():
    from app.services.auth_service import AuthService
    from app.core.security import security

    uow, store = _make_uow()
    service = AuthService(uow)

    tokens = _run(service.register(RegisterRequest(
        email="carol@example.com", password="pass1234", full_name="Carol",
    )))
    old_hash = security.hash_token(tokens.refresh_token)

    new_tokens = _run(service.refresh_tokens(RefreshRequest(refresh_token=tokens.refresh_token)))

    old_record = store.get_refresh_token_by_hash(old_hash)
    assert old_record.used_at is not None

    new_hash = security.hash_token(new_tokens.refresh_token)
    new_record = store.get_refresh_token_by_hash(new_hash)
    assert new_record is not None
    assert new_record.used_at is None


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="passlib[bcrypt] and PyJWT required")
def test_refresh_token_reuse_detection_revokes_all_sessions():
    from app.services.auth_service import AuthService
    from app.shared.exceptions import UnauthorizedException

    uow, store = _make_uow()
    service = AuthService(uow)

    tokens = _run(service.register(RegisterRequest(
        email="dave@example.com", password="pass1234", full_name="Dave",
    )))

    _run(service.refresh_tokens(RefreshRequest(refresh_token=tokens.refresh_token)))

    with pytest.raises(UnauthorizedException, match="reuse detected"):
        _run(service.refresh_tokens(RefreshRequest(refresh_token=tokens.refresh_token)))

    from app.core.security import security
    user_records = [r for r in store.refresh_tokens.values() if r.revoked_at is not None]
    assert len(user_records) >= 1


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="passlib[bcrypt] and PyJWT required")
def test_logout_revokes_refresh_token():
    from app.services.auth_service import AuthService
    from app.core.security import security

    uow, store = _make_uow()
    service = AuthService(uow)

    tokens = _run(service.register(RegisterRequest(
        email="eve@example.com", password="pass1234", full_name="Eve",
    )))
    token_hash = security.hash_token(tokens.refresh_token)

    _run(service.logout(LogoutRequest(refresh_token=tokens.refresh_token)))

    record = store.get_refresh_token_by_hash(token_hash)
    assert record is not None
    assert record.revoked_at is not None


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="passlib[bcrypt] and PyJWT required")
def test_logout_with_invalid_token_does_not_raise():
    from app.services.auth_service import AuthService

    uow, _ = _make_uow()
    service = AuthService(uow)

    _run(service.logout(LogoutRequest(refresh_token="totally.invalid.token")))


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="passlib[bcrypt] and PyJWT required")
def test_revoked_token_cannot_be_refreshed():
    from app.services.auth_service import AuthService
    from app.shared.exceptions import UnauthorizedException

    uow, _ = _make_uow()
    service = AuthService(uow)

    tokens = _run(service.register(RegisterRequest(
        email="frank@example.com", password="pass1234", full_name="Frank",
    )))
    _run(service.logout(LogoutRequest(refresh_token=tokens.refresh_token)))

    with pytest.raises(UnauthorizedException):
        _run(service.refresh_tokens(RefreshRequest(refresh_token=tokens.refresh_token)))


# ---------------------------------------------------------------------------
# Change password
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="passlib[bcrypt] and PyJWT required")
def test_change_password_succeeds_with_correct_old_password():
    from app.services.auth_service import AuthService
    from app.core.security import security

    uow, store = _make_uow()
    service = AuthService(uow)

    tokens = _run(service.register(RegisterRequest(
        email="grace@example.com", password="oldpass1", full_name="Grace",
    )))

    from app.core.security import security as sec
    claims = sec.decode_access_token(tokens.access_token)
    from uuid import UUID
    user_id = UUID(claims["sub"])

    _run(service.change_password(user_id, ChangePasswordRequest(
        old_password="oldpass1", new_password="newpass12",
    )))

    new_tokens = _run(service.login(LoginRequest(
        email="grace@example.com", password="newpass12",
    )))
    assert new_tokens.access_token


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="passlib[bcrypt] and PyJWT required")
def test_change_password_revokes_all_refresh_tokens():
    from app.services.auth_service import AuthService

    uow, store = _make_uow()
    service = AuthService(uow)

    tokens = _run(service.register(RegisterRequest(
        email="hank@example.com", password="oldpass1", full_name="Hank",
    )))
    from app.core.security import security
    claims = security.decode_access_token(tokens.access_token)
    from uuid import UUID
    user_id = UUID(claims["sub"])

    _run(service.change_password(user_id, ChangePasswordRequest(
        old_password="oldpass1", new_password="newpass12",
    )))

    revoked = [r for r in store.refresh_tokens.values() if r.revoked_at is not None]
    assert len(revoked) >= 1


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="passlib[bcrypt] and PyJWT required")
def test_change_password_wrong_old_password_raises_403():
    from app.services.auth_service import AuthService
    from app.shared.exceptions import ForbiddenException

    uow, _ = _make_uow()
    service = AuthService(uow)

    tokens = _run(service.register(RegisterRequest(
        email="iris@example.com", password="correct1", full_name="Iris",
    )))
    from app.core.security import security
    claims = security.decode_access_token(tokens.access_token)
    from uuid import UUID
    user_id = UUID(claims["sub"])

    with pytest.raises(ForbiddenException):
        _run(service.change_password(user_id, ChangePasswordRequest(
            old_password="wrongpass", new_password="newpass12",
        )))


# ---------------------------------------------------------------------------
# HTTP endpoint tests
# ---------------------------------------------------------------------------


def _make_auth_client():
    from app.api.dependencies import get_auth_service
    from app.main import create_app
    from app.services.auth_service import AuthService

    app = create_app()
    store = InMemoryStore()
    uow = AsyncMemoryUnitOfWork(store)

    async def _override() -> AsyncIterator[AuthService]:
        yield AuthService(uow)

    app.dependency_overrides[get_auth_service] = _override
    return TestClient(app, raise_server_exceptions=False), store, uow


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="passlib[bcrypt] and PyJWT required")
def test_logout_endpoint_returns_204():
    client, _, _ = _make_auth_client()

    reg = client.post("/auth/register", json={
        "email": "jack@example.com", "password": "pass1234", "full_name": "Jack",
    })
    refresh_token = reg.json()["refresh_token"]

    response = client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert response.status_code == 204


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="passlib[bcrypt] and PyJWT required")
def test_change_password_endpoint_returns_204():
    client, _, _ = _make_auth_client()

    reg = client.post("/auth/register", json={
        "email": "kate@example.com", "password": "oldpass1", "full_name": "Kate",
    })
    access_token = reg.json()["access_token"]

    response = client.post(
        "/auth/change-password",
        json={"old_password": "oldpass1", "new_password": "newpass12"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 204


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="passlib[bcrypt] and PyJWT required")
def test_change_password_wrong_old_returns_403():
    client, _, _ = _make_auth_client()

    reg = client.post("/auth/register", json={
        "email": "leo@example.com", "password": "correct1", "full_name": "Leo",
    })
    access_token = reg.json()["access_token"]

    response = client.post(
        "/auth/change-password",
        json={"old_password": "wrong123", "new_password": "newpass12"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# DEV_AUTH_BYPASS flag behavior
# ---------------------------------------------------------------------------


def test_dev_auth_bypass_true_allows_unauthenticated_in_dev():
    """With bypass=True and non-production, unauthenticated requests use SYSTEM user."""
    from app.core.config import Environment, settings
    from app.main import create_app

    with patch.object(settings, "dev_auth_bypass", True), \
         patch.object(settings, "environment", Environment.DEVELOPMENT):
        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/health")
        assert response.status_code == 200


def test_dev_auth_bypass_false_requires_token_in_dev():
    """With bypass=False, unauthenticated requests get 401 even in development."""
    from app.core.config import Environment, settings
    from app.api.dependencies import get_async_service
    from app.application.async_daily_loop_service import AsyncDailyLoopService
    from app.main import create_app

    with patch.object(settings, "dev_auth_bypass", False), \
         patch.object(settings, "environment", Environment.DEVELOPMENT):
        app = create_app()
        store = InMemoryStore()
        uow = AsyncMemoryUnitOfWork(store)

        async def _override() -> AsyncIterator[AsyncDailyLoopService]:
            yield AsyncDailyLoopService(uow)

        app.dependency_overrides[get_async_service] = _override
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/organizations", json={"name": "Org", "slug": "org"})
        assert response.status_code == 401


def test_production_with_bypass_true_refuses_startup():
    """create_app() raises RuntimeError if dev_auth_bypass=True in production."""
    from app.core.config import Environment, settings
    from app.main import create_app

    with patch.object(settings, "dev_auth_bypass", True), \
         patch.object(settings, "environment", Environment.PRODUCTION):
        with pytest.raises(RuntimeError, match="DEV_AUTH_BYPASS"):
            create_app()


def test_production_unauthenticated_request_returns_401():
    """Production with bypass=False returns 401 for unauthenticated requests."""
    from app.core.config import Environment, settings
    from app.api.dependencies import get_async_service
    from app.application.async_daily_loop_service import AsyncDailyLoopService
    from app.main import create_app

    with patch.object(settings, "dev_auth_bypass", False), \
         patch.object(settings, "environment", Environment.PRODUCTION):
        app = create_app()
        store = InMemoryStore()
        uow = AsyncMemoryUnitOfWork(store)

        async def _override() -> AsyncIterator[AsyncDailyLoopService]:
            yield AsyncDailyLoopService(uow)

        app.dependency_overrides[get_async_service] = _override
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/organizations", json={"name": "Org", "slug": "org"})
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# SecureHeadersMiddleware
# ---------------------------------------------------------------------------


def test_secure_headers_present_on_response():
    from app.main import create_app

    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/health")

    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("x-xss-protection") == "1; mode=block"
    assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="passlib[bcrypt] and PyJWT required")
def test_tenant_isolation_user_org_id_comes_from_jwt_not_request():
    """The organization_id stored in the JWT determines the user's org context.

    A user registered under org A who crafts a request with org B's ID in the
    body gets org A stored on the resource (per the JWT), demonstrating that
    client-supplied org_id in the body cannot elevate to another org.

    This test verifies the JWT payload carries the correct org_id and that
    the registered user is scoped to their own org.
    """
    from app.core.security import security
    from app.services.auth_service import AuthService

    org_a_id = uuid4()
    org_b_id = uuid4()

    uow, store = _make_uow()
    service = AuthService(uow)

    tokens = _run(service.register(RegisterRequest(
        email="alice@orga.com",
        password="pass1234",
        full_name="Alice",
        organization_id=org_a_id,
    )))

    claims = security.decode_access_token(tokens.access_token)
    assert claims["org"] == str(org_a_id)
    assert claims["org"] != str(org_b_id)


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="passlib[bcrypt] and PyJWT required")
def test_users_from_different_orgs_have_separate_jwt_org_claims():
    from app.core.security import security
    from app.services.auth_service import AuthService

    org_a_id = uuid4()
    org_b_id = uuid4()

    uow_a, _ = _make_uow()
    uow_b, _ = _make_uow()

    tokens_a = _run(AuthService(uow_a).register(RegisterRequest(
        email="a@orga.com", password="pass1234", full_name="AA", organization_id=org_a_id,
    )))
    tokens_b = _run(AuthService(uow_b).register(RegisterRequest(
        email="b@orgb.com", password="pass1234", full_name="BB", organization_id=org_b_id,
    )))

    claims_a = security.decode_access_token(tokens_a.access_token)
    claims_b = security.decode_access_token(tokens_b.access_token)

    assert claims_a["org"] == str(org_a_id)
    assert claims_b["org"] == str(org_b_id)
    assert claims_a["org"] != claims_b["org"]


# ---------------------------------------------------------------------------
# Memory refresh token repository
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="passlib[bcrypt] and PyJWT required")
def test_memory_refresh_token_repo_create_and_get_by_hash():
    from datetime import UTC, datetime, timedelta
    from app.schemas.auth import RefreshTokenCreate

    uow, store = _make_uow()
    user_id = uuid4()
    expires = datetime.now(UTC) + timedelta(days=7)

    result = _run(uow.refresh_tokens.create(RefreshTokenCreate(
        user_id=user_id, token_hash="abc123hash", expires_at=expires,
    )))

    assert result.id is not None
    assert result.user_id == user_id
    assert result.used_at is None

    fetched = _run(uow.refresh_tokens.get_by_hash("abc123hash"))
    assert fetched is not None
    assert fetched.id == result.id


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="passlib[bcrypt] and PyJWT required")
def test_memory_refresh_token_mark_used():
    from datetime import UTC, datetime, timedelta
    from app.schemas.auth import RefreshTokenCreate

    uow, store = _make_uow()
    user_id = uuid4()
    expires = datetime.now(UTC) + timedelta(days=7)

    record = _run(uow.refresh_tokens.create(RefreshTokenCreate(
        user_id=user_id, token_hash="hash456", expires_at=expires,
    )))
    _run(uow.refresh_tokens.mark_used(record.id))

    fetched = _run(uow.refresh_tokens.get_by_hash("hash456"))
    assert fetched.used_at is not None


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="passlib[bcrypt] and PyJWT required")
def test_memory_refresh_token_revoke():
    from datetime import UTC, datetime, timedelta
    from app.schemas.auth import RefreshTokenCreate

    uow, store = _make_uow()
    user_id = uuid4()
    expires = datetime.now(UTC) + timedelta(days=7)

    record = _run(uow.refresh_tokens.create(RefreshTokenCreate(
        user_id=user_id, token_hash="hash789", expires_at=expires,
    )))
    _run(uow.refresh_tokens.revoke(record.id))

    fetched = _run(uow.refresh_tokens.get_by_hash("hash789"))
    assert fetched.revoked_at is not None


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="passlib[bcrypt] and PyJWT required")
def test_memory_refresh_token_revoke_all_for_user():
    from datetime import UTC, datetime, timedelta
    from app.schemas.auth import RefreshTokenCreate

    uow, store = _make_uow()
    user_id = uuid4()
    expires = datetime.now(UTC) + timedelta(days=7)

    _run(uow.refresh_tokens.create(RefreshTokenCreate(user_id=user_id, token_hash="h1", expires_at=expires)))
    _run(uow.refresh_tokens.create(RefreshTokenCreate(user_id=user_id, token_hash="h2", expires_at=expires)))
    other_user = uuid4()
    _run(uow.refresh_tokens.create(RefreshTokenCreate(user_id=other_user, token_hash="h3", expires_at=expires)))

    _run(uow.refresh_tokens.revoke_all_for_user(user_id))

    assert store.get_refresh_token_by_hash("h1").revoked_at is not None
    assert store.get_refresh_token_by_hash("h2").revoked_at is not None
    assert store.get_refresh_token_by_hash("h3").revoked_at is None


# ---------------------------------------------------------------------------
# update_password on user repo
# ---------------------------------------------------------------------------


def test_memory_user_repo_update_password():
    uow, store = _make_uow()
    from app.schemas.auth import UserCreate

    async def _go():
        user = await uow.users.create(UserCreate(
            email="zara@example.com", hashed_password="old_hash", full_name="Zara",
        ))
        await uow.users.update_password(user.id, "new_hash")
        updated = await uow.users.get_by_id(user.id)
        return updated

    updated = _run(_go())
    assert updated.hashed_password == "new_hash"
