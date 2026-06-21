# Salience-Weighted Memory Retrieval for Long-Horizon Software Agents

### Benchmark Design, Retrieval Studies, and Initial Agent Execution Results

**Status:** Authoritative technical report for the first public release of Salience
Memory Benchmark v1.0.0 and the basis for an eventual arXiv draft.
**Date:** 2026-06-21
**Benchmark:** Salience Memory Benchmark v1.0.0 (`salience-memory-benchmark-v1`,
SHA256 `a464085c3daa64c97d2764c47f8758931b2a51c2adc1e143fcfc98d9faa74d59`)

All results below are reported against the frozen Salience Memory Benchmark v1.0.0.
Experiment JSON artifacts under `mars-experiments/` are the source of truth; the
per-experiment design docs in `docs/` are the long-form references.

---

## Executive Summary

> Salience-aware retrieval improves retrieval quality,
> improves contradiction avoidance,
> and measurably changes agent behavior.
>
> It has not yet been shown to improve task-success rates.

Software agents that work over long horizons accumulate memory: decisions,
postmortems, conventions, and stale documentation. Choosing *which* of those
memories to surface for a given task is a retrieval problem, and plain semantic
similarity is a weak ranker when the most semantically similar memories are
distractors or outdated. This report studies **salience-weighted retrieval** —
ranking that blends semantic similarity with authored *importance* and *confidence*
signals — across five retrieval studies and one real-agent execution study, all on
a single frozen benchmark.

The retrieval picture is strong and consistent. On a non-saturating, adversarial
benchmark with a real semantic baseline (Voyage embeddings), importance-weighted
retrieval lifts recall@5 by **+0.435** and MRR from **0.31 → 0.97** (Experiment 1);
the advantage **degrades gracefully** under noisy importance and never collapses
to zero (Experiment 2); **recency is not a reliable primary signal** (Experiment
3); and **confidence, applied as a multiplicative gate on importance**, rescues
contradiction avoidance from a catastrophic 0.000 to 0.964 when an important memory
is wrong (Experiment 4).

The execution picture is honest and incomplete. We wired Mars to drive **real
AutoDev agent runs** and ran two execution studies. Experiment 5 established the
pipeline but floored at 0% task success, so it could not answer the
execution-impact question. Experiment 5.1, on a purpose-built memory-dependent
benchmark, produced the first **evidential** result over 18 real agent runs:
salience-aware retrieval **clearly improved retrieval** (target-found 0.83 vs 0.00)
and **measurably changed the agent's behavior** (it switched from a stale
session-cookie scheme to the repo's current JWT convention), but **task-success did
not move** (0.333 in every arm).

**The honest bottom line:** execution impact remains unresolved, but behavioral
impact is now demonstrated. We do not claim salience improves task success.

---

## Contributions

1. **Salience Memory Benchmark v1.0.0** — a frozen, hash-pinned, synthetic labeled
   retrieval benchmark (30 queries, 552 memories, six categories) with engineered
   adversarial distractors that defeat similarity-only ranking.
2. **Importance-weighted retrieval evaluation** — a controlled, paired comparison
   of salience-weighted vs similarity-only retrieval over a real semantic baseline
   (Experiment 1).
3. **Robustness analysis under noisy importance** — a quality sweep showing the
   salience advantage degrades gracefully and monotonically, not catastrophically
   (Experiment 2).
4. **Temporal salience ablation** — an isolation of the recency term across four
   timestamp regimes, finding recency unreliable as a primary signal (Experiment 3).
5. **Confidence-gated contradiction handling** — a new `ContradictionAvoidanceRate`
   metric and a gated `importance × confidence` formulation that prevents
   important-but-wrong retrieval (Experiment 4).
6. **Real-agent execution validation via AutoDev** — an evidential 3-arm execution
   study (18 real agent runs) separating *retrieval improved + behavior changed*
   from *task-success improved* (Experiments 5 and 5.1).
