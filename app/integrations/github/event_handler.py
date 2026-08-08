"""Async event handler — validates GitHub commit URLs when a submission arrives."""
from __future__ import annotations

import logging

from app.domain.events import DomainEvent

logger = logging.getLogger("project_defense.integrations.github.event_handler")


class GitHubValidationHandler:
    """Subscribes to ``SubmissionReceived`` and validates the commit URL.

    When GitHub is configured (``settings.github_token`` is set), fetches the
    commit from the GitHub API and logs the result.  If GitHub is not
    configured the handler is a no-op so the submission pipeline continues
    unaffected.

    This handler is *async-native* — it does not extend ``EventWorker`` (which
    is synchronous) and is registered via ``HandlerRegistry.register_handler()``.
    """

    event_type: str = "SubmissionReceived"

    async def handle(self, event: DomainEvent) -> None:
        commit_url: str | None = event.payload.get("commit_url")
        if not commit_url:
            logger.debug("SubmissionReceived has no commit_url — skipping GitHub validation")
            return

        from app.integrations.github.service import get_github_service

        service = get_github_service()
        if service is None:
            logger.debug("GitHub integration not configured — skipping commit validation")
            return

        try:
            commit = await service.get_commit(commit_url)
            logger.info(
                "GitHub commit validated",
                extra={
                    "submission_id": str(event.aggregate_id),
                    "sha": commit.sha[:8],
                    "message": commit.message.splitlines()[0][:80],
                    "files_changed": len(commit.files),
                    "additions": commit.stats.additions,
                    "deletions": commit.stats.deletions,
                },
            )
        except Exception as exc:
            logger.warning(
                "GitHub commit validation failed",
                extra={"submission_id": str(event.aggregate_id), "error": str(exc)},
            )
