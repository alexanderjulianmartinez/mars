"""Retrieval-only metrics for the Salience Memory experiment (Track B).

Pure functions over a ranked list of memory ids and a gold set, kept separate
from agent/task metrics so a retrieval experiment can be judged on retrieval
quality alone.
"""

from __future__ import annotations

from math import log2


def recall_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    hits = sum(1 for i in ranked_ids[:k] if i in relevant_ids)
    return hits / min(k, len(relevant_ids))


def precision_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if k <= 0:
        return 0.0
    hits = sum(1 for i in ranked_ids[:k] if i in relevant_ids)
    return hits / k


def mrr(ranked_ids: list[str], relevant_ids: set[str]) -> float:
    for rank, i in enumerate(ranked_ids, start=1):
        if i in relevant_ids:
            return 1.0 / rank
    return 0.0


def target_found(ranked_ids: list[str], target_id: str | None, k: int) -> bool:
    return target_id is not None and target_id in ranked_ids[:k]


def context_efficiency(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """Fraction of the retrieved context budget that is actually relevant."""
    top = ranked_ids[:k]
    if not top:
        return 0.0
    return sum(1 for i in top if i in relevant_ids) / len(top)


def ndcg_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """Normalized discounted cumulative gain @k with binary relevance.

    Rewards placing relevant memories higher in the ranking. DCG sums
    ``1 / log2(rank + 1)`` over relevant hits in the top-k; the ideal DCG packs
    all relevant items into the top positions. Returns 0 when nothing is relevant.
    """
    if not relevant_ids or k <= 0:
        return 0.0
    dcg = sum(
        1.0 / log2(rank + 1)
        for rank, i in enumerate(ranked_ids[:k], start=1)
        if i in relevant_ids
    )
    ideal_hits = min(len(relevant_ids), k)
    idcg = sum(1.0 / log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg if idcg else 0.0
