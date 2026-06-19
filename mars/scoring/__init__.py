"""Pluggable scoring for Mars.

A :class:`~mars.scoring.base.Scorer` maps an ``(EvalCase, AgentRun)`` pair to a
0-100 value. :class:`~mars.scoring.composite.CompositeScorer` blends several
scorers into a single composite score. New scorers are added by implementing
the interface, never by editing existing scorers.
"""

from mars.scoring.base import ScoreOutcome, Scorer
from mars.scoring.composite import CompositeScorer, default_composite
from mars.scoring.scorers import (
    CostScorer,
    DiffScorer,
    RuntimeScorer,
    TestPassScorer,
)

__all__ = [
    "Scorer",
    "ScoreOutcome",
    "CompositeScorer",
    "default_composite",
    "TestPassScorer",
    "RuntimeScorer",
    "CostScorer",
    "DiffScorer",
]
