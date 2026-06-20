"""Importance-signal corruption for the noisy-importance study (Track 1).

The Salience Memory v1 result was obtained with importance as a *clean oracle*:
relevant memories carried high importance and distractors low, by construction.
That makes the measured effect an **upper bound**. This module degrades the
importance signal to a controllable *quality* so the experiment can ask the
production-relevant question: **how good does Cortex's importance estimate need
to be for salience weighting to still beat plain semantic retrieval?**

Noise model — ``quality`` ∈ [0, 1]:

- ``quality == 1.0`` → importance is returned untouched (the oracle / v1 case).
- ``0 < quality < 1`` → a fraction ``1 - quality`` of a query's memories are
  *corrupted*: their importance **values are randomly permuted among themselves**.
  The remaining fraction keep their true importance.
- ``quality == 0.0`` → every memory's importance is permuted (the signal is
  scrambled — importance no longer points at the right memory).

A **shuffle** (permutation) model is used rather than additive noise or uniform
replacement so the *distribution* of importance values in the pool is preserved
exactly — only the **assignment** of importance to memories degrades. This
isolates "is importance attached to the right memory?" (the signal-quality
question) from "what does the importance histogram look like?", and keeps the
0.30 importance weight in :class:`SalienceWeightedStrategy` calibrated across all
quality levels.

Corruption is applied *post-retrieval* on the candidate pool. This is faithful to
re-seeding Cortex with corrupted importance labels because importance affects
neither the embeddings nor which memories the similarity search returns (the pool
is fixed); it only feeds the salience ranking. So this avoids re-embedding all
552 memories once per noise level while measuring exactly the same thing.
"""

from __future__ import annotations

import random
from dataclasses import replace

from mars.memory.models import MemoryItem


def n_corrupted(pool_size: int, quality: float) -> int:
    """How many of ``pool_size`` memories get their importance permuted."""
    q = max(0.0, min(1.0, quality))
    if q >= 1.0 or pool_size <= 1:
        return 0
    n = round((1.0 - q) * pool_size)
    # A single corrupted index cannot be permuted (it would map to itself), so it
    # carries no degradation; require at least 2 for the shuffle to bite.
    return n if n >= 2 else 0


def corrupt_importance(
    memories: list[MemoryItem], quality: float, rng: random.Random
) -> list[MemoryItem]:
    """Return copies of ``memories`` with importance degraded to ``quality``.

    Pure (does not mutate the inputs); ``rng`` makes the corruption reproducible.
    See the module docstring for the noise model. The order of the returned list
    matches the input.
    """
    n = len(memories)
    k = n_corrupted(n, quality)
    if k == 0:
        return [replace(m) for m in memories]

    idx = list(range(n))
    rng.shuffle(idx)
    corrupt_idx = idx[:k]

    # Permute the importance values among the corrupted subset. Re-draw until the
    # permutation is a derangement-ish shuffle (at least one value actually moves)
    # so a tiny subset can't no-op; for k>=2 a single reshuffle almost always
    # moves something, and we keep it simple/deterministic with one extra retry.
    values = [memories[i].importance for i in corrupt_idx]
    shuffled = values[:]
    rng.shuffle(shuffled)
    if k >= 2 and shuffled == values:
        rng.shuffle(shuffled)

    new_importance = {i: v for i, v in zip(corrupt_idx, shuffled)}
    return [
        replace(m, importance=new_importance.get(i, m.importance))
        for i, m in enumerate(memories)
    ]
