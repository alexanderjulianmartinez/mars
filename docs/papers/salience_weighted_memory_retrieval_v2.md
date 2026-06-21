# Salience-Weighted Memory Retrieval for Long-Horizon Software Agents: Retrieval Gains, Robustness, and an Honest Execution Null

**Consolidated draft (v2) — arXiv-style technical report.**
This draft covers the full experimental program (Experiments 1–5.1). It is a research
draft: claims are scoped to the evidence, and the supported and unsupported claim
lists are kept strictly separate.

**Date:** 2026-06-21
**Benchmark:** Salience Memory Benchmark v1.0.0 (`salience-memory-benchmark-v1`,
SHA256 `a464085c3daa64c97d2764c47f8758931b2a51c2adc1e143fcfc98d9faa74d59`)

---

## Abstract

Long-horizon software agents accumulate a growing store of memories — past decisions,
postmortems, conventions, and documentation that may since have gone stale. Retrieval
over this store is typically ranked by semantic similarity to the current task. We
study whether augmenting similarity with computational *salience* signals — authored
per-memory *importance* and *confidence* — improves retrieval quality, robustness, and
downstream agent behavior. We construct a frozen, hash-pinned, synthetic labeled
benchmark (30 queries, 552 memories, six adversarial categories) in which the most
semantically similar memories are deliberately distractors of low utility, defeating
similarity-only ranking. Across five studies on this single benchmark we find: (1)
importance-weighted retrieval improves recall@5 from 0.237 to 0.672 (Δ +0.435) and MRR
from 0.313 to 0.967, with paired bootstrap confidence intervals that exclude zero; (2)
the advantage degrades gracefully and monotonically as importance is corrupted toward
random, never collapsing to the similarity baseline, with ~78% of the gain attributable
to the importance signal itself; (3) raw recency is *not* a reliable signal — it helps
only when artificially aligned with relevance, hurts symmetrically when misaligned, and
is statistically neutral in a realistic regime; (4) confidence applied as a
multiplicative gate on importance rescues a new ContradictionAvoidanceRate from 0.000
to 0.964 when an important memory is wrong; and (5) in 18 real agent runs, salience-aware
retrieval improved retrieval and measurably changed the agent's behavior (it adopted the
repository's current convention over a stale one) but did **not** raise task-success.
We are explicit throughout that importance is authored and correlated with relevance by
construction (so the Experiment-1 effect is an upper bound), that the benchmark is
synthetic, and that retrieval gains do not by themselves imply agent task-success gains.
We position salience-weighted retrieval as a prioritization mechanism for memory
retrieval and report the execution result as an honest null.

---

## 1. Introduction

Agents that operate over long horizons — across many turns, files, or sessions —
accumulate memory. A coding agent maintaining a service over weeks records design
decisions, incident postmortems, naming and API conventions, and documentation that may
later become outdated. When the agent next acts, it cannot fit this entire history into a
context window, so a retrieval system selects a small subset to inject. The quality of
that selection bounds the quality of everything downstream.

The standard default is to rank candidate memories by semantic similarity to the current
task and treat the top-K as interchangeable context. This default has a known failure
mode for long-horizon memory: the memory that is *most similar* to a query is frequently
not the memory that is *most useful*. A stale documentation note about authentication is
lexically and semantically close to a new authentication task, yet acting on it is
harmful. A high-overlap distractor — text that repeats the query's vocabulary without
carrying a decision — can crowd out the one corrective record the agent actually needs.
Similarity has no way to express that some memories carry more weight than their surface
text suggests.

We investigate a narrow, practical hypothesis: **memories should not be treated as
equally important, and a retrieval ranker that incorporates salience signals beyond
similarity retrieves better.** "Salience" here is a deliberately computational notion —
not an attempt to model emotion or affect, but a set of cognitive-style scalar signals
(importance, confidence, novelty, urgency, recency) that a memory system can attach to a
record and a ranker can consume. We isolate **importance** as the primary signal,
**confidence** as a gating signal, and treat **recency** as a candidate signal that we
test and ultimately reject.

This paper consolidates a five-experiment program. The narrative is deliberately
self-critical: each experiment after the first exists to attack a weakness of the
result before it.

> Importance helps retrieval (§5) → and survives noise (§6) → recency does not earn a
> place (§7) → confidence rescues contradictions (§8) → and inside a real agent,
> retrieval and behavior change but task-success does not (§9).

**Contributions.**

1. **Salience Memory Benchmark v1.0.0** — a frozen, hash-pinned synthetic retrieval
   benchmark (30 queries, 552 memories, six labeled categories) engineered so that
   similarity-only ranking is actively misled by high-overlap, low-importance
   distractors. It is non-saturating, unlike the 13-memory smoke test it replaces, which
   scored recall@5 = 1.0 for every strategy.
