"""Commit ingestion pipeline.

Processes a GitHub push event webhook into stored commits:
1. Look up the linked repository
2. For each commit in the push, fetch detailed diff via GitHub API
3. Apply size limits (truncate oversized patches)
4. Store commits + files
5. Mark webhook event as processed or failed
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from app.integrations.github.schemas import PushEvent
from app.integrations.github.store import GitHubMemoryStore
from app.schemas.github import CommitCreate

logger = logging.getLogger("project_defense.integrations.github.ingestion")

MAX_PATCH_BYTES = 10_000    # per-file patch size limit
MAX_DIFF_BYTES = 100_000    # total diff size limit across all files in a commit


class CommitIngestionService:
    """Converts a push-event payload into stored Commit + CommitFile records."""

    def __init__(
        self,
        store: GitHubMemoryStore,
        github_client=None,
    ) -> None:
        self._store = store
        self._client = github_client  # optional; may be None in tests/mock mode

    async def ingest_push_event(
        self,
        webhook_event_id: UUID,
        push: PushEvent,
        organization_id: UUID | None,
    ) -> list[UUID]:
        """Process a push event; return list of newly ingested commit IDs."""
        repo = self._store.get_repository_by_fullname(push.repo_full_name)
        if repo is None:
            logger.debug("No linked repository for %s — skipping ingestion", push.repo_full_name)
            self._store.mark_webhook_failed(
                webhook_event_id,
                f"Repository not linked: {push.repo_full_name}",
            )
            return []

        org_id = organization_id or repo.organization_id
        commit_ids: list[UUID] = []

        for push_commit in push.commits:
            sha = push_commit.id

            # Idempotency: skip already-ingested SHAs
            if self._store.get_commit_by_sha(repo.id, sha) is not None:
                logger.debug("Commit %s already ingested — skip", sha[:8])
                continue

            # Fetch detailed diff from GitHub when client is available
            additions = deletions = 0
            file_payloads: list[dict] = []
            diff_truncated = False

            if self._client is not None:
                try:
                    owner, repo_name = push.repo_full_name.split("/", 1)
                    info = await self._client.get_commit(owner, repo_name, sha)
                    additions = info.stats.additions
                    deletions = info.stats.deletions
                    file_payloads, diff_truncated = self._extract_files(info)
                except Exception as exc:  # pragma: no cover — network paths
                    logger.warning("Failed to fetch commit %s from GitHub: %s", sha[:8], exc)

            author_date = datetime.now(UTC)
            payload = CommitCreate(
                repository_id=repo.id,
                organization_id=org_id,
                sha=sha,
                message=push_commit.message,
                author_name=push_commit.author.get("name", ""),
                author_email=push_commit.author.get("email", ""),
                author_date=author_date,
                committer_name=push_commit.author.get("name", ""),
                committer_email=push_commit.author.get("email", ""),
                committer_date=author_date,
                branch=push.branch,
                url=push_commit.url,
                parent_shas=[push.before] if push.before else [],
                additions=additions,
                deletions=deletions,
            )
            commit = self._store.save_commit(payload, file_payloads, diff_truncated=diff_truncated)
            commit_ids.append(commit.id)
            logger.info(
                "Commit ingested",
                extra={
                    "commit_id": str(commit.id),
                    "sha": sha[:8],
                    "repo": push.repo_full_name,
                    "branch": push.branch,
                    "additions": additions,
                    "deletions": deletions,
                    "diff_truncated": diff_truncated,
                    "files": len(file_payloads),
                },
            )

        self._store.mark_webhook_processed(webhook_event_id)
        return commit_ids

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_files(self, commit_info) -> tuple[list[dict], bool]:
        """Apply size limits and return (file_dicts, diff_truncated)."""
        files: list[dict] = []
        total_bytes = 0
        diff_truncated = False

        for f in commit_info.files:
            patch = f.patch or ""
            patch_bytes = len(patch.encode("utf-8"))
            patch_truncated = False

            if patch_bytes > MAX_PATCH_BYTES:
                patch = patch.encode("utf-8")[:MAX_PATCH_BYTES].decode("utf-8", errors="ignore")
                patch_bytes = len(patch.encode("utf-8"))
                patch_truncated = True
                diff_truncated = True

            if total_bytes + patch_bytes > MAX_DIFF_BYTES:
                patch = None
                patch_truncated = True
                diff_truncated = True
            else:
                total_bytes += patch_bytes

            files.append({
                "path": f.filename,
                "status": f.status,
                "additions": f.additions,
                "deletions": f.deletions,
                "changes": f.changes,
                "patch": patch,
                "patch_truncated": patch_truncated,
            })

        return files, diff_truncated
