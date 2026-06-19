"""Retrieval strategies — the experimental variable in the salience experiment.

A strategy maps a memory to a scalar score; ``retrieve`` ranks and takes top-k.
The baseline scores by similarity only; the experimental strategy blends
salience signals (importance, recency, frequency) with similarity.

New strategies are added by subclassing :class:`RetrievalStrategy`, never by
editing existing ones — the same extensibility rule as Mars scorers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from mars.memory.models import MemoryItem, RetrievalResult


def retrieval_quality(memories: list[MemoryItem], retrieved: list[MemoryItem], k: int) -> float:
    """Recall@k of the ground-truth relevant memories (0-1)."""
    total_relevant = sum(1 for m in memories if m.relevant)
    if total_relevant == 0:
        return 0.0
    hit = sum(1 for m in retrieved if m.relevant)
    return hit / min(k, total_relevant)


class RetrievalStrategy(ABC):
    """Ranks memories for a query. Subclasses implement :meth:`score`."""

    name: str = "strategy"

    @abstractmethod
    def score(self, memory: MemoryItem) -> float:
        """Return this strategy's ranking score for ``memory``."""

    def config(self) -> dict:
        """Reproducibility metadata describing the strategy's parameters."""
        return {"name": self.name}

    def retrieve(self, memories: list[MemoryItem], k: int) -> RetrievalResult:
        scored = sorted(memories, key=self.score, reverse=True)
        top = scored[:k]
        return RetrievalResult(
            ranked=top,
            quality=retrieval_quality(memories, top, k),
            scores=[round(self.score(m), 4) for m in top],
        )


class SimilarityOnlyStrategy(RetrievalStrategy):
    """Baseline: rank purely by semantic similarity."""

    name = "similarity-only"

    def score(self, memory: MemoryItem) -> float:
        return memory.similarity


class SalienceWeightedStrategy(RetrievalStrategy):
    """Experimental: weighted blend of similarity and salience signals.

    Weights are normalized, so any positive relative weights are valid. The
    defaults weight similarity highest but let importance/recency surface
    memories that similarity alone would miss (the long-horizon case).
    """

    name = "salience-weighted"

    def __init__(
        self,
        w_similarity: float = 0.40,
        w_importance: float = 0.30,
        w_recency: float = 0.20,
        w_frequency: float = 0.10,
    ) -> None:
        weights = [w_similarity, w_importance, w_recency, w_frequency]
        if any(w < 0 for w in weights):
            raise ValueError("weights must be non-negative")
        total = sum(weights) or 1.0
        self.w_similarity = w_similarity / total
        self.w_importance = w_importance / total
        self.w_recency = w_recency / total
        self.w_frequency = w_frequency / total

    def score(self, memory: MemoryItem) -> float:
        return (
            self.w_similarity * memory.similarity
            + self.w_importance * memory.importance
            + self.w_recency * memory.recency
            + self.w_frequency * memory.frequency
        )

    def config(self) -> dict:
        return {
            "name": self.name,
            "w_similarity": round(self.w_similarity, 4),
            "w_importance": round(self.w_importance, 4),
            "w_recency": round(self.w_recency, 4),
            "w_frequency": round(self.w_frequency, 4),
        }
