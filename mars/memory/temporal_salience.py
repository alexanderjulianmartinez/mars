"""Temporal Salience study (Experiment 3) — does time help salience retrieval?

Experiment 1 showed salience beats semantic retrieval given informative
importance; Experiment 2 showed it is robust to noisy importance. In both, every
memory was seeded at roughly the same time, so the recency term contributed ≈0.
This experiment **isolates the temporal signal**: it assigns synthetic timestamps
to the (real, cached) candidate pools under four regimes and asks whether recency
— raw or decayed — helps, hurts, or is neutral, and whether it earns a place in
the Salience v2 formula.

Reuses the materialized retrieval cache from the noisy-importance study (real
Voyage semantic scores + importance + gold) so nothing is re-embedded and the
whole sweep is offline and deterministic. Only the timestamps and the ranking
strategy vary.

Honest framing (per the experiment spec):

- **raw recency** (newest=1, oldest=0, normalized within a pool),
- **decayed recency** (``exp(-age_days / half_life)``), and
- **importance + recency**

are reported as *distinct* signals. The question is not whether time *can* help
under a favourable regime, but whether it helps *reliably enough across regimes*
to justify inclusion.
"""

from __future__ import annotations

import json
import random
import statistics
from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from math import exp
from pathlib import Path

from mars.memory.expanded_experiment import ArmReport, _evaluate, _rank
from mars.memory.models import MemoryItem
from mars.memory.noisy_importance_experiment import (
    CachedQuery,
    Paired,
    _mean_rows,
    _paired,
    _row_metrics,
)
from mars.memory.retrieval import SimilarityOnlyStrategy

RESULTS_DIR = Path("mars-experiments")
DEFAULT_HALF_LIVES = (7.0, 30.0, 90.0)


# --- timestamp regimes ----------------------------------------------------- #


class Regime(str, Enum):
    """How synthetic ages are assigned relative to ground-truth relevance."""

    UNIFORM = "A_uniform"  # all same age → no temporal signal (control)
    ALIGNED = "B_recency_aligned"  # relevant newer than non-relevant
    MISALIGNED = "C_recency_misaligned"  # non-relevant newer than relevant
    MIXED = "D_mixed_realistic"  # ages independent of relevance


REGIME_DESCRIPTIONS = {
    Regime.UNIFORM: "All memories share one age; recency carries no signal (reproduces the prior, time-free result).",
    Regime.ALIGNED: "Target + relevant memories are newer than the rest; recency is aligned with relevance.",
    Regime.MISALIGNED: "Distractors/stale memories are newer than target + relevant; recency is anti-correlated with relevance.",
    Regime.MIXED: "Ages are drawn independently of relevance — some relevant memories old, some distractors new (the realistic case).",
}

#: Age bands (days). "new" = recently written, "old" = long ago.
_UNIFORM_AGE = 30.0
_NEW_BAND = (0.0, 20.0)
_OLD_BAND = (60.0, 180.0)
_FULL_BAND = (0.0, 180.0)


def assign_age(is_relevant: bool, regime: Regime, rng: random.Random) -> float:
    """Synthetic age in days for a memory under ``regime`` (deterministic via rng)."""
    if regime is Regime.UNIFORM:
        return _UNIFORM_AGE
    if regime is Regime.ALIGNED:
        band = _NEW_BAND if is_relevant else _OLD_BAND
    elif regime is Regime.MISALIGNED:
        band = _OLD_BAND if is_relevant else _NEW_BAND
    else:  # MIXED
        band = _FULL_BAND
    return rng.uniform(*band)


def normalized_recency(age_days: float, min_age: float, max_age: float) -> float:
    """Raw recency in [0, 1] within a pool: newest (min age) = 1, oldest = 0.

    When every memory shares one age (the uniform control), there is no temporal
    information; return a constant so ranking falls back to the input order.
    """
    if max_age <= min_age:
        return 1.0
    return (max_age - age_days) / (max_age - min_age)


def decay_score(age_days: float, half_life_days: float) -> float:
    """Exponentially decayed recency: ``exp(-age / half_life)`` in (0, 1]."""
    if half_life_days <= 0:
        raise ValueError("half_life_days must be positive")
    return exp(-age_days / half_life_days)


def apply_regime(
    cached: CachedQuery, regime: Regime, rng: random.Random
) -> list[MemoryItem]:
    """Return copies of the pool's memories with ``age_days`` + normalized recency
    set under ``regime``. Pure; does not mutate the cache."""
    ages = {
        m.id: assign_age(m.id in cached.relevant_ids, regime, rng)
        for m in cached.memories
    }
    lo, hi = min(ages.values()), max(ages.values())
    return [
        replace(m, age_days=ages[m.id], recency=normalized_recency(ages[m.id], lo, hi))
        for m in cached.memories
    ]


# --- strategies ------------------------------------------------------------ #
# Default temporal blend weights (per the experiment spec).
W_SIM, W_IMP, W_TEMPORAL = 0.65, 0.25, 0.10


