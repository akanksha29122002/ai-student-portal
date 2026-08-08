"""Redis Streams event bus — production transport.

Publishes domain events to Redis Streams via XADD.  Consumers read from
streams using XREADGROUP for at-least-once delivery with consumer groups.

Requires ``redis>=5.0`` (ships ``redis.asyncio``).  The module imports
gracefully when redis is not installed; attempting to instantiate
``RedisStreamEventBus`` without redis raises ``InfrastructureException``.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from uuid import UUID

from app.domain.events import DomainEvent
from app.shared.exceptions import InfrastructureException

try:
    import redis.asyncio as aioredis
    _REDIS_AVAILABLE = True
except ImportError:
    aioredis = None  # type: ignore[assignment]
    _REDIS_AVAILABLE = False

logger = logging.getLogger("project_defense.events.redis_bus")

STREAM_PREFIX = "events"


class RedisStreamEventBus:
    """Async event bus backed by Redis Streams.

    Each domain event is written to a stream keyed
    ``events:<aggregate_type>`` (e.g. ``events:student``).  The stream
    retains the last 10 000 entries per aggregate type (MAXLEN approximate
    trim) to bound memory usage.

    Consumers use XREADGROUP with the ``project_defense_workers`` group for
    at-least-once delivery.
    """

    _MAXLEN = 10_000

    def __init__(self, client) -> None:
        if not _REDIS_AVAILABLE:
            raise InfrastructureException(
                "redis is required for RedisStreamEventBus — run: pip install redis"
            )
        self._client = client

    async def publish(self, event: DomainEvent) -> None:
        stream_key = f"{STREAM_PREFIX}:{event.aggregate_type}"
        fields = {
            "event_id": str(event.event_id),
            "event_type": event.event_type,
            "aggregate_id": str(event.aggregate_id),
            "aggregate_type": event.aggregate_type,
            "payload": json.dumps(event.payload),
            "occurred_at": event.occurred_at.isoformat(),
            "correlation_id": str(event.correlation_id),
            "causation_id": str(event.causation_id) if event.causation_id else "",
            "user_id": str(event.user_id) if event.user_id else "",
            "metadata": json.dumps(event.metadata),
        }
        await self._client.xadd(stream_key, fields, maxlen=self._MAXLEN, approximate=True)
        logger.debug(
            "Published to stream",
            extra={
                "stream": stream_key,
                "event_type": event.event_type,
                "event_id": str(event.event_id),
            },
        )

    async def close(self) -> None:
        await self._client.aclose()


def make_redis_bus() -> RedisStreamEventBus:
    """Factory — creates a RedisStreamEventBus using settings.redis_url."""
    from app.core.config import settings
    client = aioredis.from_url(settings.redis_url, decode_responses=False)
    return RedisStreamEventBus(client)


def deserialize_event(fields: dict[bytes, bytes]) -> DomainEvent:
    """Reconstruct a DomainEvent from raw Redis Stream fields (bytes)."""

    def _s(key: bytes) -> str:
        return fields[key].decode()

    return DomainEvent(
        event_id=UUID(_s(b"event_id")),
        aggregate_id=UUID(_s(b"aggregate_id")),
        aggregate_type=_s(b"aggregate_type"),
        event_type=_s(b"event_type"),
        payload=json.loads(_s(b"payload")),
        occurred_at=datetime.fromisoformat(_s(b"occurred_at")),
        correlation_id=UUID(_s(b"correlation_id")),
        causation_id=UUID(_s(b"causation_id")) if _s(b"causation_id") else None,
        user_id=UUID(_s(b"user_id")) if _s(b"user_id") else None,
        metadata=json.loads(_s(b"metadata")),
    )