7. **Open-source benchmark and reproducible evaluation framework** — the frozen
   corpus, manifest, runners, committed retrieval cache, and per-experiment
   reproduction commands.

---

## 1. Benchmark Design

Salience Memory Benchmark v1 is a synthetic, labeled retrieval benchmark holding
**30 queries** and **552 memories** (~18 per query) across six labeled categories.
Each query has exactly one *target* memory, a set of *relevant* support memories,
and a controlled pool of adversarial *distractor*, *stale*, *contradictory*, and
*low-confidence* memories. Gold relevance is explicit per query, so retrieval
*coverage* — not just ranking — can be measured.

| Category | Count | Role |
| --- | --- | --- |
| `target` | 30 | The primary memory each query should retrieve (1 per query). |
| `relevant` | 102 | Helpful support memories; count toward recall/precision gold. |
| `distractor` | 210 | High overlap, low utility — engineered to mislead similarity. |
| `stale` | 90 | Previously useful, now outdated. |
| `contradictory` | 30 | Conflict with the truth (drive contradiction-avoidance). |
| `low_confidence` | 90 | Possibly incorrect (low authored confidence). |

The corpus is **adversarial by design**: distractors are written to be
*semantically closer* to the query than the truly-relevant memories, but carry low
importance. This is what makes the benchmark discriminating — the earlier 13-memory
smoke test saturated at recall@5 = 1.0 for every strategy. Each memory carries
authored salience signals (`importance`, `novelty`, `urgency`, `confidence`).

The benchmark is **frozen and hash-pinned** (v1.0.0, SHA256 `a464085c…`). Bug
fixes require a new `v1.0.x`/`v1.1`; expanded designs require `v2`; the corpus bytes
are never silently mutated (`mars corpus verify-frozen salience-memory-benchmark-v1`
plus a CI regression test guard the invariant).

---

## 2. Experiment 1 — Salience Retrieval

**Question.** Does salience-weighted retrieval beat semantic-similarity-only
retrieval?

**Setup.** Real Cortex retrieval over MCP with Voyage (`voyage-3-lite`) embeddings,
mock execution (retrieval-only). Both strategies re-rank the **same** per-query
retrieved pool. Baseline `similarity_only`; candidate `salience_weighted_v1`
(0.40 similarity + 0.30 importance + 0.20 recency + 0.10 frequency). Significance is
a paired bootstrap (10k) over the 30-query distribution.

**Results.**

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

Paired significance: recall@5 +0.435 (95% CI [+0.367, +0.502], 29/1/0 wins) and
nDCG@5 +0.531 (95% CI [+0.474, +0.583], 30/0/0). Both CIs exclude zero by a wide
margin.

**Mechanism (verified live).** For the migration query, the top semantic matches are
three distractors (sim ≈ 0.77–0.79, importance ≈ 0.04–0.07) and a contradictory
memory, burying the target at rank 6. Importance (relevant ≫ distractor) lifts the
right memories to the top — the corpus mechanism working, not a metric artifact.

**Finding.** Salience-weighted retrieval clearly and significantly improves both
ranking and coverage on a non-saturating benchmark with a real semantic baseline.
The effect size is an **upper bound**: importance is an authored oracle here
(relevant memories high, distractors low). Recency and frequency contributed
nothing (all memories seeded at once) — the entire win is importance-driven.

---

## 3. Experiment 2 — Noisy Importance

**Question.** How much of the win survives when importance is noisy rather than a
clean oracle?

**Setup.** Same corpus and real retrieval, with importance degraded via a shuffle
model (a fraction `1−quality` of each pool's importance values permuted among
themselves) across a quality grid 1.00 → 0.00, 25 seeds/level. Importance is
corrupted *post-retrieval* (it never affects the embeddings or the retrieved pool),
which is faithful to re-seeding Cortex with corrupted labels. The oracle level
reproduces Experiment 1 exactly (recall@5 +0.435), validating the pipeline.

