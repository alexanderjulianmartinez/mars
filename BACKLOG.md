# Mars Backlog

Prioritized work, highest first. Items map to roadmap phases.

## High

- [x] MCP `AutoDevProvider`: real workspace create/run/test/diff/cleanup.
      (`mars/providers/autodev_mcp.py`; env-configured, mock fallback.)
- [ ] MCP `CortexProvider`: real context packages + metadata. (Symmetric to AutoDev;
      reuse `mars/providers/mcp_client.py`.)
- [ ] Integration-test `AutoDevMCPProvider` against a reference AutoDev MCP server.
- [ ] Replace `mars/agents.py` mock presets with a real agent registry.
- [ ] Persist suites/cases to storage for a run explorer (not just YAML on disk).
- [ ] `mars report` batch mode: render a whole run/suite, not one EvalRun.

## Apollo (experiments)

- [ ] Wire experiments to real Cortex/AutoDev MCP providers (drop-in for mocks).
- [ ] Persist `ExperimentResult` to storage; add `experiment report` (md/json).
- [ ] Add a parametric significance test + multiple-comparison correction for N arms.
- [ ] Replace the synthetic memory generator with Cortex-sourced memories + gold labels.
- [ ] Define experiments in YAML (like suites) instead of code-only registry.
- [ ] First Sentinel `PolicyHook`: audit trail + policy gate around experiment runs.

## Medium

- [ ] Parallel execution in `EvalRunner.run_suite`.
- [ ] Additional scorers: lint, type-check, security, semantic diff quality.
- [ ] Per-case/per-suite scorer config (weights, budgets) in YAML.
- [ ] Baseline pinning (compare against a named baseline, not just the previous run).
- [ ] CLI `list-runs` / `history` command over `Repository.list_eval_runs`.
- [ ] JSON Schema export for suite YAML + validation in the loader.

## Low

- [ ] FastAPI read API (leaderboards, history, explorers).
- [ ] Streamlit dashboard.
- [ ] More suites: database-migration, refactoring.
- [ ] HTML report output.
- [ ] Cost/runtime trend charts in reports.

## Tech debt / polish

- [ ] `MockAutoDevProvider.capture_diff` is a no-op; revisit once real diff
      capture exists so `run_agent` and `capture_diff` responsibilities are clean.
- [ ] Add `ENDPOINT_EXISTS` / `NO_UNRELATED_CHANGES` real checks once AutoDev
      exposes the workspace tree (currently proxied via tests/file count).
