# Salience Memory Benchmark v1.0.0

**Benchmark ID:** `salience-memory-benchmark-v1`
**Version:** `1.0.0` (frozen 2026-06-21)
**Corpus:** `experiments/corpus/salience-memory-v1-expanded.corpus.yaml`
**SHA256:** `a464085c3daa64c97d2764c47f8758931b2a51c2adc1e143fcfc98d9faa74d59`
**Manifest:** `experiments/corpus/salience-memory-v1.manifest.yaml`

All Salience & Attention Systems results (Experiments 1–5) are reported against
**Salience Memory Benchmark v1.0.0**.

## Overview

Salience Memory Benchmark v1 is a synthetic, labeled retrieval benchmark. It
holds **30 queries** and **552 memories** (~18 per query) across six labeled
categories. Each query has exactly one *target* memory, a set of *relevant*
support memories, and a controlled pool of adversarial *distractor*, *stale*,
*contradictory*, and *low-confidence* memories. Gold relevance is explicit per
query (`target_memories` + `relevant_memories`), so retrieval *coverage* — not
just ranking — can be measured.

## Purpose

The benchmark exists to test **salience-weighted retrieval** (importance- and
confidence-aware ranking) against **semantic-similarity-only** retrieval. The
distractors are engineered to have high lexical/semantic overlap but low utility,
so a similarity-only ranker is actively misled. This makes the benchmark
*discriminating*: unlike the original 13-memory smoke test (where recall@5
saturated at 1.0 for every strategy), here the salience signal can measurably
change recall@k, precision@k, MRR, nDCG@k, and contradiction-avoidance.

## Corpus Design

The corpus is authored reproducibly by
`experiments/corpus/generate_expanded.py` + `scenarios_data.py` and loaded /
validated via `mars/memory/expanded_corpus.py`.

| Category | Count | Role |
| --- | --- | --- |
| `target` | 30 | The primary memory each query should retrieve (1 per query). |
| `relevant` | 102 | Helpful support memories; count toward recall/precision gold. |
| `distractor` | 210 | High overlap, low utility — engineered to mislead similarity. |
| `stale` | 90 | Previously useful, now outdated. |
| `contradictory` | 30 | Conflict with the truth (drive contradiction-avoidance). |
| `low_confidence` | 90 | Possibly incorrect (low authored confidence). |

- **Queries** — 30 natural-language retrieval prompts spanning six scenario
  categories.
- **Memories** — each carries a stable `id`, `content`, `category`, and authored
  salience signals (`importance`, `novelty`, `urgency`, `confidence`).
- **Target memories** — exactly one per query; the memory a perfect retriever
  ranks first.
- **Relevant support memories** — additional memories that count as relevant for
  recall/precision but are not the single target.
- **Distractors** — high-overlap, low-utility memories included to penalize
  similarity-only ranking.
- **Stale memories** — once-useful content that is now outdated.
- **Contradictory memories** — assert something that conflicts with the truth;
  used to measure the `ContradictionAvoidanceRate` metric.
- **Low-confidence memories** — low authored `confidence`; used to test gated
  confidence weighting.

## Intended Use

Used to test **salience-weighted retrieval against semantic similarity** —
measuring recall@k, precision@k, MRR, nDCG@k, and contradiction-avoidance over a
controlled, labeled candidate pool with adversarial distractors.

## Not Intended For

- **Not** a general coding benchmark.
- **Not** a general memory benchmark.
- **Not** evidence of production impact by itself (it measures retrieval quality,
  not downstream task success — see Experiment 5 for the separate, honest
  execution-impact study).
- **Not** an AGI benchmark.

## Validation

```bash
mars corpus validate salience-memory-v1-expanded
```

Validation confirms: query count, memory count, per-category counts, no duplicate
memory IDs, no malformed records, every query has a target, relevant support, and
distractors, and that all gold IDs resolve to memories in their query. View the
full breakdown with `mars corpus stats salience-memory-v1-expanded`.

## Reproduction

```bash
# Experiment 1 — Salience Memory v1
mars experiments run salience-memory-v1

# Experiment 2 — Noisy Importance (offline, committed retrieval cache)
python experiments/run_noisy_importance.py --cache-only

# Experiment 3 — Temporal Salience
python experiments/run_temporal_salience.py

# Experiment 4 — Confidence & Contradiction
python experiments/run_confidence_contradiction.py

# Experiment 5 — Execution Impact (apparatus validation; real-AutoDev variant
# requires MARS_AUTODEV_MCP_* — see docs/AUTODEV_EXECUTION_IMPACT_WIRING.md)
python experiments/run_execution_impact.py --simulate
```

## Known Limitations

- **Synthetic corpus** — authored by hand, not sampled from real production
  memory traces.
- **Authored importance labels** — `importance`/`novelty`/`urgency`/`confidence`
  are authored, not learned or observed.
- **Controlled adversarial distractors** — distractors are adversarial by
  construction, not naturally occurring.
- **Fixed embedding model** — semantic baselines depend on a fixed embedding
  model when run against real Cortex.
- **Not yet based on real production memory traces** — and ~18 memories per query
  is small relative to production memory stores.

## Versioning Policy

- **v1.0.0 is frozen.** The corpus bytes are pinned by the SHA256 in the manifest.
- **Bug fixes** (a genuine correctness defect in the corpus) require a new
  version `v1.0.x` or `v1.1` — never an in-place mutation of the frozen corpus.
- **Expanded or substantively different benchmark design** requires **v2** (a new
  corpus file, new manifest, new benchmark id).
- **Never silently mutate the frozen corpus.** `mars corpus verify-frozen
  salience-memory-benchmark-v1` recomputes the corpus SHA256 and fails if the
  bytes drift from the manifest, and a regression test
  (`tests/test_benchmark_freeze.py`) guards the same invariant in CI.

### Freeze verification

```bash
mars corpus verify-frozen salience-memory-benchmark-v1
mars corpus hash experiments/corpus/salience-memory-v1-expanded.corpus.yaml
```