**Results (Δ recall@5 vs baseline, 95% CI).**

| importance quality | recall@5 | Δ recall@5 (95% CI) | MRR |
| --- | --- | --- | --- |
| 1.00 (oracle) | 0.672 | +0.435 [+0.370, +0.503] | 0.967 |
| 0.75 | 0.593 | +0.356 [+0.302, +0.414] | 0.864 |
| 0.50 | 0.506 | +0.269 [+0.218, +0.322] | 0.746 |
| 0.25 | 0.420 | +0.183 [+0.142, +0.224] | 0.584 |
| 0.00 (scrambled) | 0.330 | +0.094 [+0.050, +0.139] | 0.423 |

**Finding.** Degradation is **graceful and monotonic** — there is no cliff. Every CI
excludes zero, so the salience arm beats plain semantic retrieval at every tested
importance quality. The honest measure of the importance *signal's* contribution is
**oracle − scrambled** (recall@5 0.672 → 0.330 = **+0.341**), i.e. ~78% of the
advantage is carried by the importance signal itself; the residual q=0 edge is the
stochastic perturbation breaking this corpus's adversarial similarity ordering, not
importance information. An importance-ablated floor (importance weight zeroed)
collapses exactly onto the similarity baseline (0.237), confirming that on this
corpus all of salience's deterministic value comes from importance.

**Decision.** Salience weighting is robust to substantial importance noise — it does
not need a near-perfect importance estimate to pay off.

---

## 4. Experiment 3 — Temporal Salience

**Question.** Does time (recency) improve or degrade salience-weighted retrieval,
and does it earn a place in Salience v2?

**Setup.** Reuses the committed real-retrieval cache (nothing re-embedded); only
synthetic timestamps and strategy vary. Four regimes: **A uniform** (control),
**B recency-aligned** (relevant newer), **C recency-misaligned** (distractors
newer), **D mixed-realistic** (ages independent of relevance). The recency
*marginal* is isolated as `importance_plus_recency − sim_plus_importance` (identical
similarity/importance weights; the delta is the 0.10 recency term alone).

**Results — isolated recency marginal (recall@5, paired 95% CI).**

| regime | marginal | verdict |
| --- | --- | --- |
| A uniform | +0.000 [+0.000, +0.000] | neutral (control passes) |
| B aligned | +0.262 [+0.210, +0.316] | recency **helps** |
| C misaligned | −0.206 [−0.262, −0.155] | recency **hurts** |
| D mixed realistic | +0.015 [−0.025, +0.055] | **neutral** (CI spans 0) |

`importance_only` is **regime-invariant** at recall@5 0.985 / MRR 1.000 across all
four regimes — time neither helps nor harms importance.

**Finding.** Raw recency helps only in the artificial aligned regime, hurts by a
nearly symmetric amount when misaligned, and is **statistically neutral in the
realistic mixed regime**. Importance dominates everywhere. The safest temporal
strategy is short-half-life decay (≈7 days) — the only temporal arm that
significantly beats the similarity baseline in *every* regime — but it never beats
`importance_only`.

**Decision.** Recency is **NOT promoted** to a core Salience v2 signal. At best it
is an optional short-decay, low-weight, importance-gated add-on.

---

## 5. Experiment 4 — Confidence & Contradiction

**Question.** Can confidence-aware retrieval help agents avoid outdated, incorrect,
or contradictory memories — especially when an important memory is wrong?

**Setup.** Reuses the cached pools joined to the corpus by content to recover each
memory's authored `category` + `confidence`. Five confidence regimes including an
adversarial **E "important-but-wrong"** regime where the obsolete memory is forced
to be *slightly more important than the target* but low-confidence. New metric:
**ContradictionAvoidanceRate (CAR)** — over contradiction-eligible queries (28/30),
the fraction where the correct target outranks **every** obsolete contradictory
memory. Compares additive confidence (0.65·sim + 0.25·imp + 0.10·conf) vs **gated**
confidence (0.65·sim + 0.35·(importance × confidence)).