2. **Importance-weighted retrieval evaluation** — a controlled, paired comparison of
   salience-weighted vs similarity-only retrieval over a real semantic backend (Cortex,
   Voyage embeddings), with a full retrieval metric suite and paired bootstrap
   significance testing (Experiment 1).
3. **Robustness analysis under noisy importance** — a quality sweep showing the advantage
   degrades gracefully and monotonically, attributing ~78% of the gain to the importance
   signal itself (Experiment 2).
4. **Temporal salience ablation** — an isolation of the recency term across four
   timestamp regimes, finding recency unreliable as a primary signal (Experiment 3).
5. **Confidence-gated contradiction handling** — a new ContradictionAvoidanceRate metric
   and a gated `importance × confidence` formulation that prevents important-but-wrong
   retrieval (Experiment 4).
6. **An honest real-agent execution study** — an evidential 3-arm study (18 real agent
   runs) that separates *retrieval improved + behavior changed* from *task-success
   improved*, finding the former but not the latter (Experiments 5 and 5.1).

---

## 2. Related Work

**Retrieval-augmented generation (RAG).** A large body of work injects retrieved text
into a language model's context to ground its outputs. The dominant ranking signal is
embedding similarity, optionally combined with lexical scores in hybrid rankers. Our work
is in this family but asks an orthogonal question: rather than improving the *similarity*
estimate, we add a *non-similarity* per-memory signal (importance, then confidence) to
the ranker. We do not claim hybrid sparse/dense retrieval as novel; we claim that an
authored salience term is a distinct axis.

**Agent memory systems.** Recent agent architectures maintain external memory stores with
summarization, reflection, and read/write policies, and several assign scalar scores to
memories (e.g. recency- and importance-style weights) when deciding what to surface. Our
contribution relative to this line is not the idea that memories can carry an importance
score, but a controlled, adversarial, significance-tested *evaluation* of that idea
against a real semantic baseline, together with an honest accounting of the
authored-importance ceiling and an explicit recency ablation.

**Learning-to-rank and re-ranking.** Classical learning-to-rank and neural re-rankers
optimize ranking against graded relevance. Our salience terms are closer to hand-specified
priors than learned re-rankers; we deliberately do not learn importance or confidence in
this work, and we flag learned estimation as the key open problem for real-world
applicability.

**Long-context models.** An alternative to selective retrieval is to expand the context
window and attend over more history. This trades retrieval precision for attention cost
and is complementary to ranking: even with a long window, inclusion and ordering decisions
affect what the model attends to. We do not evaluate long-context baselines.

**Attention as prioritization.** We use "attention allocation" informally to mean *which
memories a system spends its limited context budget on*. We make no claim about neural
attention mechanisms inside the model, and we avoid any cognitive or affective
interpretation beyond the engineering one: salience is a prioritization prior over a
memory store.

We are cautious about novelty. The constituent ideas — similarity ranking, scalar memory
importance, adversarial retrieval benchmarks — exist. What we offer is a clean, frozen,
significance-tested measurement of importance and confidence under controlled conditions,
with ceiling effects made explicit, plus an honest execution null.

---

## 3. Salience-Weighted Retrieval

### 3.1 Setup and notation

For a query *q* and a candidate memory *m* from the per-query retrieved pool, a ranking
strategy assigns a scalar score *s(q, m)*; memories are returned in descending score order
and the top-K are evaluated. All strategies re-rank the **same** retrieved pool, so the
comparison isolates the ranking function, not first-stage embedding recall.

Each memory carries: `sim(q, m) ∈ [0, 1]` (semantic similarity from the embedding
backend), `imp(m) ∈ [0, 1]` (authored importance), `conf(m) ∈ [0, 1]` (authored
confidence), `rec(m) ∈ [0, 1]` (recency from write time), and `freq(m) ∈ [0, 1]`
(access-frequency). The benchmark also labels `novelty` and `urgency`, which are not
consumed by the strategies evaluated here.

### 3.2 Baseline: similarity-only

$$ s_{\text{sim}}(q, m) = \mathrm{sim}(q, m) $$

This is the standard RAG ranker and the control condition.

### 3.3 Candidate: salience-weighted (v1)

$$ s_{\text{sal}}(q, m) = w_s\,\mathrm{sim}(q,m) + w_i\,\mathrm{imp}(m) + w_r\,\mathrm{rec}(m) + w_f\,\mathrm{freq}(m), $$

with non-negative weights normalized to sum to 1. We use the default
$(w_s, w_i, w_r, w_f) = (0.40, 0.30, 0.20, 0.10)$. Similarity remains the largest single
term; importance is the second-largest and is the term that can lift a low-similarity but
consequential memory above a high-similarity distractor.

### 3.4 Confidence-gated importance (v2)

Experiment 4 motivates a confidence term applied not additively but as a **multiplicative
gate** on importance:

