"""Confidence & Contradiction study (Experiment 4).

Importance is the dominant salience signal found so far. This experiment asks the
next question: **what should happen when an important memory may be wrong?** A
memory can be important *and* low-confidence (e.g. an obsolete "use integer IDs"
decision later superseded by "use UUIDs"). Confidence-aware retrieval should
prioritize the trustworthy memory and suppress contradictory/outdated ones.

Reuses the committed real-retrieval cache (real Voyage semantic scores +
importance + gold) from Experiment 2, joined to the expanded corpus **by content**
to recover each memory's authored ``category`` and ``confidence`` — so nothing is
re-embedded and the study is offline + deterministic. Only the confidence values
and the ranking strategy vary across four regimes.

New metric: **ContradictionAvoidanceRate** — over queries whose candidate pool
contains both the correct ``target`` memory and ≥1 ``contradictory`` (obsolete)
memory, the fraction where the target outranks *every* contradictory memory.

Honest framing: confidence is reported as a signal **distinct** from importance and
recency; the analysis isolates its marginal value over importance alone.
"""

from __future__ import annotations

import json
import random
import statistics
from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from pathlib import Path

from mars.memory.expanded_corpus import load_expanded_corpus
from mars.memory.expanded_experiment import ArmReport, _evaluate, _rank
from mars.memory.models import MemoryItem
from mars.memory.noisy_importance_experiment import (
    CachedQuery,
    Paired,
    _mean_rows,
    _paired,
    _row_metrics,
)
from mars.memory.temporal_salience import ImportanceOnlyStrategy, SimPlusImportanceStrategy
from mars.memory.retrieval import SimilarityOnlyStrategy

RESULTS_DIR = Path("mars-experiments")
CORPUS_NAME = "salience-memory-v1-expanded"
CONTRADICTORY = "contradictory"


# --- confidence regimes ---------------------------------------------------- #


class Regime(str, Enum):
    HIGH_EVERYWHERE = "A_high_everywhere"  # control: confidence ≈ uninformative
    LOW_CONF_DISTRACTORS = "B_low_conf_distractors"  # relevant high, others low
    CONTRADICTORY = "C_contradictory"  # obsolete contradictory memories low conf
    MIXED = "D_mixed_realistic"  # authored per-category confidence (realistic)
    CONTRADICTORY_HARD = "E_contradictory_hard"  # H4 stress: obsolete = important BUT untrusted


REGIME_DESCRIPTIONS = {
    Regime.HIGH_EVERYWHERE: "Every memory is high-confidence; confidence carries almost no signal (control).",
    Regime.LOW_CONF_DISTRACTORS: "Relevant memories are high-confidence (0.8–1.0), everything else low (0.1–0.3); confidence is aligned with relevance.",
    Regime.CONTRADICTORY: "Target/relevant high-confidence, the obsolete contradictory memories low-confidence (0.1–0.3), the rest mid; confidence should suppress the obsolete information.",
    Regime.MIXED: "Each memory keeps its authored per-category confidence (target≈0.91, relevant≈0.82, distractor≈0.71, stale≈0.64, contradictory≈0.44, low_confidence≈0.25) — the realistic regime.",
    Regime.CONTRADICTORY_HARD: "H4 stress test: the obsolete contradictory memories are forced to be slightly MORE important than the target (importance decoupled from — and actively misleading about — correctness) but low-confidence: the adversarial 'important but wrong' case importance alone gets wrong. The only regime where confidence has a job importance cannot already do.",
}

_HIGH_BAND = (0.9, 1.0)
_REL_BAND = (0.8, 1.0)
_LOW_BAND = (0.1, 0.3)
_MID_BAND = (0.5, 0.7)


# --- enrichment: join cache → corpus categories/confidence by content ------ #


