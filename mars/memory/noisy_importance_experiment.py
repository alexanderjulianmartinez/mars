"""Noisy-importance study (Track 1) — how good must importance be to pay off?

Salience Memory v1 showed salience-weighted retrieval beating plain semantic
retrieval *given a clean importance oracle*. This experiment degrades the
importance signal across a range of qualities and measures how much of the win
survives, locating the **minimum importance-signal quality at which salience
still significantly beats similarity-only retrieval**.

Design:

- One real semantic retrieval per query is **materialized once** (the candidate
  pool with real similarity scores + true importance + gold labels) and cached,
  so the whole quality sweep runs offline and deterministically.
- The **baseline** arm is ``similarity_only``. It ignores importance, so it is
  invariant to corruption: one constant per-query metric vector, the line every
  noisy salience arm must clear.
- For each ``quality`` level the importance signal is corrupted (see
  :mod:`mars.memory.importance_noise`) and re-ranked with
  ``salience_weighted_v1``. Because a single corruption draw is high-variance on
  ~12-memory pools, each level averages over ``seeds_per_level`` independent
  noise seeds; the per-query metric is the across-seed mean.
- Significance at each level is a **paired** bootstrap over the 30 queries of
  ``salience(noisy) − similarity_only`` on the headline metrics (recall@5,
  nDCG@5, MRR), reusing Apollo's bootstrap.

This module is pure aggregation over a list of cached retrievals so it is
unit-testable with a fake source; the live wiring lives in
``experiments/run_noisy_importance.py``.
"""

from __future__ import annotations

import json
import random
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path

from mars.apollo.comparison import _bootstrap_ci
from mars.memory.expanded_experiment import ArmReport, K_VALUES, _evaluate, _rank
from mars.memory.importance_noise import corrupt_importance
from mars.memory.metrics import (
    context_efficiency,
    mrr,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    target_found,
)
from mars.memory.models import MemoryItem
from mars.memory.retrieval import SalienceWeightedStrategy, SimilarityOnlyStrategy

RESULTS_DIR = Path("mars-experiments")
#: Default quality grid — 100% (oracle) down to fully scrambled importance.
DEFAULT_QUALITIES = (1.0, 0.75, 0.5, 0.25, 0.0)


# --- cached retrieval snapshot -------------------------------------------- #


@dataclass
class CachedQuery:
    """A query's materialized candidate pool + gold (one real retrieval)."""

    query: str
    memories: list[MemoryItem]
    relevant_ids: set[str]
    target_id: str | None

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "target_id": self.target_id,
            "relevant_ids": sorted(self.relevant_ids),
            "memories": [
                {
                    "id": m.id,
                    "content": m.content,
                    "similarity": m.similarity,
                    "importance": m.importance,
                    "recency": m.recency,
                    "frequency": m.frequency,
                }
                for m in self.memories
            ],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CachedQuery":
        return cls(
            query=d["query"],
            target_id=d.get("target_id"),
            relevant_ids=set(d.get("relevant_ids", [])),
            memories=[
                MemoryItem(
                    id=m["id"],
                    content=m.get("content", ""),
                    similarity=float(m["similarity"]),
                    importance=float(m.get("importance", 0.0)),
                    recency=float(m.get("recency", 0.0)),
                    frequency=float(m.get("frequency", 0.0)),
                )
                for m in d.get("memories", [])
            ],
        )


def materialize(source, queries: list[str]) -> tuple[list[CachedQuery], bool, list[str]]:
    """Snapshot one retrieval per query from a live source.

    Returns ``(cached, semantic_available, notes)``. ``semantic_available`` is
    the AND over queries so the caller can refuse to claim a semantic result.
    """
    cached: list[CachedQuery] = []
    semantic = True
    notes: set[str] = set()
    for q in queries:
        r = source.fetch(q)
        semantic = semantic and r.semantic_available
        notes.update(r.notes)
        cached.append(
            CachedQuery(
                query=q,
                memories=list(r.memories),
                relevant_ids=set(r.relevant_ids),
                target_id=r.target_id,
            )
        )
    return cached, semantic, sorted(notes)


def save_cache(cached: list[CachedQuery], path: Path, *, semantic_available: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "semantic_available": semantic_available,
                "queries": [c.to_dict() for c in cached],
            },
            indent=2,
        )
    )


def load_cache(path: Path) -> tuple[list[CachedQuery], bool]:
    data = json.loads(path.read_text())
    cached = [CachedQuery.from_dict(d) for d in data.get("queries", [])]
    return cached, bool(data.get("semantic_available", False))


# --- metrics over one ranked pool ----------------------------------------- #


def _row_metrics(ranked: list[str], rel: set[str], tgt: str | None) -> dict:
    """Per-query metric row, same shape consumed by ``ArmReport`` via _evaluate."""
    return {
        "recall": {k: recall_at_k(ranked, rel, k) for k in K_VALUES},
        "precision": {k: precision_at_k(ranked, rel, k) for k in K_VALUES},
        "mrr": mrr(ranked, rel),
        "ndcg": {k: ndcg_at_k(ranked, rel, k) for k in (5, 10)},
        "target": {k: 1.0 if target_found(ranked, tgt, k) else 0.0 for k in (1, 3, 5)},
        "ce": {k: context_efficiency(ranked, rel, k) for k in (5, 10)},
    }


