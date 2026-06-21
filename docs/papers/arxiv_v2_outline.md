# arXiv Paper v2 — Consolidated Outline (Experiments 1–5)

**Status:** Outline only. The paper is **not** rewritten here. This document defines
the revised architecture for a single consolidated paper that covers all completed
experiments, so the draft work in a later step is a fill-in, not a redesign.

**Working title:** *Salience-Weighted Memory Retrieval for Long-Horizon Software
Agents: Retrieval Gains, Robustness, and an Honest Execution Null*

**Source of truth:** technical report + result JSONs. All numbers below are quoted
from completed experiments; none are new.

---

## What changes from v1

The v1 draft (`salience_weighted_memory_retrieval_v1.md`) reports only Experiment 1
and lists Experiments 2–5 as future work. The consolidated paper promotes 2–5 into
**completed results**, which converts the v1 draft's biggest weaknesses into answered
questions. The narrative arc becomes:

> Importance helps retrieval (1) → and survives noise (2) → recency does not earn a
> place (3) → confidence rescues contradictions (4) → and inside a real agent,
> retrieval and behavior change but task-success does not (5/5.1).

The honesty posture is unchanged and central: we claim a retrieval + behavioral
result, not a task-success result.

---

## Revised Section Structure

1. **Abstract** — one paragraph; report the retrieval win (recall@5 +0.435, MRR
   0.31→0.97), the robustness result (graceful degradation, never collapses), the
   recency null, the confidence-gating contradiction rescue (CAR 0.000→0.964), and
   the execution outcome (retrieval+behavior change, task-success unchanged). State
   the authored-importance ceiling up front.

2. **Introduction** — long-horizon memory overload; similarity is a weak ranker when
   the most similar memory is a distractor or stale; salience as a prioritization
   prior; contributions (now 6, see below).

3. **Related Work** — RAG, agent memory systems, learning-to-rank/re-ranking,
   long-context models, attention-as-prioritization. Cautious novelty framing:
   contribution is the controlled, significance-tested measurement + the honest
   execution null, not the idea of memory importance.

4. **Salience-Weighted Retrieval (formalization)** — notation; baseline
   `similarity_only`; `salience_weighted_v1` four-term blend `(0.40, 0.30, 0.20,
   0.10)`; the **confidence-gated** form `effective_importance = importance ×
   confidence` introduced here (promoted by Exp 4); explicit "which signals were
   actually evaluated" table.

5. **Experimental Framework** — Cortex (retrieval, Voyage `voyage-3-lite`), Mars
   (experimentation, metrics, bootstrap), AutoDev (execution, used only in §9). Hard
   ownership boundary. Benchmark v1.0.0 (frozen, hash-pinned). Metric suite.
   Paired-bootstrap methodology. Committed retrieval cache for offline repro.

6. **Experiment 1 — Salience Retrieval** — main retrieval result + verified
   mechanism (migration query). Effect size is an upper bound.

7. **Experiment 2 — Noisy Importance** — quality sweep 1.0→0.0; graceful monotonic
   degradation; oracle−scrambled = +0.341 (~78% of the win is the importance signal);
   importance-ablated floor lands on the similarity baseline. **This section exists to
   answer the circularity objection.**

8. **Experiment 3 — Temporal Salience** — four timestamp regimes; isolated recency
   marginal (aligned +0.262 / misaligned −0.206 / realistic +0.015 n.s.);
   importance regime-invariant. Recency **not** promoted.

9. **Experiment 4 — Confidence & Contradiction** — `ContradictionAvoidanceRate`;
   additive vs gated confidence; regime E (important-but-wrong) collapses
   `importance_only` to CAR 0.000, gating restores 0.964. Confidence promoted as a
   gate; recency stays out.

10. **Experiment 5 / 5.1 — Execution Impact** — 5 as methodology milestone (pipeline
    built, floored at 0% success → unmeasurable). 5.1 as first evidential result: 18
    real AutoDev runs, retrieval improved (target-found 0.83 vs 0.00), behavior
    changed (JWT vs stale session-cookie on `bench-4`, right-approach 1.00 vs 0.83),
    **task-success unchanged (0.333 all arms)**. Outcome B. Negative recall↔success
    correlation explained as task-winnability artifact.

11. **Discussion** — salience as prioritization; supported vs unsupported claims
    (two strict lists); threats to validity consolidated across experiments.

12. **Limitations** — synthetic corpus; authored importance/confidence; recency
    inert in 1; execution underpowered (floor, single trial, n=6, dry-run); single
    embedding model / single weight set; retrieval_limit sensitivity in 5.1.

13. **Conclusion** — proportional summary; retrieval question well-characterized,
    execution-on-task-success open.

14. **Appendices** — see `APPENDIX_PLAN.md`.

