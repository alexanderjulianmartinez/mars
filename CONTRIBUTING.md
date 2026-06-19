# Contributing to Mars

## Setup

Mars targets Python 3.12 and uses [uv](https://github.com/astral-sh/uv).

```bash
uv venv --python 3.12
uv pip install -e ".[dev]"
```

## Running

```bash
mars list-suites
mars list-cases --suite backend-api
mars run --suite backend-api --agent claude-code
mars report --run-id RUN_ID
mars compare --suite backend-api --agents claude-code,codex
mars replay --run-id RUN_ID
```

Runs persist to a local SQLite file (`mars.db` by default; override with `--db`).

## Tests

```bash
pytest                       # full suite
pytest tests/test_scoring.py # one file
pytest -k composite          # by keyword
```

After any meaningful change: run tests, fix issues, verify the CLI works, update docs.

## Extending Mars

Mars grows by **adding implementations of an interface**, not by editing existing code:

- **New scorer** — subclass `mars.scoring.base.Scorer`, return a 0–100 `ScoreOutcome`,
  and add it to a `CompositeScorer` mix.
- **New suite** — drop a `*.yaml` file in `suites/`; the loader picks it up.
- **Real Cortex/AutoDev** — implement `CortexProvider` / `AutoDevProvider` from
  `mars.providers.base`. It must be a drop-in replacement for the mocks; the engine
  and CLI depend only on the abstract interfaces.

## Boundaries (please respect)

Mars evaluates; it does not generate context and does not execute engineering tasks.
Anything that runs an agent, manages a workspace, or retrieves context belongs behind
a provider interface — never inline in the engine, scorers, or CLI.
