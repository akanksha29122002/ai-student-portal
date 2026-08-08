from app.domain.events import DomainEvent
from app.workers.base import EventWorker


class NotificationWorker(EventWorker):
    worker_name = "notification"
    subscribed_events = ("ReminderTriggered", "FeedbackReleased")

    def process(self, event: DomainEvent) -> None:
        self.logger.info("notification_delivery_scheduled", extra={"correlation_id": str(event.correlation_id)})

