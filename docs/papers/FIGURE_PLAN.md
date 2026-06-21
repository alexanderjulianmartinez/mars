# Figure Plan

Specifications for all paper figures. Figures whose data exists are rendered as SVG
in `docs/papers/figures/` (Phase 4); diagram figures (architecture/pipeline/roadmap)
ship as placeholder specs to be drawn in a vector tool.

**Data provenance:** all numbers trace to the technical report and the result JSONs
under `mars-experiments/`. No figure may introduce a number not present in those
artifacts. PNG is produced by rasterizing the SVG (see Phase 4 note).

Legend: **[DATA]** = renderable from existing numbers · **[DIAGRAM]** = schematic,
hand-drawn.

---

## Figure 1 — System Architecture  **[DIAGRAM]**
- **Purpose:** Show the four systems and the hard ownership boundary; clarify what
  this paper exercises (Cortex + Mars) vs. mentions (AutoDev in §execution, Sentinel
  reserved).
- **Data source:** `ARCHITECTURE.md`, `CLAUDE.md` boundary description.
- **Chart type:** Boxes-and-arrows block diagram.
- **Caption draft:** "Figure 1: System boundaries. Cortex owns memory and retrieval;
  Mars owns experimentation and scoring; AutoDev owns agent execution (used only in
  the execution study); Sentinel owns provenance (reserved). Mars consumes Cortex and
  AutoDev through provider interfaces and never generates context or executes tasks."
- **Placement:** §Experimental Framework, top.
- **Required inputs:** boundary text. **Required outputs:** `figure1_architecture.svg` (spec only).

## Figure 2 — Retrieval Pipeline  **[DIAGRAM]**
- **Purpose:** Show query → Cortex semantic retrieval (Voyage) → per-query pool →
  re-ranking by {similarity_only | salience_weighted_v1} → top-K → metrics vs gold.
- **Data source:** `mars/memory/retrieval_source.py`, `salience_v1.py`.
- **Chart type:** Left-to-right flow diagram; annotate "both strategies re-rank the
  SAME pool".
- **Caption draft:** "Figure 2: Retrieval and evaluation pipeline. Both ranking
  strategies re-rank an identical per-query candidate pool, isolating the ranking
  function from first-stage embedding recall."
- **Placement:** §Experimental Framework.
- **Required inputs:** pipeline description. **Required outputs:** `figure2_pipeline.svg` (spec only).

## Figure 3 — Benchmark Composition  **[DATA]**
- **Purpose:** Make the adversarial corpus design legible (distractors dominate).
- **Data source:** Tech report §1 corpus table — target 30, relevant 102, distractor
  210, stale 90, contradictory 30, low_confidence 90 (total 552).
- **Chart type:** Horizontal stacked/grouped bar (counts by category).
- **Caption draft:** "Figure 3: Composition of Salience Memory Benchmark v1.0.0 (552
  memories, 30 queries). High-overlap distractors (210) and stale/contradictory
  memories are engineered to defeat similarity-only ranking."
- **Placement:** §Experimental Framework / Benchmark.
- **Required inputs:** category counts. **Required outputs:** `figure3_corpus_composition.svg`.

## Figure 4 — Salience Memory Results (Experiment 1)  **[DATA]**
- **Purpose:** Headline retrieval result across the metric suite.
- **Data source:** Tech report §2 results table.
- **Chart type:** Grouped bar chart, similarity_only vs salience_weighted_v1 across
  recall@5, recall@10, MRR, nDCG@5, TargetFound@3, ContextEfficiency@5.
- **Caption draft:** "Figure 4: Experiment 1. Importance-weighted retrieval improves
  every metric over similarity-only on the frozen benchmark (recall@5 +0.435, MRR
  0.31→0.97). Effect size is an upper bound under authored importance."
- **Placement:** §Experiment 1.
- **Required inputs:** Exp 1 metrics. **Required outputs:** `figure4_exp1_results.svg`.

## Figure 5 — Noisy Importance Results (Experiment 2)  **[DATA]**
- **Purpose:** Show graceful, monotonic degradation; advantage never collapses.
- **Data source:** Tech report §3 sweep table (quality 1.00→0.00 → recall@5 + Δ CI).
- **Chart type:** Line chart, recall@5 vs importance-quality, with similarity
  baseline (0.237) as a horizontal reference and CI band.
- **Caption draft:** "Figure 5: Experiment 2. As authored importance is degraded from
  oracle (1.0) to scrambled (0.0), the salience advantage shrinks monotonically but
  never reaches the similarity baseline; every confidence interval excludes zero."
- **Placement:** §Experiment 2.
- **Required inputs:** sweep values. **Required outputs:** `figure5_noisy_importance.svg`.

## Figure 6 — Temporal Salience Results (Experiment 3)  **[DATA]**
- **Purpose:** Show recency's isolated marginal flips sign by regime; importance is
  flat.
