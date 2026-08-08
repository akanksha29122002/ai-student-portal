"""Handler registry — maps domain event types to EventWorker instances.

Bridges the existing synchronous EventWorker classes to the async
InMemoryEventBus using thin async adapter wrappers.  Also supports
async-native handlers (objects with ``event_type: str`` and
``async def handle(event)``) registered via ``register_handler()``.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.domain.events import DomainEvent
from app.events.bus import Handler, InMemoryEventBus
from app.workers.base import EventWorker


class HandlerRegistry:
    """Registers EventWorkers and async handlers; wires them to an InMemoryEventBus.

    Usage::

        registry = HandlerRegistry()
        registry.register(SubmissionWorker(), EvaluationWorker())      # sync workers
        registry.register_handler(GitHubValidationHandler())           # async handlers
        registry.wire(bus)
    """

    def __init__(self) -> None:
        self._workers: list[EventWorker] = []
        self._async_handlers: list[Any] = []

    def register(self, *workers: EventWorker) -> "HandlerRegistry":
        """Register synchronous EventWorker instances."""
        self._workers.extend(workers)
        return self

    def register_handler(self, *handlers: Any) -> "HandlerRegistry":
        """Register async-native handlers.

        Each handler must expose:
        - ``event_type: str`` — the event type string to subscribe to
        - ``async def handle(self, event: DomainEvent) -> None``
        """
        self._async_handlers.extend(handlers)
        return self

    def wire(self, bus: InMemoryEventBus) -> None:
        """Subscribe all registered workers and async handlers to the bus."""
        for worker in self._workers:
            for event_type in worker.subscribed_events:
                bus.subscribe(event_type, _sync_adapter(worker))
        for handler in self._async_handlers:
            bus.subscribe(handler.event_type, handler.handle)

    def workers_for(self, event_type: str) -> list[EventWorker]:
        return [w for w in self._workers if event_type in w.subscribed_events]


def _sync_adapter(worker: EventWorker) -> Handler:
    """Wrap EventWorker.handle() in an async callable for the bus."""
    async def _handler(event: DomainEvent) -> None:
        worker.handle(event)
    _handler.__name__ = f"{worker.worker_name}_async_adapter"
    return _handler


def make_default_registry() -> HandlerRegistry:
    """Create a HandlerRegistry pre-loaded with all production workers and handlers."""
    from app.integrations.github.event_handler import GitHubValidationHandler
    from app.workers.evaluation_worker import EvaluationWorker
    from app.workers.notification_worker import NotificationWorker
    from app.workers.reminder_worker import ReminderWorker
    from app.workers.submission_worker import SubmissionWorker
    from app.workers.summary_worker import SummaryWorker

    return (
        HandlerRegistry()
        .register(SubmissionWorker(), EvaluationWorker(), NotificationWorker(), SummaryWorker(), ReminderWorker())
        .register_handler(GitHubValidationHandler())
    )
