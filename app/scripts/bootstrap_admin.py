"""Create the first legitimate production organization admin.

Usage:
    python -m app.scripts.bootstrap_admin

The command is intentionally CLI-only. It does not expose a public HTTP
bootstrap endpoint and it never prints the plaintext password.
"""
from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from types import TracebackType
from typing import Protocol

from app.core.security import security
from app.domain.enums import UserRole
from app.schemas.auth import User, UserCreate

ADMIN_EMAIL_ENV = "PROJECT_DEFENSE_BOOTSTRAP_ADMIN_EMAIL"
ADMIN_NAME_ENV = "PROJECT_DEFENSE_BOOTSTRAP_ADMIN_NAME"
ADMIN_PASSWORD_ENV = "PROJECT_DEFENSE_BOOTSTRAP_ADMIN_PASSWORD"
BOOTSTRAP_ADMIN_ROLE = UserRole.ORGANIZATION_ADMIN


class BootstrapAdminError(RuntimeError):
    """Raised when the bootstrap command cannot safely create/reuse an admin."""


class _UserRepository(Protocol):
    async def create(self, payload: UserCreate) -> User: ...
    async def get_by_email(self, email: str) -> User | None: ...


class _AsyncUserUnitOfWork(Protocol):
    users: _UserRepository

    async def __aenter__(self) -> "_AsyncUserUnitOfWork": ...
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


@dataclass(frozen=True)
class BootstrapAdminResult:
    created: bool
    user_id: str
    email: str
    full_name: str
    role: str


def _required_env(environ: os._Environ[str] | dict[str, str], key: str) -> str:
    value = environ.get(key, "").strip()
    if not value:
        raise BootstrapAdminError(f"Missing required environment variable: {key}")
    return value


def read_bootstrap_admin_env(
    environ: os._Environ[str] | dict[str, str] = os.environ,
) -> tuple[str, str, str]:
    email = _required_env(environ, ADMIN_EMAIL_ENV).lower()
    full_name = _required_env(environ, ADMIN_NAME_ENV)
    password = _required_env(environ, ADMIN_PASSWORD_ENV)
    if len(password) < 8:
        raise BootstrapAdminError("Bootstrap admin password must be at least 8 characters long")
    return email, full_name, password


async def bootstrap_admin(
    uow: _AsyncUserUnitOfWork,
    *,
    email: str,
    full_name: str,
    password: str,
) -> BootstrapAdminResult:
    """Create or reuse the bootstrap organization admin through the User repo."""
    normalized_email = email.strip().lower()
    if not normalized_email:
        raise BootstrapAdminError("Bootstrap admin email is required")
    if not full_name.strip():
        raise BootstrapAdminError("Bootstrap admin name is required")
    if len(password) < 8:
        raise BootstrapAdminError("Bootstrap admin password must be at least 8 characters long")

    async with uow:
        existing = await uow.users.get_by_email(normalized_email)
        if existing is not None:
            if existing.role != BOOTSTRAP_ADMIN_ROLE:
                raise BootstrapAdminError(
                    "Bootstrap admin email already exists with role "
                    f"'{existing.role}'. Expected '{BOOTSTRAP_ADMIN_ROLE}'. "
                    "Refusing to create a duplicate or silently change roles."
                )
            return BootstrapAdminResult(
                created=False,
                user_id=str(existing.id),
                email=existing.email,
                full_name=existing.full_name,
                role=str(existing.role),
            )

        user = await uow.users.create(
            UserCreate(
                email=normalized_email,
                hashed_password=security.hash_password(password),
                full_name=full_name.strip(),
                role=BOOTSTRAP_ADMIN_ROLE,
                organization_id=None,
            )
        )

    return BootstrapAdminResult(
        created=True,
        user_id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=str(user.role),
    )


async def bootstrap_admin_from_env(
    uow: _AsyncUserUnitOfWork,
    environ: os._Environ[str] | dict[str, str] = os.environ,
) -> BootstrapAdminResult:
    email, full_name, password = read_bootstrap_admin_env(environ)
    return await bootstrap_admin(
        uow,
        email=email,
        full_name=full_name,
        password=password,
    )


def format_result(result: BootstrapAdminResult) -> str:
    action = "created" if result.created else "reused"
    return (
        f"Bootstrap admin {action}: "
        f"email={result.email} role={result.role} user_id={result.user_id}"
    )


async def _run_cli() -> int:
    try:
        from app.infrastructure.database import SessionLocal, engine
        from app.infrastructure.repositories.sqlalchemy import SqlAlchemyUnitOfWork

        if SessionLocal is None:
            raise BootstrapAdminError("Database session factory is unavailable")

        async with SessionLocal() as session:
            result = await bootstrap_admin_from_env(SqlAlchemyUnitOfWork(session))

        if engine is not None:
            await engine.dispose()

        print(format_result(result))
        return 0
    except BootstrapAdminError as exc:
        print(f"Bootstrap admin failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Bootstrap admin failed with {exc.__class__.__name__}", file=sys.stderr)
        return 1


def main() -> None:
    raise SystemExit(asyncio.run(_run_cli()))


if __name__ == "__main__":
    main()
