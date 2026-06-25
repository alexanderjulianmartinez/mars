# Open Source Release Checklist

**Target release:** `v1.0.0-rc1`
**Date:** 2026-06-21
Full strategy in `OPEN_SOURCE_RELEASE_PLAN.md`; this is the go/no-go checklist.

---

## Inclusion checklist (what ships)

| Item | Path | In release | Status |
| --- | --- | :---: | --- |
| Benchmark (frozen v1.0.0) | `experiments/corpus/*.yaml`, `*.gold.json`, `*.manifest.yaml` | ✅ | **DONE** (hash verified) |
| Corpus generator | `experiments/corpus/generate_expanded.py`, `scenarios_data.py` | ✅ | **DONE** |
| Retrieval cache (offline repro) | `experiments/cache/` | ✅ | **DONE** |
| Results (Exp 1–5.1) | `mars-experiments/*.json` | ✅ | **DONE** |
| Paper (v2 + appendices) | `docs/papers/salience_weighted_memory_retrieval_v2.md` | ✅ | **DONE** |
| Figures (SVG + TikZ/PDF) | `docs/papers/figures/` | ✅ | **DONE** |
| Technical report | `docs/reports/…_TECHNICAL_REPORT.md` | ✅ | **DONE** |
| Executive summary | `docs/reports/…_EXECUTIVE_SUMMARY.md` | ✅ | **DONE** |
| Reproduction instructions | `docs/release/REPRODUCIBILITY_CHECKLIST.md` | ✅ | **DONE** (verified) |
| Mars framework (code) | `mars/`, `tests/`, `suites/` | ✅ | **DONE** (214 tests pass) |
| Provider interfaces + mocks | `mars/providers/` | ✅ | **DONE** (real internals excluded) |
| `LICENSE` (Apache-2.0) | `LICENSE` | ✅ | **DONE** |
| `LICENSE-DATA` (CC-BY-4.0) | `LICENSE-DATA` | ✅ | **DONE** |
| `NOTICE` | `NOTICE` | ✅ | **DONE** |
| `CITATION.cff` + `citation.bib` | root + `docs/papers/` | ✅ | **DONE** |
| README (external) | `README.md` | ✅ | **DONE** |

## Exclusion checklist (what must NOT ship)

| Item | Status |
| --- | --- |
| Cortex/AutoDev real implementations (only interfaces/mocks ship) | **EXCLUDED** ✓ |
| API keys / tokens / MCP endpoints | **NONE PRESENT** ✓ (scan clean) |
| Local run DBs (`mars.db`, `*.db`) | **GITIGNORED** ✓ |
| Sentinel internals | **N/A — reserved seam only** ✓ |

## Security / hygiene gates

- [x] Secret scan of `mars-experiments/*.json` + docs — no keys/endpoints/local paths.
- [x] `.gitignore` covers `__pycache__/`, `*.db`, `.venv/`.
- [x] Lazy import of optional `mcp` dependency confirmed (runs on mocks without it).
- [x] `mars corpus verify-frozen` passes on the release tree (SHA256 `a464085c…`).
- [x] Test suite green (214 passing).

## README / docs gates

- [x] README states purpose, the Cortex/AutoDev/Mars layering, and the research result.
- [x] README has Reproduce (3 tiers), License (split), and Citation sections.
- [x] License split documented in `NOTICE`.

## Versioning & tags

- **Framework:** SemVer; first public tag `v1.0.0-rc1` (then `v1.0.0` after a soak).
- **Benchmark:** independent, hash-pinned `v1.0.0` (bytes immutable; bugfix → `v1.0.x`,
  redesign → `v2`).
- **Software version in metadata (RESOLVED — Option B):** `CITATION.cff` and `pyproject`
  keep `0.1.0` as the **Mars framework package** version (early-stage library; `name =
  "mars"`). The research-release tag `v1.0.0-rc1` and the benchmark `v1.0.0` are separate
  axes; the package is intentionally *not* bumped, and the distinction is documented in
  the release notes and `POST_TAG_STATUS.md`. No version-field edits were required.

## Release notes

- [x] Drafted: `docs/release/RELEASE_NOTES_RC1.md`.

---

## Go / No-Go

| Gate | State |
| --- | --- |
| Content complete | **GO** |
| Licenses + citation present | **GO** |
| Secret scan clean | **GO** |
| Reproducibility verified | **GO** |
| Merge PR #28 | **DONE** (merge commit `c4ee136`) |
| Tag `v1.0.0-rc1` | **DONE** (pushed) |
| GitHub prerelease | **DONE** (`--prerelease` from the tag) |
| Version metadata reconciliation | **DONE** (Option B; documented, no bump) |
| **Remaining (user action):** flip visibility public | **PENDING** |

**No content or legal blockers remain.** The release is gated only on the single
remaining user-owned step: flipping repository visibility to public (see
`PUBLIC_VISIBILITY_CHECKLIST.md`).
