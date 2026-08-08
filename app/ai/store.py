"""In-memory store for AI evaluation records (Milestone 5).

Separate from InMemoryStore (core.py) and GitHubMemoryStore (github).
Keyed by evaluation_id and indexed by submission_id.
"""
from __future__ import annotations

from uuid import UUID

from app.ai.schemas import EvaluationRecord, EvaluationState


class AIEvaluationStore:
    def __init__(self) -> None:
        self._records: dict[UUID, EvaluationRecord] = {}
        self._by_submission: dict[UUID, UUID] = {}  # submission_id → latest evaluation_id

    def create(self, record: EvaluationRecord) -> EvaluationRecord:
        self._records[record.id] = record
        self._by_submission[record.submission_id] = record.id
        return record

    def get(self, evaluation_id: UUID) -> EvaluationRecord | None:
        return self._records.get(evaluation_id)

    def get_by_submission(self, submission_id: UUID) -> EvaluationRecord | None:
        eid = self._by_submission.get(submission_id)
        return self._records.get(eid) if eid else None

    def update(self, record: EvaluationRecord) -> EvaluationRecord:
        self._records[record.id] = record
        self._by_submission[record.submission_id] = record.id
        return record

    def list_for_org(self, organization_id: UUID, limit: int = 50) -> list[EvaluationRecord]:
        results = [r for r in self._records.values() if r.organization_id == organization_id]
        results.sort(key=lambda r: r.created_at, reverse=True)
        return results[:limit]

    def list_needs_review(self, organization_id: UUID) -> list[EvaluationRecord]:
        return [
            r for r in self._records.values()
            if r.organization_id == organization_id
            and r.state == EvaluationState.NEEDS_HUMAN_REVIEW
            and r.mentor_decision is None
        ]

    def find_by_context_hash(self, context_hash: str) -> EvaluationRecord | None:
        for record in self._records.values():
            if record.context_hash == context_hash and record.state == EvaluationState.COMPLETED:
                return record
        return None


# ---------------------------------------------------------------------------
# Process-level singleton
# ---------------------------------------------------------------------------

_store: AIEvaluationStore | None = None


def get_ai_store() -> AIEvaluationStore:
    global _store
    if _store is None:
        _store = AIEvaluationStore()
    return _store


def reset_ai_store() -> None:
    """Reset singleton — used in tests."""
    global _store
    _store = None
