from app.domain.events import DomainEvent
from app.workers.base import EventWorker


class SubmissionWorker(EventWorker):
    worker_name = "submission"
    subscribed_events = ("SubmissionReceived",)

    def process(self, event: DomainEvent) -> None:
        self.logger.info("submission_validation_scheduled", extra={"correlation_id": str(event.correlation_id)})

