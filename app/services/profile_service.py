"""AI-powered student profile analysis and baseline skill assessment.

Phase 3: Analyze a student's background → StudentProfileAnalysis with
         OBSERVED / INFERRED / UNKNOWN evidence distinctions.

Phase 4: Extract per-dimension baseline skill scores (0–100) →
         SkillAssessment records.

Both phases run in a single AI call; results are stored in the InMemoryStore
or the SQL database depending on which UoW is active.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from app.ai.provider import get_ai_provider
from app.domain.enums import AIInteractionType, ProfileAnalysisStatus, SkillConfidence
from app.schemas.m7 import (
    AIInteractionLogCreate,
    SkillAssessmentCreate,
    StudentProfileAnalysisCreate,
)
from app.services.store import InMemoryStore

logger = logging.getLogger("project_defense.services.profile")

# Canonical skill dimensions assessed for every student
SKILL_DIMENSIONS = [
    "problem_solving",
    "code_quality",
    "system_design",
    "testing",
    "debugging",
    "communication",
    "algorithms",
    "architecture",
    "project_management",
    "domain_knowledge",
]

_SYSTEM_PROMPT = """\
You are an expert engineering educator who assesses student skill levels.
Your job is to analyze a student's background profile and produce a structured
skill assessment in JSON format.

IMPORTANT: distinguish carefully between:
- OBSERVED: directly evidenced by something in the profile (prior project, grade, certification)
- INFERRED: plausibly deduced from indirect evidence (e.g., "they built a REST API" implies API knowledge)
- UNKNOWN: insufficient evidence to make any claim

Return ONLY valid JSON with no markdown fences or extra text."""

_USER_PROMPT_TEMPLATE = """\
Analyze this student profile and return a JSON object with EXACTLY these top-level keys:

{{
  "observed_skills": [
    {{"name": "...", "level": "beginner|intermediate|advanced", "evidence": "specific quote or fact from profile"}}
  ],
  "inferred_skills": [
    {{"name": "...", "level": "beginner|intermediate|advanced", "reasoning": "why you inferred this"}}
  ],
  "unknown_areas": ["list of important skill areas where evidence is missing"],
  "learning_style": "visual|reading|hands-on|collaborative|mixed or null",
  "risk_factors": [
    {{"factor": "short name", "description": "specific concern"}}
  ],
  "strengths": ["list of notable strengths as strings"],
  "skill_dimensions": [
    {{
      "dimension": "one of {dimensions}",
      "score": <integer 0-100>,
      "confidence": "observed|inferred|unknown",
      "rationale": "one sentence"
    }}
  ]
}}

Dimensions to score (every dimension must appear exactly once):
{dimensions}