**Results — ContradictionAvoidanceRate.**

| strategy | A | B | C | D | **E (important-but-wrong)** |
| --- | --- | --- | --- | --- | --- |
| `similarity_only` | 0.643 | 0.643 | 0.643 | 0.643 | 0.643 |
| `importance_only` | 1.000 | 1.000 | 1.000 | 1.000 | **0.000** |
| `confidence_only` | 0.479 | 1.000 | 1.000 | 1.000 | 1.000 |
| `importance_plus_confidence_gated` | 0.964 | 0.964 | 0.964 | 0.964 | **0.964** |

The isolated confidence marginal (recall@5) is positive and significant wherever
confidence is informative (B +0.265, C +0.169, D +0.108, E +0.146) and ≈0 in the
control (A +0.010).

**Finding.** In the easy regimes (A–D), importance already achieves perfect
avoidance, so confidence is **redundant**. In the adversarial regime E,
`importance_only` collapses to **CAR 0.000** (it ranks the important-but-wrong
memory first in all 28 queries) — and **confidence-gating restores avoidance to
0.964**, the only importance-based strategy that stays robust across *every* regime.
Confidence's unique, non-redundant value appears exactly when importance and
confidence diverge.

**Decision.** Confidence **joins importance as a core Salience v2 signal, in gated
(multiplicative) form** (`effective_importance = importance × confidence`). It is
redundant-but-harmless when the two agree and decisive when they diverge. Recency
stays out.

---

## 6. Experiment 5 — Execution Impact (Methodology Milestone)

**Role in this report.** Experiment 5 is retained as a **methodology milestone**: it
built and validated the real execution pipeline, but could not answer the
execution-impact question because of a floor effect.

**What it established.**

- **First real AutoDev wiring.** Mars drove a real AutoDev agent over MCP across all
  three retrieval arms (A `similarity_only`, B `sim_importance`, C `salience_v2`),
  injecting per-arm context via `start_run(retrieval_strategy=…, context_package_id=…)`.
- **Retrieval arms validated.** A Phase-3 divergence gate confirmed the arms inject
  **different** contexts (`arms_distinct=true`, `valid_comparison=true`). Retrieval
  improved as predicted: recall@5 0.50 → 0.83, MRR 0.28 → 0.57, target-found
  0.50 → 1.00, and CAR 0.00 → 1.00 — replicating Experiments 1 & 4 inside a real
  agent pipeline (18 real runs, dry-run, ≈$1.55).
- **Execution floor effect.** **Task success floored at 0.000 for all three arms**
  (0/6 each). The dry-run coder could not solve any task regardless of context.
- **No measurable task-success variance.** With zero variance in success, the
  retrieval↔success correlation was trivially 0.000 and **uninformative** — not
  evidence of "no relationship."

> Experiment 5 established the execution pipeline
> but could not answer the execution-impact question.

Because success had no variance, Experiment 5 has no statistical power to detect an
execution-success difference. We therefore could neither claim that better retrieval
helps execution nor that it fails to — the floor made the question unmeasurable.
This motivated a purpose-built, less-floored benchmark in Experiment 5.1.

---

## 7. Experiment 5.1 — Real Agent Execution Study

### Purpose

Determine whether retrieval improvements translate into downstream agent success on
a benchmark where retrieval is genuinely task-relevant.

### Setup

A purpose-built, memory-dependent benchmark: six tasks in a small, dependency-free
repo, each requiring knowledge that lives in a *decision/postmortem/convention* that
is not visible in the file being edited — or is actively contradicted by a **stale
doc** still present in the repo. Each task gets an isolated 5-record store, reseeded
before every run: one **corrective** record (importance 3.5, old, deliberately low
term-overlap) plus four recent, higher-overlap distractors. A pure-similarity ranker
buries the corrective record; importance-aware rankers surface it. Divergence is
proven offline with AutoDev's real scorers at `retrieval_limit=3`.

