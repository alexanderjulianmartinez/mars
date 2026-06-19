# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current State

The MVP is implemented per the spec in `docs/claude_code_mars_boostrap.md` (still the authoritative
design reference). The `mars` package, bundled `suites/`, tests, and CLI all exist and pass.

### Commands

Python 3.12 + [uv](https://github.com/astral-sh/uv):

```bash
uv venv --python 3.12 && uv pip install -e ".[dev]"   # setup
pytest                                                # all tests
pytest tests/test_scoring.py                          # one file
pytest -k composite                                   # by keyword
mars list-suites | list-cases --suite S | run --suite S --agent A | report --run-id R | compare --suite S --agents a,b | replay --run-id R
mars list-experiments | experiment --experiment salience-memory [--trials N --seed S]   # Apollo
```

Use the venv binaries directly (`.venv/bin/mars`, `.venv/bin/python -m pytest`) since there is no
activated shell. Runs persist to SQLite (`mars.db` by default; `--db` to override) — it is gitignored.

## What Mars Is

Mars is the **evaluation layer** for AI software engineering agents — a benchmark, scoring, and
regression-testing platform. It answers one question: "Did the agent actually succeed, and is it
getting better over time?"

### The Hard Architectural Boundary

Mars sits in a multi-system platform and must respect strict ownership boundaries:

- **Cortex** owns context generation + memory/retrieval (knowledge retrieval, context packages).
- **AutoDev** owns execution (agent runtime, workspaces, running tests, git/PR ops).
- **Mars** owns evaluation, scoring, regression detection, reporting, and **experiments (Apollo)**.
- **Sentinel** owns policy/trust/audit/governance (not yet built; reserved extension points only).

**Mars must NOT execute engineering tasks or generate context directly.** It is an orchestrator and
measurement platform that *consumes* Cortex and AutoDev and measures outcomes. When tempted to add
workspace management, agent execution, or context retrieval logic into Mars, that work belongs behind
a provider interface (see below), not in Mars itself.

## Architecture

(See `ARCHITECTURE.md` for the full picture; the constraints below are the ones easy to violate.)

### Stack
Python 3.12, full type hints required. Core deps: Typer (CLI), Pydantic (models), SQLAlchemy + SQLite
(storage), Pytest, Rich (CLI output), Jinja2 (report templates), PyYAML (suite/case definitions).
Optional/later: FastAPI, Streamlit.

### Domain model
The pipeline flows: `EvalSuite` → `EvalCase` → ( context from Cortex as `ContextPackage`) →
(execution from AutoDev as `AgentRun`) → scored into an `EvalRun`. An `EvalRun` is the central record
linking a case, the context package used, the agent run, the computed score, and test results. Design
the schema so runs carry **enough metadata to replay later** (re-evaluate against new models, prompts,
or context strategies) — replayability is a first-class requirement, not an afterthought.

### Provider interfaces (MCP-first)
Define `CortexProvider` and `AutoDevProvider` as **interfaces only** — do not hardcode transport.
Ship `MockCortexProvider` and `MockAutoDevProvider` that simulate realistic results so the full
pipeline runs end-to-end without real Cortex/AutoDev. Real MCP implementations must be drop-in
replacements for the mocks.

### Scoring
Scorers are pluggable. Initial set: `TestPassScorer`, `RuntimeScorer`, `CostScorer`, `DiffScorer`,
combined into a `CompositeScore` on a 0–100 scale. Add new scorers by implementing the scorer
interface, not by editing existing ones.

### Storage
SQLAlchemy over SQLite for the MVP, using the **repository pattern**. Persist suites, cases, runs,
scores, and context versions. Structure storage and any APIs so a future dashboard can expose
leaderboards, score history, and run/suite explorers — but do not build the dashboard yet.

### Regression detection
Compare a current run against a baseline run and emit warnings for score, runtime, and cost
regressions.

### Apollo experiments (`mars/apollo/`, `mars/memory/`)
Apollo runs controlled A/B experiments on top of the eval engine: each `Experiment` has a baseline arm
and experimental arm(s), run over a suite across N **seeded trials**, compared with a **paired** bootstrap
CI + Cohen's d verdict (`compare_arms`). The first experiment, `salience-memory`, compares
salience-weighted vs similarity-only retrieval (`mars/memory/retrieval.py`). Key invariants: the AutoDev
"luck" roll is seeded by (agent, case, trial) and **not** the strategy, so arms are properly paired;
memory-aware retrieval flows through the normal pipeline via `CortexProvider.get_context_for_case`. A
no-op `PolicyHook` is the reserved **Sentinel** extension point. Details in `docs/APOLLO.md`. Keep
retrieval/memory logic behind the Cortex provider boundary — it does not belong in Mars proper.

## Design Principles

Modular, typed, local-first, MCP-first, extensible. The recurring test for any change: **future
integrations (real Cortex/AutoDev MCP servers, new scorers, new suites) should require minimal code
changes** — prefer new implementations of an interface over modifying existing code.

## Development Process (per the spec)

Build incrementally. After every major step: run tests, fix issues, verify the CLI works, update docs.
