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
```

Two separate evaluation tracks: **agentic eval** (scoring real AutoDev runs) and
**retrieval experiments** (salience-memory). They are kept distinct on purpose.

## Mission

Build the evaluation layer for AI software engineering.

Cortex gives agents context.

AutoDev gives agents execution.

Mars determines whether they are actually improving.