**Contributions (revised, 6):** (1) frozen adversarial benchmark; (2)
importance-weighted retrieval evaluation; (3) robustness-under-noise analysis; (4)
temporal ablation; (5) confidence-gated contradiction metric + result; (6) honest
real-agent execution study separating retrieval/behavior change from task-success.

---

## New Figures Required (beyond v1)

| Fig | Title | Added because |
| --- | --- | --- |
| 3 | Benchmark Composition | Make the adversarial design legible |
| 5 | Noisy Importance Results | Exp 2 promoted to results |
| 6 | Temporal Salience Results | Exp 3 promoted |
| 7 | Confidence / Contradiction Results (CAR) | Exp 4 promoted |
| 8 | Execution Impact Results | Exp 5.1 promoted |
| 9 | Retrieval Ranking Example | Mechanism visualization |
| 10 | Research Program Overview | Tie the five experiments together |

(See `FIGURE_PLAN.md` for full specs. Figures 1–2, 4 carry over from v1.)

## New Tables Required (beyond v1)

| Table | Added because |
| --- | --- |
| Experiment Summary (one row per experiment: question, finding, decision) | Consolidation |
| Noisy-importance sweep (quality → Δrecall@5 + CI) | Exp 2 |
| Temporal recency marginal by regime | Exp 3 |
| ContradictionAvoidanceRate by strategy × regime | Exp 4 |
| Execution results (arm × success/recall/target-found/MRR) | Exp 5.1 |

(See `TABLE_PLAN.md`.)

---

## Claims Strengthened by Experiments 2–5

| Claim in v1 | How 2–5 strengthen it |
| --- | --- |
| "Importance improves retrieval (but this is an upper bound under authored importance)." | **Exp 2** shows the advantage survives heavy noise (every CI excludes zero down to q=0.25; oracle−scrambled +0.341), so the result is not purely an artifact of clean labels. |
| "Recency/frequency were inert; we make no temporal claim." | **Exp 3** converts the non-claim into a *finding*: recency is conditional and risky, importance is regime-invariant — a justified design decision, not a gap. |
| "Other salience signals authored but unused." | **Exp 4** activates confidence and shows a unique, decisive role (contradiction rescue) — extends the method (`importance × confidence`) with evidence. |
| "Retrieval is a proxy; no execution claim." | **Exp 5.1** provides a real-agent result: retrieval gains + behavior change are now demonstrated inside an agent pipeline, even though task-success is not. The proxy gap is partially closed and honestly bounded. |

## Claims That Should Remain Unchanged

- Effect size in Exp 1 is an **upper bound** (authored importance).
- The benchmark is **synthetic**; external validity unestablished.
- **No task-success claim.** Salience improves retrieval and steers behavior; it has
  not been shown to raise task-success.
- Recency stays **out** of the core signal set.
- Absolute blend numbers are **corpus/config-specific** (one weight set, one
  embedding model).

These are load-bearing and must not be softened in consolidation.

---

## Reviewer Objection → Experiment That Answers It

| # | Likely reviewer objection | Answered by | How |
| --- | --- | --- | --- |
| 1 | "Authored importance is circular; +0.435 just measures the labels." | **Exp 2 (Noisy Importance)** | Degrade importance oracle→random; advantage degrades gracefully, never collapses; ~78% of the win attributable to the importance signal; ablated floor lands exactly on similarity baseline. |
| 2 | "You bolted on a recency term you can't justify." | **Exp 3 (Temporal Salience)** | Isolated recency marginal: helps only when aligned, hurts when misaligned, neutral in realistic regime → deliberately excluded from core signals. |
| 3 | "Similarity ranking already avoids obviously wrong memories." | **Exp 4 (Confidence/Contradiction)** | New CAR metric; in the adversarial regime `importance_only` collapses to 0.000 and similarity sits at 0.643; confidence-gating restores 0.964. |
| 4 | "Retrieval metrics are a proxy — does any of this affect an agent?" | **Exp 5.1 (Execution)** | Real AutoDev runs: retrieval improved (target-found 0.83 vs 0.00) and behavior changed (JWT vs stale cookie). Honestly: task-success unchanged. |
| 5 | "Your win is one lucky configuration." | **Exp 2 (seeds) + Exp 3 (regimes)** | 25 seeds/level across the noise sweep and four timestamp regimes show the importance effect is stable across perturbations (though still one weight set / embedding model — disclosed). |
| 6 | "Single trial / floor effects make execution meaningless." | **Exp 5 → 5.1 progression** | Exp 5's floor is disclosed as the reason 5.1 was built on a less-floored, memory-dependent benchmark; the execution claim is scoped to behavior, not success, precisely because of remaining underpowering. |

**Objections still NOT fully answered (must remain in Limitations):** synthetic
corpus / real-world traces; learned (vs authored) importance and confidence; small
execution n and single trial; single embedding model + single weight set.
