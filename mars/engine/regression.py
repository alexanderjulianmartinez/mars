"""Regression detection — compare a current run against a baseline.

Flags drops in score and increases in runtime/cost beyond configurable
thresholds, plus a pass -> fail status regression.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mars.models import EvalRun, EvalStatus


@dataclass
class RegressionReport:
    has_regression: bool
    warnings: list[str] = field(default_factory=list)
    score_delta: float = 0.0
    runtime_delta_ms: int = 0
    cost_delta_usd: float = 0.0

    @property
    def summary(self) -> str:
        if not self.has_regression:
            return "no regressions detected"
        return "; ".join(self.warnings)


def detect_regression(
    current: EvalRun,
    baseline: EvalRun | None,
    *,
    score_drop_threshold: float = 2.0,
    runtime_increase_frac: float = 0.25,
    cost_increase_frac: float = 0.25,
) -> RegressionReport:
    """Compare ``current`` to ``baseline``. With no baseline, nothing regresses."""
    if baseline is None:
        return RegressionReport(has_regression=False, warnings=["no baseline to compare against"])

    warnings: list[str] = []

    score_delta = round(current.score - baseline.score, 2)
    if score_delta < -abs(score_drop_threshold):
        warnings.append(
            f"score regression: {baseline.score:.1f} -> {current.score:.1f} ({score_delta:+.1f})"
        )

    runtime_delta = current.duration_ms - baseline.duration_ms
    if baseline.duration_ms > 0 and runtime_delta > baseline.duration_ms * runtime_increase_frac:
        warnings.append(
            f"runtime regression: {baseline.duration_ms}ms -> {current.duration_ms}ms "
            f"(+{runtime_delta}ms)"
        )

    cost_delta = round(current.cost_usd - baseline.cost_usd, 4)
    if baseline.cost_usd > 0 and cost_delta > baseline.cost_usd * cost_increase_frac:
        warnings.append(
            f"cost regression: ${baseline.cost_usd:.4f} -> ${current.cost_usd:.4f} (+${cost_delta:.4f})"
        )

    if baseline.status == EvalStatus.PASSED and current.status != EvalStatus.PASSED:
        warnings.append(f"status regression: passed -> {current.status.value}")

    return RegressionReport(
        has_regression=bool(warnings),
        warnings=warnings,
        score_delta=score_delta,
        runtime_delta_ms=runtime_delta,
        cost_delta_usd=cost_delta,
    )
