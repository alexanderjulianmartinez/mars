# Salience-Weighted Memory Retrieval for Long-Horizon Software Agents

### Executive Summary — Benchmark Design, Retrieval Studies, and Initial Agent Execution Results

**Date:** 2026-06-21 · **Benchmark:** Salience Memory Benchmark v1.0.0
(`salience-memory-benchmark-v1`, frozen, SHA256 `a464085c…`)
**Full report:** [SALIENCE_WEIGHTED_MEMORY_RETRIEVAL_TECHNICAL_REPORT.md](SALIENCE_WEIGHTED_MEMORY_RETRIEVAL_TECHNICAL_REPORT.md)

---

## The Takeaway

> Salience-aware retrieval improves retrieval quality,
> improves contradiction avoidance,
> and measurably changes agent behavior.
>
> It has not yet been shown to improve task-success rates.

Execution impact remains unresolved, but **behavioral impact is now demonstrated** —
a meaningful upgrade over the prior state, where no downstream signal existed.

---

## What We Built

**Salience Memory Benchmark v1.0.0** — a frozen, hash-pinned, synthetic labeled
retrieval benchmark: 30 queries, 552 memories, six categories, with engineered
adversarial distractors that are *semantically closer* to each query than the truly
relevant memories. This defeats similarity-only ranking by design and makes the
benchmark discriminating (the prior smoke test saturated at recall@5 = 1.0).

---

## What We Learned (per experiment)

| Experiment | Finding |
| --- | --- |
| **1 — Salience Retrieval** | Importance helps retrieval: recall@5 +0.435 (95% CI [+0.367, +0.502]), MRR 0.31 → 0.97. |
| **2 — Noisy Importance** | Importance is robust to noise: graceful, monotonic degradation; beats baseline at every quality; ~78% of the win is the importance signal itself. |
| **3 — Temporal Salience** | Recency is not a reliable primary signal: helps only when aligned, hurts when misaligned, neutral in the realistic regime; importance dominates. |
| **4 — Confidence & Contradiction** | Confidence prevents contradiction failures: gated `importance × confidence` rescues avoidance from CAR 0.000 → 0.964 when an important memory is wrong. |
| **5 — Execution Impact** | Methodology milestone: established the real AutoDev pipeline but floored at 0% success — could not answer the execution-impact question. |
| **5.1 — Real Agent Execution** | Improved retrieval changes agent behavior (JWT vs stale cookie), but task-success benefits remain unproven. |

---

## Experiment 5.1 in One Table

18 real AutoDev agent runs, 6 memory-dependent tasks, 3 retrieval arms,
`evidential=true`, dry-run, `retrieval_limit=3`, ≈$1.3.

| Arm | Success | Recall@5 | Target Found | MRR |
| --- | --- | --- | --- | --- |
| Similarity Only | 0.333 | 0.000 | 0.000 | 0.000 |
| Similarity + Importance | 0.333 | 0.833 | 0.833 | 0.556 |
| Salience v2 | 0.333 | 0.833 | 0.833 | 0.556 |

**Outcome B:** retrieval improves, behavior changes, task success unchanged. On
`bench-4`, the similarity arm followed the stale `docs/AUTH.md` and used a session
cookie; both importance arms used the repo's current JWT convention (right-approach
1.00 vs 0.83). But the same 2/6 tasks pass in every arm, and 4/6 are unwinnable by
any arm at `max_iterations=3`.

> Retrieval quality appears capable of steering agent behavior,
> but this benchmark did not demonstrate an increase in task success.

---

## Salience v2 Recommendation

- **Core:** semantic similarity · importance · confidence (gated as
  `importance × confidence`).
- **Not promoted:** raw recency.
- **Possible future:** learned importance · contradiction-aware retrieval ·
  access-frequency weighting.

---

## Claims (for publication)

**Supported — we can claim:**

- salience improves retrieval quality
- salience improves contradiction avoidance
- confidence is valuable
- recency is weak
- retrieval changes agent behavior

**Unsupported — we cannot claim:**

- salience improves task success
- salience improves production outcomes
- salience generalizes beyond tested conditions

---

## Key Limitations

Synthetic benchmark · authored importance labels · authored confidence labels ·
single trial per task · only 6 execution tasks · dry-run execution ·
retrieval_limit sensitivity · execution benchmark still relatively small ·
task-success remains underpowered.

---

## Recommended Next Step

**Execution Study 5.2** on a larger, less-floored execution benchmark with multiple
trials and an iteration budget that lets correct approaches actually pass — the only
way to convert the demonstrated *behavioral* impact into a measurable *task-success*
result. No new retrieval experiments are needed.
