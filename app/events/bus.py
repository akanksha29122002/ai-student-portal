"""Core event bus infrastructure.

Provides:
- EventBus protocol
- InMemoryEventBus — synchronous in-process dispatch (dev/test)
- EventDispatchingUnitOfWork — UoW wrapper that publishes collected events after commit
"""
from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Protocol

from app.domain.events import DomainEvent

logger = logging.getLogger("project_defense.events.bus")

Handler = Callable[[DomainEvent], Awaitable[None]]


class EventBus(Protocol):
    async def publish(self, event: DomainEvent) -> None: ...


class InMemoryEventBus:
    """In-process event bus for development and testing.

    Handlers are invoked immediately and synchronously within the calling
    coroutine — no queuing, no network I/O.  Handler exceptions are caught
    and logged so one bad handler cannot abort sibling handlers.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._published: list[DomainEvent] = []

    def subscribe(self, event_type: str, handler: Handler) -> None:
        """Register a handler for a specific event type or ``"*"`` for all."""
        self._handlers[event_type].append(handler)

    async def publish(self, event: DomainEvent) -> None:
        self._published.append(event)
        for handler in [
            *self._handlers.get(event.event_type, []),
            *self._handlers.get("*", []),
        ]:
            try:
                await handler(event)
            except Exception:
                logger.exception(
                    "Event handler raised an unhandled exception",
                    extra={"event_type": event.event_type, "event_id": str(event.event_id)},
                )

    @property
    def published(self) -> list[DomainEvent]:
        return list(self._published)

    def clear(self) -> None:
        self._published.clear()


class _EventCollector:
    """Intercepts AsyncEventStore.append() to shadow-collect events."""

    def __init__(self, inner, collector: list[DomainEvent]) -> None:
        self._inner = inner
        self._collector = collector

    async def append(self, event: DomainEvent) -> DomainEvent:
        result = await self._inner.append(event)
        self._collector.append(event)
        return result

    async def list_by_aggregate(self, aggregate_id) -> list[DomainEvent]:
        return await self._inner.list_by_aggregate(aggregate_id)


class EventDispatchingUnitOfWork:
    """UoW decorator that publishes domain events to an EventBus after commit.

    Wrap any ``AsyncUnitOfWork`` implementation:

        uow = EventDispatchingUnitOfWork(inner_uow, bus)
        async with uow:
            entity = await uow.students.create(...)
            await uow.events.append(StudentRegistered(...))
        # ← StudentRegistered is published to ``bus`` here

    A rollback (or exception inside the block) suppresses dispatch — no
    events leak from failed transactions.  All repository attributes
    (``organizations``, ``batches``, …, ``users``) are transparently
    delegated to the inner UoW via ``__getattr__``.
    """

    def __init__(self, inner, bus: EventBus) -> None:
        self.__dict__["_inner"] = inner
        self.__dict__["_bus"] = bus
        self.__dict__["_pending"] = []
        self.__dict__["events"] = _EventCollector(inner.events, self.__dict__["_pending"])

    def __getattr__(self, name: str):
        return getattr(self.__dict__["_inner"], name)

    async def __aenter__(self) -> "EventDispatchingUnitOfWork":
        pending: list[DomainEvent] = self.__dict__["_pending"]
        pending.clear()
        inner = self.__dict__["_inner"]
        await inner.__aenter__()
        self.__dict__["events"] = _EventCollector(inner.events, pending)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        inner = self.__dict__["_inner"]
        await inner.__aexit__(exc_type, exc, tb)
        if exc_type is None:
            bus: EventBus = self.__dict__["_bus"]
            to_dispatch = list(self.__dict__["_pending"])
            self.__dict__["_pending"].clear()
            for event in to_dispatch:
                await bus.publish(event)

    async def commit(self) -> None:
        await self.__dict__["_inner"].commit()

    async def rollback(self) -> None:
        await self.__dict__["_inner"].rollback()

    async def begin_nested(self):
        return await self.__dict__["_inner"].begin_nested()
