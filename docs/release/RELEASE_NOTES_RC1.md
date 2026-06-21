# Release Notes — v1.0.0-rc1

**Salience-Weighted Memory Retrieval for Long-Horizon Software Agents**
**Release candidate 1 · 2026-06-21**

First public release candidate of the Mars evaluation framework, the frozen Salience
Memory Benchmark v1.0.0, and the complete five-experiment research program with its
technical report, paper, and reproduction harness.

---

## Research Summary

Long-horizon software agents accumulate memory — decisions, postmortems, conventions,
and documentation that may go stale — and depend on retrieval to surface the right
context. Plain semantic similarity is a weak ranker for this: the most similar memory is
often a distractor or an outdated note. This release studies **salience-weighted
retrieval** — blending similarity with authored *importance* and *confidence* signals —
across five experiments on a single frozen, adversarial benchmark, including one study
that drives a real software agent.

## Major Findings

1. **Importance improves retrieval.** recall@5 0.237 → 0.672 (+0.435), MRR 0.313 → 0.967,
   nDCG@5 0.184 → 0.714; paired bootstrap CIs exclude zero (29–30/30 per-query wins).
2. **The advantage is robust to noisy importance.** Degrading importance from oracle to
   random degrades the gain gracefully and monotonically; it never collapses to the
   similarity baseline; ~78% of the win is attributable to the importance signal itself.
3. **Recency is not a reliable signal.** It helps only when artificially aligned with
   relevance (+0.262), hurts symmetrically when misaligned (−0.206), and is neutral in a
   realistic regime (+0.015 n.s.). **Not promoted** to a core signal.
4. **Confidence, as a multiplicative gate on importance, prevents contradiction
   failures.** When an important memory is wrong, importance-only collapses to
   ContradictionAvoidanceRate 0.000; gating restores it to 0.964.
5. **In a real agent, retrieval and behavior changed — task-success did not.** Over 18
   real AutoDev runs, salience-aware arms surfaced a corrective record the similarity arm
   missed (target-found 0.83 vs 0.00) and steered the agent to the repo's current
   convention (JWT over a stale session-cookie scheme), but task-success was unchanged
   (0.333 in every arm). **Outcome B.**

> **Honest bottom line:** salience improves retrieval, improves contradiction avoidance,
> and changes agent behavior. It has **not** been shown to improve task-success.

## Repositories

- **Mars** (this repo): evaluation framework, benchmark, experiments, results, paper.
  `https://github.com/alexanderjulianmartinez/mars`
- **Cortex / AutoDev / Sentinel:** separate systems consumed through provider interfaces;
  only their interfaces and mocks are included here.

## Artifacts

| Artifact | Location |
| --- | --- |
| Frozen benchmark v1.0.0 (SHA256 `a464085c…`) | `experiments/corpus/` |
| Result JSONs (Exp 1–5.1) | `mars-experiments/` |
| Technical report | `docs/reports/…_TECHNICAL_REPORT.md` |
| Executive summary | `docs/reports/…_EXECUTIVE_SUMMARY.md` |
| Consolidated paper (v2) + appendices | `docs/papers/salience_weighted_memory_retrieval_v2.md` |
| Figures (SVG + TikZ/PDF) | `docs/papers/figures/` |
| Reproducibility checklist (verified) | `docs/release/REPRODUCIBILITY_CHECKLIST.md` |
| Citation (CFF + BibTeX) | `CITATION.cff`, `docs/papers/citation.bib` |
| Research blog draft | `docs/publication/research_blog_draft.md` |

## Verification (this RC)

- 214 tests pass.
- `mars corpus verify-frozen` confirms SHA256 `a464085c…`.
- Experiments 2–4 reproduce **offline** with paper-matching numbers (committed cache).
- Data figures regenerate **byte-identically**.

## Known Limitations

- Synthetic, hand-authored corpus (no real production memory traces).
- Importance and confidence are **authored**, not learned → Experiment 1's effect is an
  **upper bound**; the contradiction regime is a synthetic stress test.
- Recency/frequency inert in Experiment 1 (simultaneous seeding); studied in Experiment 3.
- Execution study underpowered: single trial, 6 tasks, dry-run, 4/6 tasks floored.
- Single embedding model (`voyage-3-lite`) and single weight set.

## Future Research (not in this release)

- Larger, less-floored execution benchmark with statistical power on task-success.
- Learned importance estimation (locate it on the noisy-importance curve).
- Real-world memory traces; external replication; weight/embedding sensitivity sweeps.

## Upgrade / Reproduce

See `docs/release/REPRODUCIBILITY_CHECKLIST.md`. Tier 0 (tests, integrity, Experiments
2–4, figures) requires no credentials.

## RC scope & next step

This is a **release candidate**. Pending before `v1.0.0`: flip repository visibility to
public and a short soak for external reproduction feedback. (PR merged and the
`v1.0.0-rc1` tag is pushed.)

**Versioning (resolved):** two independent axes are tracked deliberately — the **Mars
framework package** (`pyproject`/`CITATION.cff` version `0.1.0`, an early-stage installable
library) and the **research release** (git tag `v1.0.0-rc1`) over the **frozen benchmark**
(`v1.0.0`, SHA256 `a464085c…`). The package version is intentionally *not* bumped to the
release tag: `name = "mars"` is the framework package and is not at a stable 1.0 API. See
`OPEN_SOURCE_RELEASE_PLAN.md` (Versioning) and `POST_TAG_STATUS.md`.
