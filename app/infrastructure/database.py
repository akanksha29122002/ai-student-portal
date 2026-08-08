from collections.abc import AsyncIterator

from app.core.config import settings
from app.shared.exceptions import InfrastructureException

try:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
except ModuleNotFoundError:
    AsyncEngine = None
    AsyncSession = None
    async_sessionmaker = None
    create_async_engine = None


def create_engine(database_url: str | None = None) -> "AsyncEngine":
    if create_async_engine is None:
        raise InfrastructureException("SQLAlchemy is not installed. Install project dependencies before using PostgreSQL.")
    return create_async_engine(
        database_url or settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
    )


engine = create_engine(settings.database_url) if create_async_engine is not None else None
SessionLocal = async_sessionmaker(engine, expire_on_commit=False) if async_sessionmaker is not None and engine is not None else None


async def get_session() -> AsyncIterator["AsyncSession"]:
    if SessionLocal is None:
        raise InfrastructureException("Database session factory is unavailable.")
    async with SessionLocal() as session:
        yield session
