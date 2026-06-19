"""Statistical comparison of an experimental arm against the baseline.

Uses a **paired** design: each (case, trial) sample is run under identical luck
across arms, so the per-sample difference isolates the strategy's effect. We
report the mean difference, a bootstrap 95% confidence interval, and Cohen's d
effect size, then derive a verdict. Bootstrap keeps this dependency-free and
reproducible (seeded).
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass


@dataclass
class Comparison:
    experimental_arm: str
    baseline_arm: str
    n: int
    baseline_mean: float
    experimental_mean: float
    mean_delta: float
    lift_pct: float
    ci_low: float
    ci_high: float
    cohens_d: float
    significant: bool
    verdict: str


def _bootstrap_ci(
    diffs: list[float], iters: int = 2000, alpha: float = 0.05, seed: int = 0
) -> tuple[float, float]:
    rng = random.Random(seed)
    n = len(diffs)
    means: list[float] = []
    for _ in range(iters):
        means.append(sum(diffs[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    lo = means[max(0, int((alpha / 2) * iters))]
    hi = means[min(iters - 1, int((1 - alpha / 2) * iters))]
    return lo, hi


def _cohens_d_paired(diffs: list[float]) -> float:
    if len(diffs) < 2:
        return 0.0
    sd = statistics.pstdev(diffs)
    if sd == 0:
        return 0.0
    return statistics.fmean(diffs) / sd


def compare_arms(
    baseline_name: str,
    baseline_scores: list[float],
    experimental_name: str,
    experimental_scores: list[float],
    *,
    seed: int = 0,
) -> Comparison:
    """Compare two arms' paired, index-aligned per-sample scores."""
    if len(baseline_scores) != len(experimental_scores):
        raise ValueError("arms must have the same number of paired samples")
    n = len(baseline_scores)
    diffs = [e - b for e, b in zip(experimental_scores, baseline_scores)]

    base_mean = statistics.fmean(baseline_scores) if n else 0.0
    exp_mean = statistics.fmean(experimental_scores) if n else 0.0
    mean_delta = exp_mean - base_mean
    lift = (mean_delta / base_mean * 100.0) if base_mean else 0.0
    ci_low, ci_high = _bootstrap_ci(diffs, seed=seed) if n else (0.0, 0.0)
    d = _cohens_d_paired(diffs)

    if ci_low > 0:
        significant, verdict = True, f"{experimental_name} significantly outperforms {baseline_name}"
    elif ci_high < 0:
        significant, verdict = True, f"{baseline_name} significantly outperforms {experimental_name}"
    else:
        significant, verdict = False, "no significant difference"

    return Comparison(
        experimental_arm=experimental_name,
        baseline_arm=baseline_name,
        n=n,
        baseline_mean=round(base_mean, 2),
        experimental_mean=round(exp_mean, 2),
        mean_delta=round(mean_delta, 2),
        lift_pct=round(lift, 1),
        ci_low=round(ci_low, 2),
        ci_high=round(ci_high, 2),
        cohens_d=round(d, 2),
        significant=significant,
        verdict=verdict,
    )
