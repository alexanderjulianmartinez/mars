# Executive Release Summary

**Salience-Weighted Memory Retrieval for Long-Horizon Software Agents**
**v1.0.0-rc1 · 2026-06-21 · one page**

*Audience: engineering leaders, researchers, hiring managers, recruiters.*

---

## What was built

A complete, reproducible research program — and the infrastructure to run it — answering
a practical question about AI agent memory:

- **A frozen, adversarial benchmark** (Salience Memory Benchmark v1.0.0: 30 queries, 552
  memories, hash-pinned) purpose-built so that ranking memories by similarity alone
  *fails* — the realistic long-horizon case where the most similar memory is a distractor
  or a stale note.
- **Mars**, an evaluation framework that runs retrieval experiments, computes metrics,
  performs paired-bootstrap significance testing, and drives real agent runs through a
  clean provider boundary (it measures; it does not execute or generate context itself).
- **Five experiments**, a technical report, a consolidated paper, ten figures, and a
  reproduction harness where the core results rerun offline with no credentials.

## What was discovered

> Adding one signal — *how important a memory is* — to the retrieval ranker substantially
> improves which memories an agent sees, and changes what the agent does. It does not
> (yet) make the agent finish more tasks.

- **Retrieval improves a lot and robustly.** recall@5 0.24 → 0.67, MRR 0.31 → 0.97, with
  statistically significant, near-unanimous per-query wins — and the gain survives heavy
  corruption of the importance signal rather than collapsing.
- **Some intuitions fail.** Recency, a seemingly obvious signal, was unreliable and was
  deliberately cut. Confidence mattered only in a specific form — as a *gate* on
  importance — where it rescued the agent from acting on important-but-wrong memories.
- **The honest result inside a real agent:** better retrieval changed the agent's
  behavior (it adopted the codebase's current convention over a stale one) but did **not**
  raise task-success. We report that null plainly rather than overclaiming.

## Why it matters

- **For agent builders:** memory retrieval is a real lever — a single prioritization
  signal beats similarity-only ranking by a wide margin — but a retrieval win is **not**
  automatically a task-success win. That distinction is the difference between a demo and
  a measured system.
- **For research/eng leaders:** the work models the discipline that keeps agent claims
  trustworthy — adversarial benchmarks that can fail, ablations that cut weak signals, and
  a strict separation of proxy metrics from outcome metrics, with the null reported.
- **For evaluation infrastructure:** the result is reproducible against a frozen hash with
  a committed cache, so the numbers can be independently checked, not just believed.

## What comes next

The retrieval question is well characterized; the open frontier is **execution**:

- A larger, less-floored agent benchmark where task-success has the statistical power to
  move.
- **Learned** importance (this work used authored importance, so the headline effect is an
  upper bound).
- Real-world memory traces and independent external replication.

---

**Status:** research complete and verified; release candidate ready. Public release is
gated only on standard mechanics (merge, tag, visibility). Full detail in the technical
report and `RELEASE_NOTES_RC1.md`.
