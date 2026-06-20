"""Build the task payload Mars hands to an execution provider.

Centralizes how setup commands + acceptance criteria are formatted so both the
real AutoDev provider and the mock present them identically. When the underlying
MCP contract can't accept structured criteria, the formatted prompt embeds them
in a clearly delimited ``Acceptance Criteria:`` section.
"""

from __future__ import annotations

from mars.models import EvalCase


def format_task_prompt(case: EvalCase) -> str:
    """Task prompt with acceptance criteria appended in a delimited section."""
    parts = [case.task_prompt.strip()]
    if case.acceptance_criteria:
        parts.append("")
        parts.append("Acceptance Criteria:")
        parts.extend(f"- {c}" for c in case.acceptance_criteria)
    return "\n".join(parts)


def build_task_payload(case: EvalCase) -> dict:
    """Structured payload (prompt + criteria + setup) for an execution request."""
    return {
        "issue_url": case.issue_url,
        "task_prompt": format_task_prompt(case),
        "acceptance_criteria": list(case.acceptance_criteria),
        "setup_commands": list(case.setup_commands),
    }
