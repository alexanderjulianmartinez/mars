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

## Using a real AutoDev (MCP)

By default `mars run` uses the mock AutoDev. To drive a real AutoDev MCP server,
install the optional transport and point Mars at the server — no code changes,
the provider is selected from the environment:

```bash
uv pip install -e ".[mcp]"

# HTTP (streamable-http by default; set ..._TRANSPORT=sse for SSE):
export MARS_AUTODEV_MCP_URL="http://localhost:9000/mcp"

# …or stdio (spawn a local server process):
export MARS_AUTODEV_MCP_COMMAND="autodev-mcp"
export MARS_AUTODEV_MCP_ARGS="--workspace /tmp"

# Real Cortex is symmetric (MARS_CORTEX_MCP_URL / MARS_CORTEX_MCP_COMMAND):
export MARS_CORTEX_MCP_URL="http://localhost:8800/mcp"

mars run --suite backend-api --agent claude-code
# banner: "Cortex backend: Cortex MCP  |  AutoDev backend: AutoDev MCP"
```

Each backend is independent — enable either, both, or neither (mock fallback).
The expected MCP tool contracts are documented in `mars/providers/autodev_mcp.py`
and `mars/providers/cortex_mcp.py`.

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
