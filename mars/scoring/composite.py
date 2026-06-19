"""Composite scoring — weighted blend of individual scorers."""

from __future__ import annotations

from dataclasses import dataclass

from mars.models import AgentRun, EvalCase, ScoreComponent
from mars.scoring.base import Scorer
from mars.scoring.scorers import CostScorer, DiffScorer, RuntimeScorer, TestPassScorer


@dataclass
class CompositeResult:
    """Outcome of composite scoring."""

    score: float  # 0-100
    components: list[ScoreComponent]


class CompositeScorer:
    """Blends weighted scorers into a single 0-100 composite.

    Weights are normalized, so callers can pass any positive relative weights.
    """

    def __init__(self, scorers: list[tuple[Scorer, float]]) -> None:
        if not scorers:
            raise ValueError("CompositeScorer requires at least one scorer")
        if any(w < 0 for _, w in scorers):
            raise ValueError("weights must be non-negative")
        self._scorers = scorers

    def score(self, case: EvalCase, run: AgentRun) -> CompositeResult:
        total_weight = sum(w for _, w in self._scorers) or 1.0
        components: list[ScoreComponent] = []
        weighted_sum = 0.0
        for scorer, weight in self._scorers:
            outcome = scorer.score(case, run)
            norm = weight / total_weight
            weighted_sum += outcome.value * norm
            components.append(
                ScoreComponent(
                    scorer=scorer.name,
                    value=round(outcome.value, 2),
                    weight=round(norm, 4),
                    detail=outcome.detail,
                )
            )
        return CompositeResult(score=round(weighted_sum, 2), components=components)


def default_composite() -> CompositeScorer:
    """The default scorer mix: tests dominate, then diff focus, runtime, cost."""
    return CompositeScorer(
        [
            (TestPassScorer(), 0.55),
            (DiffScorer(), 0.20),
            (RuntimeScorer(), 0.15),
            (CostScorer(), 0.10),
        ]
    )
