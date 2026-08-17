from collections.abc import AsyncIterator
import os
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.application.async_daily_loop_service import AsyncDailyLoopService
from app.core.config import Environment, settings
from app.domain.enums import UserRole
from app.events.bus import EventDispatchingUnitOfWork, InMemoryEventBus, OptionalEventBus
from app.events.registry import make_default_registry
from app.infrastructure.database import SessionLocal
from app.infrastructure.repositories.memory import AsyncMemoryUnitOfWork
from app.schemas.auth import CurrentUser
from app.services.store import InMemoryStore
from app.shared.exceptions import UnauthorizedException

try:
    from app.infrastructure.repositories.sqlalchemy import SqlAlchemyUnitOfWork as _SqlAlchemyUnitOfWork
    _SQLALCHEMY_AVAILABLE = True
except Exception:
    _SqlAlchemyUnitOfWork = None  # type: ignore[assignment]
    _SQLALCHEMY_AVAILABLE = False

# When DEMO_MODE=true the whole stack uses InMemoryStore — seed data is
# written there and must be readable by auth and all frontend routes.
_demo_mode: bool = getattr(settings, "demo_mode", False)


def _use_database() -> bool:
    """Return True only when SQLAlchemy + a real DB session are available
    AND demo_mode is not forcing in-memory operation."""
    database_requested = (
        settings.environment == Environment.PRODUCTION
        or "PROJECT_DEFENSE_DATABASE_URL" in os.environ
    )
    return _SQLALCHEMY_AVAILABLE and SessionLocal is not None and not _demo_mode and database_requested

# ---------------------------------------------------------------------------
# Singletons — shared across requests in the same process
# ---------------------------------------------------------------------------

_dev_store = InMemoryStore()

# InMemoryEventBus wired with all production workers (used in dev/test)
_in_memory_bus = InMemoryEventBus()
make_default_registry().wire(_in_memory_bus)

_SYSTEM_USER = CurrentUser(
    id=UUID("00000000-0000-0000-0000-000000000000"),
    email="system@project-defense.ai",
    full_name="System",
    role=UserRole.SYSTEM,
    organization_id=None,
    is_active=True,
)

_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Event bus factory
# ---------------------------------------------------------------------------


def _get_bus():
    """Return the active event bus.

    Uses RedisStreamEventBus in production (non-demo) when redis is reachable,
    falls back to the module-level InMemoryEventBus otherwise.
    Demo mode always uses InMemoryEventBus — no Redis required.
    """
    redis_url = (getattr(settings, "redis_url", "") or "").strip()
    redis_required = bool(getattr(settings, "redis_required", False))

    if redis_required and not redis_url:
        from app.shared.exceptions import InfrastructureException
        raise InfrastructureException(
            "PROJECT_DEFENSE_REDIS_REQUIRED=true but PROJECT_DEFENSE_REDIS_URL is not configured"
        )

    if redis_url and not _demo_mode:
        try:
            from app.events.redis_bus import make_redis_bus
            return OptionalEventBus(make_redis_bus(redis_url), required=redis_required)
        except Exception as exc:
            import logging
            logging.getLogger("project_defense.events.bus").warning(
                "Redis event bus unavailable; using InMemoryEventBus",
                extra={"redis_required": redis_required},
                exc_info=True,
            )
            if redis_required:
                from app.shared.exceptions import InfrastructureException
                raise InfrastructureException("Redis event bus is required but unavailable") from exc
    return _in_memory_bus


# ---------------------------------------------------------------------------
# FastAPI dependency providers
# ---------------------------------------------------------------------------


async def get_async_service() -> AsyncIterator[AsyncDailyLoopService]:
    """Provide an AsyncDailyLoopService for the current request.

    Wraps the UoW in EventDispatchingUnitOfWork so domain events appended
    during the transaction are published to the event bus after commit.
    Falls back to in-memory repos when PostgreSQL is not available or
    when demo_mode is active.
    """
    bus = _get_bus()
    if _use_database():
        async with SessionLocal() as session:
            uow = EventDispatchingUnitOfWork(_SqlAlchemyUnitOfWork(session), bus)
            yield AsyncDailyLoopService(uow)
    else:
        uow = EventDispatchingUnitOfWork(AsyncMemoryUnitOfWork(_dev_store), bus)
        yield AsyncDailyLoopService(uow)


async def get_auth_service():
    """Provide an AuthService for the current request."""
    from app.services.auth_service import AuthService
    if _use_database():
        async with SessionLocal() as session:
            yield AuthService(_SqlAlchemyUnitOfWork(session))
    else:
        yield AuthService(AsyncMemoryUnitOfWork(_dev_store))


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    """Extract and validate the caller's identity from the Authorization header.

    A missing token uses the SYSTEM user only when BOTH conditions hold:
      1. settings.dev_auth_bypass is True
      2. The environment is NOT production

    Production always enforces authentication regardless of dev_auth_bypass.
    """
    if credentials is None:
        if settings.dev_auth_bypass and settings.environment != Environment.PRODUCTION:
            return _SYSTEM_USER
        raise UnauthorizedException("Authentication required")

    from app.core.security import security
    payload = security.decode_access_token(credentials.credentials)

    return CurrentUser(
        id=UUID(payload["sub"]),
        email=payload["email"],
        full_name=payload.get("full_name", ""),
        role=payload["role"],
        organization_id=UUID(payload["org"]) if payload.get("org") else None,
        is_active=True,
    )
