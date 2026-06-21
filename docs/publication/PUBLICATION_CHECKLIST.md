# Publication Checklist

**Date:** 2026-06-21
**Scope:** packaging of completed research. No new experiments, repositories, or scope.

Status legend: **DONE** · **IN PROGRESS** · **BLOCKED** · **MISSING**

---

## Artifact status

### Research content (the science)
| Item | Status | Notes |
| --- | --- | --- |
| Experiments 1–5.1 complete | **DONE** | Result JSONs in `mars-experiments/` are source of truth. |
| Frozen benchmark v1.0.0 (hash-pinned) | **DONE** | SHA256 `a464085c…`; `verify-frozen` + CI guard. |
| Technical report | **DONE** | `docs/reports/…_TECHNICAL_REPORT.md`. |
| Executive summary | **DONE** | `docs/reports/…_EXECUTIVE_SUMMARY.md`. |
| Per-experiment design/result docs | **DONE** | `docs/SALIENCE_MEMORY_*`. |
| Reproduction commands + offline cache | **DONE** | `experiments/cache/`; one command per experiment. |

### Paper
| Item | Status | Notes |
| --- | --- | --- |
| Paper draft v1 (Exp 1 only) | **DONE** | `docs/papers/salience_weighted_memory_retrieval_v1.md`. |
| v1 reviewer notes | **DONE** | Same dir, `_review_notes.md`. |
| Consolidated arXiv outline (Exp 1–5) | **DONE** | `docs/papers/arxiv_v2_outline.md`. |
| **Consolidated paper draft (Exp 1–5) written** | **DONE** | `docs/papers/salience_weighted_memory_retrieval_v2.md` — promotes Exp 2–5 to results; references Tables 1–7 and Figures 1–10. |
| Objection→experiment map | **DONE** | In the outline. |

### Figures
| Item | Status | Notes |
| --- | --- | --- |
| Figure plan (10 figures) | **DONE** | `docs/papers/FIGURE_PLAN.md`. |
| Data figures 3,4,5,6,7,8,9 (SVG) | **DONE** | `docs/papers/figures/*.svg`, generated from source-of-truth numbers; valid XML. |
| Figure generator (reproducible, no deps) | **DONE** | `generate_figures.py` (pure stdlib). |
| PNG rasterization | **IN PROGRESS** | No rasterizer in env; command documented (rsvg/cairosvg/inkscape/browser). User runs one line. |
| Diagram figures 1,2,10 | **DONE** | `docs/papers/figures/diagrams.tex` → `diagrams.pdf` (compiles clean, 3 pages). |

### Tables & appendices
| Item | Status | Notes |
| --- | --- | --- |
| Table plan + publication-ready tables | **DONE** | `docs/papers/TABLE_PLAN.md` (7 tables, final markdown). |
| Appendix plan | **DONE** | `docs/papers/APPENDIX_PLAN.md` (A–I). |
| Appendix content assembled into paper | **DONE** | Appendices A–I inlined into `salience_weighted_memory_retrieval_v2.md`. |

### Open source
Decisions (2026-06-21): personal-name copyright (**Alexander Julian Martinez**) ·
**Apache-2.0 + CC-BY-4.0 split** · flip *this* repo public · GitHub release + CITATION.cff.

| Item | Status | Notes |
| --- | --- | --- |
| Release plan | **DONE** | `docs/release/OPEN_SOURCE_RELEASE_PLAN.md`. |
| `LICENSE` (Apache-2.0, code) | **DONE** | Already present; copyright line filled (2026 Alexander Julian Martinez). |
| `LICENSE-DATA` (CC-BY-4.0, corpus) | **DONE** | Created; covers `experiments/corpus/`, `experiments/cache/`, `mars-experiments/`. |
| `NOTICE` / license split note | **DONE** | Created; documents code-vs-data split + third-party systems. |
| External-facing `README` | **DONE** | Already present; added Research / Reproduce / License / Citation sections. |
| Artifact scrub (keys/endpoints/paths) | **DONE** | Scanned committed JSON + docs: no real secrets; only benign env-var *names* in repro docs. |
| `CITATION.cff` | **DONE** | Created; valid YAML; cites report + benchmark hash. |
| Flip repo visibility to public | **IN PROGRESS** | Repo currently PRIVATE; `gh` authed. Final step, pending commit+push of release files and user go-ahead. |

### Communication
| Item | Status | Notes |
| --- | --- | --- |
| Research blog outline | **DONE** | `docs/publication/RESEARCH_BLOG_OUTLINE.md`. |
| Research blog draft | **DONE** | `docs/publication/research_blog_draft.md` — ~1,500 words, 7 figures placed, leads with the honest null. |
| Interview packet | **DONE** | `docs/interview/RESEARCH_INTERVIEW_PACKET.md`. |
| Publication readiness audit | **DONE** | `docs/publication/PUBLICATION_READINESS.md`. |

---

## Readiness estimates

| Track | Readiness | Gating items |
| --- | --- | --- |
| **Technical Report** | **Ready (100%)** | None. Releasable now. |
| **Research Blog** | **~95%** | Draft done; remaining: export the 7 figure SVGs→PNG for the publishing platform and a light copy-edit pass. |
| **Open Source Release** | **~95%** | Licenses, NOTICE, scrub, README, CITATION done. Only remaining: commit+push release files, then flip visibility to public. |
| **arXiv** | **~95%** | v2 draft written; diagram figures 1/2/10 compiled (TikZ→PDF); appendices A–I inlined. Remaining: pick a venue and do the LaTeX template + bibliography/formatting pass. No new research. |
| **Interview** | **Ready (100%)** | Packet complete; rehearse the 5/15-minute versions. |

---

## Prioritized remaining work (before public release)

1. ~~**[OSS] Artifact scrub**~~ — DONE (no real secrets found).
2. ~~**[OSS] Add licenses + NOTICE**~~ — DONE (Apache-2.0 filled, CC-BY-4.0 LICENSE-DATA, NOTICE).
3. ~~**[OSS] README + CITATION.cff**~~ — DONE.
4. **[OSS] Publish:** commit the release files (`LICENSE`, `LICENSE-DATA`, `NOTICE`,
   `CITATION.cff`, README + docs), push to `main`, then `gh repo edit --visibility public`.
   Pending user go-ahead (irreversible exposure).
5. **[arXiv] Write the consolidated v2 paper** from `arxiv_v2_outline.md` — promote
   Exp 2–5 from future-work to results; fold in tables (done) and figures (done).
5. **[arXiv] Draw diagram figures 1, 2, 10** from the figure-plan specs.
6. **[arXiv] Assemble appendices A–I** into the paper from existing sources.
7. **[Blog] Draft the research blog** from the outline; embed figures; lead with the
   honest execution null.
8. **[Polish] Rasterize SVGs → PNG** for venues that require PNG (one documented
   command).
9. **[Polish] CITATION + Zenodo DOI** for a permanently citable artifact (optional).

**Not on this list, by directive:** new experiments, new infrastructure, new
frameworks, new repositories, scope expansion. Every remaining item converts
completed research into a publishable, reproducible, communicable form.
