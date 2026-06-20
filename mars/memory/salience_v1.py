"""Salience Memory v1 experiment (Track B).

Compares the **baseline** ``similarity_only`` retrieval strategy against the
**candidate** ``salience_weighted`` strategy over a set of queries, judged purely
on retrieval metrics against gold labels. Execution is mocked/irrelevant here —
the variable under test is retrieval, not agent implementation.

Honesty rule (hard constraint): if the retrieval source can't provide semantic
scores (Cortex embeddings disabled → ``semantic_score: null``), the result is
flagged and the report must not claim semantic-vs-salience evidence.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

from mars.memory.metrics import (
    context_efficiency,
    mrr,
    precision_at_k,
    recall_at_k,
    target_found,
)
from mars.memory.retrieval import SalienceWeightedStrategy, SimilarityOnlyStrategy
from mars.memory.retrieval_source import SyntheticRetrievalSource

DEFAULT_QUERIES = [
    "migration-note-task",
    "backend-api-task",
    "infra-debug-task",
    "refactor-task",
    "auth-bug-task",
    "schema-change-task",
]

RESULTS_DIR = Path("mars-experiments")
EXPERIMENTS_DIR = Path(__file__).resolve().parents[2] / "experiments"


class SemanticUnavailableError(RuntimeError):
    """Raised in --strict-semantic mode when semantic scores are unavailable."""


@dataclass
class ExperimentSpec:
    """A retrieval experiment definition loaded from YAML."""

    id: str
    hypothesis: str
    methodology: str
    k: int
    queries: list[str]
    # query_id -> {"relevant": set[str], "target": str|None}  (gold labels)
    gold_map: dict[str, dict] = field(default_factory=dict)
    baseline_strategy: str = "similarity_only"
    candidate_strategy: str = "salience_weighted_v1"


def load_experiment_spec(name: str, experiments_dir: Path | None = None) -> ExperimentSpec:
    """Load ``experiments/<name>.yaml``; gold labels may be inline per query."""
    path = (experiments_dir or EXPERIMENTS_DIR) / f"{name}.yaml"
    data = yaml.safe_load(path.read_text())
    queries: list[str] = []
    gold_map: dict[str, dict] = {}
    for q in data.get("queries", []):
        if isinstance(q, str):
            queries.append(q)
            continue
        qid = q["id"]
        queries.append(qid)
        labels = q.get("gold", []) or []
        relevant = {g["memory_id"] for g in labels if g.get("relevant", True)}
        target = next((g["memory_id"] for g in labels if g.get("target")), None)
        if relevant or target:
            gold_map[qid] = {"relevant": relevant, "target": target}
    return ExperimentSpec(
        id=data["id"],
        hypothesis=data.get("hypothesis", "").strip(),
        methodology=data.get("methodology", "").strip(),
        k=int(data.get("k", 5)),
        queries=queries or DEFAULT_QUERIES,
        gold_map=gold_map,
        baseline_strategy=(data.get("baseline") or {}).get("strategy", "similarity_only"),
        candidate_strategy=(data.get("candidate") or {}).get("strategy", "salience_weighted_v1"),
    )


@dataclass
class ArmMetrics:
    name: str
    recall_at_k: float
    precision_at_k: float
    mrr: float
    target_rate: float
    context_efficiency: float


@dataclass
class SalienceV1Result:
    experiment: str
    retrieval_source: str
    execution_provider: str
    semantic_available: bool
    k: int
    n_queries: int
    baseline: ArmMetrics
    candidate: ArmMetrics
    limitation: str | None = None
    notes: list[str] = field(default_factory=list)
    hypothesis: str = ""
    methodology: str = ""


def _rank(strategy, memories) -> list[str]:
    return [m.id for m in sorted(memories, key=strategy.score, reverse=True)]


def _aggregate(name: str, rows: list[dict]) -> ArmMetrics:
    def mean(key: str) -> float:
        return round(statistics.fmean(r[key] for r in rows), 4) if rows else 0.0

    return ArmMetrics(
        name=name,
        recall_at_k=mean("recall"),
        precision_at_k=mean("precision"),
        mrr=mean("mrr"),
        target_rate=mean("target"),
        context_efficiency=mean("ce"),
    )


def run_salience_memory_v1(
    source=None,
    query_ids: list[str] | None = None,
    *,
    k: int = 5,
    strict_semantic: bool = False,
    execution: str = "mock",
    spec: ExperimentSpec | None = None,
) -> SalienceV1Result:
    source = source or SyntheticRetrievalSource()
    if spec is not None:
        query_ids = query_ids or spec.queries
        k = spec.k
    query_ids = query_ids or DEFAULT_QUERIES
    baseline = SimilarityOnlyStrategy()
    candidate = SalienceWeightedStrategy()

    rows = {"baseline": [], "candidate": []}
    semantic = True
    notes: set[str] = set()

    for qid in query_ids:
        retrieved = source.fetch(qid)
        semantic = semantic and retrieved.semantic_available
        notes.update(retrieved.notes)
        for arm, strat in (("baseline", baseline), ("candidate", candidate)):
            ranked = _rank(strat, retrieved.memories)
            rows[arm].append(
                {
                    "recall": recall_at_k(ranked, retrieved.relevant_ids, k),
                    "precision": precision_at_k(ranked, retrieved.relevant_ids, k),
                    "mrr": mrr(ranked, retrieved.relevant_ids),
                    "target": 1.0 if target_found(ranked, retrieved.target_id, k) else 0.0,
                    "ce": context_efficiency(ranked, retrieved.relevant_ids, k),
                }
            )

    if strict_semantic and not semantic:
        raise SemanticUnavailableError(
            "semantic scores unavailable (Cortex embeddings disabled) and --strict-semantic set"
        )

    limitation = None
    if not semantic:
        limitation = (
            "Baseline semantic retrieval unavailable because Cortex embeddings are disabled. "
            "Current run used keyword/ranking fallback and should not be treated as "
            "semantic-vs-salience evidence."
        )

    return SalienceV1Result(
        experiment="salience-memory-v1",
        retrieval_source=source.name,
        execution_provider=execution,
        semantic_available=semantic,
        k=k,
        n_queries=len(query_ids),
        baseline=_aggregate(spec.baseline_strategy if spec else "similarity_only", rows["baseline"]),
        candidate=_aggregate(spec.candidate_strategy if spec else "salience_weighted_v1", rows["candidate"]),
        limitation=limitation,
        notes=sorted(notes),
        hypothesis=spec.hypothesis if spec else "",
        methodology=spec.methodology if spec else "",
    )


# --- persistence + rendering ---------------------------------------------- #


def save_result(result: SalienceV1Result, results_dir: Path | None = None) -> Path:
    directory = results_dir or RESULTS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{result.experiment}.json"
    path.write_text(json.dumps(asdict(result), indent=2))
    return path


def load_result(name: str, results_dir: Path | None = None) -> SalienceV1Result | None:
    path = (results_dir or RESULTS_DIR) / f"{name}.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text())
    data["baseline"] = ArmMetrics(**data["baseline"])
    data["candidate"] = ArmMetrics(**data["candidate"])
    return SalienceV1Result(**data)


def render_retrieval_report(result: SalienceV1Result) -> str:
    sem = "available" if result.semantic_available else "UNAVAILABLE (embeddings disabled)"
    b, c = result.baseline, result.candidate
    lines = [
        "# Retrieval Experiment Report",
        "",
        f"**Experiment:** {result.experiment}",
        f"**Retrieval provider:** {result.retrieval_source}",
        f"**Execution provider:** {result.execution_provider}",
        f"**Semantic scores:** {sem}",
        f"**Queries:** {result.n_queries}  **k:** {result.k}",
    ]
    if result.hypothesis:
        lines += ["", "## Hypothesis", "", result.hypothesis]
    if result.methodology:
        lines += ["", "## Methodology", "", result.methodology]

    lines += [
        "",
        "## Metrics",
        "",
        f"| Metric | baseline ({b.name}) | candidate ({c.name}) | Δ (cand − base) |",
        "| --- | --- | --- | --- |",
    ]
    for label, attr in [
        ("recall@k", "recall_at_k"),
        ("precision@k", "precision_at_k"),
        ("MRR", "mrr"),
        ("target found rate", "target_rate"),
        ("context efficiency", "context_efficiency"),
    ]:
        bv, cv = getattr(b, attr), getattr(c, attr)
        lines.append(f"| {label} | {bv:.3f} | {cv:.3f} | {cv - bv:+.3f} |")

    lines += ["", "## Limitations", ""]
    if result.limitation:
        lines.append(f"⚠️ {result.limitation}")
    else:
        lines.append("None noted.")
    for n in result.notes:
        lines.append(f"- {n}")

    delta = round(c.recall_at_k - b.recall_at_k, 3)
    lines += ["", "## Recommendation", ""]
    if not result.semantic_available:
        lines.append(
            "Retrieval recall improved with salience weighting on this corpus, but because "
            "semantic scores were unavailable this is a keyword-fallback result, not "
            "semantic-vs-salience evidence. Enable Cortex embeddings (Voyage) to make it semantic."
        )
    else:
        verdict = "outperforms" if delta > 0 else "does not outperform"
        lines.append(
            f"salience_weighted_v1 {verdict} similarity_only on recall@{result.k} "
            f"(Δ {delta:+.3f}) over {result.n_queries} queries (source={result.retrieval_source})."
        )
    return "\n".join(lines)