class ImportanceOnlyStrategy:
    name = "importance_only"

    def score(self, m: MemoryItem) -> float:
        return m.importance


class SimPlusImportanceStrategy:
    """The blend with the temporal term *zeroed* — the anchor for isolating
    recency/decay at fixed similarity/importance weights (no time signal)."""

    name = "sim_plus_importance"

    def score(self, m: MemoryItem) -> float:
        return W_SIM * m.similarity + W_IMP * m.importance


class RecencyOnlyStrategy:
    name = "recency_only"

    def score(self, m: MemoryItem) -> float:
        return m.recency


class ImportancePlusRecencyStrategy:
    name = "importance_plus_recency"

    def score(self, m: MemoryItem) -> float:
        return W_SIM * m.similarity + W_IMP * m.importance + W_TEMPORAL * m.recency


class ImportancePlusDecayStrategy:
    def __init__(self, half_life_days: float) -> None:
        self.half_life_days = half_life_days
        self.name = f"importance_plus_decay_h{int(half_life_days)}"

    def score(self, m: MemoryItem) -> float:
        return (
            W_SIM * m.similarity
            + W_IMP * m.importance
            + W_TEMPORAL * decay_score(m.age_days, self.half_life_days)
        )


def temporal_strategies(half_lives: tuple[float, ...]) -> list:
    """Time-dependent strategies evaluated per regime (ages vary per seed)."""
    return [
        RecencyOnlyStrategy(),
        ImportancePlusRecencyStrategy(),
        *[ImportancePlusDecayStrategy(h) for h in half_lives],
    ]


# --- result records -------------------------------------------------------- #


@dataclass
class StrategyResult:
    strategy: str
    time_dependent: bool
    report: ArmReport
    # paired vs the similarity_only baseline, on the headline metrics
    recall5: Paired
    ndcg5: Paired
    mrr: Paired


@dataclass
class RegimeResult:
    regime: str
    description: str
    strategies: list[StrategyResult]
    # marginal value of adding recency on top of importance alone (importance+
    # recency − importance_only): the direct test of "does recency add anything?"
    recency_marginal_recall5: Paired
    recency_marginal_ndcg5: Paired


@dataclass
class TemporalStudyResult:
    experiment: str
    retrieval_source: str
    semantic_available: bool
    n_queries: int
    seeds_per_regime: int
    half_lives: list[float]
    regimes: list[RegimeResult]
    notes: list[str] = field(default_factory=list)


# --- driver ---------------------------------------------------------------- #


def _headline(rows: list[dict]) -> tuple[list[float], list[float], list[float]]:
    return (
        [r["recall"][5] for r in rows],
        [r["ndcg"][5] for r in rows],
        [r["mrr"] for r in rows],
    )


def run_temporal_study(
    cached: list[CachedQuery],
    *,
    regimes: tuple[Regime, ...] = tuple(Regime),
    half_lives: tuple[float, ...] = DEFAULT_HALF_LIVES,
    seeds_per_regime: int = 10,
    base_seed: int = 1729,
    experiment: str = "salience-memory-temporal-salience",
    retrieval_source: str = "cortex-mcp (cached)",
    semantic_available: bool = True,
    notes: list[str] | None = None,
) -> TemporalStudyResult:
    """Sweep timestamp regimes × strategies over cached real retrievals."""
    base_strat = SimilarityOnlyStrategy()
    imp_strat = ImportanceOnlyStrategy()
    sip_strat = SimPlusImportanceStrategy()

    # Time-invariant arms: computed once (ages don't affect them).
    def invariant_rows(strat) -> list[dict]:
        return [
            _row_metrics(_rank(strat, c.memories), c.relevant_ids, c.target_id)
            for c in cached
        ]

    base_rows = invariant_rows(base_strat)
    imp_rows = invariant_rows(imp_strat)
    sip_rows = invariant_rows(sip_strat)  # anchor: blend with temporal weight = 0
    base_report = _evaluate("similarity_only", base_rows)
    imp_report = _evaluate("importance_only", imp_rows)
    sip_report = _evaluate("sim_plus_importance", sip_rows)
    base_r5, base_n5, base_mrr = _headline(base_rows)
    sip_r5, sip_n5, _ = _headline(sip_rows)

    def vs_base(rows: list[dict], qi: int) -> tuple[Paired, Paired, Paired]:
        r5, n5, mr = _headline(rows)
        return (
            _paired(r5, base_r5, seed=base_seed + qi),
            _paired(n5, base_n5, seed=base_seed + qi + 1),
            _paired(mr, base_mrr, seed=base_seed + qi + 2),
        )

    regime_results: list[RegimeResult] = []
    for ri, regime in enumerate(regimes):
        tstrats = temporal_strategies(half_lives)
        acc: dict[str, list[list[dict]]] = {s.name: [[] for _ in cached] for s in tstrats}

        for seed in range(seeds_per_regime):
            for ci, c in enumerate(cached):
                rng = random.Random(base_seed * 7919 + ri * 104_729 + seed * 97 + ci)
                tmems = apply_regime(c, regime, rng)
                for s in tstrats:
                    ranked = _rank(s, tmems)
                    acc[s.name][ci].append(
                        _row_metrics(ranked, c.relevant_ids, c.target_id)
                    )

        strat_results: list[StrategyResult] = []
        # Reference (time-invariant) arms shown in every regime for context.
        for name, report, rows in (
            ("similarity_only", base_report, base_rows),
            ("importance_only", imp_report, imp_rows),
            ("sim_plus_importance", sip_report, sip_rows),
        ):
            r5p, n5p, mrp = vs_base(rows, ri)
            strat_results.append(
                StrategyResult(name, False, report, r5p, n5p, mrp)
            )

        ipr_mean_rows: list[dict] | None = None
        for s in tstrats:
            mean_rows = [_mean_rows(rows) for rows in acc[s.name]]
            if s.name == "importance_plus_recency":
                ipr_mean_rows = mean_rows
            report = _evaluate(s.name, mean_rows)
            r5p, n5p, mrp = vs_base(mean_rows, ri)
            strat_results.append(StrategyResult(s.name, True, report, r5p, n5p, mrp))

        # Recency's *isolated* marginal: importance+recency minus the same blend
        # with the temporal weight zeroed (sim_plus_importance). This holds the
        # similarity/importance weights fixed, so the delta is the recency term
        # alone — not the importance-vs-similarity reweighting.
        ipr_r5, ipr_n5, _ = _headline(ipr_mean_rows or sip_rows)
        regime_results.append(
            RegimeResult(
                regime=regime.value,
                description=REGIME_DESCRIPTIONS[regime],
                strategies=strat_results,
                recency_marginal_recall5=_paired(ipr_r5, sip_r5, seed=base_seed + ri + 3),
                recency_marginal_ndcg5=_paired(ipr_n5, sip_n5, seed=base_seed + ri + 4),
            )
        )

    return TemporalStudyResult(
        experiment=experiment,
        retrieval_source=retrieval_source,
        semantic_available=semantic_available,
        n_queries=len(cached),
        seeds_per_regime=seeds_per_regime,
        half_lives=list(half_lives),
        regimes=regime_results,
        notes=notes or [],
    )


