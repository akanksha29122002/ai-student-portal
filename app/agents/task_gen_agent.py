"""Task generation agent.

Calls the Anthropic Claude API to produce a TaskCreate for the student's
next daily assignment based on their project history and learning progression.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import Any
from uuid import UUID

from app.agents.base import TaskGenContext
from app.domain.enums import TaskType
from app.schemas.core import TaskCreate

logger = logging.getLogger("project_defense.agents.task_gen")

PROMPT_VERSION = "task-gen-agent.v1"

_SYSTEM_PROMPT = (
    "You are an AI task designer for an engineering project defense platform. "
    "Generate the next meaningful coding or spoken-question task for a student "
    "based on their project and learning history.\n\n"
    "Design tasks that:\n"
    "1. Build naturally on the student's existing work\n"
    "2. Introduce or deepen a software engineering concept\n"
    "3. Are achievable in one working day\n"
    "4. Have specific, testable acceptance criteria\n\n"
    "Respond with ONLY a JSON object — no markdown fences, no preamble.\n\n"
    "Required fields:\n"
    '{\n'
    '  "task_type": one of ["coding","spoken_question"],\n'
    '  "title": "3-10 word action-oriented title",\n'
    '  "problem_statement": "40-300 char clear problem description",\n'
    '  "acceptance_criteria": ["3-5 specific, testable criteria"],\n'
    '  "expected_concepts": ["2-5 concept tags"]\n'
    "}"
)

_TYPE_MAP: dict[str, TaskType] = {
    "coding": TaskType.CODING,
    "spoken_question": TaskType.SPOKEN_QUESTION,
}


class TaskGenAgent:
    """Generates task suggestions for a student using Claude."""

    def __init__(self, client: Any, model: str) -> None:
        self._client = client
        self._model = model

    async def generate(
        self,
        context: TaskGenContext,
        organization_id: UUID,
        batch_id: UUID,
        due_on: date,
    ) -> TaskCreate:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_prompt(context)}],
        )
        parsed = _extract_json(response.content[0].text)
        return _build_task_create(context, parsed, organization_id, batch_id, due_on)


def _build_prompt(context: TaskGenContext) -> str:
    student = context.student
    project = context.project

    lines = [
        f"STUDENT: {student.full_name}",
        f"PROJECT: {project.name}  ({project.repository_url})",
    ]
    if project.summary:
        lines.append(f"Project Summary: {project.summary[:300]}")

    if context.previous_tasks:
        lines.append("")
        lines.append("PREVIOUS TASKS (oldest first):")
        for task in context.previous_tasks[-10:]:
            lines.append(f"  - {task.title}")
        concepts_seen: set[str] = set()
        for t in context.previous_tasks:
            concepts_seen.update(t.expected_concepts)
        if concepts_seen:
            lines.append(f"Concepts covered so far: {', '.join(sorted(concepts_seen))}")
    else:
        lines.append("\nNo previous tasks — this is the student's first task.")

    lines.append("")
    lines.append("Generate the next task to continue this student's learning progression.")
    return "\n".join(lines)


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return json.loads(text.strip())


def _build_task_create(
    context: TaskGenContext,
    parsed: dict,
    organization_id: UUID,
    batch_id: UUID,
    due_on: date,
) -> TaskCreate:
    task_type = _TYPE_MAP.get(
        str(parsed.get("task_type", "coding")).lower(), TaskType.CODING
    )

    title = str(parsed.get("title", "Complete next task"))[:180].strip()
    if len(title) < 3:
        title = "Complete next task"

    problem_statement = str(
        parsed.get("problem_statement", "Complete the assigned coding task.")
    )[:4000].strip()
    if len(problem_statement) < 10:
        problem_statement = "Complete the assigned coding task as described in the project context."

    raw_criteria = parsed.get("acceptance_criteria", [])
    acceptance_criteria = [
        str(c)[:400].strip() for c in raw_criteria if str(c).strip()
    ][:10]
    if not acceptance_criteria:
        acceptance_criteria = ["Task completed as specified."]

    raw_concepts = parsed.get("expected_concepts", [])
    expected_concepts = [
        str(c)[:80].strip() for c in raw_concepts if str(c).strip()
    ][:12]

    return TaskCreate(
        organization_id=organization_id,
        batch_id=batch_id,
        student_id=context.student.id,
        project_id=context.project.id,
        task_type=task_type,
        title=title,
        problem_statement=problem_statement,
        acceptance_criteria=acceptance_criteria,
        expected_concepts=expected_concepts,
        due_on=due_on,
    )