@dataclass
class EnrichedQuery:
    """A cached pool annotated with each memory's category + authored confidence."""

    cached: CachedQuery
    category: dict[str, str]  # memory id -> corpus category
    authored_confidence: dict[str, float]  # memory id -> authored confidence

    @property
    def contradictory_ids(self) -> set[str]:
        return {mid for mid, c in self.category.items() if c == CONTRADICTORY}

    @property
    def is_contradiction_eligible(self) -> bool:
        ids = {m.id for m in self.cached.memories}
        return self.cached.target_id in ids and bool(self.contradictory_ids)


def enrich(cached: list[CachedQuery], corpus_name: str = CORPUS_NAME) -> list[EnrichedQuery]:
    """Attach category + authored confidence to each cached memory via content match."""
    corpus = load_expanded_corpus(corpus_name)
    by_content = {
        m.content.strip(): (m.category.value, m.confidence)
        for q in corpus.queries
        for m in q.memories
    }
    enriched: list[EnrichedQuery] = []
    for c in cached:
        category: dict[str, str] = {}
        confidence: dict[str, float] = {}
        for m in c.memories:
            hit = by_content.get(m.content.strip())
            if hit is None:  # pragma: no cover - cache is built from this corpus
                category[m.id], confidence[m.id] = "unknown", 0.5
            else:
                category[m.id], confidence[m.id] = hit
        enriched.append(EnrichedQuery(c, category, confidence))
    return enriched


def assign_confidence(eq: EnrichedQuery, regime: Regime, rng: random.Random) -> list[MemoryItem]:
    """Return copies of the pool with ``confidence`` (and, in the HARD regime,
    ``importance``) set under ``regime``. Pure; does not mutate the cache.

    In ``CONTRADICTORY_HARD`` the obsolete memories' importance is raised to the
    pool's top relevant importance, so importance can no longer separate them from
    the target — the decisive test of whether confidence adds anything importance
    cannot already provide.
    """
    rel = eq.cached.relevant_ids
    hard_imp = None
    if regime is Regime.CONTRADICTORY_HARD:
        # Push the obsolete memory's importance just ABOVE the most-important
        # relevant memory, so importance ranks the wrong memory first — the
        # adversarial "important but wrong" case (not a tie that luck could break).
        rel_imps = [m.importance for m in eq.cached.memories if m.id in rel]
        hard_imp = min(1.0, (max(rel_imps) if rel_imps else 0.9) + 0.1)

    out: list[MemoryItem] = []
    for m in eq.cached.memories:
        importance = m.importance
        if regime is Regime.MIXED:
            conf = eq.authored_confidence[m.id]  # realistic, deterministic
        elif regime is Regime.HIGH_EVERYWHERE:
            conf = rng.uniform(*_HIGH_BAND)
        elif regime is Regime.LOW_CONF_DISTRACTORS:
            conf = rng.uniform(*_REL_BAND) if m.id in rel else rng.uniform(*_LOW_BAND)
        else:  # CONTRADICTORY or CONTRADICTORY_HARD
            if m.id in rel:
                conf = rng.uniform(*_REL_BAND)
            elif eq.category[m.id] == CONTRADICTORY:
                conf = rng.uniform(*_LOW_BAND)
                if regime is Regime.CONTRADICTORY_HARD:
                    importance = hard_imp  # important BUT untrusted
            else:
                conf = rng.uniform(*_MID_BAND)
        out.append(replace(m, confidence=conf, importance=importance))
    return out


# --- contradiction avoidance ----------------------------------------------- #


def contradiction_avoided(
    ranked: list[str], target_id: str | None, contradictory_ids: set[str]
) -> bool | None:
    """Did the correct ``target`` outrank *every* contradictory memory present?

    Returns ``None`` when the query is not eligible (no target or no contradictory
    memory in the ranking), so it is excluded from the rate's denominator.
    """
    present = [c for c in contradictory_ids if c in ranked]
    if target_id is None or target_id not in ranked or not present:
        return None
    target_rank = ranked.index(target_id)
    return all(target_rank < ranked.index(c) for c in present)


