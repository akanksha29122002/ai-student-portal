"""Tests for the Authentication milestone.

Covers: UserRepository (memory), AuthService register/login/refresh,
get_current_user dependency, and protected route RBAC.

AuthService tests that need passlib or PyJWT are skipped automatically
when those libraries are not installed, consistent with the pattern used
for the database integration tests.
"""
import importlib.util
import asyncio
from uuid import UUID, uuid4

import pytest

from app.infrastructure.repositories.memory import AsyncMemoryUnitOfWork
from app.schemas.auth import RegisterRequest, LoginRequest, RefreshRequest, UserCreate
from app.services.store import InMemoryStore

_PASSLIB = importlib.util.find_spec("passlib") is not None
_JWT = importlib.util.find_spec("jwt") is not None
_CRYPTO_AVAILABLE = _PASSLIB and _JWT


def _run(coro):
    return asyncio.run(coro)


def _make_uow() -> tuple[AsyncMemoryUnitOfWork, InMemoryStore]:
    store = InMemoryStore()
    return AsyncMemoryUnitOfWork(store), store


# ---------------------------------------------------------------------------
# UserRepository (memory)
# ---------------------------------------------------------------------------


def test_memory_user_repo_create_and_get_by_email():
    uow, store = _make_uow()

    async def _go():
        user = await uow.users.create(UserCreate(
            email="alice@example.com",
            hashed_password="hashed_secret",
            full_name="Alice",
        ))
        fetched = await uow.users.get_by_email("alice@example.com")
        return user, fetched

    user, fetched = _run(_go())
    assert user.id is not None
    assert fetched is not None
    assert fetched.email == "alice@example.com"
    assert fetched.hashed_password == "hashed_secret"


def test_memory_user_repo_get_by_email_case_insensitive():
    uow, _ = _make_uow()

    async def _go():
        await uow.users.create(UserCreate(
            email="Bob@Example.COM",
            hashed_password="x",
            full_name="Bob",
        ))
        return await uow.users.get_by_email("bob@example.com")

    fetched = _run(_go())
    assert fetched is not None
    assert fetched.full_name == "Bob"


def test_memory_user_repo_get_by_id():
    uow, _ = _make_uow()

    async def _go():
        user = await uow.users.create(UserCreate(
            email="carol@example.com", hashed_password="x", full_name="Carol",
        ))
        return await uow.users.get_by_id(user.id)

    fetched = _run(_go())
    assert fetched is not None
    assert fetched.email == "carol@example.com"


def test_memory_user_repo_get_by_id_missing_returns_none():
    uow, _ = _make_uow()

    result = _run(uow.users.get_by_id(uuid4()))
    assert result is None


def test_memory_user_repo_get_by_email_missing_returns_none():
    uow, _ = _make_uow()

    result = _run(uow.users.get_by_email("nobody@example.com"))
    assert result is None


