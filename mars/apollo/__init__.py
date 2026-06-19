"""Apollo — the experiment framework inside Mars.

Apollo answers "did experimental strategy A outperform baseline strategy B?"
with reproducible, statistically-grounded comparisons. It composes the existing
Mars pieces (suites, EvalRunner, scoring) and adds:

  * Experiment / ExperimentArm specs (a baseline arm + experimental arm(s))
  * ExperimentRunner — runs each arm over a suite across N seeded trials
  * Paired statistical comparison (bootstrap CI + Cohen's d) and a verdict
  * PolicyHook — a no-op extension point for future Sentinel policy/audit

The first experiment is ``salience-memory`` (see :mod:`mars.apollo.registry`).
"""

from mars.apollo.comparison import Comparison, compare_arms
from mars.apollo.experiment import (
    ArmResult,
    Experiment,
    ExperimentArm,
    ExperimentResult,
    ExperimentRunner,
)
from mars.apollo.hooks import NoOpPolicyHook, PolicyHook
from mars.apollo.registry import get_experiment, list_experiments

__all__ = [
    "Experiment",
    "ExperimentArm",
    "ExperimentResult",
    "ArmResult",
    "ExperimentRunner",
    "Comparison",
    "compare_arms",
    "PolicyHook",
    "NoOpPolicyHook",
    "get_experiment",
    "list_experiments",
]