def _mean_rows(rows: list[dict]) -> dict:
    """Average a list of per-seed metric rows for one query into a single row."""

    def m(vals: list[float]) -> float:
        return statistics.fmean(vals)

    return {
        "recall": {k: m([r["recall"][k] for r in rows]) for k in K_VALUES},
        "precision": {k: m([r["precision"][k] for r in rows]) for k in K_VALUES},
        "mrr": m([r["mrr"] for r in rows]),
        "ndcg": {k: m([r["ndcg"][k] for r in rows]) for k in (5, 10)},
        "target": {k: m([r["target"][k] for r in rows]) for k in (1, 3, 5)},
        "ce": {k: m([r["ce"][k] for r in rows]) for k in (5, 10)},
    }


# --- result records -------------------------------------------------------- #


@dataclass
class Paired:
    """Paired comparison of a noisy salience arm against the baseline."""

    mean_delta: float
    ci_low: float
    ci_high: float
    wins: int
    ties: int
    losses: int
    beats: bool  # ci_low > 0


@dataclass
class NoiseLevel:
    quality: float
    salience: ArmReport
    recall5: Paired
    ndcg5: Paired
    mrr: Paired
    # across-seed spread of the aggregate (mean-over-queries) recall@5, a sanity
    # check that seeds_per_level is enough to average out corruption variance.
    seed_spread_recall5: float


@dataclass
class NoisyImportanceResult:
    experiment: str
    retrieval_source: str
    semantic_available: bool
    n_queries: int
    seeds_per_level: int
    qualities: list[float]
    baseline: ArmReport
    # Salience with the importance weight zeroed (also importance-invariant): the
    # honest floor for "what the salience blend buys with NO importance signal".
    # If a noisy level's metric ≈ this, that level's edge over the baseline is the
    # blend (similarity reweighting + recency), not the importance signal.
    ablated: ArmReport
    levels: list[NoiseLevel]
    min_quality_beating_baseline: float | None
    notes: list[str] = field(default_factory=list)


def _paired(noisy: list[float], base: list[float], *, seed: int) -> Paired:
    diffs = [a - b for a, b in zip(noisy, base)]
    lo, hi = _bootstrap_ci(diffs, seed=seed)
    wins = sum(1 for d in diffs if d > 1e-9)
    losses = sum(1 for d in diffs if d < -1e-9)
    ties = len(diffs) - wins - losses
    return Paired(
        mean_delta=round(statistics.fmean(diffs), 4) if diffs else 0.0,
        ci_low=round(lo, 4),
        ci_high=round(hi, 4),
        wins=wins,
        ties=ties,
        losses=losses,
        beats=lo > 0,
    )


def run_noisy_sweep(
    cached: list[CachedQuery],
    *,
    qualities: tuple[float, ...] = DEFAULT_QUALITIES,
    seeds_per_level: int = 25,
    base_seed: int = 1729,
    experiment: str = "salience-memory-noisy-importance",
    retrieval_source: str = "cortex-mcp",
    semantic_available: bool = True,
    notes: list[str] | None = None,
) -> NoisyImportanceResult:
    """Sweep importance quality over cached retrievals; compare to baseline."""
    baseline_strat = SimilarityOnlyStrategy()
    salience = SalienceWeightedStrategy()

    # Baseline: importance-invariant, computed once.
    base_rows = [
        _row_metrics(_rank(baseline_strat, c.memories), c.relevant_ids, c.target_id)
        for c in cached
    ]
    baseline_report = _evaluate("similarity_only", base_rows)
    base_r5 = [r["recall"][5] for r in base_rows]
    base_n5 = [r["ndcg"][5] for r in base_rows]
    base_mrr = [r["mrr"] for r in base_rows]

    # Importance-ablated salience (w_importance=0): the non-importance blend,
    # importance-invariant, so computed once. Quantifies how much of any noisy
    # level's edge is the blend rather than the importance signal.
    ablated_strat = SalienceWeightedStrategy(w_importance=0.0)
    ablated_report = _evaluate(
        "salience_no_importance",
        [_row_metrics(_rank(ablated_strat, c.memories), c.relevant_ids, c.target_id) for c in cached],
    )

    levels: list[NoiseLevel] = []
    for qi, q in enumerate(qualities):
        # accumulate per-query metric rows across seeds; track per-seed aggregate
        per_query_rows: list[list[dict]] = [[] for _ in cached]
        seed_agg_r5: list[float] = []
        for s in range(seeds_per_level):
            seed_r5: list[float] = []
            for ci, c in enumerate(cached):
                rng = random.Random(base_seed * 1_000_003 + qi * 9_176 + s * 31 + ci)
                noisy_mems = corrupt_importance(c.memories, q, rng)
                ranked = _rank(salience, noisy_mems)
                row = _row_metrics(ranked, c.relevant_ids, c.target_id)
                per_query_rows[ci].append(row)
                seed_r5.append(row["recall"][5])
            seed_agg_r5.append(statistics.fmean(seed_r5) if seed_r5 else 0.0)

        mean_rows = [_mean_rows(rows) for rows in per_query_rows]
        salience_report = _evaluate("salience_weighted_v1", mean_rows)
        noisy_r5 = [r["recall"][5] for r in mean_rows]
        noisy_n5 = [r["ndcg"][5] for r in mean_rows]
        noisy_mrr = [r["mrr"] for r in mean_rows]

        levels.append(
            NoiseLevel(
                quality=q,
                salience=salience_report,
                recall5=_paired(noisy_r5, base_r5, seed=base_seed + qi),
                ndcg5=_paired(noisy_n5, base_n5, seed=base_seed + qi + 1),
                mrr=_paired(noisy_mrr, base_mrr, seed=base_seed + qi + 2),
                seed_spread_recall5=round(
                    statistics.pstdev(seed_agg_r5) if len(seed_agg_r5) > 1 else 0.0, 4
                ),
            )
        )

    # Minimum quality where salience significantly beats baseline on recall@5
    # AND nDCG@5 (both headline coverage + ranking metrics clear zero).
    beating = [
        lvl.quality
        for lvl in levels
        if lvl.recall5.beats and lvl.ndcg5.beats
    ]
    min_quality = min(beating) if beating else None

    return NoisyImportanceResult(
        experiment=experiment,
        retrieval_source=retrieval_source,
        semantic_available=semantic_available,
        n_queries=len(cached),
        seeds_per_level=seeds_per_level,
        qualities=list(qualities),
        baseline=baseline_report,
        ablated=ablated_report,
        levels=levels,
        min_quality_beating_baseline=min_quality,
        notes=notes or [],
    )


