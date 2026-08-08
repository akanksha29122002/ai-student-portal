from app.domain.events import DomainEvent
from app.workers.base import EventWorker


class EvaluationWorker(EventWorker):
    worker_name = "evaluation"
    subscribed_events = ("SubmissionValidated", "EvaluationStarted")

    def process(self, event: DomainEvent) -> None:
        self.logger.info("evaluation_pipeline_scheduled", extra={"correlation_id": str(event.correlation_id)})

