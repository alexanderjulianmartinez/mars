"""Registry of available Apollo experiments.

New experiments are registered by adding a builder here. The first and only
registered experiment is ``salience-memory``.
"""

from __future__ import annotations

from typing import Callable

from mars.apollo.experiment import Experiment, ExperimentArm
from mars.memory.retrieval import SalienceWeightedStrategy, SimilarityOnlyStrategy


def _salience_memory() -> Experiment:
    return Experiment(
        id="salience-memory",
        title="Salience Memory for Long-Horizon Software Agents",
        hypothesis=(
            "Memory weighting (salience-weighted retrieval) improves long-horizon "
            "agent task performance compared to similarity-only retrieval."
        ),
        arms=[
            ExperimentArm("baseline-similarity", SimilarityOnlyStrategy(), baseline=True),
            ExperimentArm("salience-weighted", SalienceWeightedStrategy()),
        ],
        suite_ids=["backend-api", "infra"],
        agent="claude-code",
        trials=20,
        retrieval_k=5,
        seed=7,
    )


_BUILDERS: dict[str, Callable[[], Experiment]] = {
    "salience-memory": _salience_memory,
}


def list_experiments() -> list[Experiment]:
    return [build() for build in _BUILDERS.values()]


def get_experiment(experiment_id: str) -> Experiment:
    if experiment_id not in _BUILDERS:
        raise KeyError(f"experiment {experiment_id!r} not found")
    return _BUILDERS[experiment_id]()
