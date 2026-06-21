# Figure Review

Consistency and publication-quality review of all ten figures. Data figures (3–9) are
SVG from `generate_figures.py`; diagram figures (1, 2, 10) are TikZ from `diagrams.tex`.
Cross-checked against the technical report and the v2 paper.

Status: **OK** · **MINOR** (cosmetic, non-blocking) · **FIX** (should change before camera-ready)

---

## Per-figure review

| Fig | Title | Type | Data matches report | Status |
| --- | --- | --- | --- | --- |
| 1 | System Architecture | TikZ | n/a (schematic) | **OK** |
| 2 | Retrieval Pipeline | TikZ | n/a (schematic) | **OK** |
| 3 | Benchmark Composition | SVG | 210/102/90/90/30/30 = 552 ✓ | **OK** |
| 4 | Experiment 1 results | SVG | recall@5 0.237→0.672, MRR 0.313→0.967 ✓ | **OK** |
| 5 | Noisy Importance | SVG | 0.672/0.593/0.506/0.420/0.330; baseline 0.237 ✓ | **MINOR** |
| 6 | Temporal Salience | SVG | A +0.000, B +0.262, C −0.206, D +0.015 ✓ | **MINOR** |
| 7 | Confidence / Contradiction (CAR) | SVG | 0.643 / 0.000 / 0.964 etc. ✓ | **OK** |
| 8 | Execution Impact | SVG | success 0.333; recall 0/0.833; right-approach 0.833/1.0 ✓ | **OK** |
| 9 | Ranking Example | SVG | sim ≈0.77–0.79, imp ≈0.04–0.07, target rank 6→1 ✓ | **OK** |
| 10 | Research Program Overview | TikZ | finding panels match §9 synthesis ✓ | **OK** |

All numeric figures were cross-checked against the technical report; **no figure
contains a value absent from the source artifacts.**

---

## Consistency checks

**Labels & terminology — consistent.**
- Strategy names: `similarity_only`, `salience_weighted_v1`, `importance_only`,
  `confidence_only`, `importance × confidence (gated)`, `sim+importance`, `salience_v2`
  — match the paper's usage. ✓
- Metric names: recall@K, MRR, nDCG@5, TargetFound@K (abbreviated `TgtFound`),
  ContextEfficiency@5 (abbreviated `CtxEff`). Abbreviations are figure-only and are
  spelled out in captions. ✓
- "Outcome B" terminology in Fig 8 matches §9.2. ✓

**Units & scales — consistent.**
- All metric axes are on the [0, 1] scale; Fig 6 is a signed Δ (diverging axis centered
  at 0). No mixed units. ✓
- Δ values carry explicit signs; CIs use `[lo, hi]`. ✓

**Color semantics — consistent across figures.**
- Gray = baseline/similarity; blue = salience/candidate; green = positive/helps/robust;
  red = negative/hurts/baseline-reference; amber/purple = additional strategies in the
  multi-series figures (7, 8). Applied uniformly. ✓

**Fonts — consistent.**
- SVGs use Helvetica/Arial; TikZ uses `helvet` (a Helvetica clone). Visually consistent
  when figures are placed together. ✓

---

## Findings

**MINOR-1 (Fig 5).** The caption/figure note states "every Δrecall@5 CI excludes zero
down to q=0," which is correct, but the figure draws only the salience curve and the
baseline reference line, not the per-point CI bands. For camera-ready, consider adding
faint CI whiskers at each point (values are in Table 4a). Non-blocking; the curve plus
the baseline reference already tells the story.

**MINOR-2 (Fig 6).** Labels use the Unicode minus `−` (U+2212), which renders correctly
in SVG/browsers and matches the paper, but some downstream LaTeX `\includegraphics`
pipelines prefer ASCII. Harmless for SVG/PNG inclusion; only relevant if the SVG text is
re-typeset. Leave as-is unless a venue complains.

**MINOR-3 (generator hygiene, not a figure defect).** `generate_figures.py` computes an
unused `ci_lo` list in the Fig 5 routine (dead code). Cosmetic; does not affect output.
Optional cleanup.

**No FIX-level issues.** Nothing blocks the release candidate.

---

## Publication-quality assessment

- **Vector-native:** all figures are SVG or PDF (TikZ), so they scale losslessly for
  print and screen. PNG export for web/blog is a one-line rasterize (documented in
  `figures/README.md`); no rasterizer is bundled in the dev env.
- **Reproducible:** data figures regenerate **byte-identically** (`git status` clean
  after rerun — verified this session), so figures cannot silently drift from the data.
- **Self-describing:** every figure carries a title and a one-line provenance/finding
  note; full captions live in `FIGURE_PLAN.md` and the paper.

**Verdict:** figures are publication-ready. The three MINOR items are optional polish
for camera-ready and do not block v1.0.0-rc1.
