"""Experiment 3 — Temporal Salience: regimes, scoring, strategies, report, schema."""

from __future__ import annotations

import json
import random
from dataclasses import asdict
from math import exp

from mars.memory.models import MemoryItem
from mars.memory.noisy_importance_experiment import CachedQuery
from mars.memory.temporal_salience import (
    ImportancePlusDecayStrategy,
    Regime,
    RecencyOnlyStrategy,
    apply_regime,
    assign_age,
    decay_score,
    normalized_recency,
    render_report,
    run_temporal_study,
    save_result,
)


# --- timestamp regime generation ------------------------------------------ #


def test_uniform_regime_gives_constant_age():
    rng = random.Random(0)
    ages = [assign_age(rel, Regime.UNIFORM, rng) for rel in (True, False, True)]
    assert len(set(ages)) == 1  # no temporal signal


def test_aligned_regime_makes_relevant_newer():
    rng = random.Random(1)
    relevant_ages = [assign_age(True, Regime.ALIGNED, rng) for _ in range(20)]
    other_ages = [assign_age(False, Regime.ALIGNED, rng) for _ in range(20)]
    assert max(relevant_ages) < min(other_ages)  # relevant strictly newer


def test_misaligned_regime_makes_relevant_older():
    rng = random.Random(2)
    relevant_ages = [assign_age(True, Regime.MISALIGNED, rng) for _ in range(20)]
    other_ages = [assign_age(False, Regime.MISALIGNED, rng) for _ in range(20)]
    assert min(relevant_ages) > max(other_ages)  # relevant strictly older


def test_mixed_regime_spans_full_range_regardless_of_relevance():
    rng = random.Random(3)
    ages = [assign_age(i % 2 == 0, Regime.MIXED, rng) for i in range(200)]
    assert min(ages) < 30 and max(ages) > 150  # wide spread, relevance-independent


# --- recency + decay scoring ----------------------------------------------- #


def test_normalized_recency_endpoints():
    assert normalized_recency(0.0, 0.0, 100.0) == 1.0  # newest
    assert normalized_recency(100.0, 0.0, 100.0) == 0.0  # oldest
    assert normalized_recency(50.0, 0.0, 100.0) == 0.5  # midpoint


def test_normalized_recency_uniform_pool_is_constant():
    # No spread → no information → constant (ranking falls back to input order).
    assert normalized_recency(30.0, 30.0, 30.0) == 1.0


def test_decay_score_matches_formula_and_is_monotonic():
    assert decay_score(0.0, 30.0) == 1.0
    assert abs(decay_score(30.0, 30.0) - exp(-1)) < 1e-12
    # Shorter half-life decays faster at the same age.
    assert decay_score(30.0, 7.0) < decay_score(30.0, 90.0)
    # Older memories always score lower for a fixed half-life.
    assert decay_score(60.0, 30.0) < decay_score(10.0, 30.0)


def test_apply_regime_is_pure_and_sets_age_and_recency():
    mems = [MemoryItem(id=f"m{i}", content="", similarity=0.5) for i in range(4)]
    cached = CachedQuery("q", mems, relevant_ids={"m0"}, target_id="m0")
    out = apply_regime(cached, Regime.ALIGNED, random.Random(7))
    assert [m.id for m in mems] == [m.id for m in out]  # order preserved
    assert all(m.age_days == 0.0 for m in mems)  # inputs untouched
    # Relevant m0 is newer → higher normalized recency than the others.
    by_id = {m.id: m for m in out}
    assert by_id["m0"].recency > max(by_id[i].recency for i in ("m1", "m2", "m3"))


# --- strategy comparison --------------------------------------------------- #


def _corpus(n_queries: int = 12) -> list[CachedQuery]:
    """2 relevant (high importance, low similarity) + 8 distractors per query.

    Distractors are listed first, mirroring the real cache's similarity-descending
    order, so a tie-breaking strategy (e.g. recency under the uniform regime) falls
    back to similarity order rather than secretly leaking relevance order.
    """
    cached: list[CachedQuery] = []
    for qi in range(n_queries):
        mems, relevant = [], set()
        for j in range(8):
            mems.append(MemoryItem(id=f"q{qi}-dis{j}", content="",
                                   similarity=0.7 + 0.01 * j, importance=0.05))
        for j in range(2):
            mid = f"q{qi}-rel{j}"
            mems.append(MemoryItem(id=mid, content="", similarity=0.2 + 0.01 * j,
                                   importance=0.9 - 0.05 * j))
            relevant.add(mid)
        cached.append(CachedQuery(f"q{qi}", mems, relevant, f"q{qi}-rel0"))
    return cached


