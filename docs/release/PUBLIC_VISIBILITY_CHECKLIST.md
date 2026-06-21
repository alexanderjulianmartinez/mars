# Public Visibility Checklist

**Repository:** `alexanderjulianmartinez/mars`
**Current visibility:** PRIVATE
**Date:** 2026-06-21

Pre-flip gate for making the repository public. Every content/legal/reproducibility item
below is satisfied; the only remaining action is the manual visibility flip (held for
explicit instruction — this checklist does **not** flip it).

---

## Gates

| Gate | Status | Evidence |
| --- | --- | --- |
| **Secrets scan** | ✅ CLEAN | Grep of `mars-experiments/*.json` + docs found no API keys, tokens, or MCP endpoints — only benign env-var *names* (`VOYAGE_API_KEY`, `MARS_AUTODEV_MCP_*`) in reproduction docs and the metric `token_usage: 0.0`. |
| **Private-data scan** | ✅ CLEAN | Corpus is synthetic/hand-authored; no production memory traces, customer data, or internal hostnames. Cortex/AutoDev real internals are excluded (only interfaces + mocks ship). |
| **Local artifacts excluded** | ✅ | `.gitignore` covers `*.db` (incl. `mars.db`), `.venv/`, `__pycache__/`. No DBs tracked. |
| **Licenses** | ✅ | `LICENSE` (Apache-2.0, code, copyright filled) + `LICENSE-DATA` (CC-BY-4.0, corpus/results) + `NOTICE` (split documented). |
| **Reproducibility** | ✅ VERIFIED | 214 tests pass; Experiments 2–4 reproduce offline with paper-matching numbers; figures regenerate byte-identically. See `REPRODUCIBILITY_CHECKLIST.md`. |
| **Release status** | ✅ | `v1.0.0-rc1` tag pushed; GitHub **prerelease** created from the tag with `RELEASE_NOTES_RC1.md`. |
| **Citation** | ✅ | `CITATION.cff` (valid YAML) + `docs/papers/citation.bib` + `CITATION_TEXT.md`. |
| **Benchmark freeze hash** | ✅ | `mars corpus verify-frozen` confirms SHA256 `a464085c3daa64c97d2764c47f8758931b2a51c2adc1e143fcfc98d9faa74d59`. |
| **Version metadata** | ✅ RESOLVED | Option B: framework package stays `0.1.0`; research release tag `v1.0.0-rc1`; documented (no bump). |
| **README (external)** | ✅ | Research / Reproduce / License / Citation sections present. |

**Blockers: none.**

---

## Remaining manual step

Flipping visibility is **irreversible exposure** (GitHub may cache/index public content),
so it is intentionally left for the maintainer to run:

```bash
gh repo edit alexanderjulianmartinez/mars \
  --visibility public \
  --accept-visibility-change-consequences
```

### After flipping (recommended follow-ups)
- Re-check the GitHub release renders correctly and assets are attached as intended.
- Confirm the prerelease badge shows on the public releases page.
- Optionally mint a Zenodo DOI from the public release for permanent citability.
- Announce/link the technical report and blog once live.
