# Salience-Weighted Memory Retrieval for Long-Horizon Software Agents

**Working draft — arXiv-style technical report (v1).**
This is a research draft. Claims are scoped to the evidence; limitations are stated explicitly.

**Date:** 2026-06-21
**Benchmark:** Salience Memory Benchmark v1.0.0 (`salience-memory-benchmark-v1`,
SHA256 `a464085c3daa64c97d2764c47f8758931b2a51c2adc1e143fcfc98d9faa74d59`)

---

## Abstract

Long-horizon software agents accumulate a growing store of memories — past
decisions, postmortems, conventions, and documentation that may since have gone
stale. Retrieval over this store is typically ranked by semantic similarity to the
current task. We study whether augmenting similarity with a computational *salience*
signal — an authored, per-memory *importance* weight — improves retrieval quality.
We construct a frozen, hash-pinned, synthetic labeled benchmark (30 queries, 552
memories, six adversarial categories) in which the most semantically similar
memories are deliberately distractors of low utility, defeating similarity-only
ranking. Using real semantic retrieval (Cortex with Voyage `voyage-3-lite`
embeddings) and a paired bootstrap significance test, importance-weighted retrieval
improves recall@5 from 0.237 to 0.672 (Δ +0.435), MRR from 0.313 to 0.967
(Δ +0.654), and nDCG@5 from 0.184 to 0.714 (Δ +0.531); confidence intervals exclude
zero with 29–30 of 30 per-query wins. We are explicit that importance here is
*authored* and correlated with relevance by construction, so the measured effect is
an **upper bound** on what a learned importance estimator would achieve; that the
benchmark is synthetic; that recency and frequency contributed nothing because all
memories were seeded simultaneously; and that retrieval gains do **not** by
themselves imply downstream agent task-success gains, which we do not evaluate here.
We position salience-weighted retrieval as a *prioritization* mechanism for memory
retrieval and outline the follow-up studies — noisy importance, temporal salience,
confidence, contradiction handling, and execution impact — needed to characterize
it under realistic conditions.

---

## 1. Introduction

Agents that operate over long horizons — across many turns, files, or sessions —
accumulate memory. A coding agent maintaining a service over weeks records design
decisions, incident postmortems, naming and API conventions, and documentation that
may later become outdated. When the agent next acts, it cannot fit this entire
history into a context window, so a retrieval system selects a small subset to
inject. The quality of that selection bounds the quality of everything downstream.

The standard default is to rank candidate memories by semantic similarity to the
current task and treat the top-K as interchangeable context. This default has a
known failure mode for long-horizon memory: the memory that is *most similar* to a
query is frequently not the memory that is *most useful*. A stale documentation note
about authentication is lexically and semantically close to a new authentication
task, yet acting on it is harmful. A high-overlap distractor — text that repeats the
query's vocabulary without carrying a decision — can crowd out the one corrective
record the agent actually needs. Similarity has no way to express that some memories
carry more weight than their surface text suggests.

We investigate a narrow, practical hypothesis: **memories should not be treated as
equally important, and a retrieval ranker that incorporates a salience signal beyond
similarity retrieves better.** "Salience" here is a deliberately computational
notion — not an attempt to model emotion or affect, but a set of cognitive-style
scalar signals (importance, confidence, novelty, urgency, recency) that a memory
system can attach to a record and a ranker can consume. This first study isolates
**importance**: a scalar weight indicating how consequential a memory is,
independent of how similar it looks.

**Contributions.**

1. **Salience Memory Benchmark v1.0.0** — a frozen, hash-pinned synthetic retrieval
   benchmark (30 queries, 552 memories, six labeled categories) engineered so that
   similarity-only ranking is actively misled by high-overlap, low-importance
   distractors. The benchmark is non-saturating, unlike the 13-memory smoke test it
   replaces (which scored recall@5 = 1.0 for every strategy).
2. **A controlled, paired evaluation** of importance-weighted retrieval against a
   similarity-only baseline over a *real* semantic retrieval backend (Cortex,
   Voyage embeddings), with a full retrieval metric suite and paired bootstrap
   significance testing.
