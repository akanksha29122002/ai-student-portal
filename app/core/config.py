import os
from enum import StrEnum

from pydantic import Field

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ModuleNotFoundError:
    BaseSettings = object
    SettingsConfigDict = None


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


if SettingsConfigDict is not None:

    class Settings(BaseSettings):
        app_name: str = "Project Defense AI"
        app_version: str = "0.1.0"
        environment: Environment = Environment.DEVELOPMENT
        debug: bool = False

        # Database
        database_url: str = Field(default="postgresql+asyncpg://project_defense:project_defense@localhost:5432/project_defense")
        test_database_url: str = Field(default="postgresql+asyncpg://project_defense:project_defense@localhost:5433/project_defense_test")
        db_pool_size: int = Field(default=10, ge=1, le=100)
        db_max_overflow: int = Field(default=20, ge=0, le=100)
        db_pool_timeout: int = Field(default=30, ge=5)

        # Redis / workers
        redis_url: str = "redis://localhost:6379/0"
        worker_concurrency: int = Field(default=4, ge=1)

        # Security
        secret_key: str = Field(default="change-me-before-production-use")
        jwt_algorithm: str = "HS256"
        jwt_access_expire_minutes: int = Field(default=15, ge=1)
        jwt_refresh_expire_days: int = Field(default=7, ge=1)

        # Development — set False in production (enforced at startup)
        dev_auth_bypass: bool = Field(default=True)

        # GitHub integration
        github_token: str = Field(default="")
        github_webhook_secret: str = Field(default="")
        github_client_id: str = Field(default="")
        github_client_secret: str = Field(default="")
        # Local-dev mock mode — NEVER enable in production (enforced at startup)
        github_mock_mode: bool = Field(default=False)

        # Anthropic / AI Agents
        anthropic_api_key: str = Field(default="")
        anthropic_model: str = Field(default="claude-haiku-4-5-20251001")

        # AI Evaluation (Milestone 5)
        # sync=true → evaluate inline (dev/demo); sync=false → background worker (prod)
        ai_evaluation_sync_mode: bool = Field(default=True)
        # Below this confidence the evaluation is escalated to a human mentor
        ai_confidence_threshold: float = Field(default=0.70, ge=0.0, le=1.0)

        # Demo mode — seeds rich demo data at startup; never enable in production
        demo_mode: bool = Field(default=False)

        # CORS — allowed frontend origin(s) for demo
        frontend_url: str = Field(default="http://localhost:3000")

        # API
        api_v1_prefix: str = "/api/v1"
        # Comma-separated string so plain env var values work on all platforms
        cors_origins: str = Field(default="")

        # Logging
        log_level: str = "INFO"

        model_config = SettingsConfigDict(env_prefix="PROJECT_DEFENSE_", env_file=".env", extra="ignore")

else:

    class Settings:
        def __init__(self) -> None:
            self.app_name = os.getenv("PROJECT_DEFENSE_APP_NAME", "Project Defense AI")
            self.app_version = os.getenv("PROJECT_DEFENSE_APP_VERSION", "0.1.0")
            self.environment = Environment(os.getenv("PROJECT_DEFENSE_ENVIRONMENT", Environment.DEVELOPMENT))
            self.debug = os.getenv("PROJECT_DEFENSE_DEBUG", "false").lower() == "true"
            self.database_url = os.getenv(
                "PROJECT_DEFENSE_DATABASE_URL",
                "postgresql+asyncpg://project_defense:project_defense@localhost:5432/project_defense",
            )
            self.test_database_url = os.getenv(
                "PROJECT_DEFENSE_TEST_DATABASE_URL",
                "postgresql+asyncpg://project_defense:project_defense@localhost:5433/project_defense_test",
            )
            self.db_pool_size = int(os.getenv("PROJECT_DEFENSE_DB_POOL_SIZE", "10"))
            self.db_max_overflow = int(os.getenv("PROJECT_DEFENSE_DB_MAX_OVERFLOW", "20"))
            self.db_pool_timeout = int(os.getenv("PROJECT_DEFENSE_DB_POOL_TIMEOUT", "30"))
            self.redis_url = os.getenv("PROJECT_DEFENSE_REDIS_URL", "redis://localhost:6379/0")
            self.worker_concurrency = int(os.getenv("PROJECT_DEFENSE_WORKER_CONCURRENCY", "4"))
            self.secret_key = os.getenv("PROJECT_DEFENSE_SECRET_KEY", "change-me-before-production-use")
            self.jwt_algorithm = os.getenv("PROJECT_DEFENSE_JWT_ALGORITHM", "HS256")
            self.jwt_access_expire_minutes = int(os.getenv("PROJECT_DEFENSE_JWT_ACCESS_EXPIRE_MINUTES", "15"))
            self.jwt_refresh_expire_days = int(os.getenv("PROJECT_DEFENSE_JWT_REFRESH_EXPIRE_DAYS", "7"))
            self.dev_auth_bypass = os.getenv("PROJECT_DEFENSE_DEV_AUTH_BYPASS", "true").lower() == "true"
            self.github_token = os.getenv("PROJECT_DEFENSE_GITHUB_TOKEN", "")
            self.github_webhook_secret = os.getenv("PROJECT_DEFENSE_GITHUB_WEBHOOK_SECRET", "")
            self.github_client_id = os.getenv("PROJECT_DEFENSE_GITHUB_CLIENT_ID", "")
            self.github_client_secret = os.getenv("PROJECT_DEFENSE_GITHUB_CLIENT_SECRET", "")
            self.github_mock_mode = os.getenv("PROJECT_DEFENSE_GITHUB_MOCK_MODE", "false").lower() == "true"
            self.anthropic_api_key = os.getenv("PROJECT_DEFENSE_ANTHROPIC_API_KEY", "")
            self.anthropic_model = os.getenv("PROJECT_DEFENSE_ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
            self.ai_evaluation_sync_mode = os.getenv("PROJECT_DEFENSE_AI_EVALUATION_SYNC_MODE", "true").lower() == "true"
            self.ai_confidence_threshold = float(os.getenv("PROJECT_DEFENSE_AI_CONFIDENCE_THRESHOLD", "0.70"))
            self.demo_mode = os.getenv("PROJECT_DEFENSE_DEMO_MODE", "false").lower() == "true"
            self.frontend_url = os.getenv("PROJECT_DEFENSE_FRONTEND_URL", "http://localhost:3000")
            self.api_v1_prefix = os.getenv("PROJECT_DEFENSE_API_V1_PREFIX", "/api/v1")
            self.cors_origins = os.getenv("PROJECT_DEFENSE_CORS_ORIGINS", "").split(",") if os.getenv("PROJECT_DEFENSE_CORS_ORIGINS") else []
            self.log_level = os.getenv("PROJECT_DEFENSE_LOG_LEVEL", "INFO")


settings = Settings()
