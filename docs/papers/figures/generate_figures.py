#!/usr/bin/env python3
"""Generate publication SVG figures for the Salience-Weighted Memory Retrieval paper.

Pure standard library (no matplotlib/numpy) so it runs in the Mars venv unchanged.
Every number is hardcoded from the authoritative technical report / result JSONs
(`docs/reports/SALIENCE_WEIGHTED_MEMORY_RETRIEVAL_TECHNICAL_REPORT.md`,
`mars-experiments/*.json`). No value here is invented; this script only *draws*
already-published results.

Run:  .venv/bin/python docs/papers/figures/generate_figures.py
Out:  docs/papers/figures/figure{3,4,5,6,7,8,9}_*.svg

PNG: rasterize an SVG with any of
     rsvg-convert -w 1600 fig.svg -o fig.png   |   cairosvg fig.svg -o fig.png
     inkscape fig.svg --export-type=png        |   (or open in a browser and export)
"""
from __future__ import annotations

import html
from pathlib import Path

OUT = Path(__file__).resolve().parent

# Palette (colorblind-aware)
C_BASE = "#9aa3af"      # baseline / similarity-only (gray)
C_SAL = "#2563eb"       # salience / candidate (blue)
C_POS = "#16a34a"       # positive / helps (green)
C_NEG = "#dc2626"       # negative / hurts (red)
C_NEU = "#9aa3af"       # neutral
C_AXIS = "#374151"
C_GRID = "#e5e7eb"
C_TEXT = "#111827"
FONT = "font-family='Helvetica,Arial,sans-serif'"

# Category palette for corpus / ranking figures
CAT_COLORS = {
    "target": "#16a34a",
    "relevant": "#2563eb",
    "distractor": "#f59e0b",
    "stale": "#9aa3af",
    "contradictory": "#dc2626",
    "low_confidence": "#a855f7",
}


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def svg_open(w: int, h: int, title: str) -> list[str]:
    return [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}' "
        f"viewBox='0 0 {w} {h}' role='img' aria-label='{esc(title)}'>",
        f"<rect width='{w}' height='{h}' fill='white'/>",
    ]


def text(x, y, s, size=14, anchor="start", weight="normal", fill=C_TEXT, rot=None):
    tr = f" transform='rotate({rot} {x} {y})'" if rot is not None else ""
    return (f"<text x='{x}' y='{y}' {FONT} font-size='{size}' font-weight='{weight}' "
            f"text-anchor='{anchor}' fill='{fill}'{tr}>{esc(s)}</text>")


def write(name: str, lines: list[str]) -> None:
    lines.append("</svg>")
    (OUT / name).write_text("\n".join(lines))
    print(f"wrote {name}")


# ---------------------------------------------------------------------------
# Generic grouped-bar chart on a 0..ymax axis
# ---------------------------------------------------------------------------
def grouped_bars(name, title, groups, series, ymax=1.0, h=460, note=None,
                 value_fmt="{:.3f}"):
    """series: list of (label, color, values[len(groups)])."""
    w = 880
    ml, mr, mt, mb = 70, 30, 70, 110
    plot_w = w - ml - mr
    plot_h = h - mt - mb
    L = svg_open(w, h, title)
    L.append(text(ml, 34, title, size=18, weight="bold"))
    # y gridlines
    for i in range(6):
        yv = ymax * i / 5
        y = mt + plot_h - plot_h * (yv / ymax)
        L.append(f"<line x1='{ml}' y1='{y:.1f}' x2='{ml+plot_w}' y2='{y:.1f}' stroke='{C_GRID}'/>")
        L.append(text(ml - 8, y + 4, value_fmt.format(yv).rstrip("0").rstrip(".") if yv else "0",
                      size=11, anchor="end", fill=C_AXIS))
    n_groups = len(groups)
    n_series = len(series)
    gw = plot_w / n_groups
    bw = gw * 0.8 / n_series
    for gi, g in enumerate(groups):
        gx = ml + gi * gw + gw * 0.1
        for si, (slabel, color, vals) in enumerate(series):
            v = vals[gi]
            bh = plot_h * (v / ymax)
            x = gx + si * bw
            y = mt + plot_h - bh
            L.append(f"<rect x='{x:.1f}' y='{y:.1f}' width='{bw*0.92:.1f}' height='{bh:.1f}' fill='{color}'/>")
            L.append(text(x + bw * 0.46, y - 5, value_fmt.format(v), size=10, anchor="middle", fill=C_AXIS))
        L.append(text(ml + gi * gw + gw / 2, mt + plot_h + 18, g, size=12, anchor="middle"))
    # axis
    L.append(f"<line x1='{ml}' y1='{mt+plot_h}' x2='{ml+plot_w}' y2='{mt+plot_h}' stroke='{C_AXIS}'/>")
    # legend
    lx = ml
    ly = h - 50
    for slabel, color, _ in series:
        L.append(f"<rect x='{lx}' y='{ly-10}' width='14' height='14' fill='{color}'/>")
        L.append(text(lx + 20, ly + 2, slabel, size=12))
        lx += 30 + 9 * len(slabel)
    if note:
        L.append(text(ml, h - 18, note, size=11, fill=C_AXIS))
    write(name, L)


