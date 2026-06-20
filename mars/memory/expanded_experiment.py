"""Run the expanded Salience Memory benchmark and collect the full metric suite.

Controlled comparison: for each query the *same* candidate pool (the query's own
authored memories, retrieved from Cortex with real semantic scores) is ranked by
two strategies — ``similarity_only`` (baseline) and ``salience_weighted_v1``
(candidate) — and scored on recall/precision @1/3/5/10, MRR, nDCG@5/10,
TargetFound@1/3/5, and context efficiency.

Pure aggregation over a retrieval *source* so it is unit-testable with a fake
source; the live wiring (seed Cortex → search → evaluate → write doc) lives in
``experiments/run_expanded_benchmark.py``.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path

from mars.memory.metrics import (
    context_efficiency,
    mrr,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    target_found,
)
from mars.memory.retrieval import SalienceWeightedStrategy, SimilarityOnlyStrategy

K_VALUES = (1, 3, 5, 10)
RESULTS_DIR = Path("mars-experiments")


@dataclass
class ArmReport:
    name: str
    recall: dict[int, float] = field(default_factory=dict)
    precision: dict[int, float] = field(default_factory=dict)
    mrr: float = 0.0
    ndcg: dict[int, float] = field(default_factory=dict)  # @5, @10
    target_found: dict[int, float] = field(default_factory=dict)  # @1, @3, @5
    context_efficiency: dict[int, float] = field(default_factory=dict)  # @5, @10


@dataclass
class BenchmarkResult:
    experiment: str
    retrieval_source: str
    execution_provider: str
    semantic_available: bool
    n_queries: int
    mean_relevant_per_query: float
    mean_pool_per_query: float
    baseline: ArmReport
    candidate: ArmReport
    notes: list[str] = field(default_factory=list)


def _rank(strategy, memories) -> list[str]:
    return [m.id for m in sorted(memories, key=strategy.score, reverse=True)]


def _evaluate(name: str, per_query: list[dict]) -> ArmReport:
    def mean(values: list[float]) -> float:
        return round(statistics.fmean(values), 4) if values else 0.0

    return ArmReport(
        name=name,
        recall={k: mean([r["recall"][k] for r in per_query]) for k in K_VALUES},
        precision={k: mean([r["precision"][k] for r in per_query]) for k in K_VALUES},
        mrr=mean([r["mrr"] for r in per_query]),
        ndcg={k: mean([r["ndcg"][k] for r in per_query]) for k in (5, 10)},
        target_found={k: mean([r["target"][k] for r in per_query]) for k in (1, 3, 5)},
        context_efficiency={k: mean([r["ce"][k] for r in per_query]) for k in (5, 10)},
    )


def run_benchmark(
    source,
    queries: list[str],
    *,
    experiment: str = "salience-memory-v1-expanded",
    execution: str = "mock",
) -> BenchmarkResult:
    baseline, candidate = SimilarityOnlyStrategy(), SalienceWeightedStrategy()
    rows = {"baseline": [], "candidate": []}
    semantic = True
    notes: set[str] = set()
    rel_counts, pool_counts = [], []

    for q in queries:
        retrieved = source.fetch(q)
        semantic = semantic and retrieved.semantic_available
        notes.update(retrieved.notes)
        rel_counts.append(len(retrieved.relevant_ids))
        pool_counts.append(len(retrieved.memories))
        for arm, strat in (("baseline", baseline), ("candidate", candidate)):
            ranked = _rank(strat, retrieved.memories)
            rel, tgt = retrieved.relevant_ids, retrieved.target_id
            rows[arm].append({
                "recall": {k: recall_at_k(ranked, rel, k) for k in K_VALUES},
                "precision": {k: precision_at_k(ranked, rel, k) for k in K_VALUES},
                "mrr": mrr(ranked, rel),
                "ndcg": {k: ndcg_at_k(ranked, rel, k) for k in (5, 10)},
                "target": {k: 1.0 if target_found(ranked, tgt, k) else 0.0 for k in (1, 3, 5)},
                "ce": {k: context_efficiency(ranked, rel, k) for k in (5, 10)},
            })

    return BenchmarkResult(
        experiment=experiment,
        retrieval_source=getattr(source, "name", "unknown"),
        execution_provider=execution,
        semantic_available=semantic,
        n_queries=len(queries),
        mean_relevant_per_query=round(statistics.fmean(rel_counts), 2) if rel_counts else 0.0,
        mean_pool_per_query=round(statistics.fmean(pool_counts), 2) if pool_counts else 0.0,
        baseline=_evaluate("similarity_only", rows["baseline"]),
        candidate=_evaluate("salience_weighted_v1", rows["candidate"]),
        notes=sorted(notes),
    )


# --- persistence + rendering ---------------------------------------------- #


def save_result(result: BenchmarkResult, results_dir: Path | None = None) -> Path:
    directory = results_dir or RESULTS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{result.experiment}.json"
    path.write_text(json.dumps(asdict(result), indent=2, default=str))
    return path


def _row(label: str, b: float, c: float) -> str:
    return f"| {label} | {b:.3f} | {c:.3f} | {c - b:+.3f} |"


def render_report(result: BenchmarkResult) -> str:
    b, c = result.baseline, result.candidate
    sem = "available" if result.semantic_available else "UNAVAILABLE (embeddings disabled)"
    lines = [
        f"# {result.experiment} — Results",
        "",
        f"**Retrieval provider:** {result.retrieval_source}  ",
        f"**Execution provider:** {result.execution_provider}  ",
        f"**Semantic scores:** {sem}  ",
        f"**Queries:** {result.n_queries}  "
        f"**Mean relevant/query:** {result.mean_relevant_per_query}  "
        f"**Mean candidate pool/query:** {result.mean_pool_per_query}",
        "",
        "| Metric | baseline (similarity_only) | candidate (salience_weighted_v1) | Δ |",
        "| --- | --- | --- | --- |",
    ]
    for k in K_VALUES:
        lines.append(_row(f"recall@{k}", b.recall[k], c.recall[k]))
    for k in K_VALUES:
        lines.append(_row(f"precision@{k}", b.precision[k], c.precision[k]))
    lines.append(_row("MRR", b.mrr, c.mrr))
    for k in (5, 10):
        lines.append(_row(f"nDCG@{k}", b.ndcg[k], c.ndcg[k]))
    for k in (1, 3, 5):
        lines.append(_row(f"TargetFound@{k}", b.target_found[k], c.target_found[k]))
    for k in (5, 10):
        lines.append(_row(f"ContextEfficiency@{k}", b.context_efficiency[k], c.context_efficiency[k]))

    if result.notes:
        lines += ["", "## Notes", ""] + [f"- {n}" for n in result.notes]
    return "\n".join(lines)
