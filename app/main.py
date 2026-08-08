from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agents_router import router as agents_router
from app.api.auth_router import router as auth_router
from app.api.errors import register_exception_handlers
from app.api.evaluation_router import router as evaluation_router
from app.api.frontend_router import router as frontend_router
from app.api.github_router import router as github_router
from app.api.routes import router
from app.core.config import Environment, settings
from app.core.logging import RequestContextMiddleware, SecureHeadersMiddleware, configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    if getattr(settings, "demo_mode", False):
        try:
            from app.scripts.seed_demo import seed_demo
            await seed_demo()
        except Exception as exc:
            import logging
            logging.getLogger("project_defense").warning("Demo seed failed: %s", exc)
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
        description="AI-powered daily project defense and engineering evaluation.",
        lifespan=lifespan,
    )

    # CORS — allow the frontend dev server and any configured frontend URL
    frontend_url = getattr(settings, "frontend_url", "http://localhost:3000")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            frontend_url,
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(SecureHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)
    app.include_router(auth_router)
    app.include_router(router)
    app.include_router(frontend_router)
    app.include_router(github_router)
    app.include_router(agents_router)
    app.include_router(evaluation_router)
    return app


app = create_app()
