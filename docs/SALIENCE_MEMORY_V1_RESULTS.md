# Salience Memory v1 — Results (Expanded Benchmark)

First statistically meaningful run of the Salience Memory experiment: real Cortex
semantic retrieval (Voyage embeddings) over the 552-memory expanded benchmark,
mock execution, retrieval-only evaluation.

- Result data: `mars-experiments/salience-memory-v1-expanded.json`
- Reproduce: seed via `experiments/run_expanded_benchmark.py`, then eval with
  `--no-seed --db <cortex.db> --limit 100` (Cortex caps search `limit` at 100).

## Benchmark Summary

| | |
| --- | --- |
| Queries | 30 (6 domains × 5) |
| Memories | 552 (target 30 / relevant 102 / distractor 210 / stale 90 / contradictory 30 / low-confidence 90) |
| Mean relevant per query | 4.4 (target + support) |
| Mean candidate pool per query (returned) | ~12 of ~18 (low-similarity non-relevant fall outside the top-100 search limit) |
| Relevant-memory recovery @100 | mean 0.99; only 1/30 queries < 100% |

Composition is adversarial by design: distractors are written to be *semantically
closer* to the query than the truly-relevant memories, but carry low importance.

## Experimental Setup

| | |
| --- | --- |
| Retrieval provider | real Cortex over MCP (`cortex mcp serve --embed`) |
| Embeddings provider | Voyage (`voyage-3-lite`), confirmed live (HTTP 200 per memory) |
| Execution provider | mock (retrieval-only evaluation) |
| Candidate pooling | per-query controlled pool — both strategies re-rank the **same** retrieved set |
| Baseline strategy | `similarity_only` (rank by semantic score) |
| Candidate strategy | `salience_weighted_v1` (0.40 similarity + 0.30 importance + 0.20 recency + 0.10 frequency) |
| Determinism | fixed embeddings → deterministic retrieval; significance is over the 30-query distribution (paired bootstrap), not run-to-run noise |

## Results

| Metric | baseline (similarity_only) | candidate (salience_weighted_v1) | Δ |
| --- | --- | --- | --- |
| recall@1 | 0.067 | 0.933 | **+0.867** |
| recall@3 | 0.144 | 0.689 | +0.544 |
| recall@5 | 0.237 | 0.672 | **+0.435** |
| recall@10 | 0.761 | 0.931 | +0.169 |
| precision@1 | 0.067 | 0.933 | +0.867 |
| precision@3 | 0.144 | 0.689 | +0.544 |
| precision@5 | 0.200 | 0.567 | +0.367 |
| precision@10 | 0.330 | 0.410 | +0.080 |
| MRR | 0.313 | 0.967 | **+0.654** |
| nDCG@5 | 0.184 | 0.714 | **+0.531** |
| nDCG@10 | 0.454 | 0.847 | +0.393 |
| TargetFound@1 | 0.067 | 0.867 | +0.800 |
| TargetFound@3 | 0.367 | 1.000 | +0.633 |
| TargetFound@5 | 0.667 | 1.000 | +0.333 |
| ContextEfficiency@5 | 0.200 | 0.567 | +0.367 |
| ContextEfficiency@10 | 0.337 | 0.417 | +0.080 |

**Paired significance (per-query, 10k bootstrap):**

| Metric | mean Δ | 95% CI | wins / ties / losses |
| --- | --- | --- | --- |
| recall@5 | +0.435 | [+0.367, +0.502] | 29 / 1 / 0 |
| nDCG@5 | +0.531 | [+0.474, +0.583] | 30 / 0 / 0 |

Both CIs exclude zero by a wide margin.

### Why the baseline is so weak

For the migration query, ranked by semantic similarity (what `similarity_only`
does), the top of the pool is:

| rank | sim | importance | relevant? | memory |
| --- | --- | --- | --- | --- |
| 1 | 0.787 | 0.04 | – | distractor |
| 2 | 0.771 | 0.07 | – | distractor |
| 3 | 0.765 | 0.07 | – | distractor |
| 4 | 0.731 | 0.28 | – | contradictory |
| 5 | 0.690 | 0.40 | ✓ | relevant |
| 6 | 0.687 | 0.50 | ✓ (target) | target |