3. **An explicit characterization of what the result does and does not show** —
   in particular, that the effect size is an upper bound under authored importance,
   and that retrieval improvement is not evidence of agent task-success improvement.
4. **A reproducible evaluation framework** (Cortex for retrieval, Mars for
   experimentation and metrics) and a committed, frozen benchmark released for
   external validation.

We report a single completed retrieval study (Experiment 1). The broader research
program — noisy importance, temporal salience, confidence and contradiction
handling, and real-agent execution impact — is described in Section 7 as the
follow-up work this result motivates.

---

## 2. Related Work

**Retrieval-augmented generation (RAG).** A large body of work injects retrieved
text into a language model's context to ground its outputs. The dominant ranking
signal is embedding similarity, optionally combined with lexical scores (e.g.
BM25-style sparse retrieval) in hybrid rankers. Our work is squarely in this family
but asks an orthogonal question: rather than improving the *similarity* estimate, we
add a *non-similarity* per-memory signal (importance) to the ranker. We do not claim
hybrid sparse/dense retrieval as novel; we claim that an authored salience term is a
distinct axis from both.

**Agent memory systems.** Recent agent architectures maintain external memory stores
with summarization, reflection, and write/read policies. Several assign scalar scores
to memories (e.g. recency- and importance-style weights) when deciding what to
surface. Our contribution relative to this line is not the idea that memories can
carry an importance score, but a *controlled, adversarial, significance-tested
retrieval evaluation* of that idea against a real semantic baseline, together with an
honest accounting of the authored-importance ceiling.

**Learning-to-rank and re-ranking.** Classical learning-to-rank and neural
re-rankers optimize ranking against graded relevance. Our salience term is closer to
a hand-specified prior than a learned re-ranker; we deliberately do not learn
importance in this study, and we flag learned-importance estimation as the key open
problem that determines real-world applicability.

**Long-context models.** An alternative to selective retrieval is to expand the
context window and let the model attend over more history. This trades retrieval
precision for attention cost and is complementary to, not a substitute for, ranking:
even with a long window, ordering and inclusion decisions affect what the model
attends to. We do not evaluate long-context baselines here.

**Attention as prioritization.** We use "attention allocation" informally to mean
*which memories a system spends its limited context budget on*. We make no claim
about neural attention mechanisms inside the model, and we avoid any cognitive or
affective interpretation beyond the engineering one: salience is a prioritization
prior over a memory store.

We are cautious about novelty. The constituent ideas — similarity ranking, scalar
memory importance, adversarial retrieval benchmarks — exist. What we offer is a
clean, frozen, significance-tested measurement of the importance signal's marginal
value under controlled conditions, with the ceiling effects made explicit.

---

## 3. Salience-Weighted Retrieval

### 3.1 Setup and notation

For a query *q* and a candidate memory *m* drawn from the per-query retrieved pool,
a ranking strategy assigns a scalar score *s(q, m)*; memories are returned in
descending score order and the top-K are evaluated. Both strategies below re-rank
the **same** retrieved pool, so the comparison isolates the ranking function, not the
first-stage recall of the embedding store.

Each memory carries:

- `sim(q, m) ∈ [0, 1]` — semantic similarity from the embedding backend.
- `imp(m) ∈ [0, 1]` — authored importance.
- `rec(m) ∈ [0, 1]` — a recency term derived from write time.
- `freq(m) ∈ [0, 1]` — an access-frequency term.

The benchmark additionally labels each memory with `confidence`, `novelty`, and
`urgency` for downstream studies; these are not consumed by the strategies evaluated
in this paper.

### 3.2 Baseline: similarity-only

$$ s_{\text{sim}}(q, m) = \mathrm{sim}(q, m) $$

This is the standard RAG ranker and the control condition.

### 3.3 Candidate: salience-weighted (v1)

$$ s_{\text{sal}}(q, m) = w_s\,\mathrm{sim}(q,m) + w_i\,\mathrm{imp}(m) + w_r\,\mathrm{rec}(m) + w_f\,\mathrm{freq}(m) $$

with non-negative weights normalized to sum to 1. We use the default weights

$$ (w_s, w_i, w_r, w_f) = (0.40,\ 0.30,\ 0.20,\ 0.10), $$

