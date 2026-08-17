"""Deterministic task verification foundation.

This service creates an Evaluation from the assigned task, student explanation,
implementation statement, and commit URL. It intentionally marks Git diff
inspection as pending unless commit ingestion evidence exists later.
"""
from __future__ import annotations

from app.application.unit_of_work import AsyncUnitOfWork
from app.domain.enums import EvaluationKind, EvaluationVerdict
from app.schemas.core import Evaluation, EvaluationCreate, Evidence, Submission, Task
from app.shared.exceptions import NotFoundException


class TaskVerificationService:
    def __init__(self, uow: AsyncUnitOfWork) -> None:
        self._uow = uow

    async def verify_submission(self, submission_id) -> Evaluation:
        submission = await self._uow.submissions.get(submission_id)
        if submission is None:
            raise NotFoundException("Submission not found")
        task = await self._uow.tasks.get(submission.task_id)
        if task is None:
            raise NotFoundException("Task not found for submission")

        existing = await self._uow.evaluations.list_for_submission(submission.id)
        if existing:
            return existing[-1]

        payload = self._build_evaluation(task, submission)
        async with self._uow:
            return await self._uow.evaluations.create(payload)

    def _build_evaluation(self, task: Task, submission: Submission) -> EvaluationCreate:
        explanation = submission.transcript_text or ""
        implementation = submission.approach_note or ""
        combined = f"{explanation}\n{implementation}".lower()

        criteria_evidence: list[Evidence] = []
        missing: list[str] = []
        matched = 0
        for criterion in task.acceptance_criteria:
            tokens = [token.strip(".,:;()[]{}").lower() for token in criterion.split() if len(token.strip(".,:;()[]{}")) >= 5]
            token_hits = [token for token in tokens if token in combined]
            status = "partial" if token_hits else "cannot_verify"
            if token_hits:
                matched += 1
            else:
                missing.append(criterion)
            criteria_evidence.append(
                Evidence(
                    type="acceptance_criterion_check",
                    reference=criterion,
                    summary=f"{status}: matched terms {token_hits[:5]}" if token_hits else "cannot_verify from submitted explanation alone",
                )
            )

        has_commit = submission.commit_url is not None
        has_explanation = bool(explanation.strip())
        has_implementation = bool(implementation.strip())
        base_score = 30
        if has_commit:
            base_score += 25
        if has_explanation:
            base_score += 20
        if has_implementation:
            base_score += 15
        if task.acceptance_criteria:
            base_score += int((matched / len(task.acceptance_criteria)) * 10)
        score = max(0, min(100, base_score))

        flags = []
        if not has_commit:
            flags.append("MISSING_COMMIT")
        else:
            flags.append("GITHUB_DIFF_NOT_INGESTED")
        if missing:
            flags.append("ACCEPTANCE_CRITERIA_NOT_FULLY_VERIFIED")
        if not has_explanation or not has_implementation:
            flags.append("MISSING_STUDENT_EXPLANATION")

        verdict = (
            EvaluationVerdict.NEEDS_HUMAN_REVIEW
            if "GITHUB_DIFF_NOT_INGESTED" in flags or score < 70
            else EvaluationVerdict.ACCEPTABLE
        )

        return EvaluationCreate(
            organization_id=submission.organization_id,
            submission_id=submission.id,
            kind=EvaluationKind.GITHUB_COMMIT,
            verdict=verdict,
            score=score,
            confidence=0.55 if has_commit else 0.3,
            evidence=[
                Evidence(
                    type="commit_url",
                    reference=str(submission.commit_url or ""),
                    summary="Commit URL submitted; diff ingestion is pending." if has_commit else "No commit URL submitted.",
                ),
                Evidence(
                    type="explanation_vs_task",
                    reference=str(task.id),
                    summary=f"Matched {matched}/{len(task.acceptance_criteria)} acceptance criteria from explanation/implementation text.",
                ),
                *criteria_evidence,
            ],
            flags=flags,
            mentor_note=(
                "Submission received and preliminarily checked. "
                "Implementation claim could not be fully verified from submitted evidence until Git diff ingestion runs."
            ),
            student_feedback_draft=(
                "Your submission was received. Add clear evidence in your explanation and ensure the commit contains the requested implementation."
            ),
            recommended_next_action="mentor_review_required" if verdict == EvaluationVerdict.NEEDS_HUMAN_REVIEW else "none",
            prompt_version="deterministic-task-verification.v1",
        )