| | |
| --- | --- |
| Real AutoDev agent runs | **18** (6 tasks × 3 arms × 1 trial) |
| Memory-dependent tasks | 6 |
| Retrieval arms | 3 (A similarity_only / B sim_importance / C salience_v2) |
| Execution mode | dry-run (no PRs) |
| Retrieval limit | 3 (required — at the default 5 every arm injects the whole store) |
| Evidential | `evidential=true`, `arms_distinct=true`, `valid_comparison=true` |
| Model | AutoDev default (observed `claude-sonnet-4-6`), held constant across arms |
| Total cost | ≈ **$1.3** (token usage not exposed by AutoDev → reported missing) |

**Success oracle** = the task's targeted test, with the test file forbidden so a run
cannot pass by editing the test. Mars restores forbidden files to their committed
state before validating, so success reflects the agent's *implementation* against
the *fixed oracle* (this corrected an earlier artifactual 0% floor where the agent
had rewritten the test).

### Results

| Arm | Success | Recall@5 | Target Found | MRR |
| --- | --- | --- | --- | --- |
| Similarity Only | 0.333 | 0.000 | 0.000 | 0.000 |
| Similarity + Importance | 0.333 | 0.833 | 0.833 | 0.556 |
| Salience v2 | 0.333 | 0.833 | 0.833 | 0.556 |

Paired Δ success vs A: B +0.000 (6 ties), C +0.000 (6 ties) — **no execution
difference**. The retrieval columns differ sharply: at `limit=3` the similarity arm
**never** injects the corrective record (recall/target-found 0.0), while both
importance arms inject it ~5/6 of the time. B and C are identical (the recency term
in `salience_v2` reorders but does not change the top-3 set — consistent with
Experiment 3).

**Contradiction avoidance.** The contradiction finding from Experiment 4 replicated
at the agent layer: the similarity arm's dominant failure mode is retrieving a
contradiction (the stale-doc distractor) and acting on it — its failure breakdown is
4 contradiction-retrieval failures out of 6 tasks, versus 1 for each importance arm.
The importance arms, having surfaced the corrective record, instead fail downstream
at implementation/review.

### Behavioral Analysis

This is the most important new result. **Retrieval changed → injected context
changed → agent decisions changed.**

The clean demonstration is `bench-4` (protect-admin-reports), whose `docs/AUTH.md` is
**stale**:

- **Arm A (similarity only)** — deprived of the corrective memory, the agent trusted
  the out-of-date `docs/AUTH.md` and implemented **session-cookie** auth.
- **Arms B/C (importance-aware)** — given the corrective memory, both implemented the
  repo's current **JWT** convention.

Across the suite, the right-approach rate is **1.00 for B/C vs 0.83 for A**. This is
a genuine, observed retrieval→behavior effect: better retrieval steered the agent
toward the repo's current convention. It simply was not enough to pass the stricter,
multi-assertion oracle within the iteration budget.

### Outcome

**Outcome B.**

- Retrieval improves.
- Behavior changes.
- Task success unchanged.

The retrieval↔success correlation is slightly **negative** (recall ↔ success Pearson
−0.32), an artifact of *which* tasks are winnable: the 2 passing tasks are
discoverable-from-code (the similarity arm passes them with recall 0), while the
tasks where retrieval helped most (the contradiction tasks) are also the hardest to
implement and fail anyway. Better retrieval ≠ better outcome **on this set**.

### Interpretation

> Retrieval quality appears capable of steering agent behavior,
> but this benchmark did not demonstrate an increase in task success.

Downstream pass/fail here is dominated by implementation quality and a per-task
difficulty floor (4/6 tasks fail in every arm at `max_iterations=3`), not by which
memories were retrieved. We **do not** claim Salience v2 improves agent task
outcomes. The honest, supported claim is: *Salience v2 improves retrieval and steers
the agent toward the repo's current conventions; on this benchmark that did not yet
raise task-success.*

