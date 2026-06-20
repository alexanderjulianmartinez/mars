#!/usr/bin/env python3
"""Experiment 3 — Temporal Salience study runner.

Does adding a temporal signal (recency / decay) improve salience-weighted
retrieval? This sweeps four timestamp regimes × the temporal strategy set over
the **already-materialized** real retrieval cache (real Voyage semantic scores +
importance + gold) produced by the noisy-importance study — so nothing is
re-embedded and the whole study is offline + deterministic.

By default it reuses the noisy-importance cache. To build a fresh cache from live
Cortex (rarely needed) pass ``--rebuild --db <cortex.db>`` with the usual
``MARS_CORTEX_MCP_*`` env (``cortex mcp serve --embed``); it honest-stops if
Cortex returns ``semantic_score: null``.

Usage:
    python experiments/run_temporal_salience.py [--cache PATH] [--seeds 10]
    python experiments/run_temporal_salience.py --rebuild --db ~/.autodev/cortex-mars-expanded.db
"""

from __future__ import annotations

import sys
from pathlib import Path

from mars.memory.noisy_importance_experiment import load_cache, materialize, save_cache
from mars.memory.temporal_salience import render_report, run_temporal_study, save_result

CORPUS = "salience-memory-v1-expanded"
DEFAULT_CACHE = Path("experiments/cache/noisy-importance-retrievals.json")


def _arg(flag: str, default: str | None = None) -> str | None:
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def main() -> int:
    seeds = int(_arg("--seeds", "10"))
    cache_path = Path(_arg("--cache", str(DEFAULT_CACHE)))

    if "--rebuild" in sys.argv:
        db_path = _arg("--db")
        if not db_path:
            print("ERROR: --rebuild requires --db <sqlite path>.", file=sys.stderr)
            return 1
        from mars.memory.expanded_corpus import build_gold_pools, load_expanded_corpus
        from mars.memory.retrieval_source import CortexRetrievalSource
        from mars.providers.cortex_mcp import CortexMCPProvider

        # Reuse the expanded runner's UUID-canonicalizing DB reconstruction.
        from run_expanded_benchmark import _key_to_id_from_db  # noqa: E402

        cortex = CortexMCPProvider.from_env()
        if cortex is None:
            print("ERROR: no Cortex MCP server configured (set MARS_CORTEX_MCP_*).", file=sys.stderr)
            return 1
        corpus = load_expanded_corpus(CORPUS)
        gold, pools = build_gold_pools(corpus, _key_to_id_from_db(db_path, corpus.project))
        source = CortexRetrievalSource(cortex, corpus.project, gold, pools=pools, limit=100)
        cached, semantic, notes = materialize(source, corpus.query_texts())
        cortex.close()
        if not semantic:
            print("BLOCKED: Cortex returned semantic_score=null; refusing to claim a "
                  "semantic temporal result. Serve with `cortex mcp serve --embed`.", file=sys.stderr)
            return 2
        save_cache(cached, cache_path, semantic_available=semantic)
        print(f"Rebuilt cache → {cache_path}.", file=sys.stderr)
    else:
        if not cache_path.exists():
            print(f"ERROR: no retrieval cache at {cache_path}. Run the noisy-importance "
                  f"study first, or pass --rebuild --db <cortex.db>.", file=sys.stderr)
            return 1
        cached, semantic = load_cache(cache_path)
        notes = [f"timestamps are synthetic (per-regime); semantic pools cached from {cache_path.name}."]
        print(f"Loaded {len(cached)} cached retrievals from {cache_path}.", file=sys.stderr)

    result = run_temporal_study(cached, seeds_per_regime=seeds, semantic_available=semantic, notes=notes)
    save_result(result)
    print(render_report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