which already sum to 1. Similarity remains the largest single term; importance is
the second-largest and is the term that can lift a low-similarity but consequential
memory above a high-similarity distractor.

### 3.4 Which signals were actually evaluated

This is a load-bearing clarification.

| Signal | In the formula | Effective in Experiment 1? |
| --- | --- | --- |
| similarity | yes | yes (baseline and shared first term) |
| **importance** | yes | **yes — the only differentiating signal** |
| recency | yes | **no** — all memories seeded simultaneously, so `rec` is constant across the pool and cannot reorder |
| frequency | yes | **no** — uniform access counts, constant across the pool |
| confidence / novelty / urgency | not in v1 formula | no |

Because recency and frequency are constant across each query's pool under the v1
seeding, the *operative* contrast in this paper is **similarity-only vs.
similarity-plus-importance**. We retain the full four-term formula because it is the
deployed strategy and because the recency and frequency terms are studied
specifically in follow-up work (Section 7), but we do not attribute any of the
Experiment 1 effect to them.

The other salience signals named in the research program — confidence, novelty,
urgency — are *authored into the corpus* but not consumed by the v1 ranker. They are
the subject of separate studies and are out of scope for the claims here.

---

## 4. Experimental Framework

### 4.1 Infrastructure

The evaluation uses two systems with a hard ownership boundary between them.

- **Cortex** owns memory and retrieval: it stores memories, computes embeddings,
  performs semantic retrieval, and exposes salience metadata and ranking
  explanations. In this study Cortex serves the *real* semantic baseline via Voyage
  `voyage-3-lite` embeddings (confirmed live, HTTP 200 per memory).
- **Mars** owns experimentation: it executes the benchmark, applies the ranking
  strategies, computes retrieval metrics, runs significance tests, and produces
  reports. Mars does **not** generate context or execute tasks; it consumes Cortex
  retrieval and measures it.

Two further systems are mentioned only for completeness and are not exercised by the
results in this paper. **AutoDev** is the agent-execution framework; it is relevant
only to the future execution-impact study (Section 7), and we report no execution
results here. **Sentinel** provides auditability and provenance; we note it as a
reserved extension point for governance over experiment artifacts.

An *honesty constraint* is enforced in the framework: if the retrieval backend
cannot supply semantic scores (embeddings disabled → `semantic_score: null`), the
run is flagged and the report is forbidden from claiming a semantic-vs-salience
result. The result below was produced with `semantic_score` verified non-null.

### 4.2 Benchmark corpus

Salience Memory Benchmark v1 is a synthetic, labeled retrieval benchmark of **30
queries** and **552 memories** (~18 per query) across six categories. Each query has
exactly one *target* memory, a set of *relevant* support memories, and a controlled
pool of adversarial memories. Gold relevance is explicit per query, so both *ranking*
and *coverage* can be measured.

| Category | Count | Role |
| --- | --- | --- |
| `target` | 30 | The one primary memory each query should retrieve (1 per query). |
| `relevant` | 102 | Helpful support memories; count toward recall/precision gold. |
| `distractor` | 210 | High semantic overlap, low utility — engineered to mislead similarity. |
| `stale` | 90 | Previously useful, now outdated. |
| `contradictory` | 30 | Conflict with the truth (used by the contradiction study). |
| `low_confidence` | 90 | Possibly incorrect (low authored confidence). |
| **Total** | **552** | |

The corpus is **adversarial by construction**: distractors are written to be
*semantically closer* to the query than the truly relevant memories, while carrying
low authored importance. This is precisely the long-horizon failure mode the study
targets, and it is what makes the benchmark discriminating — an earlier 13-memory
smoke test saturated at recall@5 = 1.0 for every strategy and could not separate the
two rankers. The corpus is authored reproducibly by a committed generator and is
**frozen and hash-pinned** (v1.0.0, SHA256 `a464085c…`); bug fixes require a new
version, the bytes are never silently mutated, and a CI check plus
`mars corpus verify-frozen` guard the invariant.

### 4.3 Metrics

For gold relevance set *G(q)* and ranked output, with results averaged over the 30
queries:

