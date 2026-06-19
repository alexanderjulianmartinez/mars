# CLAUDE_CODE_MARS_BOOTSTRAP.md

````markdown
# Mars Bootstrap Prompt

You are Claude Code operating as a Staff+ Engineer, Platform Architect, and Founding Engineer.

Your objective is to create the initial implementation of a platform called Mars.

---

# Product Vision

Mars is the evaluation layer for AI software engineering systems.

Modern AI engineering infrastructure consists of three layers:

1. Cortex
   - Context Engineering
   - Knowledge Retrieval
   - Context Packages
   - Architecture Understanding
   - Documentation Intelligence

2. AutoDev
   - Agent Runtime
   - Workspace Management
   - Tool Execution
   - Test Execution
   - Git Operations
   - PR Generation

3. Mars
   - Evaluation
   - Benchmarking
   - Regression Detection
   - Agent Scoring
   - Performance Analytics

Mars answers:

"Did the agent actually succeed?"

---

# Core Principle

Mars should NOT execute engineering tasks directly.

Mars is an orchestrator and measurement platform.

Execution belongs to AutoDev.

Context belongs to Cortex.

Mars consumes both and measures outcomes.

---

# Architecture

```text
                 Human
                    │
                    ▼

              ┌──────────┐
              │  Cortex  │
              └────┬─────┘
                   │
             Context Package
                   │
                   ▼

              ┌──────────┐
              │ AutoDev  │
              └────┬─────┘
                   │
               Execution
                   │
                   ▼

              ┌──────────┐
              │   Mars   │
              └──────────┘

          Evaluation + Scoring
````

# Design Goals

Build Mars as:

* Modular
* Typed
* Local-first
* MCP-first
* Extensible
* Production-oriented

Future integrations should require minimal code changes.

---

# Technology Stack

Python 3.12

Required:

* Typer
* Pydantic
* SQLAlchemy
* SQLite
* Pytest
* Rich
* Jinja2
* PyYAML

Optional:

* FastAPI
* Streamlit

Use modern Python patterns.

Full type hints required.

---

# Domain Model

Implement:

## EvalSuite

Collection of benchmark cases.

Fields:

* id
* name
* description
* tags
* cases

---

## EvalCase

Single benchmark task.

Fields:

* id
* suite_id
* name
* description
* repo
* task_prompt
* context_profile
* setup_commands
* test_commands
* success_criteria
* timeout_seconds

---

## ContextPackage

Represents context returned by Cortex.

Fields:

* id
* profile
* version
* generated_at
* metadata

---

## AgentRun

Raw execution result returned by AutoDev.

Fields:

* id
* agent
* model
* logs
* diff
* runtime
* cost
* status

---

## EvalRun

Evaluation of an AgentRun.

Fields:

* id

* suite_id

* case_id

* context_package_id

* agent_run_id

* score

* status

* duration_ms

* cost_usd

* failure_reason

* test_results

* evaluation_summary

* created_at

---

# Scoring Engine

Create pluggable scorers.

Initial scorers:

* TestPassScorer
* RuntimeScorer
* CostScorer
* DiffScorer

CompositeScore:

0-100

---

# MCP Architecture

Implement interfaces only.

Do not hardcode transport.

Create:

## CortexProvider

Methods:

get_context_package()

list_profiles()

get_context_metadata()

---

## AutoDevProvider

Methods:

create_workspace()

run_agent()

run_tests()

capture_diff()

cleanup_workspace()

---

Implement:

MockCortexProvider

MockAutoDevProvider

These should simulate realistic results.

Future MCP implementations should be drop-in replacements.

---

# Benchmark Suites

Create:

## backend-api-suite

Cases:

* add-health-endpoint
* fix-failing-test

---

## infra-suite

Cases:

* debug-service-failure
* update-terraform-variable

Mock implementations acceptable.

---

# CLI

Implement:

mars list-suites

mars list-cases

mars run

mars report

mars compare

mars replay

Use Rich for output.

---

# Storage

Use SQLAlchemy.

Store:

* suites
* cases
* runs
* scores
* context versions

SQLite for MVP.

Repository pattern preferred.

---

# Reporting

Generate:

1. Markdown Reports

2. JSON Reports

Include:

* score
* runtime
* cost
* pass/fail
* diff summary
* context version

---

# Regression Detection

Build initial framework.

Mars should compare:

Current Run

vs

Baseline Run

Detect:

* score regression
* runtime regression
* cost regression

Generate warnings.

---

# Replay Framework

Store enough metadata to replay runs later.

Future use cases:

* Evaluate new models
* Evaluate new prompts
* Evaluate new context strategies

Design schema accordingly.

---

# Initial Dashboard Preparation

Do not build dashboard yet.

But structure APIs and storage so a future dashboard can expose:

* leaderboards
* score history
* run explorer
* suite explorer

---

# Repository Structure

Create:

mars/
docs/
suites/
tests/

Include:

README.md

ARCHITECTURE.md

ROADMAP.md

BACKLOG.md

CONTRIBUTING.md

---

# Documentation

Generate:

## README

Product overview.

## ARCHITECTURE

System design.

## ROADMAP

Phase 0-4.

## BACKLOG

Prioritized tasks.

---

# Development Process

Build incrementally.

After every major step:

1. Run tests
2. Fix issues
3. Verify CLI works
4. Update docs

---

# Integration Strategy

Assume Cortex and AutoDev already exist.

Design Mars as a consumer of those systems.

Mars owns:

* Benchmark definitions
* Evaluations
* Scoring
* Regression detection
* Reporting

Mars does not own:

* Context generation
* Agent execution

---

# Success Criteria

At completion:

* Project compiles
* Tests pass
* CLI functions
* Sample suites run
* Reports generate
* Mock Cortex integration works
* Mock AutoDev integration works
* Architecture supports future MCP integrations

Finally:

1. Print repository tree
2. Print implemented features
3. Print remaining backlog
4. Recommend next milestone

```

This prompt will give you a significantly better result than a pure "generate scaffold" prompt because it forces Claude to think like the founding engineer of Mars rather than a code generator. It also aligns with how you've been positioning **Cortex (context)** and **AutoDev (execution)** as separate platforms, which is a much stronger long-term architecture story for interviews, open source, and potential products.
```
