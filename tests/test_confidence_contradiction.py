"""Experiment 4 — Confidence & Contradiction: scoring, gating, metric, schema."""

from __future__ import annotations

import json
import random
from dataclasses import asdict

from mars.memory.confidence_contradiction import (
    ConfidenceOnlyStrategy,
    EnrichedQuery,
    ImportancePlusConfidenceGatedStrategy,
    ImportancePlusConfidenceStrategy,
    Regime,
    assign_confidence,
    contradiction_avoided,
    enrich,
    render_report,
    run_confidence_study,
    save_result,
)
from mars.memory.models import MemoryItem
from mars.memory.noisy_importance_experiment import CachedQuery


# --- confidence scoring + gating ------------------------------------------- #


def test_confidence_only_ranks_by_confidence():
    s = ConfidenceOnlyStrategy()
    assert s.score(MemoryItem("a", "", similarity=0.9, confidence=0.2)) == 0.2


def test_gating_discounts_low_confidence_important_memory():
    gated = ImportancePlusConfidenceGatedStrategy()
    # Two memories, equal similarity, both important; one trusted, one not.
    trusted = MemoryItem("t", "", similarity=0.3, importance=0.9, confidence=0.9)
    untrusted = MemoryItem("u", "", similarity=0.3, importance=0.9, confidence=0.2)
    assert gated.score(trusted) > gated.score(untrusted)
    # Additive confidence also prefers the trusted one but by a smaller margin,
    # because it does not multiply importance down.
    add = ImportancePlusConfidenceStrategy()
    gated_gap = gated.score(trusted) - gated.score(untrusted)
    add_gap = add.score(trusted) - add.score(untrusted)
    assert gated_gap > add_gap


def test_additive_confidence_formula():
    s = ImportancePlusConfidenceStrategy()
    m = MemoryItem("m", "", similarity=1.0, importance=1.0, confidence=1.0)
    assert abs(s.score(m) - (0.65 + 0.25 + 0.10)) < 1e-9


# --- contradiction pair generation + avoidance metric ---------------------- #


def _eq(confidences: dict[str, float] | None = None) -> EnrichedQuery:
    mems = [
        MemoryItem("tgt", "t", similarity=0.5, importance=0.9),
        MemoryItem("con", "c", similarity=0.9, importance=0.9),  # obsolete, high sim
        MemoryItem("d1", "d", similarity=0.6, importance=0.1),
    ]
    cached = CachedQuery("q", mems, relevant_ids={"tgt"}, target_id="tgt")
    category = {"tgt": "target", "con": "contradictory", "d1": "distractor"}
    conf = confidences or {"tgt": 0.9, "con": 0.2, "d1": 0.5}
    return EnrichedQuery(cached, category, conf)


def test_contradiction_eligibility_and_ids():
    eq = _eq()
    assert eq.contradictory_ids == {"con"}
    assert eq.is_contradiction_eligible


def test_contradiction_avoided_true_when_target_outranks():
    assert contradiction_avoided(["tgt", "con", "d1"], "tgt", {"con"}) is True


def test_contradiction_avoided_false_when_obsolete_outranks():
    assert contradiction_avoided(["con", "tgt", "d1"], "tgt", {"con"}) is False


def test_contradiction_avoided_none_when_not_eligible():
    # No contradictory memory present → not eligible (excluded from rate).
    assert contradiction_avoided(["tgt", "d1"], "tgt", set()) is None
    # No target present → not eligible.
    assert contradiction_avoided(["con", "d1"], "tgt", {"con"}) is None


def test_confidence_assignment_bands_per_regime():
    eq = _eq()
    rng = random.Random(0)
    # Contradictory regime: relevant high, contradictory low, others mid.
    out = {m.id: m.confidence for m in assign_confidence(eq, Regime.CONTRADICTORY, rng)}
    assert out["tgt"] >= 0.8
    assert out["con"] <= 0.3
    assert 0.5 <= out["d1"] <= 0.7
    # High-everywhere regime: all high.
    hi = {m.id: m.confidence for m in assign_confidence(eq, Regime.HIGH_EVERYWHERE, random.Random(0))}
    assert all(v >= 0.9 for v in hi.values())


# --- enrichment from the real cache ---------------------------------------- #


def test_enrich_matches_corpus_by_content():
    from mars.memory.noisy_importance_experiment import load_cache
    from pathlib import Path

    cache_path = Path("experiments/cache/noisy-importance-retrievals.json")
    if not cache_path.exists():  # pragma: no cover - cache is committed
        return
    cached, _ = load_cache(cache_path)
    enriched = enrich(cached)
    # Every cached memory resolves to a real corpus category (no "unknown").
    cats = {c for eq in enriched for c in eq.category.values()}
    assert "unknown" not in cats
    assert any(eq.is_contradiction_eligible for eq in enriched)


# --- study: contradiction handling + determinism + schema ------------------ #


def _corpus(n_queries: int = 12) -> list[EnrichedQuery]:
    """Each query: target (low sim, high imp) + obsolete contradictory (high sim,
    high imp) + distractors. Confidence is the lever that can separate them."""
    enriched: list[EnrichedQuery] = []
    for qi in range(n_queries):
        mems, category = [], {}
        for j in range(6):
            mid = f"q{qi}-d{j}"
            mems.append(MemoryItem(mid, f"dis {qi} {j}", similarity=0.55 + 0.01 * j, importance=0.1))
            category[mid] = "distractor"
        # Obsolete memory is *equally important* and slightly more similar than the
        # correct target — importance alone cannot separate them; only confidence can.
        con = f"q{qi}-con"
        mems.append(MemoryItem(con, f"obsolete {qi}", similarity=0.50, importance=0.9))
        category[con] = "contradictory"
        tgt = f"q{qi}-tgt"
        mems.append(MemoryItem(tgt, f"correct {qi}", similarity=0.45, importance=0.9))
        category[tgt] = "target"
        cached = CachedQuery(f"q{qi}", mems, {tgt}, tgt)
        authored = {**{m.id: 0.7 for m in mems}, tgt: 0.9, con: 0.2}
        enriched.append(EnrichedQuery(cached, category, authored))
    return enriched