- **Recall@K** — fraction of *G(q)* appearing in the top K.
- **Precision@K** — fraction of the top K that is in *G(q)*.
- **MRR** — mean reciprocal rank of the query's target memory.
- **nDCG@K** — normalized discounted cumulative gain over graded relevance,
  rewarding correct items ranked higher.
- **TargetFound@K** — fraction of queries whose single target appears in the top K.
- **ContextEfficiency@K** — fraction of the injected top-K budget spent on
  gold-relevant memories (a measure of wasted context).

### 4.4 Statistical testing

Significance is assessed by a **paired bootstrap** (10,000 resamples) over the
30-query distribution: for each metric we resample queries with replacement, recompute
the per-strategy mean on each resample, and report the 95% confidence interval of the
*difference* (salience − similarity). Because both strategies re-rank the same pool
per query, the comparison is naturally paired; we also report the per-query win/tie/
loss tally. Retrieval is deterministic given fixed embeddings, so the reported
uncertainty is over the query distribution, not run-to-run noise.

---

## 5. Results

### 5.1 Main result (Experiment 1 — Salience Retrieval)

Real Cortex retrieval over MCP with Voyage `voyage-3-lite` embeddings; mock
execution (retrieval-only). Baseline `similarity_only`; candidate
`salience_weighted_v1` with weights (0.40, 0.30, 0.20, 0.10).

| Metric | similarity_only | salience_weighted_v1 | Δ |
| --- | --- | --- | --- |
| recall@1 | 0.067 | 0.933 | +0.867 |
| recall@5 | 0.237 | 0.672 | **+0.435** |
| recall@10 | 0.761 | 0.931 | +0.169 |
| MRR | 0.313 | 0.967 | **+0.654** |
| nDCG@5 | 0.184 | 0.714 | **+0.531** |
| TargetFound@3 | 0.367 | 1.000 | +0.633 |
| TargetFound@5 | 0.667 | 1.000 | +0.333 |
| ContextEfficiency@5 | 0.200 | 0.567 | +0.367 |

**Significance.** recall@5 Δ +0.435, 95% CI [+0.367, +0.502], 29/1/0 win/tie/loss;
nDCG@5 Δ +0.531, 95% CI [+0.474, +0.583], 30/0/0. Both intervals exclude zero by a
wide margin. Every reported metric improves.

### 5.2 Mechanism (verified on a live query)

The improvement is not a metric artifact. On the migration query, the top semantic
matches are three distractors (sim ≈ 0.77–0.79, importance ≈ 0.04–0.07) and a
contradictory memory; the true target sits at rank 6 under similarity-only. The
importance term (relevant ≫ distractor by construction) lifts the relevant memories
above the distractors, moving the target into the top ranks. This is the corpus's
designed mechanism operating as intended: importance breaks ties that similarity
gets wrong.

### 5.3 Interpretation

Under these conditions, importance-weighted retrieval **substantially and
significantly improves both ranking quality (MRR, nDCG, TargetFound) and coverage
(recall) and reduces wasted context budget (ContextEfficiency)**. The natural reading
is that salience functions as a **prioritization mechanism**: it reorders a pool that
similarity has mis-ordered, surfacing consequential memories that look unremarkable
and demoting high-overlap distractors. In the language of attention allocation, the
agent spends more of its limited context budget on memories that matter.

We deliberately stop short of stronger readings. The result says nothing about
emotion, cognition, or general intelligence; it is a measurement of a ranking prior
on a synthetic benchmark. The effect size, while large, is best understood as a
**ceiling**: because importance was authored to be high on relevant memories and low
on distractors, the ranker is being handed a near-oracle signal. The same machinery
fed a noisy or learned importance estimate would land lower; how much lower is an
empirical question this paper does not answer (see Section 7).

---

## 6. Discussion

### 6.1 What the findings suggest

- On a benchmark engineered so that similarity is actively misleading, a single
  additional scalar signal (importance) is enough to recover near-perfect target
  ranking (MRR 0.967, TargetFound@3 1.000). When importance is informative,
  salience-weighted retrieval is clearly the better ranker.
