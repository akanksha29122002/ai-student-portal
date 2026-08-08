import logging
from abc import ABC, abstractmethod

from app.domain.events import DomainEvent


class EventWorker(ABC):
    worker_name: str
    subscribed_events: tuple[str, ...]

    def __init__(self) -> None:
        self.logger = logging.getLogger(f"project_defense.worker.{self.worker_name}")

    def can_handle(self, event: DomainEvent) -> bool:
        return event.event_type in self.subscribed_events

    def handle(self, event: DomainEvent) -> None:
        if not self.can_handle(event):
            return
        self.logger.info("event_received", extra={"correlation_id": str(event.correlation_id)})
        self.process(event)

    @abstractmethod
    def process(self, event: DomainEvent) -> None:
        raise NotImplementedError