def test_confidence_improves_contradiction_avoidance():
    enriched = _corpus()
    res = run_confidence_study(enriched, seeds_per_regime=8)
    contra = next(r for r in res.regimes if r.regime == Regime.CONTRADICTORY.value)

    def car(name: str) -> float:
        return next(s for s in contra.strategies if s.strategy == name).contradiction_avoidance_rate

    # importance alone cannot tell the obsolete (high-importance) memory from the
    # correct one; confidence-aware strategies suppress the obsolete one.
    assert car("importance_plus_confidence_gated") > car("importance_only")
    assert car("confidence_only") > car("similarity_only")


def test_hard_regime_decouples_importance_and_confidence_recovers():
    # Corpus where the obsolete memory is genuinely LESS important than the target,
    # so importance alone resolves the contradiction in regime C.
    enriched = []
    for qi in range(12):
        tgt = MemoryItem(f"q{qi}-tgt", f"correct {qi}", similarity=0.45, importance=0.9)
        con = MemoryItem(f"q{qi}-con", f"obsolete {qi}", similarity=0.5, importance=0.3)
        d = MemoryItem(f"q{qi}-d", f"dis {qi}", similarity=0.6, importance=0.1)
        cached = CachedQuery(f"q{qi}", [d, con, tgt], {tgt.id}, tgt.id)
        cat = {tgt.id: "target", con.id: "contradictory", d.id: "distractor"}
        enriched.append(EnrichedQuery(cached, cat, {tgt.id: 0.9, con.id: 0.2, d.id: 0.6}))
    res = run_confidence_study(enriched, seeds_per_regime=6)

    def car(regime_key: str, name: str) -> float:
        rr = next(r for r in res.regimes if r.regime == regime_key)
        return next(s for s in rr.strategies if s.strategy == name).contradiction_avoidance_rate

    # In C, importance already separates correct (0.9) from obsolete (0.3): CAR high.
    assert car(Regime.CONTRADICTORY.value, "importance_only") > 0.9
    # In HARD, the obsolete memory is raised to the target's importance, so
    # importance can no longer tell them apart and its avoidance collapses…
    assert car(Regime.CONTRADICTORY_HARD.value, "importance_only") < 0.6
    # …but confidence-gating, which discounts the untrusted memory, recovers it.
    assert (car(Regime.CONTRADICTORY_HARD.value, "importance_plus_confidence_gated")
            > car(Regime.CONTRADICTORY_HARD.value, "importance_only"))


def test_high_everywhere_confidence_is_near_neutral_marginal():
    enriched = _corpus()
    res = run_confidence_study(enriched, seeds_per_regime=6)
    control = next(r for r in res.regimes if r.regime == Regime.HIGH_EVERYWHERE.value)
    contra = next(r for r in res.regimes if r.regime == Regime.CONTRADICTORY.value)
    # Confidence helps more under contradiction than under the high-everywhere control.
    assert (contra.confidence_marginal_recall5.mean_delta
            >= control.confidence_marginal_recall5.mean_delta)


def test_importance_only_is_regime_invariant():
    enriched = _corpus()
    res = run_confidence_study(enriched, seeds_per_regime=3)
    recalls = {
        r.regime: next(s for s in r.strategies if s.strategy == "importance_only").report.recall[5]
        for r in res.regimes
    }
    assert len({round(v, 6) for v in recalls.values()}) == 1


def test_determinism():
    enriched = _corpus()
    a = run_confidence_study(enriched, seeds_per_regime=5)
    b = run_confidence_study(enriched, seeds_per_regime=5)
    sa = a.regimes[2].strategies[3]
    sb = b.regimes[2].strategies[3]
    assert sa.report.recall == sb.report.recall
    assert sa.contradiction_avoidance_rate == sb.contradiction_avoidance_rate
    assert sa.recall5.mean_delta == sb.recall5.mean_delta


def test_report_renders_all_regimes_and_strategies():
    enriched = _corpus(4)
    report = render_report(run_confidence_study(enriched, seeds_per_regime=2))
    for regime in Regime:
        assert regime.value in report
    for strat in ("similarity_only", "importance_only", "sim_plus_importance",
                  "confidence_only", "importance_plus_confidence",
                  "importance_plus_confidence_gated",
                  "importance_plus_recency_plus_confidence"):
        assert strat in report
    assert "CAR" in report


def test_result_json_schema(tmp_path):
    enriched = _corpus(4)
    res = run_confidence_study(enriched, seeds_per_regime=2)
    path = save_result(res, results_dir=tmp_path)
    data = json.loads(path.read_text())
    assert data["experiment"] == "salience-memory-confidence-and-contradiction"
    assert len(data["regimes"]) == len(Regime)
    regime = data["regimes"][0]
    assert {"regime", "description", "strategies", "confidence_marginal_recall5"} <= set(regime)
    strat = regime["strategies"][0]
    assert {"strategy", "confidence_dependent", "report", "contradiction_avoidance_rate",
            "contradiction_eligible", "recall5", "ndcg5", "mrr"} <= set(strat)
    assert asdict(res)["regimes"][0]["regime"] == regime["regime"]