- The gains are broad-based (every metric) and statistically robust (CIs exclude
  zero, near-unanimous per-query wins), not driven by a few queries.
- Salience is best framed as **prioritization**: it changes *which* memories occupy
  the limited context budget, which is the lever that matters for long-horizon
  agents facing memory overload.

### 6.2 What the findings do not suggest

- They do **not** show that *learned* importance helps. Importance here is authored
  and correlated with relevance by construction. The result is an upper bound.
- They do **not** show a downstream **agent task-success** improvement. Retrieval
  metrics are a proxy; better-ranked context does not automatically yield better
  task outcomes. We evaluate no execution here and make no execution claim.
- They do **not** establish generalization beyond this corpus, weight set, or
  embedding model.
- They say nothing about recency or frequency, which are inert in this setup.

### 6.3 Alternative explanations and threats to validity

- **Construct circularity.** The most serious threat: importance and relevance are
  correlated by authoring, so the ranker may be succeeding *because* the benchmark
  encodes the answer into the importance field. We accept this and label the effect
  an upper bound rather than an unbiased estimate. The follow-up noisy-importance
  study exists specifically to probe how much survives when this correlation is
  degraded.
- **Synthetic distribution.** Hand-authored memories may not reflect the statistics
  of real production memory traces (overlap distributions, importance calibration,
  the prevalence of true distractors). External validity is unestablished.
- **Single configuration.** One weight set, one embedding model (`voyage-3-lite`),
  binary-to-graded relevance as labeled. Absolute blend numbers are corpus-specific;
  we do not perform a weight sweep here.
- **Shared-pool re-ranking.** Both strategies re-rank the same retrieved pool, which
  isolates ranking but means we do not measure first-stage recall of the embedding
  store, nor an end-to-end retrieval system that selects the pool differently per
  strategy.
- **Metric proxy risk.** recall@5 and nDCG@5 reward the behavior the corpus was
  built to reward; on a corpus without engineered distractors the margin would
  shrink. The 13-memory saturation result is direct evidence that benchmark design
  controls the headroom.

None of these undermine the internal claim (importance helps *when informative, on
this benchmark*); they bound the external claim.

---

## 7. Future Work

