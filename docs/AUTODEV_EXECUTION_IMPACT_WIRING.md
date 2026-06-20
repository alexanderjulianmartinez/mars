# AutoDev wiring for Experiment 5 (Execution Impact)

How Mars calls **real AutoDev** for the execution-impact experiment, and exactly
what counts as evidence.

## What was blocking Mars

Nothing in the *provider* — Mars already shipped a complete, verified-contract
`AutoDevMCPProvider` (`mars/providers/autodev_mcp.py`) with `from_env()`, agentic +
deterministic modes, `dry_run`, model selection, and `setup_commands` propagation.

The block was entirely in the Experiment 5 **runner**: it returned exit 3 on the
real path (no adapter) and otherwise honest-stopped, and `MARS_AUTODEV_MCP_*` was
unset — so `using_real_autodev()` was `False` and the runner reported a generic
"AutoDev unavailable" instead of the exact missing variables. AutoDev was reachable
the whole time (local repo at `~/git/autodev` with `autodev mcp serve`).

This change adds the adapter + runner wiring + a precise availability report.

## Required environment variables

Point Mars at any AutoDev MCP server. For the local AutoDev repo over stdio:

```bash
export MARS_AUTODEV_MCP_COMMAND=$HOME/git/autodev/.venv/bin/autodev
export MARS_AUTODEV_MCP_ARGS='mcp serve'
export MARS_AUTODEV_MCP_TRANSPORT=stdio
export MARS_AUTODEV_MCP_CWD=$HOME/git/autodev
# optional: MARS_AUTODEV_MCP_ENV="KEY=VAL ..."   MARS_AUTODEV_MCP_URL=...(http)
```

`python experiments/run_execution_impact.py` (no flags) prints the full
availability report: provider selected, every var checked, transport, the
endpoint/tools attempted, and a copy-paste fix.

## Four execution modes — and which are evidence

| mode | command | real AutoDev? | agent/model invoked? | `evidential` |
| --- | --- | --- | --- | --- |
| **mock** | (engine default, no server) | no | no | n/a — never used for Exp 5 |
| **simulation** | `--simulate` | no | no | **false** (outcome is defined as a function of retrieval — circular) |
| **connectivity** | `--real-autodev --connectivity-check` | yes (`prepare_workspace`) | **no** | **false** (proves wiring only, zero LLM) |
| **real dry-run** | `--real-autodev --dry-run --issues-file …` | yes (`start_run`→`get_run`) | **yes**, no PR | **true** |
| **real** | `--real-autodev --issues-file …` | yes | yes | **true** |

`evidential=true` is set **only** when a real agent was actually invoked
(`agent_invoked`). A dry-run that drives the real AutoDev pipeline (real
plan/implement/validate/review, no PR) **is** evidence. Mock and simulation never
are.

## Smoke test (zero spend)

```bash
python experiments/run_execution_impact.py --real-autodev --dry-run --connectivity-check
```

Verified working: spawns the real AutoDev server, calls `prepare_workspace`,
returns a real `run_id` + workspace path, **zero LLM cost**. Proves Mars↔AutoDev
connectivity. Not evidence for the A/B/C comparison (no agent invoked).

## Full real run

```bash
python experiments/run_execution_impact.py \
  --real-autodev --dry-run \
  --issues-file path/to/issues.yaml \
  --limit-tasks 30 [--limit-arms N] [--model claude-sonnet-4-5]
```

`issues.yaml`:

```yaml
tasks:
  - id: repo-evo-01
    issue_url: https://github.com/<org>/<repo>/issues/123
    repo: <org>/<repo>
    setup_commands: ["uv pip install -e ."]
    test_commands: ["pytest -q"]
    acceptance_criteria: ["follows the prior migration decision in #98"]
    allowed_files: ["src/**"]
    forbidden_files: ["migrations/**"]
```

The adapter (`AutoDevExecutionImpactAdapter`) drives
`create_workspace → run_agent → run_tests → capture_diff` per (arm, task), then
converts the real `AgentRun`/`TestResult`s into a `SampleRecord`, preserving
`run_id` and provenance.

## Forward-compatible switch for per-arm retrieval (ready now)

Mars is already wired to inject the retrieval arm into a real run **the moment
AutoDev adds the parameter** — it is gated off by default because `start_run`'s
schema is `additionalProperties: false` today (an unknown arg would be rejected).

- Provider (`AutoDevMCPProvider`): `retrieval_strategy`, `retrieval_arg_name`
  (default `"retrieval_strategy"`, configurable), `send_retrieval` (default
  `False`). When enabled, the value is added to the `start_run` payload under the
  configured name and recorded in run provenance.
- Adapter (`AutoDevExecutionImpactAdapter`): `arm_retrieval` maps each arm to its
  AutoDev retrieval value (`A_similarity_only→similarity_only`,
  `B_sim_importance→sim_importance`, `C_salience_v2→salience_v2`) and applies it
  per arm when `send_retrieval=True`.
- Output: when `get_run` returns `retrieved_context` / `token_usage` /
  `review_results[].decision`, Mars parses them (`AgentRun.retrieved_context`,
  `token_usage`, `review_decision`) and computes **real** retrieval metrics
  (recall@k, MRR, target-found, contradiction-in-context) from what the run
  actually retrieved (given task gold). Absent fields are marked in
  `missing_fields`, never fabricated.

Enable once AutoDev ships the parameter:

```bash
python experiments/run_execution_impact.py --real-autodev --dry-run \
  --issues-file issues.yaml --send-retrieval [--retrieval-arg-name retrieval_mode]
```

That single flag turns the run into a real A/B/C comparison with no further Mars
changes. What AutoDev needs to ship is summarized in the handoff at the top of this
section's sibling note (a `start_run` retrieval/context arg + `get_run`
`retrieved_context`/`token_usage`/review fields).

## Honest limitations (the real remaining blocker)

1. **Per-arm context cannot be injected into a real run.** `autodev_start_run`
   accepts only `issue_url` (plus `dry_run`/`isolation_mode`/`max_iterations`) —
   **no context-package or retrieval-mode parameter**. AutoDev retrieves its own
   context. So Mars cannot make a real agentic run use arm A vs B vs C retrieval;
   the arm is recorded as *provenance only* and drives Mars-side retrieval metrics,
   not what the agent sees. **A valid per-arm execution comparison requires AutoDev
   to expose a context/retrieval-mode argument on `start_run`** (or for Mars to
   drive AutoDev's Cortex retrieval per arm). Until then, Experiment 5 can measure
   *real execution per task* but cannot attribute differences to the retrieval arm.
2. **`acceptance_criteria` are not propagated over MCP** — `start_run` has no
   criteria parameter; put them in the issue body. Mars records them for reporting.
3. **Token usage / review quality are not in the `AgentRun` contract** — the
   adapter marks them in `missing_fields` rather than fabricating values.

## Files

- `mars/providers/autodev_mcp.py` — real provider (pre-existing, verified contract).
- `mars/memory/execution_impact.py` — `AutoDevExecutionImpactAdapter`,
  `autodev_availability()`, `run_execution_impact_real()`.
- `experiments/run_execution_impact.py` — runner + flags + reports.
- `tests/test_execution_impact_real.py` — adapter/flags/availability (FakeToolCaller).
