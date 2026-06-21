# Paper Figures

Publication figures for *Salience-Weighted Memory Retrieval for Long-Horizon
Software Agents*. All rendered figures are generated from the authoritative result
numbers (technical report + `mars-experiments/*.json`) — **no figure introduces a
number absent from those artifacts**.

## Regenerate
```bash
.venv/bin/python docs/papers/figures/generate_figures.py
```

## Rasterize to PNG (no rasterizer bundled in this env)
Pick any one:
```bash
rsvg-convert -w 1600 figure4_exp1_results.svg -o figure4_exp1_results.png
cairosvg figure4_exp1_results.svg -o figure4_exp1_results.png --output-width 1600
inkscape figure4_exp1_results.svg --export-type=png --export-width=1600
# or open the .svg in any browser and "Export as PNG"
```

## Rendered (data-driven, ready)
| File | Figure | Experiment |
| --- | --- | --- |
| `figure3_corpus_composition.svg` | Benchmark composition | corpus |
| `figure4_exp1_results.svg` | Salience vs similarity retrieval | 1 |
| `figure5_noisy_importance.svg` | Robustness under noisy importance | 2 |
| `figure6_temporal_salience.svg` | Isolated recency marginal | 3 |
| `figure7_confidence_contradiction.svg` | ContradictionAvoidanceRate | 4 |
| `figure8_execution_impact.svg` | Execution impact (Outcome B) | 5.1 |
| `figure9_ranking_example.svg` | Migration-query re-ranking | 1 (mechanism) |

## Diagram figures (TikZ source)
Figures 1 (System Architecture), 2 (Retrieval Pipeline), and 10 (Research Program
Overview) are schematic diagrams authored in `diagrams.tex` (one figure per page).

```bash
pdflatex diagrams.tex        # -> diagrams.pdf (3 pages: Fig 1, Fig 2, Fig 10)
```

Crop/export per page for inclusion (e.g. `pdfseparate`, or import the page into the
paper directly). `diagrams.pdf` is the rendered output; `diagrams.tex` is the source of
truth. Full specs are in `../FIGURE_PLAN.md`.