# --- persistence + rendering ---------------------------------------------- #


def save_result(result: NoisyImportanceResult, results_dir: Path | None = None) -> Path:
    directory = results_dir or RESULTS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{result.experiment}.json"
    path.write_text(json.dumps(asdict(result), indent=2, default=str))
    return path


def render_report(result: NoisyImportanceResult) -> str:
    b, a = result.baseline, result.ablated
    sem = "available" if result.semantic_available else "UNAVAILABLE (embeddings disabled)"
    lines = [
        f"# {result.experiment} — Results",
        "",
        f"**Retrieval provider:** {result.retrieval_source}  ",
        f"**Semantic scores:** {sem}  ",
        f"**Queries:** {result.n_queries}  "
        f"**Noise seeds/level:** {result.seeds_per_level}",
        "",
        "Baseline (`similarity_only`, importance-invariant): "
        f"recall@5={b.recall[5]:.3f}, nDCG@5={b.ndcg[5]:.3f}, MRR={b.mrr:.3f}.",
        "Ablated floor (`salience_no_importance`, w_importance=0): "
        f"recall@5={a.recall[5]:.3f}, nDCG@5={a.ndcg[5]:.3f}, MRR={a.mrr:.3f} "
        "— the blend's value with NO importance signal; a noisy level at/below this "
        "owes its edge to the blend, not to importance.",
        "",
        "Salience (`salience_weighted_v1`) under degraded importance — Δ is vs the "
        "baseline above, with a paired 95% bootstrap CI over queries:",
        "",
        "| importance quality | recall@5 | Δ recall@5 (95% CI) | nDCG@5 | Δ nDCG@5 (95% CI) | MRR | Δ MRR (95% CI) | beats? |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for lvl in result.levels:
        r, n, m = lvl.recall5, lvl.ndcg5, lvl.mrr
        beats = "✓" if (r.beats and n.beats) else "—"
        lines.append(
            f"| {lvl.quality:.2f} "
            f"| {lvl.salience.recall[5]:.3f} "
            f"| {r.mean_delta:+.3f} [{r.ci_low:+.3f}, {r.ci_high:+.3f}] "
            f"| {lvl.salience.ndcg[5]:.3f} "
            f"| {n.mean_delta:+.3f} [{n.ci_low:+.3f}, {n.ci_high:+.3f}] "
            f"| {lvl.salience.mrr:.3f} "
            f"| {m.mean_delta:+.3f} [{m.ci_low:+.3f}, {m.ci_high:+.3f}] "
            f"| {beats} |"
        )

    mq = result.min_quality_beating_baseline
    lines += [
        "",
        (
            f"**Minimum importance quality that still beats semantic retrieval "
            f"(recall@5 *and* nDCG@5 CIs exclude zero): {mq:.2f}.**"
            if mq is not None
            else "**No tested importance quality significantly beats the baseline.**"
        ),
    ]
    if result.notes:
        lines += ["", "## Notes", ""] + [f"- {n}" for n in result.notes]
    return "\n".join(lines)
