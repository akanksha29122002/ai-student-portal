from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.agents_router import router as agents_router
from app.api.auth_router import router as auth_router
from app.api.errors import register_exception_handlers
from app.api.evaluation_router import router as evaluation_router
from app.api.github_router import router as github_router
from app.api.routes import router
from app.core.config import Environment, settings
from app.core.logging import RequestContextMiddleware, SecureHeadersMiddleware, configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    from app.infrastructure.database import engine
    if engine is not None:
        await engine.dispose()


def create_app() -> FastAPI:
    if settings.dev_auth_bypass and settings.environment == Environment.PRODUCTION:
        raise RuntimeError(
            "DEV_AUTH_BYPASS=true is not allowed in ENVIRONMENT=production. "
            "Remove PROJECT_DEFENSE_DEV_AUTH_BYPASS from your production environment."
        )
    if getattr(settings, "github_mock_mode", False) and settings.environment == Environment.PRODUCTION:
        raise RuntimeError(
            "GITHUB_MOCK_MODE=true is not allowed in ENVIRONMENT=production. "
            "Remove PROJECT_DEFENSE_GITHUB_MOCK_MODE from your production environment."
        )
    configure_logging(settings.log_level)
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Daily task automation and mentor-reviewed AI evaluation for engineering project defense.",
        lifespan=lifespan,
    )
    app.add_middleware(SecureHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)
    app.include_router(auth_router)
    app.include_router(router)
    app.include_router(github_router)
    app.include_router(agents_router)
    app.include_router(evaluation_router)
    return app


app = create_app()
