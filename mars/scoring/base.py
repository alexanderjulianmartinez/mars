"""Scorer interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from mars.models import AgentRun, EvalCase


@dataclass
class ScoreOutcome:
    """A single scorer's verdict, normalized to 0-100."""

    value: float  # 0-100
    detail: str = ""


class Scorer(ABC):
    """Maps an (case, agent run) pair to a 0-100 score."""

    #: Stable identifier used in score breakdowns and reports.
    name: str = "scorer"

    @abstractmethod
    def score(self, case: EvalCase, run: AgentRun) -> ScoreOutcome:
        """Return this scorer's 0-100 outcome for ``run`` against ``case``."""
