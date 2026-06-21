# Open Source Release Plan

**Goal:** release the reproducible core of the Salience & Attention research — the
Mars evaluation framework, the frozen benchmark, the result artifacts, and the
reproduction harness — while keeping proprietary system internals private.

This plan adds **no new scope**. It packages what exists.

---

## What Will Be Released

| Component | Path(s) | Why it can be public |
| --- | --- | --- |
| **Mars framework** | `mars/` | Evaluation/scoring/experiment engine; the contribution. |
| **Frozen benchmark v1.0.0** | `experiments/corpus/*.yaml`, `*.gold.json`, `*.manifest.yaml` | Synthetic, hand-authored; no proprietary data. The citable artifact. |
| **Corpus generator** | `experiments/corpus/generate_expanded.py`, `scenarios_data.py` | Reproducible authoring of the corpus. |
| **Committed retrieval cache** | `experiments/cache/` | Enables offline repro of Exp 2–4 without credentials. |
| **Experiment runners** | `experiments/run_*.py`, `experiments/launch_*.py` | Reproduction scripts. |
| **Result artifacts** | `mars-experiments/*.json` | Source-of-truth results (after scrub, below). |
| **Provider *interfaces* + mocks** | `mars/providers/*` interfaces, `Mock*Provider` | Drop-in seam; mocks run the pipeline end-to-end with no real systems. |
| **Reports & paper** | `docs/reports/`, `docs/papers/`, figures | The written record. |
| **Tests** | `tests/` | Confidence + executable documentation. |

## What Remains Private

| Component | Reason |
| --- | --- |
| **Cortex internals** (retrieval engine, embedding orchestration, storage) | Separate system; possibly proprietary. Release only the *provider interface* Mars consumes. |
| **AutoDev internals** (agent runtime, workspaces, git/PR ops) | Separate system. Release only the provider interface + adapter contract. |
| **Sentinel** | Not built; reserved extension points only. |
| **Real MCP endpoints / credentials** | `MARS_*_MCP_*` URLs, tokens, Voyage API key. Never committed. |
| **Local run databases** | `mars.db` and any `*.db` (already gitignored). |

### Pre-release scrub checklist (BLOCKING)
- [ ] Grep committed `mars-experiments/*.json` and docs for internal hostnames,
      `MARS_*_MCP_*` endpoints, tokens, emails, and absolute local paths; redact.
- [ ] Confirm `.gitignore` covers `*.db`, `.venv/`, `__pycache__/`, any `.env`.
- [ ] Confirm no Voyage/MCP key appears in scripts, JSON, or git history.
- [ ] Confirm Cortex/AutoDev imports are lazy and the repo runs on mocks with the
      optional `mcp` extra absent (matches the documented design).
- [ ] Verify `mars corpus verify-frozen` passes on the release tree.

---

## How to Reproduce Results

Released README points reproducers at three tiers:

1. **Zero-credential (offline):** `pytest`; `mars corpus verify-frozen …`;
   Exp 2–4 via committed cache (`--cache-only`). Reproduces robustness, temporal,
   and confidence/contradiction results deterministically.
2. **Semantic baseline (Voyage key):** `mars experiments run salience-memory-v1` —
   reproduces Experiment 1's live retrieval numbers.
3. **Full execution (AutoDev + Voyage, paid ≈$1.3):** Experiment 5.1 launcher.

Each experiment's exact command is in the paper's Appendix E / tech report Appendix B.

---

## Repository Structure (as released)

```
mars/                      # evaluation framework (package)
  apollo/                  #   A/B experiment engine + paired bootstrap
  memory/                  #   retrieval strategies, metrics, corpus loaders
  providers/               #   Cortex/AutoDev interfaces + mocks (+ real MCP, optional)
  scoring/                 #   scorers (test/runtime/cost/diff + agentic)
experiments/
  corpus/                  #   frozen benchmark + generator
  cache/                   #   committed retrieval cache (offline repro)
  run_*.py / launch_*.py   #   experiment runners
mars-experiments/          # result JSON artifacts (source of truth)
suites/                    # bundled eval suites
docs/
  reports/                 # technical report + executive summary + exec results
  papers/                  # paper draft, outline, figure/table/appendix plans, figures/
  publication/             # readiness, blog outline, checklist
  release/                 # this plan
tests/
LICENSE                    # Apache-2.0 (code)   [DONE — copyright filled]
LICENSE-DATA               # CC-BY-4.0 (corpus)  [DONE]
NOTICE                     # license split note  [DONE]
CITATION.cff               # citable metadata    [DONE]
README.md                  # external-facing overview [DONE — research/repro/license/cite added]
```

---

## Versioning Strategy

- **Benchmark:** semantic, hash-pinned. Bugfix → `v1.0.x`; redesign/expansion → `v2`.
  Corpus **bytes are never silently mutated**; the SHA256 in the manifest is the
  contract, guarded by `verify-frozen` + a CI regression test.
- **Framework (Mars):** SemVer; the installable `mars` package version (`0.1.0`) is an
  axis **independent** of the research-release tag. The package stays `0.1.0` (early-stage
  library, not a stable 1.0 API).
- **Research release:** git tag (`v1.0.0-rc1`) + GitHub release over a frozen benchmark
  version, so result JSONs reference a reproducible code+data state. This is the axis the
  public release advertises, distinct from the package version above.
- **Results:** each `mars-experiments/*.json` is immutable for a given benchmark
  version; re-runs that change numbers require a version note, not an in-place edit.
- **Paper/reports:** versioned by filename suffix (`_v1`, outline `v2`) and dated.

---

## Recommended Licenses

| Artifact | License | Rationale |
| --- | --- | --- |
| **Code** (`mars/`, scripts, tests) | **Apache-2.0** | Permissive + explicit patent grant; standard for ML-systems tooling. |
| **Benchmark corpus + gold labels** | **CC-BY-4.0** | Data/artifact license; attribution-friendly, citable. |
| **Paper/report text & figures** | **CC-BY-4.0** | Matches arXiv norms; allows reuse with attribution. |

Add a top-level `LICENSE` (Apache-2.0), a `LICENSE-DATA` (CC-BY-4.0) covering
`experiments/corpus/` and `mars-experiments/`, and a short `NOTICE` clarifying the
split. These files are the **only hard blockers** to release.

---

## Research Artifact Packaging

For a citable release (e.g. GitHub release + Zenodo DOI):

- Tag `mars vX.Y.Z`; attach a release archive containing `mars/`, `experiments/`,
  `mars-experiments/`, `docs/`, `tests/`, and license files.
- Include a `CITATION.cff` (cite the technical report + benchmark v1.0.0 by hash).
- Pin the benchmark SHA256 in the release notes; state the supported reproduction
  tiers and which require credentials.
- Cross-link: release notes → technical report → paper → frozen corpus manifest.
- Optional Zenodo deposit of the corpus + result JSONs for a permanent DOI.

**Status (2026-06-21):** licenses (Apache-2.0 + CC-BY-4.0), `NOTICE`, `CITATION.cff`,
and README sections are **done**; the scrub is **done** (no real secrets found). The
only remaining step is to commit + push the release files and flip the repo
visibility to public — an irreversible, outward-facing action held for explicit
go-ahead.
