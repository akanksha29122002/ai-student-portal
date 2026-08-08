"""Redis Streams consumer — reads domain events and dispatches to EventWorkers.

Run as a Celery beat-scheduled periodic task:

    celery -A app.workers.celery_app worker --loglevel=info -Q event_streams

Or invoke directly from Python (useful for one-off drain):

    import asyncio
    from app.workers.stream_consumer import consume_all_streams
    asyncio.run(consume_all_streams())
"""
from __future__ import annotations

import logging

from app.workers.celery_app import celery_app

logger = logging.getLogger("project_defense.workers.stream_consumer")

CONSUMER_GROUP = "project_defense_workers"
CONSUMER_NAME = "consumer_1"

WATCHED_STREAMS = [
    "events:student",
    "events:project",
    "events:task",
    "events:submission",
    "events:evaluation",
    "events:mentor_review",
    "events:notification",
    "events:daily_summary",
]


if celery_app is not None:
    @celery_app.task(name="workers.consume_stream", bind=True, max_retries=3, queue="event_streams")
    def consume_stream(self, stream_key: str, count: int = 50):
        """Read and dispatch pending events from one Redis Stream."""
        import asyncio
        try:
            processed = asyncio.run(_consume_once(stream_key, count))
            logger.info("Consumed %d events from %s", processed, stream_key)
            return processed
        except Exception as exc:
            logger.exception("Stream consumer failed for %s", stream_key)
            raise self.retry(exc=exc, countdown=5 ** self.request.retries)

    @celery_app.task(name="workers.consume_all_streams", queue="event_streams")
    def schedule_all_streams():
        """Fan-out: schedule one consume_stream task per watched stream."""
        for stream_key in WATCHED_STREAMS:
            consume_stream.delay(stream_key)


async def _consume_once(stream_key: str, count: int = 50) -> int:
    """Read up to ``count`` pending events from a Redis Stream.

    Returns the number of events successfully processed and acknowledged.
    """
    try:
        import redis.asyncio as aioredis
    except ImportError:
        logger.warning("redis not installed; stream consumer is a no-op for %s", stream_key)
        return 0

    from app.core.config import settings
    from app.events.redis_bus import deserialize_event
    from app.events.registry import make_default_registry

    registry = make_default_registry()
    client = aioredis.from_url(settings.redis_url, decode_responses=False)

    try:
        await _ensure_group(client, stream_key)
        messages = await client.xreadgroup(
            CONSUMER_GROUP,
            CONSUMER_NAME,
            {stream_key: ">"},
            count=count,
            block=0,
        )
        processed = 0
        for _stream, entries in (messages or []):
            for msg_id, fields in entries:
                try:
                    event = deserialize_event(fields)
                    for worker in registry.workers_for(event.event_type):
                        worker.handle(event)
                    await client.xack(stream_key, CONSUMER_GROUP, msg_id)
                    processed += 1
                except Exception:
                    logger.exception(
                        "Failed to process message %s from stream %s", msg_id, stream_key
                    )
        return processed
    finally:
        await client.aclose()


async def consume_all_streams(count_per_stream: int = 50) -> dict[str, int]:
    """Drain all watched streams once. Returns a {stream: count} map."""
    import asyncio
    results = await asyncio.gather(
        *[_consume_once(s, count_per_stream) for s in WATCHED_STREAMS],
        return_exceptions=True,
    )
    return {
        stream: (r if isinstance(r, int) else 0)
        for stream, r in zip(WATCHED_STREAMS, results)
    }


async def _ensure_group(client, stream_key: str) -> None:
    try:
        await client.xgroup_create(stream_key, CONSUMER_GROUP, id="0", mkstream=True)
    except Exception:
        pass  # Group already exists — expected after first run