---

## 8. Main Findings

> Execution impact remains unresolved,
> but behavioral impact is now demonstrated.

This is a meaningful upgrade over the prior state, in which execution impact was
simply open and no downstream signal of any kind had been observed. We now have a
genuine, evidential retrieval→behavior effect inside a real agent pipeline, cleanly
separated from the (still unproven) retrieval→task-success effect.

---

## 9. Cross-Experiment Synthesis — What We Learned

**Experiment 1 — Importance helps retrieval.** Salience-weighted retrieval beats
similarity-only by a large, significant margin (recall@5 +0.435, MRR 0.31 → 0.97).

**Experiment 2 — Importance is robust to noise.** The advantage degrades gracefully
and monotonically; it beats the baseline at every importance quality, with ~78% of
the win carried by the importance signal itself.

**Experiment 3 — Recency is not a reliable primary signal.** Raw recency helps only
when aligned, hurts symmetrically when misaligned, and is neutral in the realistic
regime; importance is regime-invariant and dominant.

**Experiment 4 — Confidence prevents contradiction failures.** As a multiplicative
gate on importance, confidence rescues contradiction avoidance from 0.000 to 0.964
when an important memory is wrong; it is redundant-but-harmless otherwise.

**Experiment 5.1 — Improved retrieval changes agent behavior, but task-success
benefits remain unproven.** The importance arms surface the corrective decision the
similarity arm misses and the agent acts on it (JWT vs stale cookie), but the same
2/6 tasks pass in every arm.

---

## 10. Salience v2 Recommendation

**Core signals:**

- semantic similarity
- importance
- confidence (applied as a multiplicative gate on importance:
  `effective_importance = importance × confidence`)

**Not promoted:**

- raw recency (Experiment 3) — at best an optional short-decay, low-weight,
  importance-gated add-on, never a core weighted term.

**Possible future signals:**

- learned importance (replace authored/shuffled importance with an estimator)
- contradiction-aware retrieval (contradiction labels from the store, e.g. Cortex
  `find_contradictions`, not the corpus)
- access-frequency / reinforcement-style recency (recall counts rather than
  write-time age)

---

## 11. Limitations

These are stated explicitly because the integrity of the conclusions depends on
them.

- **Synthetic benchmark.** The corpus is authored by hand, not sampled from real
  production memory traces.
- **Authored importance labels.** `importance`/`novelty`/`urgency` are authored, not
  learned or observed; importance and relevance are correlated by construction, so
  Experiment 1's effect size is an **upper bound**.
- **Authored confidence labels.** Confidence is synthetic per regime; real Cortex
  confidence will be noisier. The decisive Experiment 4 regime (E) is a synthetic
  stress test, not observed data.
- **Single trial per task** in Experiment 5.1 — 6 binary outcomes per arm, model
  output not seed-pinned; the exactly-tied pass rates are coarse.
- **Only 6 execution tasks.** The execution benchmark is small.
- **Dry-run execution.** No PRs; AutoDev's `review_passed` is unusable as the success
  signal (the agent edits forbidden files across all arms), so success uses
  restored-oracle validation.
- **Retrieval_limit sensitivity.** The Experiment 5.1 contrast only exists at
  `retrieval_limit=3`; at the default 5 every arm injects the whole 5-record store
  and the arms differ only in order.
- **Execution benchmark still relatively small** and partially floored: 4/6 tasks are
  unwinnable by any arm at `max_iterations=3`.
- **Task-success remains underpowered.** With zero/low success variance, the
  execution study has little power to detect an execution gain even if one existed —
  this is the central caveat on every execution claim.
- **Adversarial similarity / single weight set / fixed embedding model.** Absolute
  blend numbers are corpus-specific; one weight set and one embedding model were used.

