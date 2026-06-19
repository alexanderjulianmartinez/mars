# Mars Roadmap

## Phase 0 — Foundations (current)

- Domain model, YAML suites, repository storage.
- Provider interfaces + deterministic mocks.
- Pluggable scoring + composite score.
- Eval engine, regression detection, replay.
- Markdown/JSON reporting.
- CLI: `list-suites`, `list-cases`, `run`, `report`, `compare`, `replay`.

## Phase 1 — Real integrations

- MCP-backed `CortexProvider` and `AutoDevProvider` (drop-in for the mocks).
- Real workspace lifecycle, diff capture, and test execution via AutoDev.
- Context versioning surfaced in reports and replay.

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
