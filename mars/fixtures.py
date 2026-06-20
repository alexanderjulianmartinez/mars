"""Deterministic scoring fixtures for agentic evaluation (Track A).

A comparison fixture pairs one ``EvalCase`` (with expectations: setup commands,
acceptance criteria, expected/allowed/forbidden files, literal requirements) with
several *pre-recorded* mock AutoDev outputs. Scoring them shows whether Mars's
scorers differentiate model behaviour — with **no live/paid model calls**.

The bundled ``bootstrap-typo-and-rename`` fixture reproduces the pattern from the
first live comparison: both agents fix the reference typo and miss the file
rename; the "claude-like" run additionally makes a noisy unrelated-doc edit while
the "gpt-like" run is clean.
"""

from __future__ import annotations

from dataclasses import dataclass

from mars.models import (
    AgentRun,
    AgentRunStatus,
    EvalCase,
    LiteralCheck,
    LiteralCheckType,
    LiteralRequirement,
    TestResult,
)
from mars.scoring.composite import CompositeScorer, default_composite

# --- diffs (git unified) --------------------------------------------------- #

_CLAUDE_REF_FIX = """diff --git a/CLAUDE.md b/CLAUDE.md
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -4,7 +4,7 @@
-The MVP is implemented per the spec in `docs/claude_code_mars_boostrap.md` (still
+The MVP is implemented per the spec in `docs/claude_code_mars_bootstrap.md` (still
"""

# trailing-newline / whitespace-only churn on an unrelated doc → pure noise
_NOISY_APOLLO = """diff --git a/docs/APOLLO.md b/docs/APOLLO.md
--- a/docs/APOLLO.md
+++ b/docs/APOLLO.md
@@ -90,4 +90,4 @@
-  correction yet). See `BACKLOG.md`.
+  correction yet). See `BACKLOG.md`.
"""


def _run(model: str, diff: str, files: list[str]) -> AgentRun:
    return AgentRun(
        id=f"agent-{model}",
        agent=model,
        model=model,
        status=AgentRunStatus.SUCCESS,
        logs=f"[{model}] simulated run",
        diff=diff,
        runtime_ms=30000,
        cost_usd=0.05,
        files_changed=files,
        test_results=[TestResult(name="pytest -q", passed=True, duration_ms=500)],
    )


@dataclass
class ComparisonFixture:
    case: EvalCase
    runs: dict[str, AgentRun]


def bootstrap_typo_and_rename() -> ComparisonFixture:
    case = EvalCase(
        id="bootstrap-typo-and-rename",
        suite_id="agentic-fixtures",
        name="Fix bootstrap typo and rename file",
        task_prompt=(
            "Fix the misspelled `boostrap` reference and rename "
            "docs/claude_code_mars_boostrap.md to docs/CLAUDE_CODE_MARS_BOOTSTRAP.md."
        ),
        setup_commands=["uv sync", 'uv pip install -e ".[dev]"'],
        test_commands=["pytest -q"],
        acceptance_criteria=[
            "Fix the misspelled bootstrap reference.",
            "Rename the file if explicitly requested.",
            "Do not edit unrelated files.",
            "Preserve trailing newlines.",
        ],
        expected_files=["CLAUDE.md", "docs/CLAUDE_CODE_MARS_BOOTSTRAP.md"],
        allowed_files=["docs/**", "README.md", "CLAUDE.md"],
        forbidden_files=[".env", "secrets/**", "production/**"],
        literal_requirements=[
            LiteralRequirement(
                id="fix_bootstrap_typo",
                description="Replace boostrap with bootstrap.",
                required=True,
                check=LiteralCheck(type=LiteralCheckType.TEXT_ABSENT, pattern="boostrap"),
            ),
            LiteralRequirement(
                id="rename_file",
                description="Rename to docs/CLAUDE_CODE_MARS_BOOTSTRAP.md.",
                required=True,
                check=LiteralCheck(
                    type=LiteralCheckType.FILE_EXISTS,
                    path="docs/CLAUDE_CODE_MARS_BOOTSTRAP.md",
                ),
            ),
        ],
    )
    return ComparisonFixture(
        case=case,
        runs={
            # typo fixed, rename missed, unrelated noisy edit to docs/APOLLO.md
            "claude-like": _run(
                "claude-like", _CLAUDE_REF_FIX + _NOISY_APOLLO, ["CLAUDE.md", "docs/APOLLO.md"]
            ),
            # typo fixed, rename missed, clean diff
            "gpt-like": _run("gpt-like", _CLAUDE_REF_FIX, ["CLAUDE.md"]),
        },
    )


_FIXTURES = {"bootstrap-typo-and-rename": bootstrap_typo_and_rename}


def list_fixtures() -> list[str]:
    return list(_FIXTURES)


def get_fixture(name: str) -> ComparisonFixture:
    if name not in _FIXTURES:
        raise KeyError(f"fixture {name!r} not found; have {list_fixtures()}")
    return _FIXTURES[name]()


@dataclass
class FixtureScore:
    variant: str
    composite: float
    components: list  # list[ScoreComponent]


def score_fixture(name: str, scorer: CompositeScorer | None = None) -> list[FixtureScore]:
    """Score every variant of a fixture; returned highest-composite first."""
    scorer = scorer or default_composite()
    fixture = get_fixture(name)
    scores = [
        FixtureScore(variant, (r := scorer.score(fixture.case, run)).score, r.components)
        for variant, run in fixture.runs.items()
    ]
    scores.sort(key=lambda s: s.composite, reverse=True)
    return scores
