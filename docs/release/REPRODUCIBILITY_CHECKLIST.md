# Reproducibility Checklist

**Audience:** an external researcher with a clean checkout and no tribal knowledge.
**Date verified:** 2026-06-21 (every command below was executed; outputs are observed,
not assumed).

Three tiers. **Tier 0 needs no credentials** and reproduces Experiments 2–4, the
benchmark integrity check, the figures, and the full test suite. Tier 1 adds the live
semantic baseline (Experiment 1). Tier 2 adds real agent execution (Experiment 5.1).

---

## 0. Prerequisites

| Requirement | Version | Notes |
| --- | --- | --- |
| Python | 3.12 | exact (typed codebase targets 3.12) |
| uv | latest | https://github.com/astral-sh/uv |
| OS | macOS/Linux | developed on darwin; no OS-specific steps |
| Credentials | none for Tier 0 | Voyage key for Tier 1; `MARS_AUTODEV_MCP_*` for Tier 2 |

No GPU. No network for Tier 0 (retrieval served from the committed cache).

---

## 1. Clean checkout & install

```bash
git clone https://github.com/alexanderjulianmartinez/mars.git
cd mars
uv venv --python 3.12
uv pip install -e ".[dev]"
```

**Expected:** a `.venv/` with the `mars` CLI. Use the venv binaries directly
(`.venv/bin/mars`, `.venv/bin/python`) — there is no activated shell in CI-style use.

---

## 2. Run the test suite

```bash
.venv/bin/python -m pytest -q
```

**Expected (observed 2026-06-21):** 214 tests, **all pass**, no failures/errors.
Output ends with three full rows of dots and `[100%]`.

---

## 3. Benchmark integrity (the frozen-corpus contract)

```bash
.venv/bin/mars corpus verify-frozen salience-memory-benchmark-v1
```

**Expected (observed):**
```
✓ salience-memory-benchmark-v1 v1.0.0 frozen & verified
  sha256: a464085c3daa64c97d2764c47f8758931b2a51c2adc1e143fcfc98d9faa74d59
```
plus the category table: target 30, relevant 102, distractor 210, stale 90,
contradictory 30, low_confidence 90 (total **552**). If the SHA256 differs, the corpus
has been mutated — stop and investigate; do not trust downstream numbers.

```bash
.venv/bin/mars corpus stats salience-memory-v1-expanded   # 30 queries / 552 memories
```

---

## 4. Reproduce metrics & tables (Tier 0 — offline)

All three reuse the committed retrieval cache (`experiments/cache/`); no network.

```bash
# Experiment 2 — Noisy Importance (Table 4a)
.venv/bin/python experiments/run_noisy_importance.py --cache-only

# Experiment 3 — Temporal Salience (Table 4b)
.venv/bin/python experiments/run_temporal_salience.py

# Experiment 4 — Confidence & Contradiction (Table 4c)
.venv/bin/python experiments/run_confidence_contradiction.py
```

**Expected (observed values that match the paper):**

| Check | Expected | Observed |
| --- | --- | --- |
| Exp 2, q=0.25 Δrecall@5 | +0.183 [+0.142, +0.224] | ✓ matches |
| Exp 2, q=0.00 Δrecall@5 | +0.094 [+0.050, +0.139] | ✓ matches |
| Exp 3, regime A recency marginal | +0.000 [+0.000, +0.000] | ✓ matches |
| Exp 3, regime B recency marginal | +0.262 [+0.210, +0.316] | ✓ matches |
| Exp 4, CAR `similarity_only` | 0.643 (28q) | ✓ matches |
| Exp 4, CAR gated confidence | 0.964 (28q) | ✓ matches |

These reproduce Tables 4a–4c of the paper exactly. Results are written to
`mars-experiments/*.json`.

---

## 5. Reproduce figures

```bash
# Data figures (3–9): pure-stdlib generator, no matplotlib/numpy needed
.venv/bin/python docs/papers/figures/generate_figures.py

# Determinism check — should print NOTHING (byte-identical regeneration)
git status --short docs/papers/figures/
```

**Expected (observed):** seven SVGs written; `git status` clean afterward (the figures
regenerate **byte-identically**, confirming they are a deterministic function of the
committed numbers).

```bash
# Diagram figures (1, 2, 10)
cd docs/papers/figures && pdflatex diagrams.tex      # -> diagrams.pdf (3 pages)
```

**Expected:** clean compile, `diagrams.pdf` with 3 pages. Requires a TeX
distribution with TikZ + amsmath (TeX Live 2024 verified). If no TeX is available, the
committed `diagrams.pdf` is the rendered reference.

---

## 6. Tier 1 — live semantic baseline (Experiment 1, optional)

```bash
export VOYAGE_API_KEY=...                 # required for live embeddings
export MARS_CORTEX_MCP_URL=...            # a reachable Cortex MCP endpoint
.venv/bin/mars experiments run salience-memory-v1 --cortex-provider mcp --strict-semantic
```

**Expected:** recall@5 0.237 → 0.672 (Δ +0.435), MRR 0.313 → 0.967 (Table 3).
`--strict-semantic` makes the run **fail loudly** if `semantic_score` is null rather
than silently reporting a non-semantic result (the framework's honesty constraint).

## 7. Tier 2 — real agent execution (Experiment 5.1, optional, paid ≈$1.3)

```bash
export MARS_AUTODEV_MCP_URL=...           # a reachable AutoDev MCP endpoint
.venv/bin/python experiments/launch_exec_impact_5_1.py --real-autodev --dry-run \
    --issues-file experiments/execution_impact_5_1/issues.yaml \
    --retrieval-limit 3 --experiment salience-memory-execution-impact-5-1
```

**Expected:** 18 runs; success 0.333 in every arm; recall@5 0.000 (A) vs 0.833 (B/C);
`evidential=true`, `valid_comparison=true` (Table 5). **`--retrieval-limit 3` is
required** — at the default limit every arm injects the whole 5-record store and the
arms differ only in order.

---

## Hidden assumptions made explicit (tribal knowledge eliminated)

1. **Use `.venv/bin/...` directly.** No shell is activated; `mars`/`python` on PATH may
   be the wrong interpreter.
2. **`mars.db` is created on some runs and is gitignored.** Deleting it is safe; it is
   not an input.
3. **Tier 0 needs no network.** Experiments 2–4 read `experiments/cache/`, not live
   Cortex. The `--cache-only` flag on Exp 2 enforces this.
4. **`--strict-semantic` is the honesty switch.** Without a real embedding backend,
   `semantic_score` is null and the framework refuses to claim a semantic baseline.
5. **`--retrieval-limit 3` is load-bearing for Exp 5.1.** It is not a tuning knob; the
   arm contrast does not exist at the default limit.
6. **Figures are derived, not hand-edited.** Never edit an SVG by hand; change the
   generator and rerun. The determinism check (`git status` clean) is the guard.
7. **The corpus is frozen.** Reproducing different numbers after a corpus edit is
   expected and wrong — `verify-frozen` must pass first.
8. **Result JSONs under `mars-experiments/` are the source of truth**, not the prose in
   the design docs.
