# Mars Architecture

Mars is the **evaluation layer** for AI software engineering systems. It does not
generate context and does not execute engineering tasks — it orchestrates those
external systems and measures their outcomes.

```text
        Cortex                AutoDev                 Mars
   (context engineering)   (agent execution)      (evaluation)
          │                      │                     │
   ContextPackage  ───►   AgentRun (diff,    ───►  EvalRun (score,
                          tests, cost,             status, regression)
                          runtime)
```

## Pipeline

A single evaluation (`EvalRunner.run_case`) sequences:

1. **Context** — ask `CortexProvider` for the `ContextPackage` for the case's
   `context_profile`. Mars never builds context itself.
2. **Execution** — ask `AutoDevProvider` to `create_workspace`, `run_agent`, and
   `run_tests`. Mars never runs the agent or the tests itself.
3. **Merge** — fold the test results into the `AgentRun`.
4. **Criteria** — evaluate the case's declared `success_criteria`.
5. **Score** — blend pluggable scorers into a composite 0–100 (`CompositeScorer`).
6. **Persist** — store the `ContextPackage`, `AgentRun`, and resulting `EvalRun`.

## The provider boundary (MCP-first)

`mars/providers/base.py` defines `CortexProvider` and `AutoDevProvider` as abstract
interfaces with no transport assumptions. The MVP ships in-process mocks
(`MockCortexProvider`, `MockAutoDevProvider`) that simulate realistic, **deterministic**
results seeded from case id + agent. A future MCP client must implement the same
ABCs and drop in unchanged — the engine and CLI import only the interfaces.

## Modules

| Module | Responsibility |
| --- | --- |
| `mars/models.py` | Pydantic domain model (suites, cases, runs, scores). |
| `mars/suites.py` | Load YAML suite definitions from `suites/`. |
| `mars/providers/` | Cortex/AutoDev interfaces + mock implementations. |
| `mars/scoring/` | Scorer interface, built-in scorers, composite. |
| `mars/engine/` | `EvalRunner` orchestration + regression detection. |
| `mars/storage/` | SQLAlchemy ORM + repository (the only persistence API). |
| `mars/reporting/` | Markdown (Jinja2) + JSON report rendering. |
| `mars/agents.py` | Mock agent presets (placeholder until real AutoDev). |
| `mars/memory/` | Retrieval strategies (similarity-only, salience-weighted) + synthetic store. |
| `mars/apollo/` | Experiment framework: arms, trials, paired statistics, verdict, policy hook. |
| `mars/cli.py` | Typer + Rich command-line interface. |

## Apollo (experiments)

Apollo sits on top of the evaluation engine to run controlled A/B comparisons —
"did experimental strategy A beat baseline B?" — across seeded trials, with a
paired bootstrap-CI + Cohen's d verdict. The first experiment, `salience-memory`,
compares salience-weighted vs similarity-only memory retrieval. See `docs/APOLLO.md`.
The provider boundary is reused unchanged: a per-case `get_context_for_case` hook
on `CortexProvider` lets memory-aware retrieval flow through the same pipeline.
A `PolicyHook` extension point is reserved for future **Sentinel** policy/audit.

## Storage & replay

Each ORM row stores the full Pydantic model as JSON plus indexed columns the
explorers query on. Because the `AgentRun` is persisted intact, a frozen
execution can be **re-scored under a new scoring strategy** (`mars replay`) without
re-running the agent — the foundation for evaluating new models, prompts, and
context strategies over historical runs.

## Regression detection

`detect_regression` compares a current `EvalRun` against its baseline (the previous
run for the same suite/case/agent) and flags score drops, runtime/cost increases,
and pass→fail status changes.

## Design invariants

- Mars owns: benchmark definitions, evaluation, scoring, regression, reporting.
- Mars does **not** own: context generation, agent execution.
- New scorers, suites, and providers are added by implementing an interface or
  dropping in a file — not by editing existing code.
