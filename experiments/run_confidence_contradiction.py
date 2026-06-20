#!/usr/bin/env python3
"""Experiment 4 — Confidence & Contradiction study runner.

Can confidence-aware retrieval improve memory prioritization, and can it suppress
outdated/contradictory memories? Sweeps four confidence regimes × the confidence
strategy set over the **already-materialized** real retrieval cache (real Voyage
semantic scores + importance + gold) from Experiment 2, enriched with each
memory's authored category + confidence by content-matching the expanded corpus —
so nothing is re-embedded and the study is offline + deterministic.

Usage:
    python experiments/run_confidence_contradiction.py [--cache PATH] [--seeds 10]
"""

from __future__ import annotations

import sys
from pathlib import Path

from mars.memory.confidence_contradiction import (
    enrich,
    render_report,
    run_confidence_study,
    save_result,
)
from mars.memory.noisy_importance_experiment import load_cache

DEFAULT_CACHE = Path("experiments/cache/noisy-importance-retrievals.json")


def _arg(flag: str, default: str | None = None) -> str | None:
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def main() -> int:
    seeds = int(_arg("--seeds", "10"))
    cache_path = Path(_arg("--cache", str(DEFAULT_CACHE)))

    if not cache_path.exists():
        print(f"ERROR: no retrieval cache at {cache_path}. Run the noisy-importance "
              f"study first to materialize it.", file=sys.stderr)
        return 1

    cached, semantic = load_cache(cache_path)
    print(f"Loaded {len(cached)} cached retrievals from {cache_path}.", file=sys.stderr)
    enriched = enrich(cached)
    elig = sum(1 for eq in enriched if eq.is_contradiction_eligible)
    print(f"Enriched with corpus category/confidence; {elig} contradiction-eligible "
          f"queries.", file=sys.stderr)

    notes = [
        f"confidence values are synthetic per regime (regime D uses authored corpus "
        f"confidence); semantic pools cached from {cache_path.name}.",
        f"{elig} of {len(enriched)} queries are contradiction-eligible (pool contains "
        f"both target and >=1 contradictory memory).",
    ]
    result = run_confidence_study(enriched, seeds_per_regime=seeds,
                                  semantic_available=semantic, notes=notes)
    save_result(result)
    print(render_report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
