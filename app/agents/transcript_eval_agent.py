"""Transcript (spoken/written) evaluation agent.

Calls the Anthropic Claude API to assess whether a student's explanation
demonstrates conceptual understanding using a Socratic rubric.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.agents.base import AgentContext, bootstrap_transcript_evaluation
from app.domain.enums import EvaluationKind, EvaluationVerdict
from app.schemas.core import EvaluationCreate, Evidence

logger = logging.getLogger("project_defense.agents.transcript_eval")

PROMPT_VERSION = "transcript-eval-agent.v1"

_SYSTEM_PROMPT = (
    "You are an AI evaluator for an engineering project defense platform. "
    "Assess whether a student's written or spoken explanation demonstrates "
    "conceptual understanding of the assigned task.\n\n"
    "Apply a Socratic rubric: depth of understanding, correct use of terminology, "
    "reasoning about trade-offs, and coverage of expected concepts. Be rigorous but fair.\n\n"
    "Respond with ONLY a JSON object — no markdown fences, no preamble, no explanation.\n\n"
    "Required fields:\n"
    '{\n'
    '  "verdict": one of ["correct","partially_correct","incorrect","needs_human_review"],\n'
    '  "score": integer 0-100,\n'
    '  "confidence": float 0.0-1.0,\n'
    '  "evidence_summary": "1-3 sentences citing specific phrases or concepts from the transcript",\n'
    '  "flags": ["array","of","issue_tags"],\n'
    '  "mentor_note": "internal note for the mentor (max 400 chars)",\n'
    '  "student_feedback_draft": "constructive feedback, second-person (max 400 chars)",\n'
    '  "recommended_next_action": one of ["none","mentor_review_required","request_revision","send_reminder"]\n'
    "}"
)

_VERDICT_MAP: dict[str, EvaluationVerdict] = {
    "correct": EvaluationVerdict.CORRECT,
    "partially_correct": EvaluationVerdict.PARTIALLY_CORRECT,
    "incorrect": EvaluationVerdict.INCORRECT,
    "needs_human_review": EvaluationVerdict.NEEDS_HUMAN_REVIEW,
}

_ACTION_ALLOWLIST = frozenset({
    "none", "mentor_review_required", "request_revision", "send_reminder"
})


class TranscriptEvalAgent:
    """Evaluates a transcript submission against task rubric using Claude."""

    def __init__(self, client: Any, model: str) -> None:
        self._client = client
        self._model = model

    async def evaluate(self, context: AgentContext) -> EvaluationCreate:
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": _build_prompt(context)}],
            )
            parsed = _extract_json(response.content[0].text)
            return _build_evaluation(context, parsed)
        except Exception as exc:
            logger.warning(
                "TranscriptEvalAgent failed — falling back to bootstrap",
                extra={"error": str(exc), "submission_id": str(context.submission.id)},
            )
            fallback = bootstrap_transcript_evaluation(context)
            return fallback.model_copy(
                update={"flags": [*fallback.flags, "ai_evaluation_failed"]}
            )


def _build_prompt(context: AgentContext) -> str:
    task = context.task
    submission = context.submission

    criteria = "\n".join(f"  - {c}" for c in task.acceptance_criteria)
    concepts = ", ".join(task.expected_concepts) if task.expected_concepts else "not specified"

    lines = [
        f"TASK: {task.title}",
        f"Problem Statement: {task.problem_statement}",
        f"Acceptance Criteria:\n{criteria}",
        f"Expected Concepts: {concepts}",
        "",
        f"STUDENT SELF-STATUS: {submission.self_status}",
    ]
    if submission.approach_note:
        lines.append(f"Student's Approach Note: {submission.approach_note}")

    if submission.transcript_text:
        preview = submission.transcript_text[:3000]
        lines += ["", f"TRANSCRIPT:\n{preview}"]
        if len(submission.transcript_text) > 3000:
            lines.append("[transcript truncated to 3000 chars]")
    elif submission.transcript_url:
        lines += [
            "",
            f"TRANSCRIPT URL: {submission.transcript_url}",
            "(transcript text not provided inline — evaluate based on URL reference only)",
        ]
    else:
        lines += ["", "TRANSCRIPT: not provided"]

    return "\n".join(lines)


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return json.loads(text.strip())


def _build_evaluation(context: AgentContext, parsed: dict) -> EvaluationCreate:
    submission = context.submission
    verdict = _VERDICT_MAP.get(
        str(parsed.get("verdict", "")).lower(), EvaluationVerdict.NEEDS_HUMAN_REVIEW
    )
    score = max(0, min(100, int(parsed.get("score", 60))))
    confidence = max(0.0, min(1.0, float(parsed.get("confidence", 0.5))))
    evidence_summary = str(parsed.get("evidence_summary", "AI evaluation completed."))[:500]
    flags = [str(f)[:80] for f in parsed.get("flags", []) if str(f)][:20]
    mentor_note = str(parsed.get("mentor_note", "Awaiting mentor review."))[:400]
    student_feedback = str(parsed.get("student_feedback_draft", "Your transcript has been evaluated."))[:400]
    action = str(parsed.get("recommended_next_action", "mentor_review_required"))
    if action not in _ACTION_ALLOWLIST:
        action = "mentor_review_required"

    evidence_ref = str(submission.transcript_url or "inline_transcript")[:500]

    return EvaluationCreate(
        organization_id=submission.organization_id,
        submission_id=submission.id,
        kind=EvaluationKind.TRANSCRIPT,
        verdict=verdict,
        score=score,
        confidence=confidence,
        evidence=[Evidence(
            type="transcript_analysis",
            reference=evidence_ref,
            summary=evidence_summary,
        )],
        flags=flags,
        mentor_note=mentor_note,
        student_feedback_draft=student_feedback,
        recommended_next_action=action,
        prompt_version=PROMPT_VERSION,
    )
