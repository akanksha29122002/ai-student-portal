"""GitHub commit evaluation agent.

Calls the Anthropic Claude API to assess whether a student's code commit meets
the task acceptance criteria, then maps the response to a typed EvaluationCreate.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.agents.base import AgentContext, bootstrap_github_evaluation
from app.domain.enums import EvaluationKind, EvaluationVerdict
from app.schemas.core import EvaluationCreate, Evidence

logger = logging.getLogger("project_defense.agents.github_eval")

PROMPT_VERSION = "github-eval-agent.v1"

_SYSTEM_PROMPT = (
    "You are an AI evaluator for an engineering project defense platform. "
    "Assess whether a student's code submission meets the defined acceptance criteria.\n\n"
    "Be objective, evidence-based, and fair. Reference specific filenames, functions, "
    "or patterns from the commit when possible. Your output will be reviewed by a "
    "human mentor before being shared with the student.\n\n"
    "Respond with ONLY a JSON object — no markdown fences, no preamble, no explanation.\n\n"
    "Required fields:\n"
    '{\n'
    '  "verdict": one of ["correct","partially_correct","incorrect","needs_human_review"],\n'
    '  "score": integer 0-100 (% of acceptance criteria met),\n'
    '  "confidence": float 0.0-1.0,\n'
    '  "evidence_summary": "1-3 sentences citing specific code evidence",\n'
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


class GitHubEvalAgent:
    """Evaluates a coding submission against task acceptance criteria using Claude."""

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
                "GitHubEvalAgent failed — falling back to bootstrap",
                extra={"error": str(exc), "submission_id": str(context.submission.id)},
            )
            fallback = bootstrap_github_evaluation(context)
            return fallback.model_copy(
                update={"flags": [*fallback.flags, "ai_evaluation_failed"]}
            )


def _build_prompt(context: AgentContext) -> str:
    task = context.task
    submission = context.submission
    commit = context.commit_info

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

    if commit is not None:
        first_line = commit.message.splitlines()[0][:120]
        lines += [
            "",
            f"COMMIT SHA: {commit.sha[:12]}",
            f"Commit Message: {first_line}",
            f"Stats: +{commit.stats.additions} additions, -{commit.stats.deletions} deletions,"
            f" {len(commit.files)} file(s) changed",
        ]
        for f in commit.files[:10]:
            lines.append(f"  [{f.status}] {f.filename}  +{f.additions}/-{f.deletions}")
            if f.patch:
                lines.append(f"    Patch: {f.patch[:300]}")
    else:
        lines += ["", "COMMIT DETAILS: not available (could not be fetched from GitHub)"]

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
    student_feedback = str(parsed.get("student_feedback_draft", "Your submission has been evaluated."))[:400]
    action = str(parsed.get("recommended_next_action", "mentor_review_required"))
    if action not in _ACTION_ALLOWLIST:
        action = "mentor_review_required"

    commit_ref = str(submission.commit_url or "")
    if context.commit_info:
        commit_ref = context.commit_info.sha[:500]

    return EvaluationCreate(
        organization_id=submission.organization_id,
        submission_id=submission.id,
        kind=EvaluationKind.GITHUB_COMMIT,
        verdict=verdict,
        score=score,
        confidence=confidence,
        evidence=[Evidence(
            type="commit_analysis",
            reference=commit_ref or str(submission.id),
            summary=evidence_summary,
        )],
        flags=flags,
        mentor_note=mentor_note,
        student_feedback_draft=student_feedback,
        recommended_next_action=action,
        prompt_version=PROMPT_VERSION,
    )
