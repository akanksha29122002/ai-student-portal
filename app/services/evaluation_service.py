from uuid import UUID

from app.domain.enums import EvaluationKind, EvaluationVerdict, SelfStatus
from app.schemas.core import EvaluationCreate, Evidence, Submission
from app.services.store import InMemoryStore


class EvaluationService:
    def __init__(self, repository: InMemoryStore) -> None:
        self.repository = repository

    def evaluate_submission(self, submission: Submission):
        if submission.self_status == SelfStatus.SKIPPED:
            payload = self._no_submission(submission)
        elif submission.commit_url:
            payload = self._github_bootstrap_evaluation(submission)
        elif submission.transcript_text or submission.transcript_url:
            payload = self._transcript_bootstrap_evaluation(submission)
        else:
            payload = self._needs_review(submission)
        return self.repository.create_evaluation(payload)

    def build_daily_summary(self, batch_id: UUID) -> dict:
        submissions = self.repository.list_batch_submissions(batch_id)
        rows = []
        totals = {
            "students_expected": len({task.student_id for task in self.repository.tasks.values() if task.batch_id == batch_id}),
            "submitted": len(submissions),
            "missing": 0,
            "strong": 0,
            "flagged": 0,
            "needs_human_review": 0,
        }

        for submission in submissions:
            evaluations = self.repository.list_submission_evaluations(submission.id)
            latest = evaluations[-1] if evaluations else None
            status = "needs_review"
            summary = "Submission received but not evaluated yet."
            action = "review_submission"
            if latest:
                if latest.verdict in {EvaluationVerdict.CORRECT, EvaluationVerdict.STRONG, EvaluationVerdict.ACCEPTABLE} and latest.confidence >= 0.7:
                    status = "on_track"
                    totals["strong"] += 1
                    action = "none"
                elif latest.verdict == EvaluationVerdict.NO_VALID_SUBMISSION:
                    status = "missing"
                    totals["missing"] += 1
                    action = "send_reminder"
                elif latest.verdict == EvaluationVerdict.NEEDS_HUMAN_REVIEW:
                    totals["needs_human_review"] += 1
                else:
                    status = "flagged"
                    totals["flagged"] += 1
                summary = latest.mentor_note

            rows.append(
                {
                    "student_id": str(submission.student_id),
                    "submission_id": str(submission.id),
                    "status": status,
                    "one_line_summary": summary,
                    "recommended_mentor_action": action,
                }
            )

        return {
            "schema_version": "mentor_daily_summary.v1",
            "batch_id": str(batch_id),
            "totals": totals,
            "students": rows,
            "batch_risks": self._batch_risks(totals),
            "mentor_actions": self._mentor_actions(rows),
        }

    def _github_bootstrap_evaluation(self, submission: Submission) -> EvaluationCreate:
        return EvaluationCreate(
            organization_id=submission.organization_id,
            submission_id=submission.id,
            kind=EvaluationKind.GITHUB_COMMIT,
            verdict=EvaluationVerdict.NEEDS_HUMAN_REVIEW,
            score=60,
            confidence=0.45,
            evidence=[
                Evidence(
                    type="commit_url",
                    reference=str(submission.commit_url),
                    summary="Commit URL was submitted and is ready for GitHub diff ingestion.",
                )
            ],
            flags=["github_integration_not_connected"],
            mentor_note="Coding submission received. Connect GitHub diff ingestion before automated correctness judgment.",
            student_feedback_draft="Your coding submission was received and is waiting for mentor review.",
            recommended_next_action="mentor_review_required",
        )

    def _transcript_bootstrap_evaluation(self, submission: Submission) -> EvaluationCreate:
        evidence_reference = str(submission.transcript_url or "inline_transcript")
        return EvaluationCreate(
            organization_id=submission.organization_id,
            submission_id=submission.id,
            kind=EvaluationKind.TRANSCRIPT,
            verdict=EvaluationVerdict.NEEDS_HUMAN_REVIEW,
            score=60,
            confidence=0.45,
            evidence=[
                Evidence(
                    type="transcript",
                    reference=evidence_reference,
                    summary="Transcript evidence was submitted and is ready for rubric evaluation.",
                )
            ],
            flags=["transcript_ai_rubric_not_connected"],
            mentor_note="Transcript submission received. Connect transcript rubric evaluation before automated readiness judgment.",
            student_feedback_draft="Your spoken explanation submission was received and is waiting for mentor review.",
            recommended_next_action="mentor_review_required",
        )

    def _no_submission(self, submission: Submission) -> EvaluationCreate:
        return EvaluationCreate(
            organization_id=submission.organization_id,
            submission_id=submission.id,
            kind=EvaluationKind.TRANSCRIPT,
            verdict=EvaluationVerdict.NO_VALID_SUBMISSION,
            score=0,
            confidence=1,
            evidence=[
                Evidence(type="submission_status", reference=str(submission.id), summary="Student marked the task as skipped.")
            ],
            flags=["student_skipped_task"],
            mentor_note="Student skipped the assigned task.",
            student_feedback_draft="You skipped this task. Please complete the next assigned item or contact your mentor if blocked.",
            recommended_next_action="send_reminder",
        )

    def _needs_review(self, submission: Submission) -> EvaluationCreate:
        return EvaluationCreate(
            organization_id=submission.organization_id,
            submission_id=submission.id,
            kind=EvaluationKind.GITHUB_COMMIT,
            verdict=EvaluationVerdict.NEEDS_HUMAN_REVIEW,
            score=0,
            confidence=1,
            evidence=[
                Evidence(type="submission", reference=str(submission.id), summary="No machine-readable evidence was attached.")
            ],
            flags=["missing_evidence"],
            mentor_note="Submission is missing usable evidence.",
            student_feedback_draft="Your submission is missing the required evidence link.",
            recommended_next_action="request_revision",
        )

    def _batch_risks(self, totals: dict) -> list[str]:
        risks = []
        if totals["missing"] > 0:
            risks.append("Some students have no valid submission.")
        if totals["needs_human_review"] > 0:
            risks.append("Some evaluations need mentor review before feedback release.")
        return risks

    def _mentor_actions(self, rows: list[dict]) -> list[str]:
        actions = []
        if any(row["recommended_mentor_action"] == "review_submission" for row in rows):
            actions.append("Review pending evaluated submissions.")
        if any(row["recommended_mentor_action"] == "send_reminder" for row in rows):
            actions.append("Send reminders to students with missing or skipped work.")
        return actions

