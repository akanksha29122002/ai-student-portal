import asyncio
import importlib.util

import pytest

from app.domain.enums import UserRole
from app.infrastructure.repositories.memory import AsyncMemoryUnitOfWork
from app.schemas.auth import UserCreate
from app.scripts.bootstrap_admin import (
    ADMIN_EMAIL_ENV,
    ADMIN_NAME_ENV,
    ADMIN_PASSWORD_ENV,
    BOOTSTRAP_ADMIN_ROLE,
    BootstrapAdminError,
    bootstrap_admin,
    bootstrap_admin_from_env,
    format_result,
    read_bootstrap_admin_env,
)
from app.services.store import InMemoryStore

_PASSLIB = importlib.util.find_spec("passlib") is not None


def _run(coro):
    return asyncio.run(coro)


def _make_uow() -> tuple[AsyncMemoryUnitOfWork, InMemoryStore]:
    store = InMemoryStore()
    return AsyncMemoryUnitOfWork(store), store


@pytest.mark.skipif(not _PASSLIB, reason="passlib[bcrypt] required")
def test_bootstrap_admin_creates_new_organization_admin():
    uow, store = _make_uow()

    result = _run(
        bootstrap_admin(
            uow,
            email="Admin@ProjectDefense.ai",
            full_name="Production Admin",
            password="safe-admin-password",
        )
    )

    user = store.get_user_by_email("admin@projectdefense.ai")
    assert result.created is True
    assert user is not None
    assert user.email == "admin@projectdefense.ai"
    assert user.full_name == "Production Admin"
    assert user.role == BOOTSTRAP_ADMIN_ROLE
    assert user.organization_id is None


@pytest.mark.skipif(not _PASSLIB, reason="passlib[bcrypt] required")
def test_bootstrap_admin_is_idempotent_when_user_already_exists():
    uow, store = _make_uow()

    first = _run(
        bootstrap_admin(
            uow,
            email="admin@example.com",
            full_name="Production Admin",
            password="safe-admin-password",
        )
    )
    second = _run(
        bootstrap_admin(
            uow,
            email="admin@example.com",
            full_name="Production Admin",
            password="different-safe-password",
        )
    )

    assert first.created is True
    assert second.created is False
    assert second.user_id == first.user_id
    assert len(store.users) == 1


@pytest.mark.skipif(not _PASSLIB, reason="passlib[bcrypt] required")
def test_bootstrap_admin_hashes_password_without_plaintext_storage():
    from app.core.security import security

    uow, store = _make_uow()
    plain_password = "safe-admin-password"

    _run(
        bootstrap_admin(
            uow,
            email="admin@example.com",
            full_name="Production Admin",
            password=plain_password,
        )
    )

    user = store.get_user_by_email("admin@example.com")
    assert user is not None
    assert user.hashed_password != plain_password
    assert security.verify_password(plain_password, user.hashed_password)


@pytest.mark.skipif(not _PASSLIB, reason="passlib[bcrypt] required")
def test_bootstrap_admin_refuses_existing_non_admin_user():
    uow, store = _make_uow()

    _run(
        uow.users.create(
            UserCreate(
                email="akankshame422@gmail.com",
                hashed_password="existing-hash",
                full_name="Akanksha Kumari",
                role=UserRole.STUDENT,
            )
        )
    )

    with pytest.raises(BootstrapAdminError, match="already exists with role"):
        _run(
            bootstrap_admin(
                uow,
                email="akankshame422@gmail.com",
                full_name="Production Admin",
                password="safe-admin-password",
            )
        )

    assert len(store.users) == 1
    assert store.get_user_by_email("akankshame422@gmail.com").role == UserRole.STUDENT


def test_read_bootstrap_admin_env_requires_all_values():
    with pytest.raises(BootstrapAdminError, match=ADMIN_EMAIL_ENV):
        read_bootstrap_admin_env({})


def test_bootstrap_admin_env_reader_normalizes_email():
    email, full_name, password = read_bootstrap_admin_env(
        {
            ADMIN_EMAIL_ENV: " Admin@ProjectDefense.ai ",
            ADMIN_NAME_ENV: " Production Admin ",
            ADMIN_PASSWORD_ENV: " safe-admin-password ",
        }
    )

    assert email == "admin@projectdefense.ai"
    assert full_name == "Production Admin"
    assert password == "safe-admin-password"


@pytest.mark.skipif(not _PASSLIB, reason="passlib[bcrypt] required")
def test_bootstrap_admin_from_env_uses_correct_role():
    uow, _ = _make_uow()

    result = _run(
        bootstrap_admin_from_env(
            uow,
            {
                ADMIN_EMAIL_ENV: "admin@example.com",
                ADMIN_NAME_ENV: "Production Admin",
                ADMIN_PASSWORD_ENV: "safe-admin-password",
            },
        )
    )

    assert result.role == str(BOOTSTRAP_ADMIN_ROLE)


def test_bootstrap_admin_output_does_not_include_plaintext_password():
    output = format_result(
        result=type(
            "Result",
            (),
            {
                "created": True,
                "email": "admin@example.com",
                "role": "organization_admin",
                "user_id": "user-123",
            },
        )()
    )

    assert "safe-admin-password" not in output
    assert "password" not in output.lower()
    assert "admin@example.com" in output