def test_recency_helps_when_aligned_hurts_when_misaligned():
    cached = _corpus()
    res = run_temporal_study(cached, half_lives=(30.0,), seeds_per_regime=8)
    by_regime = {r.regime: r for r in res.regimes}

    def recency_only(regime_key: str):
        return next(s for s in by_regime[regime_key].strategies
                    if s.strategy == "recency_only")

    aligned = recency_only(Regime.ALIGNED.value)
    misaligned = recency_only(Regime.MISALIGNED.value)
    # Aligned: recency surfaces the (buried-by-similarity) relevant memories and
    # beats the baseline; misaligned ranks them last, so it does far worse.
    assert aligned.recall5.beats
    assert aligned.report.recall[5] > misaligned.report.recall[5] + 0.3
    assert not misaligned.recall5.beats

    # The "recency hurts" effect, shown against an importance anchor that is NOT
    # already at the recall floor: adding misaligned recency to importance drags
    # the recovered relevant memories back down.
    def imp(regime_key: str):
        return next(s for s in by_regime[regime_key].strategies
                    if s.strategy == "importance_only").report.recall[5]

    def ipr(regime_key: str):
        return next(s for s in by_regime[regime_key].strategies
                    if s.strategy == "importance_plus_recency").report.recall[5]

    assert ipr(Regime.MISALIGNED.value) < imp(Regime.MISALIGNED.value)


def test_importance_only_is_regime_invariant():
    cached = _corpus()
    res = run_temporal_study(cached, half_lives=(30.0,), seeds_per_regime=3)
    imp_recalls = {
        r.regime: next(s for s in r.strategies if s.strategy == "importance_only").report.recall[5]
        for r in res.regimes
    }
    # importance_only ignores time, so it is identical across every regime.
    assert len(set(round(v, 6) for v in imp_recalls.values())) == 1


def test_recency_marginal_reported_per_regime():
    cached = _corpus()
    res = run_temporal_study(cached, half_lives=(30.0,), seeds_per_regime=5)
    aligned = next(r for r in res.regimes if r.regime == Regime.ALIGNED.value)
    misaligned = next(r for r in res.regimes if r.regime == Regime.MISALIGNED.value)
    # Adding recency to importance helps when aligned, hurts when misaligned.
    assert aligned.recency_marginal_recall5.mean_delta >= misaligned.recency_marginal_recall5.mean_delta


def test_decay_strategy_named_by_half_life():
    cached = _corpus(3)
    res = run_temporal_study(cached, half_lives=(7.0, 30.0, 90.0), seeds_per_regime=2)
    names = {s.strategy for s in res.regimes[0].strategies}
    assert {"importance_plus_decay_h7", "importance_plus_decay_h30",
            "importance_plus_decay_h90"} <= names


# --- regression against uniform control ------------------------------------ #


def test_uniform_control_recency_is_neutral():
    # Under the uniform regime recency carries no signal, so recency_only must
    # not beat the baseline (no accidental temporal effect).
    cached = _corpus()
    res = run_temporal_study(cached, half_lives=(30.0,), seeds_per_regime=4)
    uniform = next(r for r in res.regimes if r.regime == Regime.UNIFORM.value)
    recency = next(s for s in uniform.strategies if s.strategy == "recency_only")
    assert not recency.recall5.beats


def test_determinism():
    cached = _corpus()
    a = run_temporal_study(cached, half_lives=(30.0,), seeds_per_regime=6)
    b = run_temporal_study(cached, half_lives=(30.0,), seeds_per_regime=6)
    sa = a.regimes[1].strategies[3]
    sb = b.regimes[1].strategies[3]
    assert sa.report.recall == sb.report.recall
    assert sa.recall5.mean_delta == sb.recall5.mean_delta


# --- report + JSON schema -------------------------------------------------- #


def test_report_renders_all_regimes_and_strategies():
    cached = _corpus(4)
    res = run_temporal_study(cached, half_lives=(7.0, 30.0), seeds_per_regime=2)
    report = render_report(res)
    for regime in Regime:
        assert regime.value in report
    for strat in ("similarity_only", "importance_only", "sim_plus_importance",
                  "recency_only", "importance_plus_recency", "importance_plus_decay_h7"):
        assert strat in report


def test_result_json_schema(tmp_path):
    cached = _corpus(4)
    res = run_temporal_study(cached, half_lives=(30.0,), seeds_per_regime=2)
    path = save_result(res, results_dir=tmp_path)
    data = json.loads(path.read_text())
    assert data["experiment"] == "salience-memory-temporal-salience"
    assert data["n_queries"] == 4
    assert len(data["regimes"]) == len(Regime)
    regime = data["regimes"][0]
    assert {"regime", "description", "strategies", "recency_marginal_recall5"} <= set(regime)
    strat = regime["strategies"][0]
    assert {"strategy", "time_dependent", "report", "recall5", "ndcg5", "mrr"} <= set(strat)
    # asdict round-trips cleanly (no un-serializable fields).
    assert asdict(res)["regimes"][0]["regime"] == regime["regime"]