$$ \text{effective\_importance}(m) = \mathrm{imp}(m) \times \mathrm{conf}(m), \qquad
   s_{\text{gated}}(q, m) = 0.65\,\mathrm{sim}(q,m) + 0.35\,\big(\mathrm{imp}(m)\times\mathrm{conf}(m)\big). $$

We compare this against an additive comparator
$0.65\,\mathrm{sim} + 0.25\,\mathrm{imp} + 0.10\,\mathrm{conf}$ in §8.

### 3.5 Which signals were actually evaluated

| Signal | In a formula | Role in the program |
| --- | --- | --- |
| similarity | yes (both) | baseline and shared first term |
| **importance** | yes (v1, v2) | **primary differentiating signal** (§5, §6) |
| **confidence** | yes (v2 gate) | **gating signal** — decisive under contradiction (§8) |
| recency | yes (v1) | candidate signal, **tested and rejected** (§7) |
| frequency | yes (v1) | inert under the benchmark's simultaneous seeding |
| novelty / urgency | no | authored but not consumed |

A load-bearing clarification: in Experiment 1, recency and frequency are *constant across
each query's pool* (all memories are seeded simultaneously, access counts are uniform), so
the operative contrast there is **similarity-only vs similarity-plus-importance**. We
retain the four-term formula because it is the deployed strategy and because recency is
studied directly in §7.

---

## 4. Experimental Framework

### 4.1 Infrastructure

The evaluation uses systems with a hard ownership boundary. **Cortex** owns memory and
retrieval: storage, embeddings, semantic retrieval, salience metadata, ranking
explanations; it serves the real semantic baseline via Voyage `voyage-3-lite` embeddings
(confirmed live, HTTP 200 per memory). **Mars** owns experimentation: it executes the
benchmark, applies ranking strategies, computes metrics, runs significance tests, and
produces reports; it does not generate context or execute tasks. **AutoDev** owns agent
execution and is exercised only in §9. **Sentinel** provides auditability/provenance and is
a reserved extension point. *(Figure 1: system architecture; Figure 2: retrieval pipeline.)*

An honesty constraint is enforced in the framework: if the backend cannot supply semantic
scores (embeddings disabled → `semantic_score: null`), the run is flagged and the report
is forbidden from claiming a semantic-vs-salience result. All retrieval results below were
produced with `semantic_score` verified non-null.

### 4.2 Benchmark corpus

Salience Memory Benchmark v1 is a synthetic, labeled retrieval benchmark of 30 queries and
552 memories (~18/query) across six categories *(Figure 3; Table 1)*. Each query has
exactly one *target* memory, a set of *relevant* support memories, and a controlled pool
of adversarial memories. Gold relevance is explicit per query, so ranking and coverage are
both measurable.

| Category | Count | Role |
| --- | ---: | --- |
| `target` | 30 | One primary memory per query (gold target). |
| `relevant` | 102 | Helpful support memories. |
| `distractor` | 210 | High overlap, low utility; engineered to mislead similarity. |
| `stale` | 90 | Previously useful, now outdated. |
| `contradictory` | 30 | Conflict with the truth. |
| `low_confidence` | 90 | Possibly incorrect (low authored confidence). |
| **Total** | **552** | 30 queries. |

The corpus is **adversarial by construction**: distractors are written to be *semantically
closer* to the query than the truly relevant memories while carrying low importance. This
is the long-horizon failure mode the study targets, and it is what makes the benchmark
discriminating — an earlier 13-memory smoke test saturated at recall@5 = 1.0 for every
strategy. The corpus is authored reproducibly by a committed generator and is frozen and
hash-pinned (v1.0.0, SHA256 `a464085c…`); bytes are never silently mutated, and
`mars corpus verify-frozen` plus a CI check guard the invariant.

### 4.3 Metrics

For gold set *G(q)* and ranked output, averaged over the 30 queries: **Recall@K** /
**Precision@K** (coverage of *G(q)* in the top K), **MRR** (mean reciprocal rank of the
target), **nDCG@K** (graded ranking quality), **TargetFound@K** (fraction of queries whose
single target appears in the top K), and **ContextEfficiency@K** (fraction of the top-K
budget spent on gold-relevant memories). Experiment 4 adds **ContradictionAvoidanceRate
(CAR)**: over contradiction-eligible queries (28/30), the fraction where the correct target
outranks *every* obsolete contradictory memory.

### 4.4 Statistical testing

Significance is a **paired bootstrap** (10,000 resamples) over the 30-query distribution:
we resample queries with replacement, recompute per-strategy means, and report the 95% CI
of the difference (salience − baseline). Because both strategies re-rank the same pool per
query, the comparison is naturally paired; we also report per-query win/tie/loss tallies.
Retrieval is deterministic given fixed embeddings, so the reported uncertainty is over the
query distribution, not run-to-run noise. Experiments 2–4 reuse a committed real-retrieval
cache so their sweeps are offline and deterministic; Experiment 2 uses 25 seeds/level.

