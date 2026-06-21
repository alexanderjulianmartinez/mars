# Mars

> Continuous evaluation for AI software engineering agents.

Mars is a benchmark, evaluation, and regression testing platform for AI engineering systems.

As AI agents become capable of implementing features, fixing bugs, writing migrations, and operating software systems, teams need a reliable way to answer a simple question:

**Are our agents actually getting better?**

Mars provides the infrastructure to continuously measure agent performance across real engineering tasks.

## Vision

Modern AI engineering systems require three core layers:

Cortex → Context  
AutoDev → Execution  
Mars → Evaluation

## Core Concepts

### Suite

A collection of related benchmark tasks.

Examples:

- backend-api-suite
- infra-debugging-suite
- database-migration-suite
- refactoring-suite

### Case

A single benchmark task.

Example:

```yaml
id: add-health-endpoint

task:
  Add a /health endpoint returning:
  {"ok": true}

success_criteria:
  - tests_pass
  - endpoint_exists
  - no_unrelated_changes
```

### Run

An execution of an evaluation case.

Each run captures:

- Agent
- Model
- Context Package
- Runtime
- Cost
- Duration
- Diff
- Logs
- Test Results
- Score

## Why Mars?

Mars is named after the Roman god of war.

Engineering agents should not be trusted based on demos.

They should be tested under pressure.

Every feature request, migration, bug fix, and refactor is a battle.

Mars exists to determine which agents consistently win.

## Features

- Benchmark Suites
- Agent Comparison
- Regression Detection
- Replay Engine
- Leaderboards
- Cost Analysis

## Example CLI

```bash
mars list-suites
mars list-cases --suite backend-api
mars run --suite backend-api --agent claude-code
mars report --run-id RUN_123
mars compare --suite backend-api --agents claude-code,codex

# Agentic evaluation (Track A) — no paid models; see docs/AGENTIC_EVALS.md
mars score-fixture bootstrap-typo-and-rename

# Salience Memory retrieval experiment (Track B) — see docs/SALIENCE_MEMORY_V1.md
mars experiments run salience-memory-v1
mars experiments report salience-memory-v1

# Salience Memory Benchmark v1.0.0 (frozen) — see docs/SALIENCE_MEMORY_BENCHMARK_V1.md
mars corpus verify-frozen salience-memory-benchmark-v1
```

Two separate evaluation tracks: **agentic eval** (scoring real AutoDev runs) and
**retrieval experiments** (salience-memory). They are kept distinct on purpose.
All salience-memory results (Experiments 1–5) are reported against **Salience
Memory Benchmark v1.0.0** (`salience-memory-benchmark-v1`), a frozen, hash-pinned
research artifact — see [docs/SALIENCE_MEMORY_BENCHMARK_V1.md](docs/SALIENCE_MEMORY_BENCHMARK_V1.md).

## Research: Salience-Weighted Memory Retrieval

This repository also hosts a research program studying whether **salience signals**
(authored importance and confidence) improve memory retrieval for long-horizon
agents over similarity-only ranking. Headline result on the frozen benchmark:
importance-weighted retrieval lifts recall@5 from 0.237 → 0.672 and MRR from 0.31 →
0.97 (paired bootstrap, CIs exclude zero). The effect is an **upper bound** under
authored importance, and improved retrieval has **not** been shown to raise agent
task-success — both stated plainly in the report.

- Technical report: [docs/reports/SALIENCE_WEIGHTED_MEMORY_RETRIEVAL_TECHNICAL_REPORT.md](docs/reports/SALIENCE_WEIGHTED_MEMORY_RETRIEVAL_TECHNICAL_REPORT.md)
- Paper draft + figures: [docs/papers/](docs/papers/)

### Reproduce

Three tiers — only the first needs no credentials:

```bash
# 1. Offline (no credentials): tests, benchmark integrity, Exp 2–4 via committed cache
pytest
mars corpus verify-frozen salience-memory-benchmark-v1
python experiments/run_noisy_importance.py --cache-only        # Exp 2
python experiments/run_temporal_salience.py                    # Exp 3
python experiments/run_confidence_contradiction.py             # Exp 4

# 2. Semantic baseline (needs a Voyage embeddings key): Exp 1
mars experiments run salience-memory-v1

# 3. Real agent execution (needs MARS_AUTODEV_MCP_*, paid ~$1.3): Exp 5.1
#    see docs/AUTODEV_EXECUTION_IMPACT_WIRING.md
```

## License

Dual-licensed by artifact type (see [NOTICE](NOTICE)):

- **Source code** (`mars/`, scripts, tests) — Apache-2.0 ([LICENSE](LICENSE))
- **Benchmark corpus & result artifacts** (`experiments/corpus/`,
  `experiments/cache/`, `mars-experiments/`) — CC-BY-4.0 ([LICENSE-DATA](LICENSE-DATA))

## Citation

If you use Mars, the benchmark, or the results, please cite via
[CITATION.cff](CITATION.cff).

## Mission

Build the evaluation layer for AI software engineering.

Cortex gives agents context.

AutoDev gives agents execution.

Mars determines whether they are actually improving.

