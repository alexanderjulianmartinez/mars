#!/usr/bin/env python3
"""Track 1 — noisy-importance study runner.

How robust is the Salience Memory v1 win to a *noisy* importance signal? The v1
result used importance as a clean oracle (an upper bound). This runner degrades
importance across a quality grid and finds the minimum quality at which salience
still beats plain semantic retrieval.

Two phases, decoupled so the expensive one runs once:

1. **Materialize** one real Cortex retrieval per query (the candidate pool with
   real semantic scores + true importance + gold) into a JSON **cache**. Reuses
   the already-seeded expanded corpus DB via ``--no-seed --db <path>`` exactly
   like ``run_expanded_benchmark.py`` (no re-seeding / re-embedding). Requires a
   configured embedding-capable Cortex (``MARS_CORTEX_MCP_*`` + ``cortex mcp
   serve --embed``); honest-stops if Cortex returns ``semantic_score: null``.
2. **Sweep** importance quality offline over the cache (deterministic, no Cortex),
   then save the result JSON + print the report.

Once the cache exists, phase 2 re-runs with no Cortex at all:

    python experiments/run_noisy_importance.py --no-seed --db <cortex.db>   # builds cache, runs
    python experiments/run_noisy_importance.py --cache-only                  # reuse cache, re-sweep

Usage:
    python experiments/run_noisy_importance.py --no-seed --db ~/.autodev/cortex-mars-expanded.db \
        [--seeds 25] [--cache PATH]
"""

from __future__ import annotations

import sys
from pathlib import Path

from mars.memory.expanded_corpus import build_gold_pools, load_expanded_corpus
from mars.memory.noisy_importance_experiment import (
    load_cache,
    materialize,
    render_report,
    run_noisy_sweep,
    save_cache,
    save_result,
)
from mars.memory.retrieval_source import CortexRetrievalSource

CORPUS = "salience-memory-v1-expanded"
CACHE = Path("experiments/cache/noisy-importance-retrievals.json")


def _arg(flag: str, default: str | None = None) -> str | None:
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


# Reuse the DB-key reconstruction from the expanded runner (UUID canonicalization).
from run_expanded_benchmark import _key_to_id_from_db  # noqa: E402  (sibling script)


def main() -> int:
    seeds = int(_arg("--seeds", "25"))
    cache_path = Path(_arg("--cache", str(CACHE)))
    cache_only = "--cache-only" in sys.argv

    corpus = load_expanded_corpus(CORPUS)

    if cache_only:
        if not cache_path.exists():
            print(f"ERROR: --cache-only but no cache at {cache_path}.", file=sys.stderr)
            return 1
        cached, semantic = load_cache(cache_path)
        notes = ["retrievals loaded from cache (no live Cortex this run)."]
        print(f"Loaded {len(cached)} cached retrievals from {cache_path}.", file=sys.stderr)
    else:
        db_path = _arg("--db")
        if "--no-seed" not in sys.argv or not db_path:
            print(
                "ERROR: need --no-seed --db <sqlite path> to materialize from the "
                "already-seeded expanded corpus (or --cache-only to reuse a cache).",
                file=sys.stderr,
            )
            return 1
        from mars.providers.cortex_mcp import CortexMCPProvider

        cortex = CortexMCPProvider.from_env()
        if cortex is None:
            print("ERROR: no Cortex MCP server configured (set MARS_CORTEX_MCP_*).", file=sys.stderr)
            return 1

        key_to_id = _key_to_id_from_db(db_path, corpus.project)
        gold, pools = build_gold_pools(corpus, key_to_id)
        print(
            f"Reconstructed gold/pools from {len(key_to_id)} seeded memories; "
            f"materializing live retrievals…",
            file=sys.stderr,
        )
        source = CortexRetrievalSource(cortex, corpus.project, gold, pools=pools, limit=100)
        cached, semantic, notes = materialize(source, corpus.query_texts())
        cortex.close()

        if not semantic:
            print(
                "BLOCKED: Cortex returned semantic_score=null — refusing to claim a "
                "semantic noisy-importance result. Serve with `cortex mcp serve --embed` "
                "and a valid CORTEX_VOYAGE_API_KEY.",
                file=sys.stderr,
            )
            return 2

        save_cache(cached, cache_path, semantic_available=semantic)
        print(f"Cached {len(cached)} retrievals → {cache_path}.", file=sys.stderr)

    result = run_noisy_sweep(
        cached,
        seeds_per_level=seeds,
        semantic_available=semantic,
        notes=notes,
    )
    save_result(result)
    print(render_report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
