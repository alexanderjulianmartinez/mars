# Mars Roadmap

## Phase 0 — Foundations (done)

- Domain model, YAML suites, repository storage.
- Provider interfaces + deterministic mocks.
- Pluggable scoring + composite score.
- Eval engine, regression detection, replay.
- Markdown/JSON reporting.
- CLI: `list-suites`, `list-cases`, `run`, `report`, `compare`, `replay`.

## Phase 1 — Real integrations (in progress)

- [x] MCP-backed `AutoDevProvider` (drop-in for the mock; env-configured).
- [x] MCP-backed `CortexProvider` (symmetric; shares the MCP client).
- [ ] Real workspace lifecycle, diff capture, and test execution verified
      against a reference AutoDev MCP server.
- [ ] Context versioning surfaced in reports and replay.

## Phase 2 — Scale & rigor

- Parallel run execution and run batching.
- Richer scorers (lint/type checks, security, semantic diff quality).
- Per-suite scorer configuration and weighting.
- Baseline pinning and historical trend tracking.

## Phase 3 — Analytics surface

- Read APIs (FastAPI) over the repository: leaderboards, score history,
  run explorer, suite explorer.
- Aggregate regression dashboards across suites and agents.

## Phase 4 — Dashboard & ecosystem

- Streamlit/web dashboard consuming the Phase 3 APIs.
- Suite authoring tooling and a shared suite registry.
- Replay-driven evaluation of new models, prompts, and context strategies.

## Delivered alongside Phase 1 — evaluation readiness

**Track A — Agentic eval readiness** (`docs/AGENTIC_EVALS.md`): per-case
`setup_commands` + `acceptance_criteria` propagation, and three new scorers
(`DiffQualityScorer`, `NoiseScorer`, `LiteralInstructionScorer`) folded into a
reweighted composite. `mars score-fixture` compares pre-recorded mock outputs
with no paid models.

**Track B — Salience Memory v1** (`docs/SALIENCE_MEMORY_V1.md`): retrieval metrics
(recall@k/precision@k/MRR/target/context-efficiency), real-Cortex retrieval source,
and honest `semantic_score: null` detection. `mars experiments run salience-memory-v1`.
