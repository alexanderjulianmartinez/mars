#!/usr/bin/env python3
"""Live runner: seed the expanded corpus into Cortex, then run the benchmark.

Seeds all ~552 memories (with embeddings), retrieves each query's own pool with
real semantic scores, ranks with similarity_only vs salience_weighted_v1, and
prints + saves the full metric suite. Requires a configured Cortex MCP server
(MARS_CORTEX_MCP_*). Honest-stop: if semantic scores are unavailable it writes
docs/SALIENCE_MEMORY_BLOCKED.md and exits non-zero instead of claiming results.

Usage:  python experiments/run_expanded_benchmark.py [--limit 600]
"""

from __future__ import annotations

import sys
from pathlib import Path

from mars.memory.expanded_corpus import load_expanded_corpus, seed_expanded_corpus
from mars.memory.expanded_experiment import render_report, run_benchmark, save_result
from mars.memory.retrieval_source import CortexRetrievalSource
from mars.providers.cortex_mcp import CortexMCPProvider

CORPUS = "salience-memory-v1-expanded"
BLOCKED_DOC = Path("docs/SALIENCE_MEMORY_BLOCKED.md")


def _key_to_id_from_db(db_path: str, project: str) -> dict[str, str]:
    """Reconstruct authored-key → assigned-id from an already-seeded sqlite DB.

    Memories were seeded with ``summary`` set to the authored stable id, so the
    benchmark can be re-evaluated without re-seeding (and re-embedding).
    """
    import sqlite3
    import uuid

    def canon(mid: str) -> str:
        # Cortex stores the UUID without dashes; the search tool returns it
        # dashed. Normalize to the dashed form the search results use.
        try:
            return str(uuid.UUID(mid))
        except (ValueError, TypeError):
            return mid

    con = sqlite3.connect(db_path)
    rows = con.execute("SELECT summary, id FROM memory_objects").fetchall()
    con.close()
    return {summary: canon(mid) for summary, mid in rows if summary}


def main() -> int:
    limit = 100  # Cortex caps search limit at 100
    if "--limit" in sys.argv:
        limit = min(int(sys.argv[sys.argv.index("--limit") + 1]), 100)
    db_path = sys.argv[sys.argv.index("--db") + 1] if "--db" in sys.argv else None
    no_seed = "--no-seed" in sys.argv

    cortex = CortexMCPProvider.from_env()
    if cortex is None:
        print("ERROR: no Cortex MCP server configured (set MARS_CORTEX_MCP_*).", file=sys.stderr)
        return 1

    corpus = load_expanded_corpus(CORPUS)
    if no_seed:
        if not db_path:
            print("ERROR: --no-seed requires --db <sqlite path>.", file=sys.stderr)
            return 1
        from mars.memory.expanded_corpus import build_gold_pools

        key_to_id = _key_to_id_from_db(db_path, corpus.project)
        gold, pools = build_gold_pools(corpus, key_to_id)
        print(f"Reconstructed gold/pools from {len(key_to_id)} seeded memories "
              f"(no re-seed).", file=sys.stderr)
    else:
        print(f"Seeding {corpus.n_memories} memories across {corpus.n_queries} queries "
              f"into Cortex project '{corpus.project}' (embeddings on)…", file=sys.stderr)
        gold, pools, key_to_id = seed_expanded_corpus(cortex, corpus)
        print(f"Seeded {len(key_to_id)} memories.", file=sys.stderr)

    source = CortexRetrievalSource(cortex, corpus.project, gold, pools=pools, limit=limit)
    result = run_benchmark(source, corpus.query_texts())

    if not result.semantic_available:
        BLOCKED_DOC.parent.mkdir(parents=True, exist_ok=True)
        BLOCKED_DOC.write_text(
            "# Salience Memory — Experiment Blocked\n\n"
            "The expanded benchmark could not run as a semantic experiment: Cortex returned "
            "`semantic_score: null`, so retrieval fell back to keyword ranking.\n\n"
            "## Why it cannot proceed\n"
            "A salience-vs-similarity comparison requires a real semantic baseline. Without "
            "embeddings, the 'similarity_only' arm is keyword-based and the result is not "
            "semantic evidence.\n\n"
            "## Missing configuration\n"
            "- Cortex must serve with embeddings enabled: `cortex mcp serve --embed`.\n"
            "- `CORTEX_VOYAGE_API_KEY` must be present in the served process's environment "
            "(its `.env`), and the serving venv needs both the `mcp` and `voyageai` extras.\n\n"
            "## Command to validate embeddings\n"
            "```\n"
            "MARS_CORTEX_MCP_ARGS='mcp serve --embed' \\\n"
            "MARS_CORTEX_MCP_CWD=/path/to/cortex \\\n"
            "python experiments/run_expanded_benchmark.py\n"
            "```\n"
        )
        print(f"BLOCKED: semantic unavailable. Wrote {BLOCKED_DOC}.", file=sys.stderr)
        cortex.close()
        return 2

    save_result(result)
    cortex.close()
    print(render_report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
