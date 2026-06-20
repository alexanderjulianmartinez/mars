"""Expanded labeled benchmark corpus for Salience Memory v1 (discriminating set).

The original ``salience-memory-v1`` corpus is a smoke test: 4 queries / 13
memories / k=5, so recall@5 saturates at 1.0 for every strategy. This module
defines a richer schema and validator for a corpus large enough that retrieval
*coverage* (not just ranking) can be measured.

Schema differences from the v1 :mod:`mars.memory.corpus`:

- memories carry ``id`` (stable) plus ``importance``/``novelty``/``urgency``/
  ``confidence`` signals and a ``category`` label;
- gold relevance is explicit per query (``target_memories`` + ``relevant_memories``)
  rather than per-memory boolean flags;
- ~20 memories per query spanning six categories (target, relevant, distractor,
  stale, contradictory, low_confidence), so ``relevant_count`` can exceed ``k``.

This file is pure data + validation; seeding into real Cortex reuses the v1
:func:`mars.memory.corpus.seed_corpus` contract via :func:`to_seed_corpus`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import yaml

CORPUS_DIR = Path(__file__).resolve().parents[2] / "experiments" / "corpus"

#: Minimum memories per query for the benchmark to be non-trivial.
MIN_MEMORIES_PER_QUERY = 10


class Category(str, Enum):
    """Why a memory is in a query's candidate pool (drives gold + analysis)."""

    TARGET = "target"  # primary memory we want retrieved
    RELEVANT = "relevant"  # helpful support, not primary
    DISTRACTOR = "distractor"  # high overlap, not useful
    STALE = "stale"  # previously useful, now outdated
    CONTRADICTORY = "contradictory"  # conflicts with the truth
    LOW_CONFIDENCE = "low_confidence"  # possibly incorrect

    @property
    def is_relevant(self) -> bool:
        """Target + relevant-support count toward recall/precision gold."""
        return self in (Category.TARGET, Category.RELEVANT)


# Map an eval ``category`` to a Cortex memory ``type`` for seeding.
_CATEGORY_TO_CORTEX_TYPE = {
    Category.TARGET: "decision",
    Category.RELEVANT: "note",
    Category.DISTRACTOR: "note",
    Category.STALE: "observation",
    Category.CONTRADICTORY: "decision",
    Category.LOW_CONFIDENCE: "observation",
}


@dataclass
class ExpandedMemory:
    id: str
    content: str
    category: Category
    importance: float = 0.5
    novelty: float = 0.5
    urgency: float = 0.5
    confidence: float = 0.8

    @property
    def cortex_type(self) -> str:
        return _CATEGORY_TO_CORTEX_TYPE.get(self.category, "note")


@dataclass
class ExpandedQuery:
    query: str
    memories: list[ExpandedMemory]
    target_memories: list[str] = field(default_factory=list)
    relevant_memories: list[str] = field(default_factory=list)

    def category_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {c.value: 0 for c in Category}
        for m in self.memories:
            counts[m.category.value] += 1
        return counts


@dataclass
class ExpandedCorpus:
    name: str
    project: str
    queries: list[ExpandedQuery] = field(default_factory=list)

    @property
    def n_memories(self) -> int:
        return sum(len(q.memories) for q in self.queries)

    @property
    def n_queries(self) -> int:
        return len(self.queries)

    def query_texts(self) -> list[str]:
        return [q.query for q in self.queries]

    def category_counts(self) -> dict[str, int]:
        totals: dict[str, int] = {c.value: 0 for c in Category}
        for q in self.queries:
            for cat, n in q.category_counts().items():
                totals[cat] += n
        return totals


def _coerce_category(value: str) -> Category:
    try:
        return Category(value)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError(f"unknown memory category: {value!r}") from exc


def load_expanded_corpus(name: str, corpus_dir: Path | None = None) -> ExpandedCorpus:
    path = (corpus_dir or CORPUS_DIR) / f"{name}.corpus.yaml"
    data = yaml.safe_load(path.read_text())
    queries: list[ExpandedQuery] = []
    for q in data.get("queries", []):
        memories = [
            ExpandedMemory(
                id=m["id"],
                content=str(m["content"]).strip(),
                category=_coerce_category(m["category"]),
                importance=float(m.get("importance", 0.5)),
                novelty=float(m.get("novelty", 0.5)),
                urgency=float(m.get("urgency", 0.5)),
                confidence=float(m.get("confidence", 0.8)),
            )
            for m in q.get("memories", [])
        ]
        queries.append(
            ExpandedQuery(
                query=q["query"],
                memories=memories,
                target_memories=list(q.get("target_memories", [])),
                relevant_memories=list(q.get("relevant_memories", [])),
            )
        )
    return ExpandedCorpus(name=name, project=data.get("project", "mars"), queries=queries)


