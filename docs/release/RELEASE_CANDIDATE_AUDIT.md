# Release Candidate Audit

**Phase:** Final Release Candidate (v1.0.0-rc1)
**Date:** 2026-06-21
**Source of truth:** technical report + `mars-experiments/*.json` + frozen benchmark
(SHA256 `a464085c…`, verified this session).

Status legend: **COMPLETE** · **NEEDS_REVIEW** · **MISSING**

---

## Artifact inventory

### Paper & appendices
| Artifact | Path | Status |
| --- | --- | --- |
| Consolidated paper (Exp 1–5) | `docs/papers/salience_weighted_memory_retrieval_v2.md` | **COMPLETE** (markdown; LaTeX port pending venue) |
| Appendices A–I | inlined in the v2 paper | **COMPLETE** |
| v1 paper (Exp 1 only) | `docs/papers/salience_weighted_memory_retrieval_v1.md` | **COMPLETE** (superseded by v2; keep for history) |
| v1 reviewer notes | `…_v1_review_notes.md` | **COMPLETE** |
| v2 outline | `docs/papers/arxiv_v2_outline.md` | **COMPLETE** |
| Table plan (7 tables) | `docs/papers/TABLE_PLAN.md` | **COMPLETE** |
| Appendix plan | `docs/papers/APPENDIX_PLAN.md` | **COMPLETE** |

> Note: the brief references `docs/papers/arxiv_v2.md`; the actual file is
> `salience_weighted_memory_retrieval_v2.md`. No separate `arxiv_v2.md` exists or is
> needed — treat the longer filename as the canonical v2 paper.

### Figures
| Artifact | Path | Status |
| --- | --- | --- |
| Data figures 3–9 (SVG) | `docs/papers/figures/figure{3..9}_*.svg` | **COMPLETE** (regenerate byte-identically; verified) |
| Figure generator | `docs/papers/figures/generate_figures.py` | **COMPLETE** |
| Diagram figures 1,2,10 (TikZ) | `docs/papers/figures/diagrams.tex` → `diagrams.pdf` | **COMPLETE** (compiles clean, 3 pages) |
| Figure plan | `docs/papers/FIGURE_PLAN.md` | **COMPLETE** |
| Figure review | `docs/papers/FIGURE_REVIEW.md` | **COMPLETE** (Phase 4) |

### Benchmark, corpus & results
| Artifact | Path | Status |
| --- | --- | --- |
| Frozen benchmark v1.0.0 | `experiments/corpus/*.yaml`, `*.gold.json`, `*.manifest.yaml` | **COMPLETE** (hash verified `a464085c…`) |
| Corpus generator | `experiments/corpus/generate_expanded.py`, `scenarios_data.py` | **COMPLETE** |
| Committed retrieval cache | `experiments/cache/` | **COMPLETE** (offline Exp 2–4 verified) |
| Result JSONs (Exp 1–5.1) | `mars-experiments/*.json` | **COMPLETE** |
| Integrity guard | `mars corpus verify-frozen` + CI test | **COMPLETE** |

### Reports
| Artifact | Path | Status |
| --- | --- | --- |
| Technical report | `docs/reports/…_TECHNICAL_REPORT.md` | **COMPLETE** |
| Executive summary | `docs/reports/…_EXECUTIVE_SUMMARY.md` | **COMPLETE** |
| Per-experiment docs | `docs/SALIENCE_MEMORY_*` | **COMPLETE** |

### Release assets
| Artifact | Path | Status |
| --- | --- | --- |
| `LICENSE` (Apache-2.0) | `LICENSE` | **COMPLETE** (copyright filled) |
| `LICENSE-DATA` (CC-BY-4.0) | `LICENSE-DATA` | **COMPLETE** |
| `NOTICE` | `NOTICE` | **COMPLETE** |
| `CITATION.cff` | `CITATION.cff` | **COMPLETE** (valid YAML) |
| `citation.bib` | `docs/papers/citation.bib` | **COMPLETE** (Phase 3) |
| External `README` | `README.md` | **COMPLETE** (research/repro/license/cite sections) |
| Open-source release plan | `docs/release/OPEN_SOURCE_RELEASE_PLAN.md` | **COMPLETE** |
| OSS release checklist | `docs/release/OSS_RELEASE_CHECKLIST.md` | **COMPLETE** (Phase 6) |
| Release notes RC1 | `docs/release/RELEASE_NOTES_RC1.md` | **COMPLETE** (Phase 9) |
| Reproducibility checklist | `docs/release/REPRODUCIBILITY_CHECKLIST.md` | **COMPLETE** (Phase 2, verified) |
| Version tag `v1.0.0-rc1` | git tag | **MISSING** (created at release time; intentional) |

### Blog
| Artifact | Path | Status |
| --- | --- | --- |
| Blog outline | `docs/publication/RESEARCH_BLOG_OUTLINE.md` | **COMPLETE** |
| Blog draft | `docs/publication/research_blog_draft.md` | **COMPLETE** |
| Blog review | `docs/publication/BLOG_REVIEW.md` | **COMPLETE** (Phase 7) |

### Interview packet
| Artifact | Path | Status |
| --- | --- | --- |
| Interview packet | `docs/interview/RESEARCH_INTERVIEW_PACKET.md` | **COMPLETE** |
| Interview packet review | `docs/interview/INTERVIEW_PACKET_REVIEW.md` | **COMPLETE** (Phase 8) |

---

## Publication blockers

There are **no content blockers**. The remaining items are deliberate release
mechanics and one external choice:

| # | Item | Type | Severity | Owner |
| --- | --- | --- | --- | --- |
| 1 | Merge PR #28 into `main` | process | required for release | user |
| 2 | Flip repo visibility to public | irreversible action | required for OSS | user |
| 3 | Create `v1.0.0-rc1` tag (after merge) | process | required for RC | user/me on go |
| 4 | Choose arXiv venue → LaTeX/`.bib` formatting pass | external choice | blocks **arXiv only** | user |
| 5 | SVG→PNG export for the blog platform | mechanical | blocks **blog publish only** | me (one command) |

**Verified this session (not asserted):** 214 tests pass; `verify-frozen` confirms
SHA256 `a464085c…`; Experiments 2–4 reproduce offline with paper-matching numbers;
figures regenerate byte-identically. Reproducibility is **established, not aspirational**.

**Conclusion:** all artifacts are COMPLETE except the intentional `v1.0.0-rc1` tag
(created at tag time). No artifact is in a NEEDS_REVIEW state that blocks the RC.