---

## 5. Experiment 1 — Salience Retrieval

**Question.** Does salience-weighted retrieval beat semantic-similarity-only retrieval?

**Setup.** Real Cortex retrieval over MCP with Voyage `voyage-3-lite` embeddings; mock
execution (retrieval-only). Baseline `similarity_only`; candidate `salience_weighted_v1`
with weights (0.40, 0.30, 0.20, 0.10).

**Results** *(Table 3; Figure 4).*

| Metric | similarity_only | salience_weighted_v1 | Δ |
| --- | ---: | ---: | ---: |
| recall@1 | 0.067 | 0.933 | +0.867 |
| recall@5 | 0.237 | 0.672 | **+0.435** |
| recall@10 | 0.761 | 0.931 | +0.169 |
| MRR | 0.313 | 0.967 | **+0.654** |
| nDCG@5 | 0.184 | 0.714 | **+0.531** |
| TargetFound@3 | 0.367 | 1.000 | +0.633 |
| TargetFound@5 | 0.667 | 1.000 | +0.333 |
| ContextEfficiency@5 | 0.200 | 0.567 | +0.367 |

Paired significance: recall@5 +0.435 (95% CI [+0.367, +0.502], 29/1/0 win/tie/loss);
nDCG@5 +0.531 (95% CI [+0.474, +0.583], 30/0/0). Both intervals exclude zero by a wide
margin; every metric improves.

**Mechanism (verified live)** *(Figure 9).* On the migration query, the top semantic
matches are three distractors (sim ≈ 0.77–0.79, importance ≈ 0.04–0.07) and a contradictory
memory, burying the target at rank 6. The importance term (relevant ≫ distractor by
construction) lifts the relevant memories above the distractors, moving the target to the
top. This is the corpus's designed mechanism operating as intended, not a metric artifact.

**Finding.** Salience-weighted retrieval clearly and significantly improves both ranking
and coverage on a non-saturating benchmark with a real semantic baseline. The effect size
is an **upper bound**: importance is an authored oracle here (relevant high, distractors
low). Recency and frequency contribute nothing (all memories seeded at once) — the entire
win is importance-driven, which §6 then stress-tests.

---

## 6. Experiment 2 — Noisy Importance

**Question.** How much of the win survives when importance is noisy rather than a clean
oracle? *(This section exists to answer the circularity objection to §5.)*