# --- strategies ------------------------------------------------------------ #
# Confidence blend weights (documented; parallel to the temporal-study weights).
W_SIM, W_IMP, W_CONF = 0.65, 0.25, 0.10
# Gated: a single confidence-gated importance term (0.25 + 0.10 budget merged).
W_GATED_IMP = 0.35
# recency+confidence comparison weights (recency is the flat cache value).
WR_SIM, WR_IMP, WR_CONF, WR_REC = 0.60, 0.20, 0.10, 0.10


class ConfidenceOnlyStrategy:
    name = "confidence_only"

    def score(self, m: MemoryItem) -> float:
        return m.confidence


class ImportancePlusConfidenceStrategy:
    """Additive: ``0.65·sim + 0.25·importance + 0.10·confidence``."""

    name = "importance_plus_confidence"

    def score(self, m: MemoryItem) -> float:
        return W_SIM * m.similarity + W_IMP * m.importance + W_CONF * m.confidence


class ImportancePlusConfidenceGatedStrategy:
    """Gated: ``0.65·sim + 0.35·(importance × confidence)``.

    Confidence multiplies importance, so a low-confidence memory's importance is
    discounted — a highly-important but untrusted memory cannot dominate (H4).
    """

    name = "importance_plus_confidence_gated"

    def score(self, m: MemoryItem) -> float:
        return W_SIM * m.similarity + W_GATED_IMP * (m.importance * m.confidence)


class ImportancePlusRecencyPlusConfidenceStrategy:
    """Comparison only: ``0.60·sim + 0.20·imp + 0.10·conf + 0.10·recency``.

    Recency is the flat cache value (Exp 3 showed raw recency is unreliable); it is
    included to check it does not unlock anything confidence does not.
    """

    name = "importance_plus_recency_plus_confidence"

    def score(self, m: MemoryItem) -> float:
        return (
            WR_SIM * m.similarity
            + WR_IMP * m.importance
            + WR_CONF * m.confidence
            + WR_REC * m.recency
        )


def confidence_strategies() -> list:
    return [
        ConfidenceOnlyStrategy(),
        ImportancePlusConfidenceStrategy(),
        ImportancePlusConfidenceGatedStrategy(),
        ImportancePlusRecencyPlusConfidenceStrategy(),
    ]


# --- result records -------------------------------------------------------- #


@dataclass
class StrategyResult:
    strategy: str
    confidence_dependent: bool
    report: ArmReport
    contradiction_avoidance_rate: float
    contradiction_eligible: int
    recall5: Paired  # vs similarity_only baseline
    ndcg5: Paired
    mrr: Paired


@dataclass
class RegimeResult:
    regime: str
    description: str
    strategies: list[StrategyResult]
    # confidence's isolated marginal over importance alone (importance+confidence −
    # importance_only) on the headline metrics
    confidence_marginal_recall5: Paired
    confidence_marginal_ndcg5: Paired


@dataclass
class ConfidenceStudyResult:
    experiment: str
    retrieval_source: str
    semantic_available: bool
    n_queries: int
    seeds_per_regime: int
    regimes: list[RegimeResult]
    notes: list[str] = field(default_factory=list)


# --- driver ---------------------------------------------------------------- #


def _headline(rows: list[dict]) -> tuple[list[float], list[float], list[float]]:
    return (
        [r["recall"][5] for r in rows],
        [r["ndcg"][5] for r in rows],
        [r["mrr"] for r in rows],
    )


def _avoidance_rate(per_query_indicators: list[list[float]]) -> tuple[float, int]:
    """Mean avoidance over eligible queries (per-query value averaged over seeds)."""
    per_query = [statistics.fmean(xs) for xs in per_query_indicators if xs]
    if not per_query:
        return 0.0, 0
    return round(statistics.fmean(per_query), 4), len(per_query)


