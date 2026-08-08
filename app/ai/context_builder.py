"""Evaluation context builder.

Assembles all context needed to evaluate a submission:
  - Task + acceptance criteria
  - Submission metadata + student explanation
  - Commit metadata + changed files + diff
  - Project context (simplified — RAG can be added later)
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from uuid import UUID

logger = logging.getLogger("project_defense.ai.context_builder")


@dataclass
class FileContext:
    path: str
    status: str
    additions: int
    deletions: int
    changes: int
    patch: str | None
    patch_truncated: bool = False


@dataclass
class EvaluationContext:
    """All context needed to evaluate one submission."""
    task_id: UUID
    task_title: str
    problem_statement: str
    acceptance_criteria: list[str]
    expected_concepts: list[str]

    submission_id: UUID
    organization_id: UUID
    student_approach: str | None

    commit_sha: str | None
    commit_message: str | None
    additions: int
    deletions: int
    files: list[FileContext] = field(default_factory=list)

    project_context: str | None = None

    def context_hash(self) -> str:
        """Deterministic hash of (task_id, commit_sha, diff).

        Used to skip re-evaluation of identical context.
        """
        key_parts = [
            str(self.task_id),
            self.commit_sha or "",
            "".join(f.patch or "" for f in self.files),
        ]
        raw = "|".join(key_parts)
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def to_prompt_kwargs(self) -> dict:
        return {
            "task_title": self.task_title,
            "problem_statement": self.problem_statement,
            "acceptance_criteria": self.acceptance_criteria,
            "expected_concepts": self.expected_concepts,
            "student_approach": self.student_approach,
            "commit_sha": self.commit_sha,
            "commit_message": self.commit_message,
            "additions": self.additions,
            "deletions": self.deletions,
            "files_changed": [
                {
                    "path": f.path,
                    "status": f.status,
                    "additions": f.additions,
                    "deletions": f.deletions,
                    "patch": f.patch,
                    "patch_truncated": f.patch_truncated,
                }
                for f in self.files
            ],
            "project_context": self.project_context,
        }


class ContextBuilder:
    """Builds an EvaluationContext from domain objects.

    The builder is intentionally simple: it takes what's available
    and does not fail on missing optional data.  RAG/project intelligence
    can be added later by extending the `_build_project_context` method.
    """

    def build(
        self,
        task,
        submission,
        commit=None,
        commit_files=None,
    ) -> EvaluationContext:
        """Build context from domain objects.

        Parameters
        ----------
        task:
            Task schema from core.py
        submission:
            Submission schema from core.py
        commit:
            Optional Commit schema from schemas/github.py
        commit_files:
            Optional list[CommitFile] from schemas/github.py
        """
        files: list[FileContext] = []
        if commit is not None and commit_files:
            for cf in commit_files:
                files.append(FileContext(
                    path=cf.path,
                    status=cf.status,
                    additions=cf.additions,
                    deletions=cf.deletions,
                    changes=cf.changes,
                    patch=cf.patch,
                    patch_truncated=cf.patch_truncated,
                ))

        project_ctx = self._build_project_context(task, submission)

        return EvaluationContext(
            task_id=task.id,
            task_title=task.title,
            problem_statement=task.problem_statement,
            acceptance_criteria=list(task.acceptance_criteria),
            expected_concepts=list(task.expected_concepts),
            submission_id=submission.id,
            organization_id=submission.organization_id,
            student_approach=getattr(submission, "approach_note", None),
            commit_sha=commit.sha if commit else None,
            commit_message=commit.message if commit else None,
            additions=commit.additions if commit else 0,
            deletions=commit.deletions if commit else 0,
            files=files,
            project_context=project_ctx,
        )

    def _build_project_context(self, task, submission) -> str | None:
        """Lightweight project context — no RAG yet."""
        parts = []
        task_type = getattr(task, "task_type", "coding")
        if task_type:
            parts.append(f"Task type: {task_type}")
        if hasattr(task, "expected_concepts") and task.expected_concepts:
            parts.append(f"Expected technology/concepts: {', '.join(task.expected_concepts)}")
        return "\n".join(parts) if parts else None