**Setup.** Same corpus and real retrieval, with importance degraded by a shuffle model (a
fraction `1−quality` of each pool's importance values permuted among themselves) across a
quality grid 1.00 → 0.00, 25 seeds/level. Importance is corrupted *post-retrieval* (it
never affects the embeddings or the retrieved pool), faithful to re-seeding Cortex with
corrupted labels. The oracle level reproduces Experiment 1 exactly, validating the
pipeline.

**Results** *(Table 4a; Figure 5).*

| importance quality | recall@5 | Δ recall@5 (95% CI) | MRR |
| --- | ---: | --- | ---: |
| 1.00 (oracle) | 0.672 | +0.435 [+0.370, +0.503] | 0.967 |
| 0.75 | 0.593 | +0.356 [+0.302, +0.414] | 0.864 |
| 0.50 | 0.506 | +0.269 [+0.218, +0.322] | 0.746 |
| 0.25 | 0.420 | +0.183 [+0.142, +0.224] | 0.584 |
| 0.00 (scrambled) | 0.330 | +0.094 [+0.050, +0.139] | 0.423 |

**Finding.** Degradation is **graceful and monotonic** — there is no cliff, and every CI
excludes zero, so the salience arm beats plain semantic retrieval at every tested
importance quality. The honest measure of the importance *signal's* contribution is
oracle − scrambled (recall@5 0.672 → 0.330 = **+0.341**), i.e. ~78% of the advantage is
carried by the importance signal itself; the residual q=0 edge is the stochastic
perturbation breaking this corpus's adversarial similarity ordering, not importance
information. An importance-ablated floor (importance weight zeroed) collapses exactly onto
the similarity baseline (0.237), confirming that all of salience's *deterministic* value on
this corpus comes from importance.

**Decision.** Salience weighting is robust to substantial importance noise; it does not
need a near-perfect importance estimate to pay off. This bounds, but does not eliminate,
the §5 ceiling caveat: the effect is not purely an artifact of clean labels.

---

## 7. Experiment 3 — Temporal Salience

**Question.** Does recency improve or degrade salience-weighted retrieval, and does it earn
a place as a core signal?

**Setup.** Reuses the committed real-retrieval cache (nothing re-embedded); only synthetic
timestamps and strategy vary. Four regimes: **A uniform** (control), **B recency-aligned**
(relevant newer), **C recency-misaligned** (distractors newer), **D mixed-realistic** (ages
independent of relevance). The recency *marginal* is isolated as
`importance_plus_recency − sim_plus_importance` (identical similarity/importance weights;
the delta is the 0.10 recency term alone).

**Results — isolated recency marginal (recall@5, paired 95% CI)** *(Table 4b; Figure 6).*

| Regime | marginal | verdict |
| --- | --- | --- |
| A uniform | +0.000 [+0.000, +0.000] | neutral (control passes) |
| B aligned | +0.262 [+0.210, +0.316] | recency **helps** |
| C misaligned | −0.206 [−0.262, −0.155] | recency **hurts** |
| D mixed realistic | +0.015 [−0.025, +0.055] | **neutral** (CI spans 0) |

`importance_only` is **regime-invariant** at recall@5 0.985 / MRR 1.000 across all four
regimes — time neither helps nor harms importance.

**Finding.** Raw recency helps only in the artificial aligned regime, hurts by a nearly
symmetric amount when misaligned, and is statistically neutral in the realistic mixed
regime. Importance dominates everywhere. The safest temporal strategy is a short-half-life
decay (≈7 days) — the only temporal arm that significantly beats the similarity baseline in
*every* regime — but it never beats `importance_only`.

**Decision.** Recency is **not promoted** to a core signal. At best it is an optional
short-decay, low-weight, importance-gated add-on. Reporting this negative result as a design
decision is itself a contribution: a plausible signal that fails its ablation is removed.

---

## 8. Experiment 4 — Confidence & Contradiction

**Question.** Can confidence-aware retrieval help agents avoid outdated, incorrect, or
contradictory memories — especially when an important memory is wrong?

**Setup.** Reuses the cached pools joined to the corpus by content to recover each memory's
authored `category` + `confidence`. Five confidence regimes, including an adversarial **E
"important-but-wrong"** regime where the obsolete memory is forced to be *slightly more
important than the target* but low-confidence. New metric: ContradictionAvoidanceRate (CAR)
over the 28/30 contradiction-eligible queries. Compares additive confidence
(0.65·sim + 0.25·imp + 0.10·conf) vs **gated** confidence (0.65·sim + 0.35·(imp × conf)).

**Results — ContradictionAvoidanceRate** *(Table 4c; Figure 7).*

| Strategy | A | B | C | D | E (important-but-wrong) |
| --- | ---: | ---: | ---: | ---: | ---: |
| `similarity_only` | 0.643 | 0.643 | 0.643 | 0.643 | 0.643 |
| `importance_only` | 1.000 | 1.000 | 1.000 | 1.000 | **0.000** |
| `confidence_only` | 0.479 | 1.000 | 1.000 | 1.000 | 1.000 |
| `importance × confidence` (gated) | 0.964 | 0.964 | 0.964 | 0.964 | **0.964** |

The isolated confidence marginal (recall@5) is positive and significant wherever confidence
is informative (B +0.265, C +0.169, D +0.108, E +0.146) and ≈0 in the control (A +0.010).

**Finding.** In the easy regimes (A–D), importance already achieves perfect avoidance, so
confidence is redundant. In the adversarial regime E, `importance_only` collapses to **CAR
0.000** (it ranks the important-but-wrong memory first in all 28 queries) — and
**confidence-gating restores avoidance to 0.964**, the only importance-based strategy robust
across *every* regime. Confidence's unique, non-redundant value appears exactly when
importance and confidence diverge.

**Decision.** Confidence **joins importance as a core signal, in gated (multiplicative)
form** (`effective_importance = importance × confidence`). It is redundant-but-harmless when
the two agree and decisive when they diverge. Recency stays out. The *form* of the signal
matters: the multiplicative gate is what produces robustness; an additive term does not.

---

## 9. Experiments 5 & 5.1 — Execution Impact

### 9.1 Experiment 5 (methodology milestone)

We wired Mars to drive a real AutoDev agent over MCP across all three retrieval arms (A
`similarity_only`, B `sim_importance`, C `salience_v2`), injecting per-arm context via
`start_run(retrieval_strategy=…, context_package_id=…)`. A Phase-3 divergence gate confirmed
the arms inject **different** contexts (`arms_distinct=true`, `valid_comparison=true`).
Retrieval improved as predicted inside the real pipeline (recall@5 0.50 → 0.83, MRR 0.28 →
0.57, target-found 0.50 → 1.00, CAR 0.00 → 1.00 over 18 runs, ≈$1.55). However,
**task-success floored at 0.000 for all three arms** (the dry-run coder solved no task
regardless of context). With zero success variance, the retrieval↔success correlation was
trivially 0.000 and *uninformative* — not evidence of "no relationship." Experiment 5 thus
established the pipeline but could not answer the execution-impact question, motivating a
purpose-built, less-floored benchmark.

### 9.2 Experiment 5.1 (first evidential result)

**Setup.** A purpose-built, memory-dependent benchmark: six tasks in a small,
dependency-free repo, each requiring knowledge that lives in a decision/postmortem/convention
not visible in the edited file — or actively contradicted by a stale doc still present in the
repo. Each task gets an isolated 5-record store, reseeded before every run: one **corrective**
record (importance 3.5, old, deliberately low term-overlap) plus four recent, higher-overlap
distractors. A pure-similarity ranker buries the corrective record; importance-aware rankers
surface it. 18 real AutoDev runs (6 tasks × 3 arms × 1 trial), dry-run, `retrieval_limit=3`,
≈$1.3. Success oracle = the task's targeted test with the test file forbidden; Mars restores
forbidden files before validating, so success reflects the agent's implementation against a
fixed oracle.

**Results** *(Table 5; Figure 8).*

| Arm | Task success | recall@5 | Target found | MRR | Right-approach |
| --- | ---: | ---: | ---: | ---: | ---: |
| A — similarity_only | 0.333 | 0.000 | 0.000 | 0.000 | 0.833 |
| B — sim+importance | 0.333 | 0.833 | 0.833 | 0.556 | 1.000 |
| C — salience_v2 | 0.333 | 0.833 | 0.833 | 0.556 | 1.000 |

Paired Δ success vs A: B +0.000 (6 ties), C +0.000 (6 ties). At `limit=3` the similarity
arm **never** injects the corrective record (recall/target-found 0.0), while both importance
arms inject it ~5/6 of the time; B and C are identical because the recency term in
`salience_v2` reorders but does not change the top-3 set (consistent with §7).

**Behavioral analysis.** The clearest case is `bench-4` (protect-admin-reports), whose
`docs/AUTH.md` is stale. Arm A, deprived of the corrective memory, trusted the out-of-date
doc and implemented **session-cookie** auth; arms B/C, given the corrective memory,
implemented the repo's current **JWT** convention. Across the suite, the right-approach rate
is **1.00 for B/C vs 0.83 for A** — a genuine, observed retrieval→behavior effect. It was
simply not enough to pass the stricter, multi-assertion oracle within the iteration budget.
The contradiction finding from §8 also replicated at the agent layer: the similarity arm's
dominant failure mode is retrieving a contradiction and acting on it (4/6 tasks), versus 1/6
for each importance arm.

**Outcome.** **Outcome B: retrieval improves, behavior changes, task-success does not.** The
recall↔success correlation is slightly **negative** (Pearson −0.32), an artifact of *which*
tasks are winnable: the 2 passing tasks are discoverable-from-code (the similarity arm passes
them with recall 0), while the tasks where retrieval helped most (the contradiction tasks)
are also the hardest to implement and fail anyway. Downstream pass/fail here is dominated by
implementation quality and a per-task difficulty floor (4/6 tasks fail in every arm at
`max_iterations=3`), not by which memories were retrieved.

We **do not** claim salience improves agent task outcomes. The supported claim is: salience
improves retrieval and steers the agent toward the repository's current conventions; on this
benchmark that did not yet raise task-success.

---

## 10. Discussion

**Salience as prioritization.** Across the retrieval studies, a small number of
non-similarity scalars reorder a pool that similarity has mis-ordered, surfacing
consequential-but-unremarkable memories and demoting high-overlap distractors. In the
language of attention allocation, the agent spends more of its limited context budget on
memories that matter. We make no cognitive or affective claim beyond this.

**Supported vs unsupported claims.** We keep these strictly separate.

*Supported:* salience improves retrieval quality (§5); the gain is robust to importance
noise (§6); recency is weak and not promoted (§7); confidence, as a gate, prevents
contradiction failures (§8); improved retrieval changes agent behavior (§9.2).

*Unsupported:* salience improves agent task-success; salience improves production outcomes;
salience generalizes beyond the tested corpus, weight set, and embedding model.

**Threats to validity.** The most serious is *construct circularity*: importance and
relevance are correlated by authoring, so §5's effect is an upper bound — §6 bounds but does
not eliminate this. The corpus is synthetic; external validity is unestablished. Execution is
underpowered (a floor in §9.1; single trial, 6 tasks, dry-run in §9.2), so the execution
study has little power to detect a task-success gain even if one existed — this is the
central caveat on every execution sentence. Absolute blend numbers are corpus-specific: one
weight set, one embedding model. *(Table 6.)*

---

## 11. Limitations

- **Synthetic benchmark** authored by hand, not sampled from production memory traces.
- **Authored importance** (correlated with relevance by construction) → §5 effect is an
  upper bound.
- **Authored confidence**; the decisive §8 regime E is a synthetic stress test.
- **Recency/frequency inert in §5** (simultaneous seeding); studied directly in §7.
- **Execution underpowered:** §9.1 floored at 0% success; §9.2 is a single trial over 6
  tasks, dry-run, with `review_passed` unusable (forbidden-file edits) so success uses
  restored-oracle validation; the §9.2 contrast exists only at `retrieval_limit=3`.
- **Single embedding model** (`voyage-3-lite`) and **single weight set** throughout.

---

## 12. Conclusion

We asked whether authored salience signals improve memory retrieval for long-horizon agents
over similarity-only ranking. On a frozen, adversarial, synthetic benchmark with a real
semantic baseline, importance-weighted retrieval improved every retrieval metric we measured
(recall@5 +0.435, MRR 0.31 → 0.97), the advantage survived heavy importance noise
(never collapsing to the baseline, ~78% attributable to the importance signal), recency
failed its ablation and was rejected, and confidence applied as a multiplicative gate
rescued contradiction avoidance from 0.000 to 0.964 when an important memory was wrong.
Inside a real agent pipeline over 18 runs, salience-aware retrieval improved retrieval and
changed the agent's behavior — but did not raise task-success.

We keep the conclusion proportional to the evidence. Salience-weighted retrieval is a
prioritization mechanism for attention allocation over a memory store; its retrieval and
behavioral benefits are demonstrated under controlled conditions, and its effect on
downstream agent task-success remains an open, honestly-reported null. The retrieval
question is well characterized; the open frontier is execution.

---

## Figures

See `docs/papers/figures/` (rendered SVGs for the data figures) and `FIGURE_PLAN.md` for
full specifications.

- **Figure 1 — System Architecture** (diagram).
- **Figure 2 — Retrieval Pipeline** (diagram).
- **Figure 3 — Benchmark Composition** — `figures/figure3_corpus_composition.svg`.
- **Figure 4 — Experiment 1 Results** — `figures/figure4_exp1_results.svg`.
- **Figure 5 — Noisy Importance** — `figures/figure5_noisy_importance.svg`.
- **Figure 6 — Temporal Salience** — `figures/figure6_temporal_salience.svg`.
- **Figure 7 — Confidence / Contradiction (CAR)** — `figures/figure7_confidence_contradiction.svg`.
- **Figure 8 — Execution Impact** — `figures/figure8_execution_impact.svg`.
- **Figure 9 — Retrieval Ranking Example** — `figures/figure9_ranking_example.svg`.
- **Figure 10 — Research Program Overview** (diagram).

## Tables

Publication-ready tables are in `TABLE_PLAN.md`: Table 1 (corpus statistics), Table 2
(experiment summary), Table 3 (Experiment 1 metrics), Tables 4a–4c (noisy importance /
temporal / CAR), Table 5 (execution results), Table 6 (threats to validity), Table 7
(future research).

## Appendix A — Benchmark Specification

Salience Memory Benchmark **v1.0.0** (`salience-memory-benchmark-v1`), SHA256
`a464085c3daa64c97d2764c47f8758931b2a51c2adc1e143fcfc98d9faa74d59`. 30 queries, 552
memories, six categories (Table 1), exactly one `target` per query. The corpus is
**frozen and hash-pinned**: byte changes are forbidden in place; a bug fix requires a new
`v1.0.x`, a redesign a new `v2`. Integrity is checked by
`mars corpus verify-frozen salience-memory-benchmark-v1` and a CI regression test. Gold
relevance is explicit per query, enabling coverage metrics (recall/precision), not only
ranking metrics. Manifest: `experiments/corpus/salience-memory-v1.manifest.yaml`.

## Appendix B — Corpus Schema

Each **memory** record carries: `id`; `content`; `category ∈ {target, relevant,
distractor, stale, contradictory, low_confidence}`; authored salience scalars
`importance`, `novelty`, `urgency`, `confidence ∈ [0, 1]`; and a similarity provenance
populated at retrieval time by the embedding backend. Each **query** carries an `id` and a
gold map `{relevant: set[memory_id], target: memory_id}`. The corpus is authored
reproducibly by `experiments/corpus/generate_expanded.py` + `scenarios_data.py` and loaded
via `mars/memory/expanded_corpus.py`. Gold labels: `experiments/corpus/salience-memory-v1.gold.json`.

## Appendix C — Metric Definitions

For a query *q* with gold set *G(q)*, ranked output, and top-*K* prefix, averaged over the
30 queries:

- **Recall@K** = |G(q) ∩ top-K| / |G(q)|.
- **Precision@K** = |G(q) ∩ top-K| / K.
- **MRR** = mean over queries of 1 / rank(target), where rank(target) is the position of
  the query's single target memory.
- **nDCG@K** = DCG@K / IDCG@K, with DCG@K = Σ_{i=1..K} rel_i / log₂(i + 1) and IDCG@K the
  DCG of the ideal ordering.
- **TargetFound@K** = mean of 1[target ∈ top-K].
- **ContextEfficiency@K** = fraction of the injected top-K budget occupied by
  gold-relevant memories (wasted-context measure).
- **ContradictionAvoidanceRate (CAR)** = over the contradiction-eligible queries (28/30),
  the fraction where the correct target outranks **every** obsolete contradictory memory.

Implementation: `mars/memory/metrics.py`.

## Appendix D — Bootstrap Methodology

Significance is a **paired bootstrap** with 10,000 resamples over the 30-query
distribution. Each resample draws 30 queries with replacement, recomputes the per-strategy
metric mean, and records the difference (salience − baseline); we report the 2.5/97.5
percentiles as the 95% CI of the difference. Because both strategies re-rank the same
per-query pool, the comparison is paired by query; we also report per-query win/tie/loss
tallies. Retrieval is deterministic given fixed embeddings, so the reported uncertainty is
over the query distribution, not run-to-run noise. Experiment 2 additionally averages over
25 seeds per importance-quality level; Experiments 3–4 average over seeds per regime. The
paired-arm comparison logic lives in Apollo (`mars/apollo/`, `compare_arms`).

## Appendix E — Reproduction Instructions

The committed retrieval cache (`experiments/cache/`) makes Experiments 2–4 fully offline
and deterministic; only Experiment 1 (live Voyage) and Experiment 5.1 (paid AutoDev)
require credentials.

```bash
mars corpus verify-frozen salience-memory-benchmark-v1            # integrity
mars experiments run salience-memory-v1                           # Exp 1 (live Voyage)
python experiments/run_noisy_importance.py --cache-only           # Exp 2 (offline)
python experiments/run_temporal_salience.py                       # Exp 3 (offline)
python experiments/run_confidence_contradiction.py                # Exp 4 (offline)
python experiments/launch_exec_impact_5_1.py --real-autodev --dry-run \
    --issues-file experiments/execution_impact_5_1/issues.yaml \
    --retrieval-limit 3 --experiment salience-memory-execution-impact-5-1   # Exp 5.1 (paid)
```

Result artifacts (source of truth): `mars-experiments/*.json`.

## Appendix F — Configuration

Python 3.12 with uv. Core dependencies: Typer (CLI), Pydantic (models), SQLAlchemy + SQLite
(storage), Rich (output), Jinja2 (reports), PyYAML (definitions). The real
Cortex/AutoDev providers use an optional `mcp` extra, imported lazily; Mars runs end-to-end
on mocks without it. Providers auto-select the real implementation when `MARS_CORTEX_MCP_*`
/ `MARS_AUTODEV_MCP_*` are set, else fall back to mocks, independently. Runs persist to
SQLite (`mars.db`, gitignored).

## Appendix G — Weighting Parameters

- **`similarity_only`** (baseline): s(q, m) = sim(q, m).
- **`salience_weighted_v1`**: normalized blend with (w_sim, w_imp, w_rec, w_freq) =
  (0.40, 0.30, 0.20, 0.10). Recency and frequency are inert in Experiment 1 (constant
  across each pool under simultaneous seeding).
- **Confidence-gated (Experiment 4)**: s = 0.65·sim + 0.35·(importance × confidence).
- **Additive comparator (Experiment 4)**: s = 0.65·sim + 0.25·importance + 0.10·confidence.

A single weight set was used throughout (a disclosed limitation). Implementation:
`mars/memory/retrieval.py`, `mars/memory/salience_v1.py`.

## Appendix H — Embedding Configuration

Cortex retrieval over MCP with Voyage `voyage-3-lite` embeddings, confirmed live (HTTP 200
per memory). The `semantic_score` field is verified non-null before any
semantic-vs-salience claim is reported (the framework's honesty constraint). Retrieval is
deterministic given fixed embeddings. One embedding model was evaluated (a disclosed
limitation).

## Appendix I — Threats to Validity (extended)

Consolidated from §10–§11. (1) **Construct circularity**: authored importance is correlated
with relevance, so §5's effect is an upper bound; §6 bounds but does not remove this. (2)
**Synthetic corpus**: hand-authored, not sampled from production traces; external validity
open. (3) **Authored confidence**: the decisive §8 regime E is a synthetic stress test. (4)
**Recency/frequency inert in §5** under simultaneous seeding; studied directly in §7. (5)
**Execution underpowered**: §9.1 floored at 0% success (correlation trivially 0, not
"no relationship"); §9.2 is a single trial over 6 tasks, dry-run, with `review_passed`
unusable (forbidden-file edits) so success uses restored-oracle validation; the §9.2
contrast exists only at `retrieval_limit=3`. (6) **Single embedding model and single weight
set**: absolute blend numbers are corpus/config-specific.