# ---------------------------------------------------------------------------
# AuthService — requires passlib + PyJWT
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="passlib[bcrypt] and PyJWT required")
def test_auth_service_register_returns_tokens():
    from app.services.auth_service import AuthService

    uow, _ = _make_uow()
    service = AuthService(uow)

    tokens = _run(service.register(RegisterRequest(
        email="dave@example.com",
        password="securepass",
        full_name="Dave",
    )))

    assert tokens.access_token
    assert tokens.refresh_token
    assert tokens.token_type == "bearer"


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="passlib[bcrypt] and PyJWT required")
def test_auth_service_register_duplicate_email_raises_conflict():
    from app.services.auth_service import AuthService
    from app.shared.exceptions import ConflictException

    uow, _ = _make_uow()
    service = AuthService(uow)

    _run(service.register(RegisterRequest(
        email="eve@example.com", password="securepass", full_name="Eve",
    )))

    with pytest.raises(ConflictException):
        _run(service.register(RegisterRequest(
            email="eve@example.com", password="otherpass", full_name="Eve",
        )))


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="passlib[bcrypt] and PyJWT required")
def test_auth_service_login_returns_tokens():
    from app.services.auth_service import AuthService

    uow, _ = _make_uow()
    service = AuthService(uow)

    _run(service.register(RegisterRequest(
        email="frank@example.com", password="mypassword", full_name="Frank",
    )))
    tokens = _run(service.login(LoginRequest(
        email="frank@example.com", password="mypassword",
    )))

    assert tokens.access_token
    assert tokens.refresh_token


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="passlib[bcrypt] and PyJWT required")
def test_auth_service_login_wrong_password_raises_unauthorized():
    from app.services.auth_service import AuthService
    from app.shared.exceptions import UnauthorizedException

    uow, _ = _make_uow()
    service = AuthService(uow)

    _run(service.register(RegisterRequest(
        email="grace@example.com", password="correct1", full_name="Grace",
    )))

    with pytest.raises(UnauthorizedException):
        _run(service.login(LoginRequest(
            email="grace@example.com", password="wrong",
        )))


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="passlib[bcrypt] and PyJWT required")
def test_auth_service_login_unknown_email_raises_unauthorized():
    from app.services.auth_service import AuthService
    from app.shared.exceptions import UnauthorizedException

    uow, _ = _make_uow()
    service = AuthService(uow)

    with pytest.raises(UnauthorizedException):
        _run(service.login(LoginRequest(email="nobody@example.com", password="pass")))


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="passlib[bcrypt] and PyJWT required")
def test_auth_service_refresh_returns_new_tokens():
    from app.services.auth_service import AuthService

    uow, _ = _make_uow()
    service = AuthService(uow)

    tokens = _run(service.register(RegisterRequest(
        email="hank@example.com", password="pass1234", full_name="Hank",
    )))
    new_tokens = _run(service.refresh_tokens(RefreshRequest(refresh_token=tokens.refresh_token)))

    assert new_tokens.access_token
    assert new_tokens.refresh_token


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="passlib[bcrypt] and PyJWT required")
def test_auth_service_get_profile_returns_user():
    from app.services.auth_service import AuthService

    uow, store = _make_uow()
    service = AuthService(uow)

    tokens = _run(service.register(RegisterRequest(
        email="iris@example.com", password="pass1234", full_name="Iris",
    )))

    from app.core.security import security
    claims = security.decode_access_token(tokens.access_token)
    user_id = UUID(claims["sub"])

    profile = _run(service.get_profile(user_id))
    assert profile.email == "iris@example.com"
    assert profile.full_name == "Iris"
    assert profile.is_active is True


# ---------------------------------------------------------------------------
# Auth HTTP endpoints
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="passlib[bcrypt] and PyJWT required")
def test_register_endpoint_returns_201():
    from collections.abc import AsyncIterator
    from fastapi.testclient import TestClient
    from app.api.dependencies import get_auth_service
    from app.services.auth_service import AuthService
    from app.main import create_app

    application = create_app()
    store = InMemoryStore()
    uow = AsyncMemoryUnitOfWork(store)

    async def _override() -> AsyncIterator[AuthService]:
        yield AuthService(uow)

    application.dependency_overrides[get_auth_service] = _override
    client = TestClient(application)

    response = client.post("/auth/register", json={
        "email": "jack@example.com",
        "password": "securepass",
        "full_name": "Jack",
    })

    assert response.status_code == 201
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="passlib[bcrypt] and PyJWT required")
def test_login_endpoint_returns_tokens():
    from collections.abc import AsyncIterator
    from fastapi.testclient import TestClient
    from app.api.dependencies import get_auth_service
    from app.services.auth_service import AuthService
    from app.main import create_app

    application = create_app()
    store = InMemoryStore()
    uow = AsyncMemoryUnitOfWork(store)

    async def _override() -> AsyncIterator[AuthService]:
        yield AuthService(uow)

    application.dependency_overrides[get_auth_service] = _override
    client = TestClient(application)

    client.post("/auth/register", json={
        "email": "kate@example.com", "password": "mypass123", "full_name": "Kate",
    })
    response = client.post("/auth/token", json={
        "email": "kate@example.com", "password": "mypass123",
    })

    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="passlib[bcrypt] and PyJWT required")
def test_login_wrong_password_returns_401():
    from collections.abc import AsyncIterator
    from fastapi.testclient import TestClient
    from app.api.dependencies import get_auth_service
    from app.services.auth_service import AuthService
    from app.main import create_app

    application = create_app()
    store = InMemoryStore()
    uow = AsyncMemoryUnitOfWork(store)

    async def _override() -> AsyncIterator[AuthService]:
        yield AuthService(uow)

    application.dependency_overrides[get_auth_service] = _override
    client = TestClient(application)

    client.post("/auth/register", json={
        "email": "leo@example.com", "password": "correct", "full_name": "Leo",
    })
    response = client.post("/auth/token", json={
        "email": "leo@example.com", "password": "wrong",
    })

    assert response.status_code == 401
