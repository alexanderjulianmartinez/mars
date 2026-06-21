# Publication Readiness Audit

**Program:** Salience & Attention Systems
**Date:** 2026-06-21
**Scope:** Convert completed research into publishable, reproducible, communicable artifacts.
**Source of truth:** Frozen Salience Memory Benchmark v1.0.0
(`salience-memory-benchmark-v1`, SHA256 `a464085c…`), the authoritative technical
report, and the experiment result JSONs under `mars-experiments/`.

This audit assumes the research phase is **complete**. No new experiments are
proposed; this is a packaging and communication readiness assessment.

---

## Existing Assets

### Research reports
| Asset | Path | Status |
| --- | --- | --- |
| Authoritative technical report (Exp 1–5.1) | `docs/reports/SALIENCE_WEIGHTED_MEMORY_RETRIEVAL_TECHNICAL_REPORT.md` | Complete |
| Executive summary (full 2–4pp) | `docs/reports/SALIENCE_WEIGHTED_MEMORY_RETRIEVAL_EXECUTIVE_SUMMARY.md` | Complete |
| Paper draft v1 (Exp 1 only) | `docs/papers/salience_weighted_memory_retrieval_v1.md` | Complete, narrow scope |
| Paper draft v1 reviewer notes | `docs/papers/salience_weighted_memory_retrieval_v1_review_notes.md` | Complete |

### Per-experiment design/result docs
| Experiment | Design doc | Result JSON (source of truth) |
| --- | --- | --- |
| 1 — Salience Retrieval | `docs/SALIENCE_MEMORY_V1_RESULTS.md`, `docs/SALIENCE_MEMORY_V1_EXPANDED.md` | `mars-experiments/salience-memory-v1-expanded.json` |
| 2 — Noisy Importance | `docs/SALIENCE_MEMORY_NOISY_IMPORTANCE.md` | `mars-experiments/salience-memory-noisy-importance.json` |
| 3 — Temporal Salience | `docs/SALIENCE_MEMORY_TEMPORAL_SALIENCE.md` | `mars-experiments/salience-memory-temporal-salience.json` |
| 4 — Confidence/Contradiction | `docs/SALIENCE_MEMORY_CONFIDENCE_AND_CONTRADICTION.md` | `mars-experiments/salience-memory-confidence-and-contradiction.json` |
| 5 — Execution Impact | `docs/SALIENCE_MEMORY_EXECUTION_IMPACT.md`, `docs/reports/SALIENCE_MEMORY_EXECUTION_IMPACT_RESULTS.md` | `mars-experiments/salience-memory-execution-impact-v2.json` |
| 5.1 — Real Agent Execution | `docs/reports/SALIENCE_MEMORY_EXECUTION_IMPACT_5_1_RESULTS.md` | `…-execution-impact-5-1.json` (+ `…-5-1-behavioral.json`) |

### Benchmark & corpus artifacts
| Asset | Path | Status |
| --- | --- | --- |
| Benchmark spec | `docs/SALIENCE_MEMORY_BENCHMARK_V1.md` | Complete |
| Frozen corpus (552 mem / 30 q) | `experiments/corpus/salience-memory-v1-expanded.corpus.yaml` | Frozen, hash-pinned |
| Manifest (hash pin) | `experiments/corpus/salience-memory-v1.manifest.yaml` | Complete |
| Gold labels | `experiments/corpus/salience-memory-v1.gold.json` | Complete |
| Reproducible generator | `experiments/corpus/generate_expanded.py`, `scenarios_data.py` | Complete |
| Integrity guard | `mars corpus verify-frozen` + CI regression test | Complete |
| Committed retrieval cache | `experiments/cache/` | Complete (offline repro for Exp 2–4) |

### Framework & reproducibility
| Asset | Path | Status |
| --- | --- | --- |
| Mars eval/experiment framework | `mars/` | Complete, tests passing |
| Retrieval strategies | `mars/memory/retrieval.py`, `salience_v1.py` | Complete |
| Metrics | `mars/memory/metrics.py` | Complete |
| Real Cortex/AutoDev MCP providers | `mars/providers/` | Complete |
| Reproduction commands | Tech report Appendix B | Complete |
| v2 signal proposal | `docs/salience-memory-v2-proposal.md` | Complete |

