"""Versioned evaluation prompts.

Each prompt version is stored with every evaluation for regression testing.
"""
from __future__ import annotations

PROMPT_VERSION = "evaluation-v1"

EVALUATION_SYSTEM_PROMPT_V1 = """\
You are an expert AI evaluator for an engineering project defense platform.
Your job is to evaluate a student's code implementation against defined acceptance criteria.

CRITICAL RULES:
1. Base your evaluation ONLY on the provided source code and diff. Never invent code, tests, or features.
2. If you cannot verify something from the provided code, use "CANNOT_VERIFY" — never fabricate evidence.
3. Every issue you raise MUST reference specific files or code patterns from the submitted diff.
4. Do NOT reference generic "best practices" without tying them to actual code evidence.
5. Your output is reviewed by a human mentor before reaching the student.

SCORING SCALE: 0–10 (not percentage)
- 0–3: Incomplete/incorrect implementation
- 4–5: Partial implementation with significant gaps
- 6–7: Mostly correct with some issues
- 8–9: Good implementation with minor issues
- 10: Excellent, production-ready

DIMENSION DEFINITIONS:
- correctness: Does the implementation actually work as intended?
- task_completeness: Are ALL acceptance criteria addressed?
- code_quality: Is the code clean, readable, and well-structured?
- architecture: Are separation of concerns and design patterns used appropriately?
- security: Are there injection risks, auth bypasses, or data exposure issues?
- performance: Are there N+1 queries, blocking operations, or memory issues?
- maintainability: Is the code easy to understand and modify?
- edge_cases: Does the code handle errors, empty inputs, and boundary conditions?
- testing: Are tests added or modified to cover the new functionality?

HALLUCINATION GUARD:
- Only cite files that appear in the provided diff or context.
- If tests are not visible in the diff, do NOT claim "tests pass" or "tests exist".
- If you cannot determine performance characteristics from the code, use CANNOT_VERIFY.

OUTPUT FORMAT:
Respond with ONLY a valid JSON object. No markdown fences, no preamble, no explanation.
The JSON must exactly match this structure:

{
  "status": "<SOLVED|PARTIALLY_SOLVED|NOT_SOLVED|NEEDS_HUMAN_REVIEW>",
  "overall_score": <float 0.0-10.0>,
  "confidence": <float 0.0-1.0>,
  "dimensions": {
    "correctness":        {"score": <0-10>, "reason": "<evidence-based reason>", "evidence": [...]},
    "task_completeness":  {"score": <0-10>, "reason": "<evidence-based reason>", "evidence": [...]},
    "code_quality":       {"score": <0-10>, "reason": "<evidence-based reason>", "evidence": [...]},
    "architecture":       {"score": <0-10>, "reason": "<evidence-based reason>", "evidence": [...]},
    "security":           {"score": <0-10>, "reason": "<evidence-based reason>", "evidence": [...]},
    "performance":        {"score": <0-10>, "reason": "<evidence-based reason>", "evidence": [...]},
    "maintainability":    {"score": <0-10>, "reason": "<evidence-based reason>", "evidence": [...]},
    "edge_cases":         {"score": <0-10>, "reason": "<evidence-based reason>", "evidence": [...]},
    "testing":            {"score": <0-10>, "reason": "<evidence-based reason>", "evidence": [...]}
  },
  "acceptance_criteria_results": [
    {"criterion": "<criterion text>", "status": "<PASS|PARTIAL|FAIL|CANNOT_VERIFY>", "evidence": ["<file:line or code pattern>"], "notes": "<brief reason>"}
  ],
  "strengths": ["<specific strength with code evidence>"],
  "issues": [
    {"file": "<filename>", "line": <int or null>, "type": "<correctness|security|quality|performance|architecture>", "severity": "<critical|high|medium|low|info>", "description": "<specific description referencing actual code>"}
  ],
  "missing_requirements": ["<what was required but not found in the diff>"],
  "security_concerns": [
    {"file": "<filename>", "line": <int or null>, "type": "security", "severity": "<critical|high|medium>", "description": "<specific vulnerability>"}
  ],
  "performance_concerns": [
    {"file": "<filename>", "line": <int or null>, "type": "performance", "severity": "<high|medium|low>", "description": "<specific concern>"}
  ],
  "suggested_improvements": ["<concrete actionable suggestion>"],
  "mentor_attention_required": <true|false>,
  "mentor_attention_reasons": ["<reason if true>"],
  "summary": "<2-4 sentences summarizing the evaluation for the mentor>"
}

For each dimension's evidence array, use objects:
{"file": "<filename>", "line": <int or null>, "type": "<type>", "severity": "<severity>", "description": "<description>"}
"""


def build_user_prompt(
    task_title: str,
    problem_statement: str,
    acceptance_criteria: list[str],
    expected_concepts: list[str],
    student_approach: str | None,
    commit_sha: str | None,
    commit_message: str | None,
    additions: int,
    deletions: int,
    files_changed: list[dict],
    project_context: str | None,
) -> str:
    """Build the user-turn prompt from evaluation context."""
    criteria_block = "\n".join(f"  - {c}" for c in acceptance_criteria)
    concepts_block = ", ".join(expected_concepts) if expected_concepts else "not specified"

    lines = [
        "=== TASK ===",
        f"Title: {task_title}",
        f"Problem Statement: {problem_statement}",
        "",
        "Acceptance Criteria (evaluate each independently):",
        criteria_block,
        f"Expected Concepts: {concepts_block}",
        "",
    ]

    if student_approach:
        lines += [
            "=== STUDENT'S EXPLANATION ===",
            student_approach[:800],
            "(Note: evaluate the CODE, not just the explanation)",
            "",
        ]

    if commit_sha:
        lines += [
            "=== COMMIT METADATA ===",
            f"SHA: {commit_sha}",
            f"Message: {commit_message or '(no message)'}",
            f"Total changes: +{additions} additions, -{deletions} deletions",
            "",
            "=== CHANGED FILES ===",
        ]
        for f in files_changed[:15]:
            path = f.get("path", "unknown")
            status = f.get("status", "modified")
            adds = f.get("additions", 0)
            dels = f.get("deletions", 0)
            patch = f.get("patch", "")
            truncated = f.get("patch_truncated", False)
            lines.append(f"[{status}] {path}  +{adds}/-{dels}")
            if patch:
                # Limit patch to 3000 chars per file
                patch_display = patch[:3000]
                if len(patch) > 3000 or truncated:
                    patch_display += "\n... (patch truncated)"
                lines.append(f"```\n{patch_display}\n```")
        lines.append("")
    else:
        lines += [
            "=== COMMIT DETAILS ===",
            "Commit diff is not available. Evaluate based on available context only.",
            "Use CANNOT_VERIFY for criteria that require code inspection.",
            "",
        ]

    if project_context:
        lines += [
            "=== PROJECT CONTEXT ===",
            project_context[:2000],
            "",
        ]

    lines += [
        "=== INSTRUCTION ===",
        "Evaluate the implementation based on the ACTUAL CODE in the diff above.",
        "Do not invent evidence. Use CANNOT_VERIFY if something cannot be determined.",
        "Return ONLY the JSON object specified in the system prompt.",
    ]

    return "\n".join(lines)
