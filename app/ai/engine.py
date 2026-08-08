"""AI Evaluation Engine — core evaluation pipeline.

Pipeline:
  PENDING → CONTEXT_BUILDING → EVALUATING → VALIDATING
  → COMPLETED | NEEDS_HUMAN_REVIEW | FAILED
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import UTC, datetime
from uuid import UUID

from app.ai.context_builder import EvaluationContext
from app.ai.prompts import EVALUATION_SYSTEM_PROMPT_V1, PROMPT_VERSION, build_user_prompt
from app.ai.rubric import DEFAULT_CONFIDENCE_THRESHOLD, requires_human_review
from app.ai.schemas import (
    CriterionResult,
    CriterionStatus,
    DimensionScore,
    EvaluationDimensions,
    EvaluationRecord,
    EvaluationResult,
    EvaluationState,
    EvidenceItem,
    EvidenceSeverity,
    RawEvaluationResult,
    SubmissionVerdict,
)
from app.ai.store import AIEvaluationStore

logger = logging.getLogger("project_defense.ai.engine")


class EvaluationEngine:
    """Orchestrates the full evaluation pipeline."""

    def __init__(
        self,
        provider,
        store: AIEvaluationStore,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    ) -> None:
        self._provider = provider
        self._store = store
        self._threshold = confidence_threshold

    async def evaluate(
        self,
        record: EvaluationRecord,
        context: EvaluationContext,
    ) -> EvaluationRecord:
        """Run the full pipeline and return the updated record."""
        start = time.monotonic()

        # --- CONTEXT_BUILDING ---
        record = self._set_state(record, EvaluationState.CONTEXT_BUILDING)
        user_prompt = build_user_prompt(**context.to_prompt_kwargs())

        # --- EVALUATING ---
        record = self._set_state(record, EvaluationState.EVALUATING)
        try:
            ai_message = await self._provider.complete(
                system_prompt=EVALUATION_SYSTEM_PROMPT_V1,
                user_prompt=user_prompt,
                max_tokens=4096,
            )
        except Exception as exc:
            logger.error(
                "AI provider failed",
                extra={
                    "evaluation_id": str(record.id),
                    "error": str(exc),
                    "provider": self._provider.provider_name(),
                },
            )
            return self._fail(record, f"AI provider error: {exc}", start)

        duration_ms = int((time.monotonic() - start) * 1000)

        # --- VALIDATING ---
        record = self._set_state(record, EvaluationState.VALIDATING)
        try:
            result = self._parse_and_validate(ai_message.content)
        except Exception as exc:
            logger.warning(
                "AI output validation failed",
                extra={"evaluation_id": str(record.id), "error": str(exc)},
            )
            return self._fail(record, f"Validation error: {exc}", start)

        # Check human review escalation
        has_critical = any(
            c.severity == EvidenceSeverity.CRITICAL
            for c in result.security_concerns
        )
        needs_review, review_reasons = requires_human_review(
            confidence=result.confidence,
            has_critical_security=has_critical,
            validation_failed=False,
            context_incomplete=context.commit_sha is None,
            threshold=self._threshold,
        )

        final_state = (
            EvaluationState.NEEDS_HUMAN_REVIEW if needs_review else EvaluationState.COMPLETED
        )

        record = record.model_copy(update={
            "state": final_state,
            "result": result,
            "provider": self._provider.provider_name(),
            "model": self._provider.model_name(),
            "prompt_version": PROMPT_VERSION,
            "context_hash": context.context_hash(),
            "input_tokens": ai_message.input_tokens,
            "output_tokens": ai_message.output_tokens,
            "duration_ms": duration_ms,
            "updated_at": datetime.now(UTC),
        })

        if needs_review:
            # Merge review reasons into result
            existing = list(result.mentor_attention_reasons)
            merged = list(dict.fromkeys(existing + review_reasons))
            record = record.model_copy(update={
                "result": result.model_copy(update={
                    "mentor_attention_required": True,
                    "mentor_attention_reasons": merged,
                })
            })

        record = self._store.update(record)

        logger.info(
            "Evaluation completed",
            extra={
                "evaluation_id": str(record.id),
                "submission_id": str(record.submission_id),
                "state": record.state,
                "provider": record.provider,
                "model": record.model,
                "overall_score": result.overall_score,
                "confidence": result.confidence,
                "input_tokens": record.input_tokens,
                "output_tokens": record.output_tokens,
                "duration_ms": record.duration_ms,
            },
        )

        return record

    # ------------------------------------------------------------------
    # Parsing and validation
    # ------------------------------------------------------------------

    def _parse_and_validate(self, raw: str) -> EvaluationResult:
        """Parse AI JSON output into a validated EvaluationResult."""
        text = raw.strip()
        # Strip markdown fences if present
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```$", "", text.strip())

        data = json.loads(text.strip())
        raw_result = RawEvaluationResult.model_validate(data)
        return self._coerce_to_strict(raw_result)

    def _coerce_to_strict(self, raw: RawEvaluationResult) -> EvaluationResult:
        """Convert the permissive raw result to the strict EvaluationResult schema."""

        def _coerce_evidence(items: list) -> list[EvidenceItem]:
            result = []
            for item in items:
                if isinstance(item, dict):
                    try:
                        ev = EvidenceItem(
                            file=str(item.get("file", "unknown"))[:800],
                            line=item.get("line"),
                            type=str(item.get("type", "quality"))[:80],
                            severity=_safe_severity(item.get("severity", "info")),
                            description=str(item.get("description", ""))[:1000] or "No description.",
                        )
                        result.append(ev)
                    except Exception:
                        pass
            return result[:10]

        def _coerce_dim(rd) -> DimensionScore:
            return DimensionScore(
                score=max(0.0, min(10.0, float(rd.score))),
                reason=str(rd.reason or "No reason provided.")[:1000] or "No reason provided.",
                evidence=_coerce_evidence(rd.evidence),
            )

        dims = raw.dimensions
        dimensions = EvaluationDimensions(
            correctness=_coerce_dim(dims.correctness),
            task_completeness=_coerce_dim(dims.task_completeness),
            code_quality=_coerce_dim(dims.code_quality),
            architecture=_coerce_dim(dims.architecture),
            security=_coerce_dim(dims.security),
            performance=_coerce_dim(dims.performance),
            maintainability=_coerce_dim(dims.maintainability),
            edge_cases=_coerce_dim(dims.edge_cases),
            testing=_coerce_dim(dims.testing),
        )

        criteria_results = []
        for cr in raw.acceptance_criteria_results:
            try:
                status_str = str(cr.status).upper()
                status = CriterionStatus(status_str) if status_str in CriterionStatus.__members__ else CriterionStatus.CANNOT_VERIFY
                criteria_results.append(CriterionResult(
                    criterion=str(cr.criterion)[:500],
                    status=status,
                    evidence=[str(e)[:300] for e in cr.evidence[:10]],
                    notes=str(cr.notes or "")[:300],
                ))
            except Exception:
                pass

        verdict_str = str(raw.status).upper()
        try:
            verdict = SubmissionVerdict(verdict_str)
        except ValueError:
            verdict = SubmissionVerdict.NEEDS_HUMAN_REVIEW

        summary_text = str(raw.summary or "Evaluation completed.")
        if not summary_text.strip():
            summary_text = "Evaluation completed."

        return EvaluationResult(
            status=verdict,
            overall_score=max(0.0, min(10.0, float(raw.overall_score))),
            confidence=max(0.0, min(1.0, float(raw.confidence))),
            dimensions=dimensions,
            acceptance_criteria_results=criteria_results,
            strengths=[str(s)[:500] for s in raw.strengths[:20]],
            issues=_coerce_evidence(raw.issues),
            missing_requirements=[str(m)[:500] for m in raw.missing_requirements[:20]],
            security_concerns=_coerce_evidence(raw.security_concerns),
            performance_concerns=_coerce_evidence(raw.performance_concerns),
            suggested_improvements=[str(s)[:500] for s in raw.suggested_improvements[:20]],
            mentor_attention_required=bool(raw.mentor_attention_required),
            mentor_attention_reasons=[str(r)[:300] for r in raw.mentor_attention_reasons[:10]],
            summary=summary_text[:3000],
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_state(self, record: EvaluationRecord, state: EvaluationState) -> EvaluationRecord:
        updated = record.model_copy(update={"state": state, "updated_at": datetime.now(UTC)})
        return self._store.update(updated)

    def _fail(
        self,
        record: EvaluationRecord,
        error: str,
        start: float,
    ) -> EvaluationRecord:
        duration_ms = int((time.monotonic() - start) * 1000)
        updated = record.model_copy(update={
            "state": EvaluationState.FAILED,
            "error": error[:500],
            "duration_ms": duration_ms,
            "updated_at": datetime.now(UTC),
        })
        return self._store.update(updated)


def _safe_severity(value: object) -> EvidenceSeverity:
    try:
        return EvidenceSeverity(str(value).lower())
    except ValueError:
        return EvidenceSeverity.INFO