This paper reports one retrieval study. The research program defines a sequence of
follow-up studies, each targeting a specific limitation above. (Several of these have
since been conducted within the program and are reported separately in the project's
technical report; we list them here as the work this v1 result motivates, and keep
this paper's evidential claims scoped to Experiment 1.)

| Study | Question it answers | Limitation it addresses |
| --- | --- | --- |
| **Noisy importance** | How much of the win survives when importance is degraded from a clean oracle toward random? | The authored-importance ceiling (§6.3). |
| **Temporal salience** | Does recency help or hurt, and should it be a core signal? | Recency was inert here (all memories seeded at once). |
| **Confidence systems** | Does a confidence signal improve retrieval, and in what form (additive vs. gated)? | Confidence authored but unused in v1. |
| **Contradiction systems** | Can confidence-aware retrieval avoid surfacing important-but-wrong memories? | The contradictory/stale categories are unexploited by v1. |
| **Execution impact** | Do retrieval gains translate into downstream agent task-success, via real AutoDev runs? | The retrieval-vs-task-success gap (§6.2). |
| **Learned importance** | Where on the noisy-importance curve does a real estimator land? | The core obstacle to deployment. |
| **Real-world memory traces** | Do the results hold off the synthetic corpus? | External validity (§6.3). |

The **execution-impact** study is the pivotal one: until retrieval improvements are
shown (or shown not) to move agent task-success, the practical value of
salience-weighted retrieval for agents remains an open empirical question. The
**learned-importance** study is the one that determines whether the upper bound
reported here is reachable in practice.

---

## 8. Conclusion

We asked whether an authored salience signal improves memory retrieval for
long-horizon agents over similarity-only ranking. On a frozen, adversarial,
synthetic benchmark with a real semantic baseline, importance-weighted retrieval
improved every retrieval metric we measured — recall@5 +0.435, MRR 0.313 → 0.967,
nDCG@5 +0.184 → 0.714 — with paired confidence intervals that exclude zero and
near-unanimous per-query wins. The mechanism is verifiable: importance lifts
consequential-but-unremarkable memories above high-overlap distractors that
similarity ranks first.

We keep the conclusion proportional to the evidence. The result demonstrates that
salience helps **when importance is informative**, on a **synthetic** benchmark, with
importance **authored** rather than learned; recency and frequency were inert; and
retrieval improvement is **not** evidence of agent task-success improvement, which we
did not evaluate. Salience-weighted retrieval is best understood as a prioritization
mechanism for attention allocation over a memory store. Whether its benefit survives
noisy or learned importance, and whether it propagates to downstream agent outcomes,
are the questions that determine its practical value — and they are the explicit
targets of the follow-up studies this work motivates.

---

## Figures

> Placeholders only; no images generated.

**Figure 1 — System Architecture.**
`[FIGURE: Cortex (memory + embeddings + retrieval) ──provides retrieval──▶ Mars
(benchmark execution, ranking strategies, metrics, significance). AutoDev (execution)
and Sentinel (provenance) shown grayed-out as out-of-scope for this paper. Hard
ownership boundary annotated between Cortex and Mars.]`

**Figure 2 — Retrieval Pipeline.**
`[FIGURE: query ─▶ Cortex semantic retrieval (Voyage embeddings) ─▶ per-query
candidate pool ─▶ {similarity_only | salience_weighted_v1} re-ranking ─▶ top-K ─▶
metric computation vs gold labels. Annotate that both strategies re-rank the SAME
pool.]`

**Figure 3 — Recall Comparison.**
`[FIGURE: grouped bar chart of recall@1 / recall@5 / recall@10 for similarity_only
vs salience_weighted_v1; Δ annotated; bootstrap CI whiskers on the @5 bars.]`

**Figure 4 — MRR Comparison.**
`[FIGURE: bar chart, MRR 0.313 → 0.967, with 30 faint per-query dots showing the
paired shift to illustrate 29/1/0 directionality.]`

**Figure 5 — TargetFound Comparison.**
`[FIGURE: bar chart of TargetFound@3 (0.367 → 1.000) and TargetFound@5 (0.667 →
1.000).]`

**Figure 6 — Research Roadmap.**
`[FIGURE: timeline/DAG — Experiment 1 (this paper, completed) ─▶ noisy importance ─▶
temporal salience ─▶ confidence ─▶ contradiction ─▶ execution impact ─▶ learned
importance; execution impact highlighted as the pivotal open question.]`

---

## Tables

**Table 1 — Corpus statistics.** See Section 4.2 (552 memories across six categories,
30 queries, ~18 memories/query, one target per query).

**Table 2 — Experimental results.** See Section 5.1 (full metric suite with deltas
and paired bootstrap significance).

**Table 3 — Limitations.**

| # | Limitation | Consequence for claims |
| --- | --- | --- |
| 1 | Importance is authored, correlated with relevance by construction | Effect size is an upper bound, not an unbiased estimate |
| 2 | Synthetic, hand-authored benchmark | External validity to real memory traces unestablished |
| 3 | Recency and frequency inert (simultaneous seeding) | No temporal evidence; effective contrast is sim vs sim+importance |
| 4 | Execution impact not evaluated | No agent task-success claim; retrieval is a proxy |
| 5 | Single embedding model and single weight set | Absolute numbers corpus/config-specific; no robustness sweep |

**Table 4 — Future-work roadmap.** See Section 7.

---

## Appendix A — Reproduction

```bash
# Benchmark integrity (verify the frozen corpus hash)
mars corpus verify-frozen salience-memory-benchmark-v1

# Corpus statistics
mars corpus stats salience-memory-v1-expanded

# Experiment 1 — Salience Retrieval (real Cortex; requires MARS_CORTEX_MCP_* + Voyage)
mars experiments run salience-memory-v1 --cortex-provider mcp --strict-semantic
```

Artifacts (source of truth): retrieval result JSON
`mars-experiments/salience-memory-v1-expanded.json`; corpus + manifest under
`experiments/corpus/`; long-form design doc `docs/SALIENCE_MEMORY_V1_RESULTS.md`.