Student profile:
{profile}
"""


def _build_prompt(student_name: str, raw_profile: dict) -> str:
    dims_str = ", ".join(SKILL_DIMENSIONS)
    profile_str = json.dumps(raw_profile, indent=2)
    return _USER_PROMPT_TEMPLATE.format(
        dimensions=dims_str,
        profile=f"Name: {student_name}\n{profile_str}",
    )


def _parse_ai_response(content: str) -> dict:
    try:
        # Strip possible markdown fences
        text = content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"AI returned invalid JSON: {exc}") from exc


def _score_to_confidence(confidence_str: str) -> SkillConfidence:
    mapping = {
        "observed": SkillConfidence.OBSERVED,
        "inferred": SkillConfidence.INFERRED,
        "unknown": SkillConfidence.UNKNOWN,
    }
    return mapping.get((confidence_str or "").lower(), SkillConfidence.UNKNOWN)


# ---------------------------------------------------------------------------
# Mock fallback
# ---------------------------------------------------------------------------


def _mock_analysis(student_name: str, raw_profile: dict, seed: int) -> dict:
    dims = {}
    for i, dim in enumerate(SKILL_DIMENSIONS):
        raw = (seed >> (i * 5)) & 0x1F
        score = 30 + int(raw / 31 * 50)  # 30-80 range for baseline
        dims[dim] = {"score": score, "confidence": "inferred", "rationale": f"Mock baseline for {dim}."}

    return {
        "observed_skills": [
            {"name": "Python", "level": "intermediate", "evidence": "Mock: profile contains Python mention."},
        ],
        "inferred_skills": [
            {"name": "REST APIs", "level": "beginner", "reasoning": "Mock: inferred from project context."},
        ],
        "unknown_areas": ["cloud_deployment", "advanced_algorithms"],
        "learning_style": "hands-on",
        "risk_factors": [
            {"factor": "mock", "description": "Connect ANTHROPIC_API_KEY for real analysis."},
        ],
        "strengths": [f"Enrolled in the program ({student_name})"],
        "skill_dimensions": [
            {
                "dimension": dim,
                "score": v["score"],
                "confidence": v["confidence"],
                "rationale": v["rationale"],
            }
            for dim, v in dims.items()
        ],
    }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class StudentProfileService:
    """Generates AI-driven profile analysis and baseline skill assessments."""

    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

    async def analyze_student(
        self,
        student_id: UUID,
        organization_id: UUID,
        student_name: str,
        raw_profile: dict,
    ):
        """Run AI profile analysis + skill assessment for one student.

        Returns the StudentProfileAnalysis entity.
        Stores SkillAssessment records for each dimension.
        """
        # Mark as running
        analysis = self._store.create_student_profile_analysis(
            StudentProfileAnalysisCreate(
                student_id=student_id,
                organization_id=organization_id,
                status=ProfileAnalysisStatus.RUNNING,
                raw_profile=raw_profile,
            )
        )

        provider = get_ai_provider()
        system_prompt = _SYSTEM_PROMPT
        user_prompt = _build_prompt(student_name, raw_profile)

        # Dedup — don't re-analyse same profile twice
        request_hash = hashlib.sha256(user_prompt.encode()).hexdigest()[:64]

        start = datetime.now(UTC)
        success = True
        error_msg = None
        ai_result: dict = {}

        try:
            if provider.is_mock():
                seed = int(hashlib.md5(user_prompt.encode()).hexdigest(), 16)  # noqa: S324
                ai_result = _mock_analysis(student_name, raw_profile, seed)
            else:
                message = await provider.complete(system_prompt, user_prompt, max_tokens=2048)
                ai_result = _parse_ai_response(message.content)
        except Exception as exc:
            success = False
            error_msg = str(exc)
            logger.warning("Profile analysis failed for student %s: %s", student_id, exc)

        latency_ms = int((datetime.now(UTC) - start).total_seconds() * 1000)

        # Log AI interaction
        self._store.log_ai_interaction(
            AIInteractionLogCreate(
                organization_id=organization_id,
                student_id=student_id,
                interaction_type=AIInteractionType.PROFILE_ANALYSIS,
                ai_model=provider.model_name(),
                prompt_tokens=len(user_prompt.split()) * 2,
                completion_tokens=len(json.dumps(ai_result).split()),
                latency_ms=latency_ms,
                success=success,
                error_message=error_msg,
                request_hash=request_hash,
            )
        )

        if not success:
            self._store.update_profile_analysis(
                analysis.id,
                status=ProfileAnalysisStatus.FAILED,
            )
            raise RuntimeError(f"AI profile analysis failed: {error_msg}")

        # Persist results back to the analysis record
        updated = self._store.update_profile_analysis(
            analysis.id,
            status=ProfileAnalysisStatus.COMPLETE,
            observed_skills=ai_result.get("observed_skills", []),
            inferred_skills=ai_result.get("inferred_skills", []),
            unknown_areas=ai_result.get("unknown_areas", []),
            learning_style=ai_result.get("learning_style"),
            risk_factors=ai_result.get("risk_factors", []),
            strengths=ai_result.get("strengths", []),
            ai_model=provider.model_name(),
            confidence=0.85 if not provider.is_mock() else 0.5,
            generated_at=datetime.now(UTC),
        )

        # Phase 4: create SkillAssessment per dimension
        for dim_entry in ai_result.get("skill_dimensions", []):
            dim = dim_entry.get("dimension", "")
            score = dim_entry.get("score", 50)
            conf = _score_to_confidence(dim_entry.get("confidence", "unknown"))
            if not dim:
                continue
            self._store.upsert_skill_assessment(
                SkillAssessmentCreate(
                    student_id=student_id,
                    organization_id=organization_id,
                    profile_analysis_id=analysis.id,
                    dimension=dim,
                    score=max(0, min(100, int(score))),
                    evidence_sources=[{"rationale": dim_entry.get("rationale", "")}],
                    confidence=conf,
                    assessed_at=datetime.now(UTC),
                )
            )

        return updated
