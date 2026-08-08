from app.domain.events import DomainEvent
from app.workers.base import EventWorker


class SummaryWorker(EventWorker):
    worker_name = "summary"
    subscribed_events = ("EvaluationCompleted", "MentorReviewed")

    def process(self, event: DomainEvent) -> None:
        self.logger.info("summary_refresh_scheduled", extra={"correlation_id": str(event.correlation_id)})

