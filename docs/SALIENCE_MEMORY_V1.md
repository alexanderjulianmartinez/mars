# Salience Memory v1 (Track B)

Track B runs the first **retrieval-focused** experiment: does salience-weighted
memory retrieval beat similarity-only retrieval? The variable under test is the
**retrieval strategy** — so execution is mocked/irrelevant, and the experiment is
judged on retrieval metrics, not agent implementation quality. Kept separate from
agentic evals (Track A, `docs/AGENTIC_EVALS.md`).

## Arms

- **baseline:** `similarity_only`
- **candidate:** `salience_weighted_v1` (similarity + importance + recency + frequency)

## Retrieval metrics

`recall@k`, `precision@k`, `MRR`, `target found rate`, `context efficiency` —
computed against gold labels (local YAML for v1; Cortex-sourced later, issue #7):

```yaml
gold_memories:
  - { memory_id: migration-note-001, relevant: true, target: true }
```

## Honesty rule (hard constraint)

Cortex may return `semantic_score: null` when embeddings are disabled. Mars
**detects this** and:

- marks semantic retrieval as **unavailable**,
- emits a warning and states it in the report,
- never claims "semantic baseline" without real semantic scores,
- exits non-zero only under `--strict-semantic`.

So the experiment runs **now** (keyword/ranking fallback) and *automatically*
becomes a semantic comparison once Cortex returns `semantic_score` (enable the
`embeddings` extra + a Voyage AI key — see `docs/setup.md` in the Cortex repo).

## Run it

```bash
# default: synthetic retrieval source, no keys needed
mars experiments run salience-memory-v1

# real Cortex retrieval (needs MARS_CORTEX_MCP_*; honest about semantic state)
mars experiments run salience-memory-v1 --cortex-provider mcp --autodev-provider mock

# fail loudly if semantic scores are unavailable
mars experiments run salience-memory-v1 --strict-semantic

mars experiments report salience-memory-v1
```

The report includes the retrieval/execution providers, semantic availability,
per-arm metrics, limitations, and an honest decision line.

## Status / next steps

- Runs today on the **synthetic** source and on **real Cortex** (keyword fallback).
- To make it a genuine *semantic*-vs-salience result: enable Cortex embeddings
  (`--extra embeddings` + `VOYAGE_API_KEY`) so `semantic_score` is non-null.
- To use real Cortex memories with real labels: provide `gold_memories` (issue #7).

## Real Cortex corpus + gold labels (issue #7)

Cortex assigns its own UUID per memory, so gold labels are produced **by seeding**,
not authored against fixed ids:

1. Author the labeled corpus: `experiments/corpus/salience-memory-v1.corpus.yaml`
   (per-query memories with stable `key`s + `relevant`/`target` flags; relevant
   memories are high-importance/moderate-overlap, distractors are
   high-overlap/low-importance so salience can help).
2. Seed it and capture gold labels (live, opt-in — writes to the Cortex project):
   ```bash
   mars experiments seed-corpus salience-memory-v1   # writes <name>.gold.json (gitignored)
   ```
3. Run against real Cortex using the seeded corpus + captured gold:
   ```bash
   mars experiments run salience-memory-v1 --cortex-provider mcp --strict-semantic
   ```

If no gold file exists yet, the `--cortex-provider mcp` run warns and falls back
to the spec's (synthetic-id) gold. Seeding logic is unit-tested with a fake
Cortex (no keys).
