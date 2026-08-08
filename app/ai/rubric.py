"""Evaluation rubric — dimension weights and score calculation."""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Rubric weights (must sum to 1.0)
# ---------------------------------------------------------------------------

RUBRIC_WEIGHTS: dict[str, float] = {
    "correctness": 0.25,
    "task_completeness": 0.20,
    "code_quality": 0.15,
    "architecture": 0.10,
    "security": 0.10,
    "performance": 0.05,
    "maintainability": 0.05,
    "edge_cases": 0.05,
    "testing": 0.05,
}

assert abs(sum(RUBRIC_WEIGHTS.values()) - 1.0) < 1e-9, "Rubric weights must sum to 1.0"

# Threshold below which a submission is escalated for human review
DEFAULT_CONFIDENCE_THRESHOLD: float = 0.70


def calculate_weighted_score(dimension_scores: dict[str, float]) -> float:
    """Calculate overall weighted score (0–10) from 9 dimension scores."""
    total = 0.0
    for dim, weight in RUBRIC_WEIGHTS.items():
        score = dimension_scores.get(dim, 0.0)
        total += score * weight
    return round(total, 2)


def requires_human_review(
    confidence: float,
    has_critical_security: bool = False,
    validation_failed: bool = False,
    context_incomplete: bool = False,
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> tuple[bool, list[str]]:
    """Return (needs_review, reasons) based on evaluation output."""
    reasons = []
    if confidence < threshold:
        reasons.append(f"Confidence {confidence:.0%} is below threshold {threshold:.0%}")
    if has_critical_security:
        reasons.append("Critical security vulnerability detected")
    if validation_failed:
        reasons.append("AI output failed validation")
    if context_incomplete:
        reasons.append("Evaluation context is incomplete (missing diff or commit data)")
    return bool(reasons), reasons
