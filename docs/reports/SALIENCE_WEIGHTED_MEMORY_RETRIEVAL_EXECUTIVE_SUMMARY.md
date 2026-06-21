# Salience-Weighted Memory Retrieval for Long-Horizon Software Agents

## Executive Summary

**Date:** 2026-06-21 · **Benchmark:** Salience Memory Benchmark v1.0.0
(`salience-memory-benchmark-v1`, frozen, SHA256 `a464085c…`)
**Full report:** [SALIENCE_WEIGHTED_MEMORY_RETRIEVAL_TECHNICAL_REPORT.md](SALIENCE_WEIGHTED_MEMORY_RETRIEVAL_TECHNICAL_REPORT.md)

---

## One-Paragraph Summary

Long-horizon software agents accumulate memory — past decisions, postmortems,
conventions, and stale documentation — and depend on retrieval to surface the right
context for the task at hand. Plain semantic similarity is a weak ranker for this
job: the most similar memory is often a distractor or an outdated note. We
investigated whether *salience* signals — authored **importance** and **confidence**
attached to each memory — improve retrieval over similarity alone. We built a frozen,
adversarial benchmark and ran five experiments, including one study driving a real
software agent. Under these conditions, salience-weighted retrieval improved
retrieval quality substantially, improved avoidance of contradictory memories, and
measurably changed the agent's behavior on real tasks. A downstream improvement in
**task-success rate has not been demonstrated** and remains an open question.

---

## Why We Studied This

Most agent systems retrieve from a memory store and inject the results into the
model's context. The common default is to rank by semantic similarity and treat all
memories as roughly interchangeable. The question this program asks is narrow and
practical:

```text
Should all memories be treated equally?
```

The hypothesis is that they should not. Some memories carry more weight than their
surface text suggests:

* important architectural decisions
* incident root causes
* migration guidance
* corrected historical decisions that override stale documentation

We treat **salience** as prioritization — a way to rank memories by how much they
should matter for a decision, not just how lexically close they are to the query. The
practical risk we target is the case where the most *similar* memory is also the most
*misleading*: a stale doc or a confidently-worded distractor that an
importance-blind ranker puts first.

---

## What We Built

The work spans four systems with strict ownership boundaries; this program touches
all four but the experiments live in the evaluation layer.

**Cortex** — the memory and retrieval system. It owns context generation,
knowledge storage, and the retrieval that ranks memories for a query. The salience
signals (importance, confidence) and the embeddings used as the semantic baseline
come from here.

**Mars** — the benchmark and experimentation platform, and the home of this research.
Mars defines the benchmark, runs the controlled A/B experiments over seeded trials,
computes retrieval and execution metrics, and reports results. It consumes Cortex and
AutoDev through provider interfaces; it does not generate context or execute tasks
itself.

**AutoDev** — the agent execution runtime. It owns the coding agent, its workspaces,
running tests, and git operations. In the execution study, Mars drives real AutoDev
runs and injects different retrieval strategies per arm.

**Sentinel** — the auditability and governance layer (policy, trust, audit). It is
not yet built; the architecture reserves extension points for it.

---

## Benchmark

**Salience Memory Benchmark v1.0.0** is a synthetic, labeled retrieval benchmark of
**30 queries** and **552 memories** (~18 per query) across six labeled categories.
Each query has exactly one *target* memory plus a controlled mix of supporting and
adversarial memories:

| Category | Count | Role |
| --- | --- | --- |
| `target` | 30 | The one memory each query should retrieve. |
| `relevant` | 102 | Helpful support memories (count toward gold). |
| `distractor` | 210 | High overlap, low utility — engineered to mislead similarity. |
| `stale` | 90 | Previously useful, now outdated. |
| `contradictory` | 30 | Conflict with the truth. |
| `low_confidence` | 90 | Possibly incorrect (low authored confidence). |

The benchmark exists because the earlier 13-memory smoke test **saturated** —
recall@5 = 1.0 for every strategy, so it could not discriminate. v1.0.0 is
**adversarial by design**: distractors are written to be *semantically closer* to the
query than the truly relevant memories, but carry low importance. This is what makes
salience measurable rather than free. The corpus is frozen and hash-pinned; fixes
require a new version and the bytes are never silently mutated.

---

## Key Findings

### Finding 1 — Importance improves retrieval

On the adversarial benchmark with a real semantic baseline (Voyage embeddings),
importance-weighted retrieval beat similarity-only retrieval by a large, significant
margin.

| Metric | similarity_only | salience_weighted_v1 | Δ |
| --- | --- | --- | --- |
| recall@5 | 0.237 | 0.672 | **+0.435** |
| MRR | 0.313 | 0.967 | **+0.654** |
| nDCG@5 | 0.184 | 0.714 | **+0.531** |

Paired bootstrap: recall@5 +0.435 (95% CI [+0.367, +0.502]); nDCG@5 +0.531 (95% CI
[+0.474, +0.583]). Both CIs exclude zero by a wide margin. Note this effect size is
an **upper bound** — importance here is an authored oracle.

### Finding 2 — Importance is robust to noisy labels