---

## Missing Assets

These are the gaps this publication phase fills. None require new experiments.

| Asset | Phase | Priority |
| --- | --- | --- |
| Consolidated arXiv outline covering Exp 1–5 (current paper draft is Exp 1 only) | 2 | **High** |
| Figure plan (10 figures) | 3 | High |
| Rendered figures (SVG; PNG on rasterize) | 4 | High |
| Table plan + publication-ready tables | 5 | Medium |
| Appendix plan | 6 | Medium |
| Open-source release plan (license, structure, what's public/private) | 7 | **High** |
| Research blog outline | 8 | Medium |
| Interview packet | 9 | Low (non-blocking for publication) |
| Publication checklist | 10 | High |
| **LICENSE file(s)** for code + corpus | 7 | **High (blocks OSS release)** |
| Top-level repo `README` oriented to external readers | 7 | Medium |

---

## Publication Risks

Risks are split between **content/credibility** risks (could draw reviewer or reader
objections) and **process/legal** risks (could block release mechanically).

### Content / credibility risks
| Risk | Severity | Mitigation (already available) |
| --- | --- | --- |
| **Authored-importance ceiling** read as inflating Exp 1's +0.435 | High | Exp 2 (noisy importance) bounds it: degrades gracefully, ~78% of the win is the importance signal, never collapses. Lead with Exp 2 as the honesty anchor. |
| **Synthetic benchmark** external validity | High | State plainly; frame Exp 1–4 as controlled retrieval studies, not field results. Already in every report's limitations. |
| **No task-success win** mistaken for a failed program | Medium | Exp 5.1 reframes as Outcome B (retrieval + behavior change, success unchanged), an honest, publishable null. Keep the two claim-lists (supported / unsupported) strictly separate. |
| **Execution underpowered** (floor, single trial, n=6) | Medium | Already disclosed; present execution as a methodology + behavioral result, not a task-success claim. |
| Numbers drift between docs | Medium | Designate the technical report + result JSONs as single source of truth; figures/tables cite JSON. |

### Process / legal risks
| Risk | Severity | Mitigation |
| --- | --- | --- |
| **No LICENSE** for code or corpus | High | Add licenses before any public push (Phase 7 recommends Apache-2.0 code / CC-BY-4.0 corpus). |
| Cortex/AutoDev/Sentinel are **separate, possibly proprietary systems** | High | Release Mars + benchmark + result artifacts; keep Cortex/AutoDev internals private; release only their **provider interfaces** and mocks. |
| Real-run artifacts may embed **API keys / internal endpoints** | High | Scrub `MARS_*_MCP_*` endpoints, tokens, and any internal hostnames from committed JSON before release. |
| Embedding provider (Voyage) **cost/ToS** for reproduction | Low | Document that semantic repro requires a Voyage key; offline cache covers Exp 2–4 without it. |
| `mars.db` / local run DBs leaking | Low | Already gitignored; confirm in release scrub. |

---

## Release Recommendation

| Track | Recommendation | Rationale |
| --- | --- | --- |
| **Technical Report** | **Release now.** | Complete, scoped, reproducible against a frozen hash. The strongest artifact. |
| **Research Blog** | **Release now** (after Phase 8 outline → draft). | Accessible narrative; the mechanism + honest-null story is compelling without hype. |
| **Open Source Release** | **Release after Phase 7 + license + scrub.** | Mechanically blocked only by LICENSE and an artifact scrub; content is ready. Release Mars + frozen benchmark + result JSONs + repro; keep Cortex/AutoDev internals private. |
| **arXiv** | **Consolidate first (Phase 2), then submit.** | The current paper draft covers only Exp 1 and is exposed on the circularity objection. The consolidated paper (Exp 1–5, with Exp 2 defusing circularity and Exp 5.1 as an honest null) is a credible workshop/arXiv submission. No new experiments required — only writing. |

**Bottom line:** Technical Report, Research Blog, and Open Source are release-ready
pending mechanical steps (license, scrub, blog draft). arXiv requires the paper
consolidation in Phase 2 — a writing task over already-complete results, not new
research.