def run_confidence_study(
    enriched: list[EnrichedQuery],
    *,
    regimes: tuple[Regime, ...] = tuple(Regime),
    seeds_per_regime: int = 10,
    base_seed: int = 1729,
    experiment: str = "salience-memory-confidence-and-contradiction",
    retrieval_source: str = "cortex-mcp (cached)",
    semantic_available: bool = True,
    notes: list[str] | None = None,
) -> ConfidenceStudyResult:
    """Sweep confidence regimes × strategies over the enriched cached retrievals."""
    base_strat = SimilarityOnlyStrategy()
    imp_strat = ImportanceOnlyStrategy()
    sip_strat = SimPlusImportanceStrategy()

    def avoid(eq: EnrichedQuery, ranked: list[str]) -> bool | None:
        return contradiction_avoided(ranked, eq.cached.target_id, eq.contradictory_ids)

    def arm(strat, mems_per_query: list[list[MemoryItem]]) -> tuple[ArmReport, list[dict], float, int]:
        rows, ind = [], []
        for eq, mems in zip(enriched, mems_per_query):
            ranked = _rank(strat, mems)
            rows.append(_row_metrics(ranked, eq.cached.relevant_ids, eq.cached.target_id))
            a = avoid(eq, ranked)
            ind.append([] if a is None else [1.0 if a else 0.0])
        rate, elig = _avoidance_rate(ind)
        return _evaluate(strat.name, rows), rows, rate, elig

    # similarity_only ignores importance + confidence, so it is invariant across
    # every regime (including the HARD importance override) — the global baseline.
    raw_mems = [list(eq.cached.memories) for eq in enriched]
    base_report, base_rows, base_rate, base_elig = arm(base_strat, raw_mems)
    base_r5, base_n5, base_mrr = _headline(base_rows)

    def vs_base(rows: list[dict], qi: int) -> tuple[Paired, Paired, Paired]:
        r5, n5, mr = _headline(rows)
        return (
            _paired(r5, base_r5, seed=base_seed + qi),
            _paired(n5, base_n5, seed=base_seed + qi + 1),
            _paired(mr, base_mrr, seed=base_seed + qi + 2),
        )

    regime_results: list[RegimeResult] = []
    for ri, regime in enumerate(regimes):
        # Per-regime base memories: importance overrides applied (HARD only);
        # confidence is irrelevant to the importance/sim arms, so a fixed seed is
        # fine. importance_only and sim_plus_importance must be recomputed because
        # the HARD regime decouples importance from correctness.
        base_mems = [assign_confidence(eq, regime, random.Random(base_seed * 13 + ri))
                     for eq in enriched]
        imp_report, imp_rows, imp_rate, imp_elig = arm(imp_strat, base_mems)
        sip_report, sip_rows, sip_rate, sip_elig = arm(sip_strat, base_mems)
        sip_r5, sip_n5, _ = _headline(sip_rows)

        cstrats = confidence_strategies()
        acc: dict[str, list[list[dict]]] = {s.name: [[] for _ in enriched] for s in cstrats}
        avoid_acc: dict[str, list[list[float]]] = {s.name: [[] for _ in enriched] for s in cstrats}

        for seed in range(seeds_per_regime):
            for ci, eq in enumerate(enriched):
                rng = random.Random(base_seed * 6311 + ri * 50_021 + seed * 89 + ci)
                cmems = assign_confidence(eq, regime, rng)
                for s in cstrats:
                    ranked = _rank(s, cmems)
                    acc[s.name][ci].append(
                        _row_metrics(ranked, eq.cached.relevant_ids, eq.cached.target_id)
                    )
                    a = avoid(eq, ranked)
                    if a is not None:
                        avoid_acc[s.name][ci].append(1.0 if a else 0.0)

        strat_results: list[StrategyResult] = []
        # reference arms (confidence-invariant within a regime)
        for name, report, rows, rate, elig in (
            ("similarity_only", base_report, base_rows, base_rate, base_elig),
            ("importance_only", imp_report, imp_rows, imp_rate, imp_elig),
            ("sim_plus_importance", sip_report, sip_rows, sip_rate, sip_elig),
        ):
            r5p, n5p, mrp = vs_base(rows, ri)
            strat_results.append(
                StrategyResult(name, False, report, rate, elig, r5p, n5p, mrp)
            )

        ipc_mean_rows: list[dict] | None = None
        for s in cstrats:
            mean_rows = [_mean_rows(rows) for rows in acc[s.name]]
            if s.name == "importance_plus_confidence":
                ipc_mean_rows = mean_rows
            report = _evaluate(s.name, mean_rows)
            rate, elig = _avoidance_rate(avoid_acc[s.name])
            r5p, n5p, mrp = vs_base(mean_rows, ri)
            strat_results.append(
                StrategyResult(s.name, True, report, rate, elig, r5p, n5p, mrp)
            )

        # Confidence's isolated marginal: importance+confidence minus the same blend
        # with the confidence weight zeroed (sim_plus_importance) — holds sim/imp
        # weights fixed so the delta is the confidence term alone.
        ipc_r5, ipc_n5, _ = _headline(ipc_mean_rows or sip_rows)
        regime_results.append(
            RegimeResult(
                regime=regime.value,
                description=REGIME_DESCRIPTIONS[regime],
                strategies=strat_results,
                confidence_marginal_recall5=_paired(ipc_r5, sip_r5, seed=base_seed + ri + 3),
                confidence_marginal_ndcg5=_paired(ipc_n5, sip_n5, seed=base_seed + ri + 4),
            )
        )

    return ConfidenceStudyResult(
        experiment=experiment,
        retrieval_source=retrieval_source,
        semantic_available=semantic_available,
        n_queries=len(enriched),
        seeds_per_regime=seeds_per_regime,
        regimes=regime_results,
        notes=notes or [],
    )


