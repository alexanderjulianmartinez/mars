"""Memory retrieval sources for Salience Memory v1 (Track B).

A retrieval source yields candidate memories (with signals) + gold labels for a
query. Two implementations:

- ``SyntheticRetrievalSource`` — the seeded synthetic store (no keys, default).
- ``CortexRetrievalSource`` — real Cortex via ``search_memory`` over MCP.

Both report whether **semantic** scores were available, so the experiment can
refuse to claim a semantic baseline when Cortex embeddings are disabled
(``semantic_score: null``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mars.memory.models import MemoryItem
from mars.memory.store import generate_case_memories


@dataclass
class Retrieved:
    memories: list[MemoryItem]
    relevant_ids: set[str]
    target_id: str | None
    semantic_available: bool
    source: str
    notes: list[str] = field(default_factory=list)


class SyntheticRetrievalSource:
    """Deterministic synthetic memories with built-in relevance labels."""

    name = "synthetic"

    def fetch(self, query_id: str) -> Retrieved:
        mems = generate_case_memories(query_id, trial=0)
        relevant = {m.id for m in mems if m.relevant}
        target = next((m.id for m in mems if m.relevant), None)
        # Synthetic memories carry a real similarity signal, so "semantic" is
        # available *within the simulation* (clearly labelled source=synthetic).
        return Retrieved(mems, relevant, target, semantic_available=True, source=self.name)


def semantic_available(memories) -> bool:
    """True only if at least one memory carries a non-null semantic score."""
    return any(getattr(m, "semantic_score", None) is not None for m in memories)


class CortexRetrievalSource:
    """Real Cortex retrieval via an MCP CortexProvider's ``search_memories``.

    Gold labels come from ``gold_map`` (local YAML for v1; Cortex-sourced later).
    Detects semantic availability from the returned ranking breakdown.
    """

    name = "cortex-mcp"

    def __init__(self, cortex, project: str, gold_map: dict[str, dict]) -> None:
        self._cortex = cortex
        self._project = project
        self._gold = gold_map  # query_id -> {"relevant": set[str], "target": str|None}

    def fetch(self, query_id: str) -> Retrieved:
        results = self._cortex.search_memories(self._project, query_id, limit=25)
        mems: list[MemoryItem] = []
        any_semantic = False
        for r in results:
            sem = r.get("semantic_score")
            any_semantic = any_semantic or (sem is not None)
            mems.append(
                MemoryItem(
                    id=str(r.get("id")),
                    content=r.get("content", ""),
                    similarity=float(sem if sem is not None else r.get("keyword_score", 0.0)),
                    importance=float(r.get("importance_score", 0.0)),
                    recency=float(r.get("recency_factor", 0.0)),
                    frequency=0.0,
                )
            )
        gold = self._gold.get(query_id, {})
        notes = []
        if not any_semantic:
            notes.append("Cortex returned semantic_score=null; similarity is keyword-based.")
        return Retrieved(
            memories=mems,
            relevant_ids=set(gold.get("relevant", set())),
            target_id=gold.get("target"),
            semantic_available=any_semantic,
            source=self.name,
            notes=notes,
        )
