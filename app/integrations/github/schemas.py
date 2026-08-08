"""Pydantic schemas that mirror the GitHub REST API response shapes.

Uses ``extra="ignore"`` so the large GitHub payloads can be parsed without
enumerating every field — only the fields we actually use are declared.
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _GitHubModel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class CommitAuthor(_GitHubModel):
    name: str
    email: str
    date: datetime


class CommitFile(_GitHubModel):
    filename: str
    status: str
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    patch: str | None = None


class CommitStats(_GitHubModel):
    additions: int = 0
    deletions: int = 0
    total: int = 0


class CommitInfo(_GitHubModel):
    """Flattened view of a single GitHub commit."""

    sha: str
    url: str
    message: str
    author: CommitAuthor
    committer: CommitAuthor
    stats: CommitStats = Field(default_factory=CommitStats)
    files: list[CommitFile] = Field(default_factory=list)

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "CommitInfo":
        commit = data["commit"]
        return cls(
            sha=data["sha"],
            url=data.get("html_url", ""),
            message=commit["message"],
            author=CommitAuthor.model_validate(commit["author"]),
            committer=CommitAuthor.model_validate(commit["committer"]),
            stats=CommitStats.model_validate(data.get("stats", {})),
            files=[CommitFile.model_validate(f) for f in data.get("files", [])],
        )


class RepositoryInfo(_GitHubModel):
    github_id: int = Field(alias="id")
    name: str
    full_name: str
    description: str | None = None
    private: bool = False
    default_branch: str = "main"
    language: str | None = None
    stars: int = Field(0, alias="stargazers_count")
    forks: int = Field(0, alias="forks_count")
    url: str = Field(alias="html_url")

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "RepositoryInfo":
        return cls.model_validate(data)


class PushEventCommit(_GitHubModel):
    id: str
    message: str
    url: str
    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    modified: list[str] = Field(default_factory=list)
    author: dict[str, str] = Field(default_factory=dict)


class PushEvent(_GitHubModel):
    """Webhook push event payload from GitHub."""

    ref: str
    before: str = ""
    after: str = ""
    repository: dict[str, Any] = Field(default_factory=dict)
    commits: list[PushEventCommit] = Field(default_factory=list)
    head_commit: PushEventCommit | None = None
    pusher: dict[str, str] = Field(default_factory=dict)

    @property
    def branch(self) -> str:
        return self.ref.removeprefix("refs/heads/")

    @property
    def repo_full_name(self) -> str:
        return self.repository.get("full_name", "")

    @property
    def repo_html_url(self) -> str:
        return self.repository.get("html_url", "")