# ---------------------------------------------------------------------------
# Figure 3 — Benchmark composition (horizontal bars)
# ---------------------------------------------------------------------------
def figure3():
    data = [("distractor", 210), ("relevant", 102), ("stale", 90),
            ("low_confidence", 90), ("contradictory", 30), ("target", 30)]
    w, h = 880, 420
    ml, mr, mt, mb = 150, 60, 60, 50
    plot_w = w - ml - mr
    maxv = 210
    L = svg_open(w, h, "Benchmark composition")
    L.append(text(ml - 110, 34, "Figure 3 — Benchmark Composition (552 memories, 30 queries)",
                  size=17, weight="bold"))
    bar_h = (h - mt - mb) / len(data) * 0.7
    gap = (h - mt - mb) / len(data)
    for i, (cat, cnt) in enumerate(data):
        y = mt + i * gap
        bw = plot_w * cnt / maxv
        L.append(f"<rect x='{ml}' y='{y:.1f}' width='{bw:.1f}' height='{bar_h:.1f}' fill='{CAT_COLORS[cat]}'/>")
        L.append(text(ml - 10, y + bar_h * 0.7, cat, size=13, anchor="end"))
        L.append(text(ml + bw + 8, y + bar_h * 0.7, str(cnt), size=12, fill=C_AXIS))
    L.append(text(ml, h - 18, "Adversarial by design: 210 high-overlap distractors carry low importance.",
                  size=11, fill=C_AXIS))
    write("figure3_corpus_composition.svg", L)


# ---------------------------------------------------------------------------
# Figure 4 — Experiment 1 results
# ---------------------------------------------------------------------------
def figure4():
    groups = ["recall@5", "recall@10", "MRR", "nDCG@5", "TgtFound@3", "CtxEff@5"]
    base = [0.237, 0.761, 0.313, 0.184, 0.367, 0.200]
    sal = [0.672, 0.931, 0.967, 0.714, 1.000, 0.567]
    grouped_bars(
        "figure4_exp1_results.svg",
        "Figure 4 — Experiment 1: Salience vs Similarity Retrieval",
        groups,
        [("similarity_only", C_BASE, base), ("salience_weighted_v1", C_SAL, sal)],
        ymax=1.0,
        note="Real Cortex retrieval (Voyage voyage-3-lite). recall@5 +0.435, MRR 0.31→0.97. Effect size is an upper bound (authored importance).",
    )


