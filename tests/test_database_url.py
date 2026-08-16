from sqlalchemy.engine.url import make_url

from app.core.database_url import normalize_async_database_url, normalize_sync_database_url
from app.infrastructure.database import create_engine


URL_VARIANTS = [
    "postgres://user:pass@host/db?sslmode=require",
    "postgresql://user:pass@host/db?sslmode=require",
    "postgresql+asyncpg://user:pass@host/db?ssl=require",
    "postgresql://user:pass@host/db?sslmode=require&channel_binding=require",
]


def test_normalize_async_database_url_variants():
    for raw in URL_VARIANTS:
        assert normalize_async_database_url(raw) == "postgresql+asyncpg://user:pass@host/db?ssl=require"


def test_normalize_sync_database_url_variants():
    for raw in URL_VARIANTS:
        assert normalize_sync_database_url(raw) == "postgresql+psycopg2://user:pass@host/db?sslmode=require"


def test_async_engine_uses_asyncpg_driver():
    engine = create_engine("postgresql://user:pass@host/db?sslmode=require")

    try:
        assert engine.url.drivername == "postgresql+asyncpg"
    finally:
        engine.sync_engine.dispose()


def test_sync_migration_url_uses_psycopg2_driver():
    url = make_url(normalize_sync_database_url("postgresql+asyncpg://user:pass@host/db?ssl=require"))

    assert url.drivername == "postgresql+psycopg2"


def test_async_url_contains_no_sslmode():
    normalized = normalize_async_database_url(
        "postgresql://user:pass@host/db?sslmode=require&channel_binding=require"
    )

    assert "ssl=require" in normalized
    assert "sslmode" not in normalized


def test_sync_url_contains_no_asyncpg_ssl_param():
    normalized = normalize_sync_database_url(
        "postgresql+asyncpg://user:pass@host/db?ssl=require&channel_binding=require"
    )

    assert "sslmode=require" in normalized
    assert "ssl=" not in normalized


def test_channel_binding_does_not_survive_driver_normalization():
    raw = "postgresql://user:pass@host/db?sslmode=require&channel_binding=require"

    assert "channel_binding" not in normalize_async_database_url(raw)
    assert "channel_binding" not in normalize_sync_database_url(raw)


def test_url_encoded_credentials_are_preserved():
    raw = "postgresql://user%40domain:p%40ss%3Aword%2Fsafe@host/db?sslmode=require&channel_binding=require"

    assert (
        normalize_async_database_url(raw)
        == "postgresql+asyncpg://user%40domain:p%40ss%3Aword%2Fsafe@host/db?ssl=require"
    )
    assert (
        normalize_sync_database_url(raw)
        == "postgresql+psycopg2://user%40domain:p%40ss%3Aword%2Fsafe@host/db?sslmode=require"
    )
