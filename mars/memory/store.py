"""Deterministic synthetic memory generator for the salience experiment.

Generates a per-(case, trial) memory set with a known ground-truth relevant
subset. The construction deliberately includes:

  * "easy" relevant memories  — high similarity AND high salience
  * "hard" relevant memories  — LOW similarity but high importance/recency
                                (the long-horizon signal similarity-only misses)
  * "hard" distractors        — high similarity but low salience (similarity traps)

A similarity-only strategy is fooled by the traps and misses the hard relevant
memories; a salience-weighted strategy recovers them. This is what gives the
experiment a real, measurable effect to detect — and the same harness would
report "no difference" if the salience signals carried no information.
"""

from __future__ import annotations

import hashlib
import random

from mars.memory.models import MemoryItem


def _seed(case_id: str, trial: int) -> int:
    digest = hashlib.sha256(f"{case_id}:{trial}".encode()).hexdigest()
    return int(digest[:8], 16)


def generate_case_memories(
    case_id: str,
    trial: int = 0,
    *,
    n_memories: int = 24,
    n_relevant: int = 6,
) -> list[MemoryItem]:
    rng = random.Random(_seed(case_id, trial))
    memories: list[MemoryItem] = []
    easy_relevant = n_relevant // 2

    for i in range(n_relevant):
        if i < easy_relevant:
            similarity = rng.uniform(0.60, 0.90)  # easy: also similar
        else:
            similarity = rng.uniform(0.10, 0.40)  # hard: distant but important
        memories.append(
            MemoryItem(
                id=f"{case_id}-rel-{i}",
                content=f"relevant memory {i} for {case_id}",
                similarity=round(similarity, 4),
                importance=round(rng.uniform(0.60, 1.00), 4),
                recency=round(rng.uniform(0.50, 1.00), 4),
                frequency=round(rng.uniform(0.40, 1.00), 4),
                relevant=True,
            )
        )

    for j in range(n_memories - n_relevant):
        memories.append(
            MemoryItem(
                id=f"{case_id}-dis-{j}",
                content=f"distractor memory {j} for {case_id}",
                similarity=round(rng.uniform(0.35, 0.75), 4),  # similarity trap
                importance=round(rng.uniform(0.00, 0.40), 4),
                recency=round(rng.uniform(0.00, 0.50), 4),
                frequency=round(rng.uniform(0.00, 0.50), 4),
                relevant=False,
            )
        )

    rng.shuffle(memories)
    return memories
