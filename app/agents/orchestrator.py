"""AgentOrchestrator — selects and runs the right agent for a given submission."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any
from uuid import UUID

from app.agents.base import (
    AgentContext,
    TaskGenContext,
    bootstrap_github_evaluation,
    bootstrap_transcript_evaluation,
)
from app.schemas.core import EvaluationCreate, Project, Student, Submission, Task, TaskCreate
from app.shared.exceptions import InfrastructureException

logger = logging.getLogger("project_defense.agents.orchestrator")

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"

_orchestrator: "AgentOrchestrator | None" = None


class AgentOrchestrator:
    """Selects the appropriate evaluation or generation agent and handles graceful fallback.

    When ``api_key`` is empty or the ``anthropic`` package is not installed,
    evaluation falls back to deterministic bootstrap results.  Task generation
    raises ``InfrastructureException`` because there is no sensible deterministic
    fallback for open-ended task synthesis.
    """

    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL) -> None:
        self._model = model
        self._client: Any = None
        if api_key:
            try:
                import anthropic
                self._client = anthropic.AsyncAnthropic(api_key=api_key)
            except ImportError:
                logger.warning(
                    "anthropic package not installed — AI evaluation will use bootstrap fallback"
                )

    @property
    def is_configured(self) -> bool:
        """True when the Anthropic client was successfully initialised."""
        return self._client is not None

    async def evaluate_submission(
        self,
        task: Task,
        submission: Submission,
    ) -> EvaluationCreate:
        """Evaluate a submission, fetching commit metadata from GitHub when available."""
        from app.integrations.github.service import get_github_service

        commit_info = None
        if submission.commit_url:
            service = get_github_service()
            if service is not None:
                try:
                    commit_info = await service.get_commit(str(submission.commit_url))
                except Exception as exc:
                    logger.debug(
                        "Could not fetch GitHub commit for evaluation",
                        extra={"url": str(submission.commit_url), "error": str(exc)},
                    )

        context = AgentContext(task=task, submission=submission, commit_info=commit_info)

        if not self.is_configured:
            return (
                bootstrap_github_evaluation(context)
                if submission.commit_url
                else bootstrap_transcript_evaluation(context)
            )

        if submission.commit_url:
            from app.agents.github_eval_agent import GitHubEvalAgent
            return await GitHubEvalAgent(self._client, self._model).evaluate(context)

        from app.agents.transcript_eval_agent import TranscriptEvalAgent
        return await TranscriptEvalAgent(self._client, self._model).evaluate(context)

    async def generate_task(
        self,
        context: TaskGenContext,
        organization_id: UUID,
        batch_id: UUID,
        due_on: date,
    ) -> TaskCreate:
        """Generate a task suggestion for a student.

        Raises ``InfrastructureException`` when the Anthropic client is not configured,
        because there is no deterministic fallback for task generation.
        """
        if not self.is_configured:
            raise InfrastructureException(
                "Task generation requires ANTHROPIC_API_KEY to be configured"
            )
        from app.agents.task_gen_agent import TaskGenAgent
        return await TaskGenAgent(self._client, self._model).generate(
            context, organization_id, batch_id, due_on
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            await self._client.close()


def get_orchestrator() -> AgentOrchestrator:
    """Return the process-level singleton AgentOrchestrator.

    Lazily initialised from ``settings.anthropic_api_key`` and
    ``settings.anthropic_model`` on first call.
    """
    global _orchestrator
    if _orchestrator is None:
        from app.core.config import settings
        _orchestrator = AgentOrchestrator(
            api_key=getattr(settings, "anthropic_api_key", ""),
            model=getattr(settings, "anthropic_model", _DEFAULT_MODEL),
        )
    return _orchestrator
