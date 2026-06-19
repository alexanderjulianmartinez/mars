"""Memory data structures used by retrieval strategies.

These are lightweight dataclasses (internal experiment data, not part of the
persisted domain model). In a real run the signal values come from Cortex; here
they are generated synthetically and deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MemoryItem:
    """A candidate memory with its retrieval signals.

    ``relevant`` is ground truth — whether this memory actually helps the task.
    It is known only to the experiment harness (and to Cortex's gold labels);
    retrieval strategies never see it. It exists so we can measure retrieval
    quality.
    """

    id: str
    content: str
    similarity: float  # semantic similarity to the query, 0-1
    recency: float = 0.0  # 1 = just written, 0 = old
    importance: float = 0.0  # salience / importance signal, 0-1
    frequency: float = 0.0  # normalized access frequency, 0-1
    relevant: bool = False  # ground-truth: does this memory help the task?


@dataclass
class RetrievalResult:
    """Outcome of ranking a memory set with a strategy."""

    ranked: list[MemoryItem]
    quality: float  # 0-1, recall@k of the relevant items
    scores: list[float] = field(default_factory=list)
