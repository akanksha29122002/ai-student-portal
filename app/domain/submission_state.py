"""Submission state machine — pure domain logic, no persistence."""
from __future__ import annotations

from app.domain.enums import SubmissionState

_VALID_TRANSITIONS: dict[SubmissionState, frozenset[SubmissionState]] = {
    SubmissionState.DRAFT: frozenset({
        SubmissionState.SUBMITTED,
        SubmissionState.CANCELLED,
        SubmissionState.FAILED,
    }),
    SubmissionState.SUBMITTED: frozenset({
        SubmissionState.VALIDATING,
        SubmissionState.CANCELLED,
    }),
    SubmissionState.VALIDATING: frozenset({
        SubmissionState.VALIDATED,
        SubmissionState.FAILED,
    }),
    SubmissionState.VALIDATED: frozenset({
        SubmissionState.READY_FOR_EVALUATION,
        SubmissionState.FAILED,
    }),
    SubmissionState.READY_FOR_EVALUATION: frozenset({
        SubmissionState.EVALUATING,
        SubmissionState.CANCELLED,
    }),
    SubmissionState.EVALUATING: frozenset({
        SubmissionState.EVALUATED,
        SubmissionState.FAILED,
    }),
    SubmissionState.EVALUATED: frozenset({
        SubmissionState.MENTOR_REVIEW,
        SubmissionState.APPROVED,
    }),
    SubmissionState.MENTOR_REVIEW: frozenset({
        SubmissionState.APPROVED,
        SubmissionState.REJECTED,
    }),
    SubmissionState.APPROVED: frozenset(),
    SubmissionState.REJECTED: frozenset({
        SubmissionState.DRAFT,
        SubmissionState.CANCELLED,
    }),
    SubmissionState.FAILED: frozenset({
        SubmissionState.DRAFT,
        SubmissionState.CANCELLED,
    }),
    SubmissionState.CANCELLED: frozenset(),
}

_TERMINAL_STATES: frozenset[SubmissionState] = frozenset({
    SubmissionState.APPROVED,
    SubmissionState.CANCELLED,
})


def transition(current: SubmissionState, target: SubmissionState) -> SubmissionState:
    """Return *target* if the transition is valid, otherwise raise ValueError."""
    allowed = _VALID_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise ValueError(
            f"Invalid state transition: {current!r} → {target!r}. "
            f"Allowed from {current!r}: {sorted(str(s) for s in allowed)}"
        )
    return target


def can_transition(current: SubmissionState, target: SubmissionState) -> bool:
    return target in _VALID_TRANSITIONS.get(current, frozenset())


def is_terminal(state: SubmissionState) -> bool:
    return state in _TERMINAL_STATES


def allowed_next(state: SubmissionState) -> list[SubmissionState]:
    return list(_VALID_TRANSITIONS.get(state, frozenset()))