---

## 12. Future Work

1. **Benchmark v1 public release** — publish the frozen corpus, manifest, and
   reproduction framework.
2. **Technical report publication** — release this report.
3. **Research blog** — an accessible write-up of the retrieval and behavioral
   findings.
4. **arXiv submission** — submit the retrieval studies plus the honest execution
   null.
5. **Execution Study 5.2** — multiple trials, a less-floored task set, and an
   iteration budget that lets correct approaches actually pass.
6. **Larger execution benchmark** — more tasks with non-zero, varied success so the
   metric has power.
7. **Learned importance estimation** — replace authored/shuffled importance with a
   real estimator and locate where it lands on the noisy-importance curve.
8. **Real-world memory traces** — move off the synthetic corpus toward sampled
   production memory.
9. **External validation** — independent replication of the retrieval results.

(No new retrieval experiments are proposed; the retrieval question is well
characterized. The open frontier is execution.)

---

## 13. Publication Guidance

### Supported Claims

We can claim:

- salience improves retrieval quality
- salience improves contradiction avoidance
- confidence is valuable (as a gate on importance)
- recency is weak (not a reliable primary signal)
- retrieval changes agent behavior

### Unsupported Claims

We cannot claim:

- salience improves task success
- salience improves production outcomes
- salience generalizes beyond tested conditions

The report is structured so these two lists are never blurred: every execution
sentence is paired with the floor/variance caveat that prevents a task-success claim.

---

## Appendix A — Artifacts (Source of Truth)

| Experiment | Result JSON | Design doc |
| --- | --- | --- |
| Benchmark v1.0.0 | `experiments/corpus/salience-memory-v1.manifest.yaml` | `docs/SALIENCE_MEMORY_BENCHMARK_V1.md` |
| 1 — Salience Retrieval | `mars-experiments/salience-memory-v1-expanded.json` | `docs/SALIENCE_MEMORY_V1_RESULTS.md` |
| 2 — Noisy Importance | `mars-experiments/salience-memory-noisy-importance.json` | `docs/SALIENCE_MEMORY_NOISY_IMPORTANCE.md` |
| 3 — Temporal Salience | `mars-experiments/salience-memory-temporal-salience.json` | `docs/SALIENCE_MEMORY_TEMPORAL_SALIENCE.md` |
| 4 — Confidence & Contradiction | `mars-experiments/salience-memory-confidence-and-contradiction.json` | `docs/SALIENCE_MEMORY_CONFIDENCE_AND_CONTRADICTION.md` |
| 5 — Execution Impact | `mars-experiments/salience-memory-execution-impact-v2.json` | `docs/reports/SALIENCE_MEMORY_EXECUTION_IMPACT_RESULTS.md` |
| 5.1 — Real Agent Execution | `mars-experiments/salience-memory-execution-impact-5-1.json` (+ `…-5-1-behavioral.json`) | `docs/reports/SALIENCE_MEMORY_EXECUTION_IMPACT_5_1_RESULTS.md` |

## Appendix B — Reproduction

```bash
# Benchmark integrity
mars corpus verify-frozen salience-memory-benchmark-v1

# Experiment 1 — Salience Retrieval
mars experiments run salience-memory-v1

# Experiment 2 — Noisy Importance (offline, committed retrieval cache)
python experiments/run_noisy_importance.py --cache-only

# Experiment 3 — Temporal Salience
python experiments/run_temporal_salience.py

# Experiment 4 — Confidence & Contradiction
python experiments/run_confidence_contradiction.py

# Experiment 5.1 — Real Agent Execution (paid, ≈$1.3; requires MARS_AUTODEV_MCP_*)
python experiments/launch_exec_impact_5_1.py --real-autodev --dry-run \
    --issues-file experiments/execution_impact_5_1/issues.yaml \
    --retrieval-limit 3 --experiment salience-memory-execution-impact-5-1
```
