# Apollo — Experiment Framework

Apollo is the experiment layer **inside Mars**. Where Mars scores a single
agent run, Apollo runs a controlled A/B(/C) comparison and answers:

> "Did experimental strategy A outperform baseline strategy B?"

with a reproducible, statistically-grounded verdict.

## How it fits the four systems

```text
Cortex   — memory / retrieval (the experimental variable lives here)
AutoDev  — agent execution (outcome depends on retrieved context)
Mars     — evaluation + scoring (per-run score)
Apollo   — experiment control, trials, statistics, verdict   ← this module
Sentinel — policy / audit (future; wired via PolicyHook)
```

Mars still does not generate context or execute tasks. Apollo only *sequences*
Cortex and AutoDev under different conditions and measures the results. In the
mock path the providers are `MemoryAwareCortexProvider` / `MemoryAwareAutoDevProvider`;
in production they are MCP clients that satisfy the same interfaces.

## The first experiment: `salience-memory`

**Research question:** can memory weighting improve long-horizon agent task
performance compared to similarity-only retrieval?

| Arm | Strategy | Retrieval score |
| --- | --- | --- |
| `baseline-similarity` (baseline) | `SimilarityOnlyStrategy` | `similarity` |
| `salience-weighted` (experimental) | `SalienceWeightedStrategy` | weighted blend of `similarity`, `importance`, `recency`, `frequency` |

The causal chain the experiment exploits:

```text
retrieval strategy -> top-k memories -> context relevance (recall@k)
                   -> agent success probability -> Mars composite score
```

## Why the result is trustworthy (not rigged)

- **Paired design.** Each `(case, trial)` sample uses the *same* seeded AutoDev
  "luck" across arms (the roll is seeded by agent/case/trial, never by the
  strategy). Arms differ only through retrieval relevance, so the per-sample
  difference isolates the strategy's effect.
- **Distribution, not a point.** Each arm runs every case across `trials` seeded
  repetitions, producing index-aligned score vectors.
- **Bootstrap CI + effect size.** `compare_arms` reports the mean difference, a
  2000-resample 95% confidence interval, and Cohen's d. The verdict is
  "significant" only when the CI excludes zero — so a strategy that carried no
  information would correctly read as "no significant difference".
- **Reproducible.** Everything is seeded; the same seed yields the same verdict.

The synthetic memory generator (`mars/memory/store.py`) is deliberately
constructed so similarity-only is *beatable but not hopeless* (it includes
"hard" relevant memories with low similarity but high importance, plus
similarity-trap distractors). The effect size is a property of that synthetic
data and is **tunable** — the framework's job is to measure whatever effect is
actually there.

## Running it

```bash
mars list-experiments
mars experiment --experiment salience-memory                 # defaults
mars experiment --experiment salience-memory --trials 25 --seed 7
```

Example verdict:

```
salience-weighted significantly outperforms baseline-similarity
Δ mean +26.2  lift +38.7%  95% CI [+18.8, +33.8]  Cohen's d 0.73
```

## Extending Apollo

- **New strategy** — subclass `mars.memory.retrieval.RetrievalStrategy`.
- **New experiment** — add a builder in `mars/apollo/registry.py` (a baseline
  arm + one or more experimental arms over chosen suites).
- **Real Cortex/AutoDev** — implement the provider interfaces; Apollo is agnostic
  to whether providers are mocks or MCP clients.
- **Sentinel** — implement `mars.apollo.hooks.PolicyHook` to enforce policy or
  emit an audit trail around every run; pass it to `ExperimentRunner(hook=...)`.

## Limitations (v1)

- Mock providers only; no real MCP transport yet.
- Single experimental arm registered; the framework supports N arms.
- Significance via bootstrap CI (no parametric test / multiple-comparison
  correction yet). See `BACKLOG.md`.

## Salience Memory v1 (retrieval-focused)

The first *real* salience experiment is **Track B** — see
`docs/SALIENCE_MEMORY_V1.md`. It uses real Cortex retrieval + mock execution and
is judged on retrieval metrics (not the agentic composite), with honest
`semantic_score: null` handling. Run it with `mars experiments run salience-memory-v1`.
