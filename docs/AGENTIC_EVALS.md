# Agentic Evaluation (Track A)

Track A makes Mars score **real AutoDev runs** well enough to compare models
meaningfully. It is deliberately separate from retrieval experiments (Track B,
`docs/SALIENCE_MEMORY_V1.md`) — do not mix them.

## Why it exists

The first live `claude-sonnet-4-5` vs `gpt-4.1` comparison was operationally
useful but not scientific: the workspace had no deps (tests failed for both),
acceptance criteria weren't propagated, and the composite was nearly identical
because there was no diff-quality / noise / literal-instruction scoring. Track A
closes those gaps.

## What an eval case can now declare

```yaml
setup_commands:                 # run before validation (deps install)
  - uv sync
  - pip install -e ".[dev]"

acceptance_criteria:            # propagated to AutoDev / shown in reports
  - Fix the misspelled bootstrap reference.
  - Do not edit unrelated files.

expected_files: [CLAUDE.md, docs/CLAUDE_CODE_MARS_BOOTSTRAP.md]
allowed_files:  ["docs/**", README.md]
forbidden_files: [.env, "secrets/**"]

literal_requirements:
  - id: fix_bootstrap_typo
    required: true
    check: { type: text_absent, pattern: boostrap }
  - id: rename_file
    required: true
    check: { type: file_exists, path: docs/CLAUDE_CODE_MARS_BOOTSTRAP.md }
```

## Scorers

| Scorer | What it measures |
| --- | --- |
| `TestPassScorer` | fraction of validation commands that passed |
| `LiteralInstructionScorer` | per-requirement pass/fail (diff-based checks) |
| `DiffQualityScorer` | targeted vs noisy/broad/forbidden change |
| `NoiseScorer` | unrelated edits + whitespace/newline churn |
| `RuntimeScorer` / `CostScorer` | budget adherence |

Composite weights (agentic): test 0.30, literal 0.25, diff_quality 0.20, noise
0.10, runtime 0.075, cost 0.075. Each agentic scorer is a **no-op (100)** when
the case declares no relevant config, so the composite stays meaningful for
plain cases. If setup/tests fail, the other scorers still give partial signal.

Literal check types: `text_present`, `text_absent`, `file_exists`,
`file_not_exists`, `file_renamed`, `changed_file_matches` — all evaluated
against the agent's unified diff.

## Propagation to AutoDev

`setup_commands` run as a gated `autodev_validate` call **before** the scored
tests. `acceptance_criteria` are formatted into a delimited `Acceptance
Criteria:` section in the task payload; because `autodev_start_run` accepts only
an `issue_url`, the provider logs a warning and records them in run metadata
(put them in the issue body to actually influence a live run).

## Try it (no API keys, no paid models)

```bash
mars list-fixtures
mars score-fixture bootstrap-typo-and-rename
```

Expected: the clean **gpt-like** run scores higher than the noisy **claude-like**
run, and **both** are penalised for missing the literal file rename.

## Running against a real model

This is opt-in and costs money on the AutoDev side. Configure
`MARS_AUTODEV_MCP_*` + an `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` on AutoDev, give
the case an `issue_url`, then run via the normal pipeline. Mars never opens PRs.