# ---------------------------------------------------------------------------
# Figure 5 — Noisy importance (line chart)
# ---------------------------------------------------------------------------
def figure5():
    quality = [1.00, 0.75, 0.50, 0.25, 0.00]
    recall = [0.672, 0.593, 0.506, 0.420, 0.330]
    ci_lo = [0.672 - 0.435 + 0.370, 0.0, 0.0, 0.0, 0.0]  # not all needed; band drawn from Δ CIs textually
    baseline = 0.237
    w, h = 880, 480
    ml, mr, mt, mb = 70, 40, 70, 90
    plot_w = w - ml - mr
    plot_h = h - mt - mb
    ymin, ymax = 0.2, 0.72
    L = svg_open(w, h, "Noisy importance")
    L.append(text(ml, 34, "Figure 5 — Experiment 2: Robustness under Noisy Importance", size=17, weight="bold"))

    def xpix(q):  # quality 1.0 (left) -> 0.0 (right)
        return ml + plot_w * (1.0 - q)

    def ypix(v):
        return mt + plot_h - plot_h * (v - ymin) / (ymax - ymin)

    # grid + y labels
    for i in range(6):
        yv = ymin + (ymax - ymin) * i / 5
        y = ypix(yv)
        L.append(f"<line x1='{ml}' y1='{y:.1f}' x2='{ml+plot_w}' y2='{y:.1f}' stroke='{C_GRID}'/>")
        L.append(text(ml - 8, y + 4, f"{yv:.2f}", size=11, anchor="end", fill=C_AXIS))
    # x labels
    for q in quality:
        x = xpix(q)
        L.append(text(x, mt + plot_h + 20, f"{q:.2f}", size=12, anchor="middle"))
    L.append(text(ml + plot_w / 2, h - 40, "importance quality  (1.0 = oracle  →  0.0 = scrambled)",
                  size=12, anchor="middle", fill=C_AXIS))
    # baseline reference
    yb = ypix(baseline)
    L.append(f"<line x1='{ml}' y1='{yb:.1f}' x2='{ml+plot_w}' y2='{yb:.1f}' stroke='{C_NEG}' stroke-dasharray='6 4'/>")
    L.append(text(ml + plot_w - 4, yb - 6, "similarity baseline 0.237", size=11, anchor="end", fill=C_NEG))
    # salience curve
    pts = " ".join(f"{xpix(q):.1f},{ypix(v):.1f}" for q, v in zip(quality, recall))
    L.append(f"<polyline points='{pts}' fill='none' stroke='{C_SAL}' stroke-width='2.5'/>")
    for q, v in zip(quality, recall):
        L.append(f"<circle cx='{xpix(q):.1f}' cy='{ypix(v):.1f}' r='4' fill='{C_SAL}'/>")
        L.append(text(xpix(q), ypix(v) - 10, f"{v:.3f}", size=10, anchor="middle", fill=C_AXIS))
    L.append(text(ml, h - 16, "Every Δ-recall@5 CI excludes zero down to q=0; oracle−scrambled = +0.341 (~78% of the win is the importance signal).",
                  size=11, fill=C_AXIS))
    write("figure5_noisy_importance.svg", L)


# ---------------------------------------------------------------------------
# Figure 6 — Temporal salience (diverging bars)
# ---------------------------------------------------------------------------
def figure6():
    regimes = [("A uniform", 0.000, C_NEU), ("B aligned", 0.262, C_POS),
               ("C misaligned", -0.206, C_NEG), ("D realistic", 0.015, C_NEU)]
    w, h = 820, 420
    ml, mr, mt, mb = 130, 40, 70, 70
    plot_w = w - ml - mr
    plot_h = h - mt - mb
    vmax = 0.30
    zx = ml + plot_w / 2
    L = svg_open(w, h, "Temporal salience")
    L.append(text(ml - 80, 34, "Figure 6 — Experiment 3: Isolated Recency Marginal (Δrecall@5)", size=16, weight="bold"))
    L.append(f"<line x1='{zx}' y1='{mt}' x2='{zx}' y2='{mt+plot_h}' stroke='{C_AXIS}'/>")
    bh = plot_h / len(regimes) * 0.55
    gap = plot_h / len(regimes)
    for i, (lab, val, col) in enumerate(regimes):
        y = mt + i * gap + (gap - bh) / 2
        bw = plot_w / 2 * abs(val) / vmax
        x = zx if val >= 0 else zx - bw
        L.append(f"<rect x='{x:.1f}' y='{y:.1f}' width='{bw:.1f}' height='{bh:.1f}' fill='{col}'/>")
        L.append(text(ml - 10, y + bh * 0.7, lab, size=12, anchor="end"))
        tx = zx + bw + 6 if val >= 0 else zx - bw - 6
        ta = "start" if val >= 0 else "end"
        L.append(text(tx, y + bh * 0.7, f"{val:+.3f}", size=11, anchor=ta, fill=C_AXIS))
    L.append(text(zx, mt + plot_h + 24, "0", size=11, anchor="middle", fill=C_AXIS))
    L.append(text(ml - 80, h - 16, "Recency helps only when aligned, hurts when misaligned, neutral when realistic. importance_only is regime-invariant (recall@5 0.985).",
                  size=11, fill=C_AXIS))
    write("figure6_temporal_salience.svg", L)