def validate_corpus(corpus: ExpandedCorpus) -> list[str]:
    """Return a list of validation errors; empty list means the corpus is valid.

    Fails when: a query has no target memories; memory ids are duplicated
    (globally); a query has fewer than ``MIN_MEMORIES_PER_QUERY`` memories; a
    query has no distractors; a query has no relevant memories; or a gold id does
    not resolve to a memory in that query.
    """
    errors: list[str] = []
    seen_ids: dict[str, str] = {}  # id -> first query it appeared in

    for q in corpus.queries:
        label = q.query[:60]
        ids = {m.id for m in q.memories}

        for m in q.memories:
            if m.id in seen_ids:
                errors.append(f"duplicate memory id {m.id!r} (also in {seen_ids[m.id]!r})")
            else:
                seen_ids[m.id] = label

        if len(q.memories) < MIN_MEMORIES_PER_QUERY:
            errors.append(
                f"query {label!r} has {len(q.memories)} memories "
                f"(< {MIN_MEMORIES_PER_QUERY})"
            )

        cats = {m.category for m in q.memories}
        if not q.target_memories:
            errors.append(f"query {label!r} has no target_memories")
        if Category.TARGET not in cats:
            errors.append(f"query {label!r} has no memory categorized 'target'")
        if Category.DISTRACTOR not in cats:
            errors.append(f"query {label!r} has no distractors")
        if not q.relevant_memories:
            errors.append(f"query {label!r} has no relevant_memories")

        for gid in q.target_memories + q.relevant_memories:
            if gid not in ids:
                errors.append(f"query {label!r} gold id {gid!r} is not among its memories")

    return errors


def gold_from_corpus(corpus: ExpandedCorpus) -> dict[str, dict]:
    """Build a gold map (``query -> {relevant: set, target: id}``) for metrics."""
    gold: dict[str, dict] = {}
    for q in corpus.queries:
        relevant = set(q.relevant_memories) | set(q.target_memories)
        gold[q.query] = {
            "relevant": relevant,
            "target": q.target_memories[0] if q.target_memories else None,
        }
    return gold


def seed_expanded_corpus(cortex, corpus: ExpandedCorpus):
    """Seed the expanded corpus into Cortex; capture gold + per-query pools.

    Cortex assigns a UUID per ``add_memory``, so gold/pools are keyed to the
    *assigned* ids (not the authored stable ids). Returns
    ``(gold_map, pools, key_to_id)`` where ``gold_map`` is
    ``query -> {relevant: set[uuid], target: uuid|None}`` and ``pools`` is
    ``query -> set[uuid]`` (the query's own candidate set for a controlled re-rank).

    ``cortex`` must expose ``add_memory(project, mem_type, content, importance,
    summary) -> id`` (the v1 contract).
    """
    key_to_id: dict[str, str] = {}
    for q in corpus.queries:
        for m in q.memories:
            key_to_id[m.id] = cortex.add_memory(
                corpus.project, m.cortex_type, m.content,
                importance=m.importance, summary=m.id,
            )
    gold_map, pools = build_gold_pools(corpus, key_to_id)
    return gold_map, pools, key_to_id


def build_gold_pools(corpus: ExpandedCorpus, key_to_id: dict[str, str]):
    """Build ``(gold_map, pools)`` from a corpus + authored-key→assigned-id map.

    Pure (no Cortex): lets a benchmark re-run reconstruct gold/pools from an
    already-seeded store without re-seeding. ``gold_map`` is
    ``query -> {relevant: set[id], target: id|None}``; ``pools`` is
    ``query -> set[id]``.
    """
    gold_map: dict[str, dict] = {}
    pools: dict[str, set[str]] = {}
    for q in corpus.queries:
        relevant: set[str] = set()
        target: str | None = None
        pool: set[str] = set()
        for m in q.memories:
            mid = key_to_id.get(m.id)
            if mid is None:
                continue
            pool.add(mid)
            if m.id in q.target_memories:
                relevant.add(mid)
                if target is None:
                    target = mid
            elif m.id in q.relevant_memories:
                relevant.add(mid)
        gold_map[q.query] = {"relevant": relevant, "target": target}
        pools[q.query] = pool
    return gold_map, pools
