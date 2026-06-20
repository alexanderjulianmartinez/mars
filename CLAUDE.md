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
mars list-fixtures | score-fixture bootstrap-typo-and-rename                             # Track A (no paid models)
mars experiments run salience-memory-v1 [--cortex-provider mcp --strict-semantic] | experiments report ...  # Track B
mars corpus validate salience-memory-v1-expanded | corpus stats salience-memory-v1-expanded             # benchmark corpus
python experiments/run_noisy_importance.py --no-seed --db <cortex.db> | --cache-only                     # Track 1 noisy-importance
python experiments/run_temporal_salience.py [--seeds 10]                                                 # Experiment 3 temporal salience
python experiments/run_confidence_contradiction.py [--seeds 10]                                          # Experiment 4 confidence & contradiction
python experiments/run_execution_impact.py [--simulate]                                                  # Experiment 5 execution impact (BLOCKED w/o AutoDev)
```

Two evaluation tracks (kept separate): **Track A — agentic eval** scores real AutoDev runs via new
case fields (`setup_commands`, `acceptance_criteria`, `expected/allowed/forbidden_files`,
`literal_requirements`) and scorers (`DiffQualityScorer`, `NoiseScorer`, `LiteralInstructionScorer` in
`mars/scoring/agentic.py`) folded into a reweighted `default_composite`; `mars/fixtures.py` +
`score-fixture` compare mock outputs with no paid models. **Track B — Salience Memory v1**
(`mars/memory/salience_v1.py`, `metrics.py`, `retrieval_source.py`) runs retrieval metrics over real
Cortex retrieval + mock execution and is **honest about `semantic_score: null`** (never claims a
semantic baseline without embeddings). The **expanded benchmark corpus**
(`experiments/corpus/salience-memory-v1-expanded.corpus.yaml`, 30 queries / 552 memories across six
categories) replaces the saturating 13-memory smoke test; it is authored reproducibly by
`experiments/corpus/generate_expanded.py` + `scenarios_data.py`, loaded/validated via
`mars/memory/expanded_corpus.py` (`mars corpus validate|stats`), and scored with metrics incl.
`ndcg_at_k`. **Track 1 — noisy-importance study** (`mars/memory/importance_noise.py`,
`noisy_importance_experiment.py`, `experiments/run_noisy_importance.py`) degrades the importance signal
(shuffle model, quality 1.0→0.0) over the same corpus/retrieval to find how robust the salience win is
to noisy importance; it materializes one real retrieval per query into a committed cache
(`experiments/cache/`) so the quality sweep is offline + deterministic, and isolates the importance
*signal's* contribution via an `oracle − scrambled` comparison + an importance-ablated floor.
**Experiment 3 — temporal salience** (`mars/memory/temporal_salience.py`,
`experiments/run_temporal_salience.py`) reuses that same cache to assign synthetic timestamps under
four regimes (uniform / recency-aligned / misaligned / mixed-realistic) and isolates recency vs decay
(`exp(-age/half_life)`, half-lives 7/30/90) against a `sim_plus_importance` anchor: finding — importance
is regime-invariant and dominant, raw recency helps only when aligned and hurts symmetrically when
misaligned (neutral in the realistic regime), so recency stays an optional short-decay/low-weight/
importance-gated add-on, NOT a core v2 signal. **Experiment 4 — confidence & contradiction**
(`mars/memory/confidence_contradiction.py`, `experiments/run_confidence_contradiction.py`) reuses the
same cache (joined to the corpus by content for category+confidence) over five regimes incl. an
adversarial "important-but-wrong" H4 stress regime, adds the `ContradictionAvoidanceRate` metric, and
compares additive vs **gated** confidence (`effective_importance = importance × confidence`): finding —
confidence is mostly redundant with importance UNTIL they diverge, where `importance_only` collapses to
CAR 0.000 and gated confidence restores it to 0.964, so **confidence joins importance as a core v2
signal in gated form** (recency stays out). **Experiment 5 — execution impact** (first downstream study;
`mars/memory/execution_impact.py`, `experiments/run_execution_impact.py`) builds a real, provider-agnostic
3-arm (A similarity / B +importance / C salience_v2) harness with execution/quality/efficiency metrics,
`RetrievalToExecutionCorrelation`, and failure classification. It **runs real AutoDev** via Mars's
existing `AutoDevMCPProvider` + `AutoDevExecutionImpactAdapter` when `MARS_AUTODEV_MCP_*` is set
(connectivity verified: `--real-autodev --dry-run --connectivity-check` returns a real `run_id`, zero
LLM); `evidential=true` only when a real agent is invoked; default **honest-stops** with a precise
availability report; `--simulate` is non-evidential apparatus validation (mock success is *defined* by
retrieval → circular). **Honest blocker for the A/B/C comparison:** `autodev_start_run` takes `issue_url`
only (no context-injection arg), so Mars cannot vary per-arm retrieval inside a real run (arm is
provenance only) — needs AutoDev to expose a context/retrieval-mode parameter. Wiring guide:
`docs/AUTODEV_EXECUTION_IMPACT_WIRING.md`. Verdict: execution impact of Salience v2 is **untested/open**;
don't claim it improves agent outcomes yet. Details: `docs/AGENTIC_EVALS.md`, `docs/SALIENCE_MEMORY_V1.md`,
`docs/SALIENCE_MEMORY_V1_EXPANDED.md`, `docs/SALIENCE_MEMORY_NOISY_IMPORTANCE.md`,
`docs/SALIENCE_MEMORY_TEMPORAL_SALIENCE.md`, `docs/SALIENCE_MEMORY_CONFIDENCE_AND_CONTRADICTION.md`,
`docs/SALIENCE_MEMORY_EXECUTION_IMPACT.md`, `docs/AUTODEV_EXECUTION_IMPACT_WIRING.md`,
`docs/salience-memory-v2-proposal.md`.

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

Both real providers exist: `AutoDevMCPProvider` (`mars/providers/autodev_mcp.py`) and
`CortexMCPProvider` (`mars/providers/cortex_mcp.py`) speak their tool contracts over MCP via the
shared transport seam in `mars/providers/mcp_client.py` (a sync `ToolCaller` protocol + SDK-backed
`MCPToolCaller` that bridges async MCP on a background loop). `make_autodev` / `make_cortex`
(`mars/agents.py`) auto-select the real provider when `MARS_AUTODEV_MCP_*` / `MARS_CORTEX_MCP_*` is
set, else fall back to mocks — independently. The `mcp` package is an **optional** dependency,
imported lazily — do not import it at module load.

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
