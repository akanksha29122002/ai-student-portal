from app.domain.events import DomainEvent
from app.workers.base import EventWorker


class ReminderWorker(EventWorker):
    worker_name = "reminder"
    subscribed_events = ("SubmissionMissed",)

    def process(self, event: DomainEvent) -> None:
        self.logger.info("reminder_rule_scheduled", extra={"correlation_id": str(event.correlation_id)})