The distractors are genuinely the closest semantic matches, so similarity-only
buries the target at rank 6. Salience adds importance (relevant ≫ distractor),
lifting the right memories to the top. This is the corpus mechanism working, not
a metric artifact — verified directly on the live retrieval.

## Interpretation

1. **Did salience improve recall?** Yes, substantially and significantly:
   recall@5 +0.435 (95% CI [+0.367, +0.502]), recall@1 +0.867. The benchmark no
   longer saturates, so this is a real coverage gain, not just re-ordering.
2. **Did salience improve ranking?** Yes, strongly: MRR +0.654 (0.31→0.97),
   nDCG@5 +0.531, TargetFound@1 +0.800. It reliably puts the right memory first.
3. **Did salience improve target-memory retrieval?** Yes: TargetFound@3 reached
   1.000 (vs 0.367 baseline) — the single most-important memory is always within
   the top 3 under salience.
4. **Did salience improve context efficiency?** Yes at tight budgets:
   ContextEfficiency@5 +0.367 (0.20→0.57) — more of the 5-item budget is relevant.
   The gain shrinks at @10 (+0.08) as both arms eventually include the relevant set.
5. **Is the result statistically meaningful?** Yes. Across 30 queries the candidate
   wins 29–30 and the paired bootstrap CIs for recall@5 and nDCG@5 exclude zero.

The earlier hypothesis ("salience may improve prioritization more than coverage")
is **only half right**: salience improves *both* ranking and coverage here — but
the coverage gain is conditional on importance being an informative signal, which
this corpus guarantees (see weaknesses).

## Recommendation

**Continue Research.**

Salience-weighted retrieval clearly and significantly improves retrieval quality
on a non-saturating benchmark with a real semantic baseline. The mechanism is
verified. The next step is to test how much of the gain survives when importance
is *noisy* rather than a clean oracle (see next experiment).

## Remaining weaknesses in the benchmark

1. **Importance is an authored oracle.** Relevant memories carry high importance and
   distractors low, by construction. This makes salience's job easy and means the
   effect size is an **upper bound** — it proves salience *can* help a lot *when
   importance is informative*, not that it will in a production store where
   importance is estimated and noisy.
2. **Recency contributed nothing.** All memories were seeded at once, so
   `recency_factor` is ~uniform (~0.30); the entire win is importance-driven. The
   recency and frequency weights are untested here.
3. **Partial candidate pools.** Cortex caps search `limit` at 100, so ~6 of each
   query's ~18 authored memories (the lowest-similarity ones) fall outside the
   pool. Relevant recovery is 99%, so the comparison is fair and recall ceilings
   are nearly intact, but the pool is not the full authored set.
4. **Synthetic, hand-authored content.** Realistic but not sampled from production;
   absolute numbers are not externally comparable.
5. **Single configuration.** One weight set, one embedding model, binary relevance.

## Recommended next experiment

**Salience under noisy importance.** Re-run the same benchmark with importance
signals progressively degraded (add noise / shuffle a fraction of labels) and plot
the recall@5 and nDCG@5 gain vs importance-signal quality. This answers the
question that actually matters for production: *how good does Cortex's importance
estimate need to be for salience weighting to pay off?* Pair it with a recency
sub-study (stagger `created_at` so recency carries signal) to isolate each term's
contribution. Both reuse this corpus and runner unchanged — only the seeding
signals and weights vary.

## Research readiness

> Can we now confidently test: "Does salience improve retrieval quality?"

**YES.** We have a non-saturating benchmark (552 memories, 30 queries), a real
semantic baseline (Voyage embeddings, confirmed live), the full metric suite
(recall/precision@1/3/5/10, MRR, nDCG@5/10, TargetFound, ContextEfficiency), a
controlled per-query comparison, and paired significance testing. The one caveat
is *scope*: we can confidently test whether salience helps *given an importance
signal*; quantifying the dependence on importance-signal quality is exactly the
recommended next experiment.
