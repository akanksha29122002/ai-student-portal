from uuid import UUID, uuid4

import pytest

from app.domain.events import (
    DailySummaryGenerated,
    DomainEvent,
    EvaluationCompleted,
    EvaluationStarted,
    MentorReviewed,
    ProjectCreated,
    ReminderTriggered,
    StudentRegistered,
    SubmissionReceived,
    SubmissionValidated,
    TaskAssigned,
)
from app.infrastructure.repositories.memory import MemoryEventStore
from app.services.store import InMemoryStore


def test_domain_event_has_required_fields():
    event = StudentRegistered(aggregate_id=uuid4(), payload={"email": "asha@example.com"})

    assert isinstance(event.event_id, UUID)
    assert isinstance(event.correlation_id, UUID)
    assert event.event_type == "StudentRegistered"
    assert event.aggregate_type == "student"
    assert event.occurred_at is not None


def test_all_event_types_have_correct_aggregate_type():
    agg_id = uuid4()
    payload = {"key": "value"}

    assertions = [
        (StudentRegistered(aggregate_id=agg_id, payload=payload), "student", "StudentRegistered"),
        (ProjectCreated(aggregate_id=agg_id, payload=payload), "project", "ProjectCreated"),
        (TaskAssigned(aggregate_id=agg_id, payload=payload), "task", "TaskAssigned"),
        (SubmissionReceived(aggregate_id=agg_id, payload=payload), "submission", "SubmissionReceived"),
        (SubmissionValidated(aggregate_id=agg_id, payload=payload), "submission", "SubmissionValidated"),
        (EvaluationStarted(aggregate_id=agg_id, payload=payload), "evaluation", "EvaluationStarted"),
        (EvaluationCompleted(aggregate_id=agg_id, payload=payload), "evaluation", "EvaluationCompleted"),
        (MentorReviewed(aggregate_id=agg_id, payload=payload), "mentor_review", "MentorReviewed"),
        (ReminderTriggered(aggregate_id=agg_id, payload=payload), "notification", "ReminderTriggered"),
        (DailySummaryGenerated(aggregate_id=agg_id, payload=payload), "daily_summary", "DailySummaryGenerated"),
    ]
    for event, expected_agg_type, expected_event_type in assertions:
        assert event.aggregate_type == expected_agg_type, f"{type(event).__name__} aggregate_type mismatch"
        assert event.event_type == expected_event_type, f"{type(event).__name__} event_type mismatch"


def test_domain_event_unique_ids_per_instance():
    agg_id = uuid4()
    e1 = StudentRegistered(aggregate_id=agg_id, payload={})
    e2 = StudentRegistered(aggregate_id=agg_id, payload={})

    assert e1.event_id != e2.event_id
    assert e1.correlation_id != e2.correlation_id


def test_domain_event_carries_causation_and_user():
    user_id = uuid4()
    cause_id = uuid4()
    event = EvaluationCompleted(
        aggregate_id=uuid4(),
        payload={"verdict": "needs_human_review"},
        causation_id=cause_id,
        user_id=user_id,
    )

    assert event.causation_id == cause_id
    assert event.user_id == user_id


def test_domain_event_metadata_defaults_to_empty_dict():
    event = TaskAssigned(aggregate_id=uuid4(), payload={})
    assert event.metadata == {}


def test_memory_event_store_append_and_retrieve():
    store = InMemoryStore()
    event_store = MemoryEventStore(store)
    agg_id = uuid4()

    e1 = StudentRegistered(aggregate_id=agg_id, payload={"email": "asha@example.com"})
    e2 = ProjectCreated(aggregate_id=agg_id, payload={"name": "Defense App"})
    other = TaskAssigned(aggregate_id=uuid4(), payload={})

    event_store.append(e1)
    event_store.append(e2)
    event_store.append(other)

    results = event_store.list_by_aggregate(agg_id)
    assert len(results) == 2
    assert results[0].event_type == "StudentRegistered"
    assert results[1].event_type == "ProjectCreated"


def test_memory_event_store_returns_empty_list_for_unknown_aggregate():
    store = InMemoryStore()
    event_store = MemoryEventStore(store)

    assert event_store.list_by_aggregate(uuid4()) == []


def test_memory_event_store_append_returns_event():
    store = InMemoryStore()
    event_store = MemoryEventStore(store)
    event = StudentRegistered(aggregate_id=uuid4(), payload={})

    returned = event_store.append(event)

    assert returned is event


def test_events_are_isolated_across_stores():
    store_a = InMemoryStore()
    store_b = InMemoryStore()
    es_a = MemoryEventStore(store_a)
    es_b = MemoryEventStore(store_b)
    agg_id = uuid4()

    es_a.append(StudentRegistered(aggregate_id=agg_id, payload={}))

    assert len(es_a.list_by_aggregate(agg_id)) == 1
    assert len(es_b.list_by_aggregate(agg_id)) == 0
