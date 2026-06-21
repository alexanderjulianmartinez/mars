# Appendix Plan

Appendix structure for the consolidated paper. Each appendix below names its purpose,
its source artifact (already exists — nothing to be produced experimentally), and the
content to lift in. Appendices are reproducibility scaffolding; the body of the paper
should remain readable without them.

---

## Appendix A — Benchmark Specification
- **Purpose:** Define Salience Memory Benchmark v1.0.0 precisely enough to cite and reuse.
- **Source:** `docs/SALIENCE_MEMORY_BENCHMARK_V1.md`, `experiments/corpus/salience-memory-v1.manifest.yaml`.
- **Content:** version (v1.0.0), SHA256 `a464085c…`, freeze policy (bugfix→v1.0.x,
  redesign→v2, bytes never mutated), integrity command
  `mars corpus verify-frozen salience-memory-benchmark-v1`, query/memory counts
  (30/552), one-target-per-query invariant, gold-label format.

## Appendix B — Corpus Schema
- **Purpose:** Document the per-memory and per-query record format.
- **Source:** `experiments/corpus/salience-memory-v1-expanded.corpus.yaml`,
  `salience-memory-v1.gold.json`, `mars/memory/expanded_corpus.py`.
- **Content:** memory fields (`id`, `content`, `category`, `importance`, `novelty`,
  `urgency`, `confidence`, similarity provenance); category enum (target / relevant /
  distractor / stale / contradictory / low_confidence); gold map structure
  (`relevant` set + single `target`); generator provenance
  (`generate_expanded.py` + `scenarios_data.py`).

## Appendix C — Metric Definitions
- **Purpose:** Make every reported metric reproducible from a ranked list + gold set.
- **Source:** `mars/memory/metrics.py`.
- **Content:** formal definitions of Recall@K, Precision@K, MRR, nDCG@K,
  TargetFound@K, ContextEfficiency@K; the ContradictionAvoidanceRate (CAR) definition
  from Exp 4 (fraction of contradiction-eligible queries where the target outranks
  every obsolete contradictory memory; eligibility 28/30); averaging convention (mean
  over 30 queries).

## Appendix D — Bootstrap Methodology
- **Purpose:** Specify the significance procedure.
- **Source:** tech report §2/§4 + Apollo `compare_arms` (`mars/apollo/`).
- **Content:** paired bootstrap, 10,000 resamples over the 30-query distribution;
  resample queries with replacement, recompute per-strategy means, report 95% CI of
  the difference (salience − baseline); per-query win/tie/loss tally; note that
  retrieval is deterministic given fixed embeddings, so uncertainty is over the query
  distribution, not run noise; seeds (25/level in Exp 2; N seeds/regime in Exp 3–4).

## Appendix E — Reproduction Instructions
- **Purpose:** One-command-per-experiment reproduction.
- **Source:** tech report Appendix B, `CLAUDE.md` command list.
- **Content:**
  ```bash
  mars corpus verify-frozen salience-memory-benchmark-v1        # integrity
  mars experiments run salience-memory-v1                       # Exp 1
  python experiments/run_noisy_importance.py --cache-only       # Exp 2 (offline)
  python experiments/run_temporal_salience.py                   # Exp 3 (offline cache)
  python experiments/run_confidence_contradiction.py            # Exp 4 (offline cache)
  python experiments/launch_exec_impact_5_1.py --real-autodev --dry-run \
      --issues-file experiments/execution_impact_5_1/issues.yaml \
      --retrieval-limit 3 --experiment salience-memory-execution-impact-5-1  # Exp 5.1
  ```
  Note the committed retrieval cache (`experiments/cache/`) makes Exp 2–4 offline and
  deterministic; only Exp 1 (live Voyage) and Exp 5.1 (paid AutoDev) need credentials.

## Appendix F — Configuration
- **Purpose:** Pin the environment.
- **Source:** `pyproject.toml`, `CLAUDE.md`.
- **Content:** Python 3.12 + uv; core deps (Typer, Pydantic, SQLAlchemy/SQLite, Rich,
  Jinja2, PyYAML); optional `mcp` extra for real providers; provider auto-selection
  via `MARS_AUTODEV_MCP_*` / `MARS_CORTEX_MCP_*`; SQLite persistence (`mars.db`,
  gitignored).

## Appendix G — Weighting Parameters
- **Purpose:** State the exact ranking functions.
- **Source:** `mars/memory/retrieval.py`, `salience_v1.py`.
- **Content:**
  - `similarity_only`: s = sim(q, m).
  - `salience_weighted_v1`: normalized blend (w_sim, w_imp, w_rec, w_freq) =
    (0.40, 0.30, 0.20, 0.10).
  - gated confidence (Exp 4): s = 0.65·sim + 0.35·(importance × confidence);
    additive comparator: 0.65·sim + 0.25·imp + 0.10·conf.
  - Note that recency/frequency are inert in Exp 1 (constant across each pool under
    simultaneous seeding); single weight set used throughout (disclosed limitation).

## Appendix H — Embedding Configuration
- **Purpose:** Pin the semantic baseline.
- **Source:** `docs/SALIENCE_MEMORY_V1_RESULTS.md`.
- **Content:** Cortex retrieval over MCP; Voyage `voyage-3-lite` embeddings, confirmed
  live (HTTP 200 per memory); `semantic_score` verified non-null (honesty constraint);
  deterministic retrieval given fixed embeddings; single embedding model (disclosed
  limitation).

## Appendix I — Threats to Validity (extended)
- **Purpose:** Full, consolidated limitations beyond the body's summary.
- **Source:** tech report §11.
- **Content:** synthetic corpus; authored importance/confidence; Exp 1 effect as upper
  bound; execution underpowering (floor, single trial, 6 tasks, dry-run,
  `review_passed` unusable → restored-oracle validation); retrieval_limit sensitivity;
  single embedding model / single weight set; adversarial-similarity corpus making
  absolute numbers corpus-specific.

---

### Appendix ordering note
Recommended body order: A (spec) → B (schema) → C (metrics) → D (bootstrap) → E
(reproduction) → F (config) → G (weights) → H (embeddings) → I (threats). G and H may
be folded into F if the venue limits appendix length.
