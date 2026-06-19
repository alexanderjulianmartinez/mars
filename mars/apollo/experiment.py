"""Experiment specs and the runner that executes them.

An :class:`Experiment` declares a baseline arm and one or more experimental
arms, each carrying a retrieval strategy. The :class:`ExperimentRunner` runs
every arm over the experiment's suite(s) across ``trials`` seeded repetitions,
collecting an index-aligned per-sample score vector per arm, then compares each
experimental arm to the baseline.

Mars stays in its lane: it sequences Cortex (retrieval) and AutoDev (execution)
and measures outcomes. The only experimental variable is the retrieval strategy.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from mars.apollo.comparison import Comparison, compare_arms
from mars.apollo.hooks import NoOpPolicyHook, PolicyHook
from mars.engine.runner import EvalRunner
from mars.memory.retrieval import RetrievalStrategy
from mars.models import EvalCase, EvalStatus
from mars.providers.memory_mock import (
    MemoryAwareAutoDevProvider,
    MemoryAwareCortexProvider,
)
from mars.scoring.composite import default_composite
from mars.suites import load_suite


@dataclass
class ExperimentArm:
    """One condition in an experiment: a named retrieval strategy."""

    name: str
    strategy: RetrievalStrategy
    baseline: bool = False


@dataclass
class Experiment:
    """A reproducible A/B(/C) experiment definition."""

    id: str
    title: str
    hypothesis: str
    arms: list[ExperimentArm]
    suite_ids: list[str]
    agent: str = "claude-code"
    base_quality: float = 0.9
    retrieval_k: int = 5
    trials: int = 20
    seed: int = 7

    def baseline_arm(self) -> ExperimentArm:
        for arm in self.arms:
            if arm.baseline:
                return arm
        raise ValueError(f"experiment {self.id!r} has no baseline arm")


@dataclass
class ArmResult:
    """Aggregated outcome for one arm across all (case, trial) samples."""

    name: str
    baseline: bool
    scores: list[float]  # index-aligned across arms (case-major, trial-minor)
    statuses: list[str]
    relevances: list[float]
    config: dict
    sample_keys: list[str] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.scores)

    @property
    def mean_score(self) -> float:
        return round(statistics.fmean(self.scores), 2) if self.scores else 0.0

    @property
    def pass_rate(self) -> float:
        if not self.statuses:
            return 0.0
        passed = sum(1 for s in self.statuses if s == EvalStatus.PASSED.value)
        return round(passed / len(self.statuses), 4)

    @property
    def mean_relevance(self) -> float:
        return round(statistics.fmean(self.relevances), 4) if self.relevances else 0.0


@dataclass
class ExperimentResult:
    id: str
    title: str
    hypothesis: str
    trials: int
    agent: str
    arms: list[ArmResult]
    comparisons: list[Comparison]

    @property
    def headline(self) -> str:
        if not self.comparisons:
            return "no comparisons"
        # Headline on the strongest positive experimental arm, else first.
        best = max(self.comparisons, key=lambda c: c.mean_delta)
        return best.verdict


class ExperimentRunner:
    """Executes experiments with the memory-aware mock providers."""

    def __init__(self, hook: PolicyHook | None = None) -> None:
        self.hook = hook or NoOpPolicyHook()

    def _load_cases(self, suite_ids: list[str]) -> list[EvalCase]:
        cases: list[EvalCase] = []
        for sid in suite_ids:
            cases.extend(load_suite(sid).cases)
        return cases

    def run(self, experiment: Experiment) -> ExperimentResult:
        cases = self._load_cases(experiment.suite_ids)
        arm_results: list[ArmResult] = []

        for arm in experiment.arms:
            cortex = MemoryAwareCortexProvider(
                arm.strategy, k=experiment.retrieval_k, seed=experiment.seed
            )
            autodev = MemoryAwareAutoDevProvider(
                agent=experiment.agent, base_quality=experiment.base_quality
            )
            runner = EvalRunner(cortex, autodev, repository=None, scorer=default_composite())

            scores: list[float] = []
            statuses: list[str] = []
            relevances: list[float] = []
            keys: list[str] = []

            # case-major, trial-minor ordering — identical across arms so the
            # resulting vectors are paired index-for-index.
            for case in cases:
                for trial in range(experiment.trials):
                    cortex.trial = trial
                    autodev.trial = trial
                    self.hook.before_run(experiment.id, arm.name, case, trial)
                    eval_run = runner.run_case(case)
                    self.hook.after_run(experiment.id, arm.name, case, trial, eval_run)
                    scores.append(eval_run.score)
                    statuses.append(eval_run.status.value)
                    relevances.append(float(cortex.last_relevance or 0.0))
                    keys.append(f"{case.id}#{trial}")

            arm_results.append(
                ArmResult(
                    name=arm.name,
                    baseline=arm.baseline,
                    scores=scores,
                    statuses=statuses,
                    relevances=relevances,
                    config=arm.strategy.config(),
                    sample_keys=keys,
                )
            )

        baseline = next(a for a in arm_results if a.baseline)
        comparisons = [
            compare_arms(
                baseline.name,
                baseline.scores,
                arm.name,
                arm.scores,
                seed=experiment.seed,
            )
            for arm in arm_results
            if not arm.baseline
        ]

        self.hook.on_experiment_complete(experiment.id)
        return ExperimentResult(
            id=experiment.id,
            title=experiment.title,
            hypothesis=experiment.hypothesis,
            trials=experiment.trials,
            agent=experiment.agent,
            arms=arm_results,
            comparisons=comparisons,
        )