# ---------------------------------------------------------------------------
# Figure 7 — Confidence / contradiction (CAR grouped bars)
# ---------------------------------------------------------------------------
def figure7():
    regimes = ["A", "B", "C", "D", "E (imp-but-wrong)"]
    series = [
        ("similarity_only", C_BASE, [0.643, 0.643, 0.643, 0.643, 0.643]),
        ("importance_only", "#f59e0b", [1.000, 1.000, 1.000, 1.000, 0.000]),
        ("confidence_only", "#a855f7", [0.479, 1.000, 1.000, 1.000, 1.000]),
        ("importance×confidence (gated)", C_POS, [0.964, 0.964, 0.964, 0.964, 0.964]),
    ]
    grouped_bars(
        "figure7_confidence_contradiction.svg",
        "Figure 7 — Experiment 4: ContradictionAvoidanceRate by Regime",
        regimes, series, ymax=1.0, h=500,
        note="Regime E (important-but-wrong): importance_only collapses to 0.000; gated confidence restores 0.964 — robust across every regime.",
    )


# ---------------------------------------------------------------------------
# Figure 8 — Execution impact 5.1
# ---------------------------------------------------------------------------
def figure8():
    arms = ["A similarity", "B sim+importance", "C salience_v2"]
    series = [
        ("task success", C_BASE, [0.333, 0.333, 0.333]),
        ("recall@5", C_SAL, [0.000, 0.833, 0.833]),
        ("target found", "#0891b2", [0.000, 0.833, 0.833]),
        ("right approach", C_POS, [0.833, 1.000, 1.000]),
    ]
    grouped_bars(
        "figure8_execution_impact.svg",
        "Figure 8 — Experiment 5.1: Execution Impact (18 real AutoDev runs)",
        arms, series, ymax=1.0, h=500,
        note="Outcome B: retrieval (target-found 0.00→0.83) and behavior (right-approach 0.83→1.00) improve; task-success unchanged (0.333 all arms).",
    )


# ---------------------------------------------------------------------------
# Figure 9 — Ranking example (two ranked columns)
# ---------------------------------------------------------------------------
def figure9():
    before = [("distractor", "sim 0.79 / imp 0.05"), ("distractor", "sim 0.78 / imp 0.07"),
              ("distractor", "sim 0.77 / imp 0.04"), ("contradictory", "sim 0.74"),
              ("relevant", "support"), ("target", "TARGET — rank 6")]
    after = [("target", "TARGET — rank 1"), ("relevant", "support"),
             ("relevant", "support"), ("distractor", "imp 0.05"),
             ("distractor", "imp 0.07"), ("contradictory", "demoted")]
    w, h = 880, 460
    colw = 320
    x1, x2 = 70, 70 + colw + 120
    mt = 90
    rh = 46
    L = svg_open(w, h, "Ranking example")
    L.append(text(70, 34, "Figure 9 — Worked Example: Migration Query Re-ranking", size=17, weight="bold"))
    L.append(text(x1, mt - 14, "similarity_only", size=14, weight="bold", fill=C_BASE))
    L.append(text(x2, mt - 14, "+ importance", size=14, weight="bold", fill=C_SAL))
    for col_x, col in ((x1, before), (x2, after)):
        for i, (cat, note) in enumerate(col):
            y = mt + i * rh
            L.append(f"<rect x='{col_x}' y='{y}' width='{colw}' height='{rh-8}' rx='4' "
                     f"fill='{CAT_COLORS[cat]}' opacity='0.85'/>")
            L.append(text(col_x + 10, y + 19, f"{i+1}. {cat}", size=12, weight="bold", fill="white"))
            L.append(text(col_x + 10, y + 33, note, size=10, fill="white"))
    L.append(f"<path d='M {x1+colw+10} {mt+30} L {x2-10} {mt+30}' stroke='{C_AXIS}' "
             f"marker-end='url(#a)' fill='none'/>")
    L.insert(2, "<defs><marker id='a' markerWidth='10' markerHeight='10' refX='8' refY='3' "
                "orient='auto'><path d='M0,0 L8,3 L0,6 Z' fill='#374151'/></marker></defs>")
    L.append(text(70, h - 16, "Importance lifts the relevant target from rank 6 to rank 1 and demotes high-overlap distractors.",
                  size=11, fill=C_AXIS))
    write("figure9_ranking_example.svg", L)


if __name__ == "__main__":
    figure3()
    figure4()
    figure5()
    figure6()
    figure7()
    figure8()
    figure9()
    print("done")
