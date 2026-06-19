"""Built-in scorers.

Each scorer is independent and returns a 0-100 value. Runtime and cost scorers
use a soft budget: at or under budget scores 100, degrading toward 0 as the
metric grows past the budget.
"""

from __future__ import annotations

from mars.models import AgentRun, AgentRunStatus, EvalCase
from mars.scoring.base import ScoreOutcome, Scorer


def _budget_score(value: float, budget: float) -> float:
    """Score 100 at/under budget, decaying to 0 at 2x budget (clamped)."""
    if budget <= 0:
        return 100.0 if value <= 0 else 0.0
    if value <= budget:
        return 100.0
    over = (value - budget) / budget  # fraction over budget
    return max(0.0, 100.0 * (1.0 - over))


class TestPassScorer(Scorer):
    """Fraction of the case's tests that passed (0-100)."""

    name = "test_pass"

    def score(self, case: EvalCase, run: AgentRun) -> ScoreOutcome:
        if not run.test_results:
            return ScoreOutcome(0.0, "no tests reported")
        passed = sum(1 for t in run.test_results if t.passed)
        total = len(run.test_results)
        value = 100.0 * passed / total
        return ScoreOutcome(value, f"{passed}/{total} tests passed")


class RuntimeScorer(Scorer):
    """Rewards staying within a runtime budget derived from the timeout."""

    name = "runtime"

    def __init__(self, budget_fraction: float = 0.5) -> None:
        # Default budget = half the case timeout.
        self.budget_fraction = budget_fraction

    def score(self, case: EvalCase, run: AgentRun) -> ScoreOutcome:
        budget_ms = case.timeout_seconds * 1000 * self.budget_fraction
        value = _budget_score(run.runtime_ms, budget_ms)
        return ScoreOutcome(value, f"{run.runtime_ms}ms vs budget {int(budget_ms)}ms")


class CostScorer(Scorer):
    """Rewards staying within a USD cost budget."""

    name = "cost"

    def __init__(self, budget_usd: float = 0.10) -> None:
        self.budget_usd = budget_usd

    def score(self, case: EvalCase, run: AgentRun) -> ScoreOutcome:
        value = _budget_score(run.cost_usd, self.budget_usd)
        return ScoreOutcome(value, f"${run.cost_usd:.4f} vs budget ${self.budget_usd:.2f}")


class DiffScorer(Scorer):
    """Rewards a focused, non-empty diff; penalizes sprawling changes.

    A failed run with no diff scores 0. A successful run scores 100 when it
    touches at most ``focus_files`` files, decaying as it changes more.
    """

    name = "diff"

    def __init__(self, focus_files: int = 3) -> None:
        self.focus_files = focus_files

    def score(self, case: EvalCase, run: AgentRun) -> ScoreOutcome:
        if run.status != AgentRunStatus.SUCCESS or not run.diff.strip():
            return ScoreOutcome(0.0, "no diff produced")
        n = len(run.files_changed) or 1
        if n <= self.focus_files:
            return ScoreOutcome(100.0, f"{n} file(s) changed")
        over = (n - self.focus_files) / self.focus_files
        return ScoreOutcome(max(0.0, 100.0 * (1.0 - over)), f"{n} files changed (sprawling)")
