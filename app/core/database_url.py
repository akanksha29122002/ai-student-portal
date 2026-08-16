from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_ASYNC_DRIVER = "postgresql+asyncpg"
_SYNC_DRIVER = "postgresql+psycopg2"
_ASYNC_UNSUPPORTED_QUERY_PARAMS = {"sslmode", "channel_binding"}
_SYNC_UNSUPPORTED_QUERY_PARAMS = {"ssl", "channel_binding"}


def _with_driver(database_url: str, driver: str) -> tuple:
    parsed = urlsplit(database_url)
    scheme = parsed.scheme
    if scheme not in {"postgres", "postgresql", "postgresql+asyncpg", "postgresql+psycopg2"}:
        return parsed
    return parsed._replace(scheme=driver)


def _normalized_query(
    query: str,
    *,
    renamed_param: tuple[str, str],
    unsupported_params: set[str],
) -> str:
    source_param, target_param = renamed_param
    pairs = parse_qsl(query, keep_blank_values=True)
    normalized: list[tuple[str, str]] = []
    target_seen = False
    renamed_value: str | None = None

    for key, value in pairs:
        if key == source_param:
            if renamed_value is None:
                renamed_value = value
            continue
        if key in unsupported_params:
            continue
        if key == target_param:
            target_seen = True
        normalized.append((key, value))

    if renamed_value is not None and not target_seen:
        normalized.append((target_param, renamed_value))

    return urlencode(normalized, doseq=True)


def normalize_async_database_url(database_url: str) -> str:
    """Return a SQLAlchemy async URL for hosted/local PostgreSQL providers."""
    parsed = _with_driver(database_url, _ASYNC_DRIVER)
    query = _normalized_query(
        parsed.query,
        renamed_param=("sslmode", "ssl"),
        unsupported_params=_ASYNC_UNSUPPORTED_QUERY_PARAMS,
    )
    return urlunsplit(parsed._replace(query=query))


def normalize_sync_database_url(database_url: str) -> str:
    """Return a sync SQLAlchemy URL for Alembic migrations."""
    parsed = _with_driver(database_url, _SYNC_DRIVER)
    query = _normalized_query(
        parsed.query,
        renamed_param=("ssl", "sslmode"),
        unsupported_params=_SYNC_UNSUPPORTED_QUERY_PARAMS,
    )
    return urlunsplit(parsed._replace(query=query))