# --- persistence + rendering ---------------------------------------------- #


def save_result(result: TemporalStudyResult, results_dir: Path | None = None) -> Path:
    directory = results_dir or RESULTS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{result.experiment}.json"
    path.write_text(json.dumps(asdict(result), indent=2, default=str))
    return path


def render_report(result: TemporalStudyResult) -> str:
    sem = "available" if result.semantic_available else "UNAVAILABLE"
    lines = [
        f"# {result.experiment} — Results",
        "",
        f"**Retrieval provider:** {result.retrieval_source}  ",
        f"**Semantic scores:** {sem}  ",
        f"**Queries:** {result.n_queries}  "
        f"**Seeds/regime:** {result.seeds_per_regime}  "
        f"**Decay half-lives (days):** {', '.join(str(int(h)) for h in result.half_lives)}",
        "",
        "Δ columns are vs the `similarity_only` baseline with a paired 95% bootstrap "
        "CI over queries; ✓ = CI excludes zero (beats baseline), ✗ = CI below zero "
        "(worse than baseline).",
    ]
    for rr in result.regimes:
        lines += [
            "",
            f"## Regime {rr.regime}",
            "",
            f"_{rr.description}_",
            "",
            "| strategy | recall@5 | Δ recall@5 (95% CI) | nDCG@5 | Δ nDCG@5 (95% CI) | MRR | verdict |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for s in rr.strategies:
            r, n = s.recall5, s.ndcg5
            if r.beats and n.beats:
                verdict = "✓ beats"
            elif r.ci_high < 0 and n.ci_high < 0:
                verdict = "✗ worse"
            else:
                verdict = "≈ tie"
            lines.append(
                f"| `{s.strategy}` "
                f"| {s.report.recall[5]:.3f} "
                f"| {r.mean_delta:+.3f} [{r.ci_low:+.3f}, {r.ci_high:+.3f}] "
                f"| {s.report.ndcg[5]:.3f} "
                f"| {n.mean_delta:+.3f} [{n.ci_low:+.3f}, {n.ci_high:+.3f}] "
                f"| {s.report.mrr:.3f} "
                f"| {verdict} |"
            )
        m = rr.recency_marginal_recall5
        sign = "helps" if m.beats else ("hurts" if m.ci_high < 0 else "is neutral")
        lines.append(
            f"\nIsolated recency marginal (`importance_plus_recency` − "
            f"`sim_plus_importance`, temporal weight held at 0.10 vs 0): recall@5 "
            f"{m.mean_delta:+.3f} [{m.ci_low:+.3f}, {m.ci_high:+.3f}] → adding raw "
            f"recency **{sign}** here."
        )

    if result.notes:
        lines += ["", "## Notes", ""] + [f"- {n}" for n in result.notes]
    return "\n".join(lines)