When importance was degraded from a clean oracle down to fully scrambled, the
advantage **degraded gracefully and monotonically** — there is no cliff. The salience
arm beat plain semantic retrieval at every tested importance quality (every CI
excludes zero). Isolating the importance *signal* (oracle − scrambled) shows ~78% of
the win is carried by importance itself. The practical implication: salience does not
require a near-perfect importance estimate to pay off.

### Finding 3 — Recency is weaker than expected

Isolating the recency term across four timestamp regimes:

* **helps** when recency is aligned with relevance (+0.262 recall@5),
* **hurts** by a nearly symmetric amount when misaligned (−0.206),
* is **statistically neutral** in the realistic regime where age is independent of
  relevance (+0.015, CI spans 0).

Importance was regime-invariant and dominant throughout. Raw recency is therefore
**not promoted** to a core signal; at best it is an optional short-decay, low-weight,
importance-gated add-on.

### Finding 4 — Confidence matters

In easy regimes, importance alone already achieves perfect contradiction avoidance,
so confidence is redundant. The value appears in the adversarial **"important-but-
wrong"** regime, where a memory is forced to be slightly *more important* than the
target but low-confidence. There, importance-only collapses to a
ContradictionAvoidanceRate (CAR) of **0.000** — it ranks the wrong memory first
every time. Applying confidence as a **multiplicative gate on importance**
(`effective_importance = importance × confidence`) restores CAR to **0.964**, the
only importance-based strategy robust across every regime. Confidence joins
importance as a core signal, in gated form.

### Finding 5 — Retrieval changes agent behavior

Experiment 5.1 drove **18 real AutoDev agent runs** (6 memory-dependent tasks × 3
retrieval arms, dry-run, `evidential=true`, ≈$1.3).

| Arm | Success | Recall@5 | Target Found | MRR |
| --- | --- | --- | --- | --- |
| Similarity Only | 0.333 | 0.000 | 0.000 | 0.000 |
| Similarity + Importance | 0.333 | 0.833 | 0.833 | 0.556 |
| Salience v2 | 0.333 | 0.833 | 0.833 | 0.556 |

The clearest case is `bench-4`, where the repo's `docs/AUTH.md` is stale. **Deprived
of the corrective memory, the similarity arm trusted the stale doc and implemented
session-cookie auth; given the corrective memory, both importance arms implemented
the repo's current JWT convention** (right-approach rate 1.00 for B/C vs 0.83 for A).
So: **retrieval changed, and agent behavior changed — but task-success did not move**
(0.333 in every arm; the same 2/6 tasks pass). Recall and success were even slightly
negatively correlated (Pearson −0.32), an artifact of which tasks were winnable
within the iteration budget.

---

## What We Can Claim

Within this benchmark and under these conditions, the evidence supports:

* ✓ Salience improves retrieval quality.
* ✓ Salience improves contradiction avoidance.
* ✓ Confidence is useful (as a gate on importance).
* ✓ Retrieval can change agent behavior.
* ✓ Recency should not be a primary signal.

---

## What We Cannot Claim

The evidence does **not** support:

* ✗ Improved task-success rates.
* ✗ Production impact.
* ✗ Generalization to all agents.
* ✗ Generalization beyond the tested conditions.
* ✗ Any AGI-related conclusions.

---

## Recommended Salience v2 Design

**Core signals:**

* semantic similarity
* importance
* confidence (applied as a multiplicative gate on importance)

**Not promoted:**

* raw recency

**Future candidates:**

* learned importance (an estimator replacing authored labels)
* contradiction-aware retrieval
* access-frequency / reinforcement-style weighting

---

## Limitations

These are stated plainly because the conclusions depend on them:

* **Synthetic benchmark** — authored by hand, not sampled from real production memory
  traces.
* **Authored labels** — importance and confidence are written, not learned or
  observed; importance and relevance are correlated by construction, so Finding 1 is
  an upper bound.
* **Small execution benchmark** — only 6 execution tasks, 4 of which are unwinnable by
  any arm within the iteration budget.
* **Single-trial execution study** — 6 binary outcomes per arm, model output not
  seed-pinned; the tied pass rates are coarse and underpowered.
* **Retrieval improvements exceeded execution improvements** — the central caveat:
  with low success variance, the study has little power to detect a task-success gain
  even if one existed.

---

## Next Steps

1. Public release of Salience Memory Benchmark v1.0.0.
2. Publication of the full technical report.
3. An accessible research blog write-up.
4. arXiv submission (retrieval studies plus the honest execution null).
5. A larger, less-floored execution study with multiple trials and a workable
   iteration budget.
6. Moving off the synthetic corpus toward real-world memory traces.
7. Learned salience estimation (replace authored importance with an estimator).

---

## Closing Summary

> The strongest conclusion from this work is not that salience improves agent
> performance. The strongest conclusion is that **importance and confidence
> substantially improve retrieval quality and contradiction avoidance, and that those
> retrieval improvements can measurably alter agent behavior.** Whether those
> improvements ultimately increase task-success rates remains an open question for
> future work.
