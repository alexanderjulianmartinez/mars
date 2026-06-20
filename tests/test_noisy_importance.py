"""Track 1 noisy-importance study: noise model + sweep behaviour."""

from __future__ import annotations

import random

from mars.memory.importance_noise import corrupt_importance, n_corrupted
from mars.memory.models import MemoryItem
from mars.memory.noisy_importance_experiment import (
    CachedQuery,
    materialize,
    run_noisy_sweep,
)
from mars.memory.retrieval_source import Retrieved


def _mems(importances: list[float], sims: list[float]) -> list[MemoryItem]:
    return [
        MemoryItem(id=f"m{i}", content="", similarity=s, importance=imp)
        for i, (imp, s) in enumerate(zip(importances, sims))
    ]


# --- noise model ----------------------------------------------------------- #


def test_quality_one_is_identity():
    mems = _mems([0.1, 0.9, 0.5, 0.2], [0.3, 0.4, 0.5, 0.6])
    out = corrupt_importance(mems, 1.0, random.Random(0))
    assert [m.importance for m in out] == [0.1, 0.9, 0.5, 0.2]


def test_corruption_preserves_importance_multiset():
    # Shuffle model: the *set* of importance values is preserved, only the
    # assignment changes. True at every quality level.
    imps = [0.05, 0.95, 0.4, 0.6, 0.1, 0.8]
    mems = _mems(imps, [0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
    for q in (0.0, 0.25, 0.5, 0.75):
        out = corrupt_importance(mems, q, random.Random(7))
        assert sorted(m.importance for m in out) == sorted(imps)


def test_quality_zero_scrambles_signal():
    # With a perfectly importance-sorted pool, full scramble should move things.
    imps = [i / 10 for i in range(10)]
    mems = _mems(imps, [0.5] * 10)
    out = corrupt_importance(mems, 0.0, random.Random(3))
    assert [m.importance for m in out] != imps


def test_corruption_is_deterministic():
    mems = _mems([0.1, 0.9, 0.5, 0.2, 0.7], [0.3, 0.4, 0.5, 0.6, 0.7])
    a = corrupt_importance(mems, 0.5, random.Random(42))
    b = corrupt_importance(mems, 0.5, random.Random(42))
    assert [m.importance for m in a] == [m.importance for m in b]


def test_corruption_does_not_mutate_input():
    mems = _mems([0.1, 0.9, 0.5, 0.2], [0.3, 0.4, 0.5, 0.6])
    before = [m.importance for m in mems]
    corrupt_importance(mems, 0.0, random.Random(1))
    assert [m.importance for m in mems] == before


def test_n_corrupted_edges():
    assert n_corrupted(12, 1.0) == 0  # oracle
    assert n_corrupted(1, 0.0) == 0  # singleton can't permute
    assert n_corrupted(12, 0.0) == 12  # full scramble
    assert n_corrupted(12, 0.75) == 3
    assert n_corrupted(12, 0.5) == 6


# --- sweep ----------------------------------------------------------------- #


def _adversarial_corpus(n_queries: int = 12) -> list[CachedQuery]:
    """Importance perfectly predicts relevance; similarity is adversarial.

    Each query has 2 relevant memories (high importance, *low* similarity) and 8
    distractors (low importance, *high* similarity). similarity_only therefore
    buries the relevant memories; salience with good importance recovers them.
    This mirrors the real expanded-corpus mechanism in miniature.
    """
    cached: list[CachedQuery] = []
    for qi in range(n_queries):
        mems: list[MemoryItem] = []
        relevant = set()
        for j in range(2):  # relevant: high importance, low similarity
            mid = f"q{qi}-rel{j}"
            mems.append(MemoryItem(id=mid, content="", similarity=0.2 + 0.01 * j,
                                   importance=0.9 - 0.05 * j))
            relevant.add(mid)
        for j in range(8):  # distractors: low importance, high similarity
            mems.append(MemoryItem(id=f"q{qi}-dis{j}", content="",
                                   similarity=0.7 + 0.01 * j, importance=0.05 + 0.005 * j))
        cached.append(CachedQuery(query=f"q{qi}", memories=mems,
                                  relevant_ids=relevant, target_id=f"q{qi}-rel0"))
    return cached


def test_oracle_beats_baseline_noise_erodes_it():
    cached = _adversarial_corpus()
    res = run_noisy_sweep(cached, qualities=(1.0, 0.0), seeds_per_level=15)

    oracle = next(l for l in res.levels if l.quality == 1.0)
    scrambled = next(l for l in res.levels if l.quality == 0.0)

    # Oracle importance recovers the buried relevant memories; baseline cannot.
    assert oracle.recall5.beats
    assert oracle.salience.recall[5] > res.baseline.recall[5]
    # Scrambling importance erodes the advantage.
    assert scrambled.salience.recall[5] < oracle.salience.recall[5]


def test_baseline_is_importance_invariant():
    cached = _adversarial_corpus()
    a = run_noisy_sweep(cached, qualities=(1.0,), seeds_per_level=3)
    b = run_noisy_sweep(cached, qualities=(0.0,), seeds_per_level=3)
    # Baseline ignores importance, so it is identical regardless of corruption.
    assert a.baseline.recall == b.baseline.recall
    assert a.baseline.ndcg == b.baseline.ndcg


def test_importance_signal_contributes_oracle_over_scrambled():
    # The honest measure of the importance *signal* is oracle (q=1) vs scrambled
    # (q=0): same blend, differing only in whether importance points at the right
    # memory. Oracle must clear scrambled by a wide margin.
    cached = _adversarial_corpus()
    res = run_noisy_sweep(cached, qualities=(1.0, 0.0), seeds_per_level=20)
    oracle = next(l for l in res.levels if l.quality == 1.0).salience.recall[5]
    scrambled = next(l for l in res.levels if l.quality == 0.0).salience.recall[5]
    assert oracle > scrambled + 0.2


def test_ablated_floor_is_importance_invariant():
    # The ablated arm zeroes the importance weight, so corrupting importance
    # cannot change it; it is reported once regardless of the quality grid.
    cached = _adversarial_corpus()
    a = run_noisy_sweep(cached, qualities=(1.0,), seeds_per_level=2)
    b = run_noisy_sweep(cached, qualities=(0.0,), seeds_per_level=2)
    assert a.ablated.recall == b.ablated.recall
    assert a.ablated.ndcg == b.ablated.ndcg


def test_min_quality_is_reported_when_some_level_beats():
    cached = _adversarial_corpus()
    res = run_noisy_sweep(cached, qualities=(1.0, 0.75, 0.5, 0.25, 0.0),
                          seeds_per_level=20)
    # At least the oracle beats, so a threshold exists and is one of the grid points.
    assert res.min_quality_beating_baseline in set(res.qualities)
    # Monotonicity: every level at/above the threshold also beats.
    thr = res.min_quality_beating_baseline
    for lvl in res.levels:
        if lvl.quality >= thr:
            assert lvl.recall5.beats and lvl.ndcg5.beats


def test_determinism_of_sweep():
    cached = _adversarial_corpus()
    a = run_noisy_sweep(cached, qualities=(0.5,), seeds_per_level=10)
    b = run_noisy_sweep(cached, qualities=(0.5,), seeds_per_level=10)
    la, lb = a.levels[0], b.levels[0]
    assert la.salience.recall == lb.salience.recall
    assert la.recall5.mean_delta == lb.recall5.mean_delta


# --- cache + materialize --------------------------------------------------- #


def test_cache_roundtrip():
    cached = _adversarial_corpus(3)
    restored = [CachedQuery.from_dict(c.to_dict()) for c in cached]
    for c, r in zip(cached, restored):
        assert r.query == c.query
        assert r.relevant_ids == c.relevant_ids
        assert r.target_id == c.target_id
        assert [m.id for m in r.memories] == [m.id for m in c.memories]
        assert [m.similarity for m in r.memories] == [m.similarity for m in c.memories]


class _FakeSource:
    name = "fake"

    def __init__(self, cached: list[CachedQuery], semantic: bool):
        self._by_q = {c.query: c for c in cached}
        self._semantic = semantic

    def fetch(self, query: str) -> Retrieved:
        c = self._by_q[query]
        return Retrieved(
            memories=c.memories, relevant_ids=c.relevant_ids, target_id=c.target_id,
            semantic_available=self._semantic, source=self.name,
            notes=[] if self._semantic else ["semantic null"],
        )


def test_materialize_tracks_semantic_availability():
    cached = _adversarial_corpus(3)
    queries = [c.query for c in cached]

    snap, semantic, _ = materialize(_FakeSource(cached, True), queries)
    assert semantic and len(snap) == 3

    _, semantic_off, notes = materialize(_FakeSource(cached, False), queries)
    assert not semantic_off and notes
