"""AI Provider abstraction for evaluation engine.

The application never depends directly on the Anthropic SDK.
Instead it uses the AIProvider interface, with two implementations:
  - AnthropicProvider: uses the real Claude API
  - MockAIProvider: deterministic responses for development/testing

Selection logic (see get_ai_provider()):
  - ANTHROPIC_API_KEY set → AnthropicProvider
  - not set             → MockAIProvider
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

logger = logging.getLogger("project_defense.ai.provider")


class AIMessage(BaseModel):
    content: str
    input_tokens: int = 0
    output_tokens: int = 0


@runtime_checkable
class AIProvider(Protocol):
    """Minimal interface every AI provider must implement."""

    async def complete(
        self, system_prompt: str, user_prompt: str, max_tokens: int = 4096
    ) -> AIMessage: ...

    def provider_name(self) -> str: ...
    def model_name(self) -> str: ...
    def is_mock(self) -> bool: ...


# ---------------------------------------------------------------------------
# Anthropic implementation
# ---------------------------------------------------------------------------


class AnthropicProvider:
    """Wraps anthropic.AsyncAnthropic; raises InfrastructureException on import failure."""

    def __init__(self, api_key: str, model: str) -> None:
        try:
            import anthropic as _anthropic
            self._client = _anthropic.AsyncAnthropic(api_key=api_key)
        except ImportError as exc:
            from app.shared.exceptions import InfrastructureException
            raise InfrastructureException(
                "anthropic package is required — run: pip install anthropic"
            ) from exc
        self._model = model

    async def complete(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> AIMessage:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        content = response.content[0].text if response.content else ""
        return AIMessage(
            content=content,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    def provider_name(self) -> str:
        return "anthropic"

    def model_name(self) -> str:
        return self._model

    def is_mock(self) -> bool:
        return False


# ---------------------------------------------------------------------------
# Mock implementation
# ---------------------------------------------------------------------------

_MOCK_VERDICTS = ["PARTIALLY_SOLVED", "SOLVED", "NOT_SOLVED", "PARTIALLY_SOLVED", "SOLVED"]


class MockAIProvider:
    """Deterministic mock provider for development and testing.

    Scores are seeded by a hash of the user prompt so the same context
    always produces the same result (regression-safe).
    """

    MODEL = "mock-v1"
    PROVIDER = "development_mock"
    PROMPT_VERSION = "evaluation-v1"

    def provider_name(self) -> str:
        return self.PROVIDER

    def model_name(self) -> str:
        return self.MODEL

    def is_mock(self) -> bool:
        return True

    async def complete(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> AIMessage:
        seed_int = int(hashlib.md5(user_prompt.encode()).hexdigest(), 16)  # noqa: S324
        scores = self._gen_scores(seed_int)
        result = self._build_mock_result(user_prompt, scores)
        content = json.dumps(result, indent=2)
        return AIMessage(
            content=content,
            input_tokens=len(user_prompt.split()) * 2,
            output_tokens=len(content.split()),
        )

    def _gen_scores(self, seed: int) -> dict[str, float]:
        bases = [7.0, 6.5, 7.5, 7.0, 8.0, 6.0, 7.0, 6.5, 5.5]
        names = [
            "correctness", "task_completeness", "code_quality", "architecture",
            "security", "performance", "maintainability", "edge_cases", "testing",
        ]
        result = {}
        for i, name in enumerate(names):
            raw = (seed >> (i * 4)) & 0xF
            delta = (raw / 15.0) * 2.0 - 1.0
            result[name] = round(min(10.0, max(0.0, bases[i] + delta)), 1)
        return result

    def _build_mock_result(self, prompt: str, scores: dict[str, float]) -> dict:
        seed_int = int(hashlib.md5(prompt.encode()).hexdigest(), 16)
        verdict_idx = seed_int % len(_MOCK_VERDICTS)
        verdict = _MOCK_VERDICTS[verdict_idx]

        overall = round(
            scores["correctness"] * 0.25 +
            scores["task_completeness"] * 0.20 +
            scores["code_quality"] * 0.15 +
            scores["architecture"] * 0.10 +
            scores["security"] * 0.10 +
            scores["performance"] * 0.05 +
            scores["maintainability"] * 0.05 +
            scores["edge_cases"] * 0.05 +
            scores["testing"] * 0.05,
            2,
        )
        confidence = round(0.70 + (seed_int % 20) / 100, 2)

        # Extract any criteria from prompt for per-criterion results
        criteria_results = self._extract_criteria_results(prompt)

        return {
            "status": verdict,
            "overall_score": overall,
            "confidence": confidence,
            "dimensions": {
                name: {
                    "score": sc,
                    "reason": f"Mock evaluation: {name} assessed at {sc}/10 based on submitted code.",
                    "evidence": [
                        {
                            "file": "app/main.py",
                            "line": None,
                            "type": "quality",
                            "severity": "info",
                            "description": f"Mock evidence for {name} dimension.",
                        }
                    ],
                }
                for name, sc in scores.items()
            },
            "acceptance_criteria_results": criteria_results,
            "strengths": [
                "Implementation follows the project structure.",
                "Code is reasonably organized.",
            ],
            "issues": [
                {
                    "file": "app/main.py",
                    "line": None,
                    "type": "quality",
                    "severity": "low",
                    "description": "Mock evaluation — connect ANTHROPIC_API_KEY for real analysis.",
                }
            ],
            "missing_requirements": [],
            "security_concerns": [],
            "performance_concerns": [],
            "suggested_improvements": [
                "Add more comprehensive tests.",
                "Consider adding inline documentation.",
            ],
            "mentor_attention_required": confidence < 0.75,
            "mentor_attention_reasons": [] if confidence >= 0.75 else ["Low confidence — mock mode active."],
            "summary": (
                f"[MOCK EVALUATION — development_mock provider] "
                f"Submission scored {overall}/10 (verdict: {verdict}). "
                f"Set PROJECT_DEFENSE_ANTHROPIC_API_KEY for real AI evaluation."
            ),
        }

    def _extract_criteria_results(self, prompt: str) -> list[dict]:
        results = []
        lines = prompt.split("\n")
        in_criteria = False
        for line in lines:
            line = line.strip()
            if "acceptance criteria" in line.lower():
                in_criteria = True
                continue
            if in_criteria:
                if line.startswith("- "):
                    criterion = line[2:].strip()
                    if criterion:
                        results.append({
                            "criterion": criterion[:200],
                            "status": "CANNOT_VERIFY",
                            "evidence": ["Mock mode — real code analysis requires ANTHROPIC_API_KEY"],
                            "notes": "Cannot verify without real AI analysis.",
                        })
                elif line and not line.startswith(" ") and len(results) > 0:
                    in_criteria = False
        return results[:10]


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------

_provider_singleton: AIProvider | None = None


def get_ai_provider() -> AIProvider:
    """Return the process-level singleton AIProvider.

    Lazily initialised:
    - ANTHROPIC_API_KEY set → AnthropicProvider
    - not set              → MockAIProvider (never claims to be real)
    """
    global _provider_singleton
    if _provider_singleton is None:
        from app.core.config import settings
        api_key = getattr(settings, "anthropic_api_key", "")
        model = getattr(settings, "anthropic_model", "claude-haiku-4-5-20251001")
        if api_key:
            logger.info("AI provider: AnthropicProvider (model=%s)", model)
            _provider_singleton = AnthropicProvider(api_key=api_key, model=model)
        else:
            logger.info("AI provider: MockAIProvider (ANTHROPIC_API_KEY not set)")
            _provider_singleton = MockAIProvider()
    return _provider_singleton


def reset_provider() -> None:
    """Reset the singleton — used in tests to inject a custom provider."""
    global _provider_singleton
    _provider_singleton = None
