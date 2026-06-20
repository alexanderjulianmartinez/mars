"""Composite scoring — weighted blend of individual scorers."""

from __future__ import annotations

from dataclasses import dataclass

from mars.models import AgentRun, EvalCase, ScoreComponent
from mars.scoring.agentic import (
    DiffQualityScorer,
    LiteralInstructionScorer,
    NoiseScorer,
)
from mars.scoring.base import Scorer
from mars.scoring.scorers import CostScorer, RuntimeScorer, TestPassScorer


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
                    data=outcome.data,
                )
            )
        return CompositeResult(score=round(weighted_sum, 2), components=components)


def default_composite() -> CompositeScorer:
    """Agentic-evaluation mix (Track A weights).

    Tests dominate, then literal-instruction adherence and diff quality, with
    noise/runtime/cost as modifiers. Each agentic scorer is a no-op (100) when
    the case declares no relevant config, so this is safe as the global default.
    """
    return CompositeScorer(
        [
            (TestPassScorer(), 0.30),
            (LiteralInstructionScorer(), 0.25),
            (DiffQualityScorer(), 0.20),
            (NoiseScorer(), 0.10),
            (RuntimeScorer(), 0.075),
            (CostScorer(), 0.075),
        ]
    )