- **Data source:** Tech report §4 marginal table (A +0.000, B +0.262, C −0.206, D
  +0.015).
- **Chart type:** Diverging horizontal bar (recency marginal Δrecall@5 by regime),
  zero line centered, CI whiskers.
- **Caption draft:** "Figure 3 [6]: Experiment 3. The isolated recency marginal helps
  only when recency is aligned with relevance (B), hurts symmetrically when
  misaligned (C), and is statistically neutral in the realistic regime (D).
  Importance is regime-invariant. Recency is not promoted to a core signal."
- **Placement:** §Experiment 3.
- **Required inputs:** regime marginals. **Required outputs:** `figure6_temporal_salience.svg`.

## Figure 7 — Confidence / Contradiction Results (Experiment 4)  **[DATA]**
- **Purpose:** Show gated confidence is the only strategy robust across all regimes,
  especially E.
- **Data source:** Tech report §5 CAR table (4 strategies × regimes A–E).
- **Chart type:** Grouped bar of ContradictionAvoidanceRate by strategy, highlighting
  regime E: importance_only 0.000, gated 0.964, similarity 0.643.
- **Caption draft:** "Figure 7: Experiment 4. ContradictionAvoidanceRate. In the
  adversarial important-but-wrong regime (E), importance-only collapses to 0.000;
  confidence applied as a multiplicative gate on importance restores 0.964 — the only
  importance-based strategy robust across every regime."
- **Placement:** §Experiment 4.
- **Required inputs:** CAR matrix. **Required outputs:** `figure7_confidence_contradiction.svg`.

## Figure 8 — Execution Impact Results (Experiment 5.1)  **[DATA]**
- **Purpose:** Show the Outcome-B split: retrieval/target-found rise across arms while
  task-success stays flat.
- **Data source:** Tech report §7 results table (arm × success/recall@5/target-found/
  MRR; right-approach 0.83 vs 1.00).
- **Chart type:** Grouped bar, three arms (A/B/C) × {success, recall@5, target-found,
  right-approach}, with success annotated as flat 0.333.
- **Caption draft:** "Figure 8: Experiment 5.1 (18 real AutoDev runs). Importance-aware
  arms surface the corrective record (target-found 0.83 vs 0.00) and change agent
  behavior (right-approach 1.00 vs 0.83), but task-success is unchanged (0.333 in all
  arms). Outcome B: retrieval and behavior improve; task-success does not."
- **Placement:** §Experiment 5.1.
- **Required inputs:** Exp 5.1 metrics. **Required outputs:** `figure8_execution_impact.svg`.

## Figure 9 — Retrieval Ranking Example  **[DATA]**
- **Purpose:** Concrete mechanism — the migration query; target buried at rank 6 under
  similarity, lifted to top under importance.
- **Data source:** Tech report §2 mechanism paragraph (distractors sim ≈ 0.77–0.79,
  importance ≈ 0.04–0.07; target at rank 6 → top).
- **Chart type:** Two side-by-side ranked lists (before/after), color-coded by
  category, with sim/importance annotations.
- **Caption draft:** "Figure 9: Worked example (migration query). Under similarity-only
  three high-overlap distractors and a contradiction outrank the target (rank 6).
  Adding importance lifts the relevant memory to the top."
- **Placement:** §Experiment 1 (mechanism).
- **Required inputs:** the example ranks. **Required outputs:** `figure9_ranking_example.svg`.

## Figure 10 — Research Program Overview  **[DIAGRAM/DATA]**
- **Purpose:** Tie the five experiments into one narrative with each finding + the
  signal-promotion decision.
- **Data source:** Tech report §9 synthesis + §10 v2 recommendation.
- **Chart type:** Horizontal flow / DAG: Exp1→2→3→4→5.1 with a one-line finding under
  each and a "core v2 signals = similarity + importance + gated confidence; recency
  excluded" panel.
- **Caption draft:** "Figure 10: The Salience & Attention research program. Importance
  helps retrieval (1) and survives noise (2); recency is unreliable (3); gated
  confidence rescues contradictions (4); inside a real agent, retrieval and behavior
  change but task-success does not (5.1)."
- **Placement:** §Introduction or §Conclusion.
- **Required inputs:** synthesis text. **Required outputs:** `figure10_program_overview.svg` (spec + data panels).

---

## Rendering status summary
| Fig | Type | Renderable now |
| --- | --- | --- |
| 1 Architecture | DIAGRAM | spec only |
| 2 Pipeline | DIAGRAM | spec only |
| 3 Corpus | DATA | **yes** |
| 4 Exp 1 | DATA | **yes** |
| 5 Exp 2 | DATA | **yes** |
| 6 Exp 3 | DATA | **yes** |
| 7 Exp 4 | DATA | **yes** |
| 8 Exp 5.1 | DATA | **yes** |
| 9 Ranking example | DATA | **yes** |
| 10 Program overview | DIAGRAM+DATA | partial (finding panels yes, layout schematic) |
