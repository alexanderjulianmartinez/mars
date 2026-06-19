"""Memory retrieval strategies for Apollo experiments.

Cortex owns memory; Mars only *measures* retrieval strategies. This module
models the retrieval scoring so an experiment can compare a baseline
(similarity-only) against an experimental strategy (salience-weighted) and
quantify the difference in retrieval quality.

The synthetic memory store here is experiment scaffolding for the mock path; a
real run sources memories from Cortex over MCP.
"""

from mars.memory.models import MemoryItem, RetrievalResult
from mars.memory.retrieval import (
    RetrievalStrategy,
    SalienceWeightedStrategy,
    SimilarityOnlyStrategy,
    retrieval_quality,
)
from mars.memory.store import generate_case_memories

__all__ = [
    "MemoryItem",
    "RetrievalResult",
    "RetrievalStrategy",
    "SimilarityOnlyStrategy",
    "SalienceWeightedStrategy",
    "retrieval_quality",
    "generate_case_memories",
]