# --- persistence + rendering ---------------------------------------------- #


def save_result(result: ConfidenceStudyResult, results_dir: Path | None = None) -> Path:
    directory = results_dir or RESULTS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{result.experiment}.json"
    path.write_text(json.dumps(asdict(result), indent=2, default=str))
    return path


def render_report(result: ConfidenceStudyResult) -> str:
    sem = "available" if result.semantic_available else "UNAVAILABLE"
    lines = [
        f"# {result.experiment} — Results",
        "",
        f"**Retrieval provider:** {result.retrieval_source}  ",
        f"**Semantic scores:** {sem}  ",
        f"**Queries:** {result.n_queries}  **Seeds/regime:** {result.seeds_per_regime}",
        "",
        "Δ columns are vs the `similarity_only` baseline (paired 95% bootstrap CI over "
        "queries). **CAR** = ContradictionAvoidanceRate (target outranks every obsolete "
        "contradictory memory), over eligible queries.",
    ]
    for rr in result.regimes:
        lines += [
            "",
            f"## Regime {rr.regime}",
            "",
            f"_{rr.description}_",
            "",
            "| strategy | recall@5 | Δ recall@5 (95% CI) | nDCG@5 | MRR | TgtFound@3 | CAR |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for s in rr.strategies:
            r = s.recall5
            lines.append(
                f"| `{s.strategy}` "
                f"| {s.report.recall[5]:.3f} "
                f"| {r.mean_delta:+.3f} [{r.ci_low:+.3f}, {r.ci_high:+.3f}] "
                f"| {s.report.ndcg[5]:.3f} "
                f"| {s.report.mrr:.3f} "
                f"| {s.report.target_found[3]:.3f} "
                f"| {s.contradiction_avoidance_rate:.3f} ({s.contradiction_eligible}q) |"
            )
        m = rr.confidence_marginal_recall5
        sign = "helps" if m.beats else ("hurts" if m.ci_high < 0 else "is neutral")
        lines.append(
            f"\nIsolated confidence marginal (`importance_plus_confidence` − "
            f"`sim_plus_importance`, confidence weight 0.10 vs 0): recall@5 "
            f"{m.mean_delta:+.3f} [{m.ci_low:+.3f}, {m.ci_high:+.3f}] → adding "
            f"confidence **{sign}** here."
        )

    if result.notes:
        lines += ["", "## Notes", ""] + [f"- {n}" for n in result.notes]
    return "\n".join(lines)
