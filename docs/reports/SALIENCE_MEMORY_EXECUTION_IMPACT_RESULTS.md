# Execution Impact (Experiment 5) — Results

> Does improved retrieval produce better agent outcomes?

**Status: RUN — evidential. Real AutoDev agent executed all three arms over 6
memory-dependent tasks.** Headline: **retrieval improved substantially and the
contradiction-avoidance result replicated at the agent layer, but task success
floored at 0% for every arm — so the execution payoff of better retrieval is
*undetermined* (a floor effect), not shown to be zero.**

- Data: `mars-experiments/salience-memory-execution-impact-v2.json` (`evidential=true`)
- Harness: `mars/memory/execution_impact.py` · Runner: `experiments/run_execution_impact.py`
- Benchmark: `github.com/alexanderjulianmartinez/mars-exec-impact-bench` (6 issues)

## 1. Retrieval arm implementation
Same issue / model / criteria / repo per task; only retrieval varied, injected via
AutoDev `start_run(retrieval_strategy=…, context_package_id=…)`:
A = `similarity_only`, B = `sim_importance`, C = `salience_v2` (sim+importance+recency).

## 2. AutoDev context-injection mechanism
`StartRunRequest.retrieval_strategy` + `context_package_id`; AutoDev memory provider
strategies `similarity_only / sim_importance / salience_v2`. Verified the arms inject
**different** contexts at run time (Phase-3 gate `arms_distinct=true`,
`valid_comparison=true`).

## 3–6. Run accounting
| | |
| --- | --- |
| Tasks | 6 (repo-evolution ×2, historical-decision, contradiction ×2, long-horizon) |
| Real agent runs | **18** (3 arms × 6 tasks, dry_run) |
| Dry runs | 18 (all; no PRs) |
| Total cost | ≈ **$1.55** (mean ≈ $0.08/run; A 0.078, B 0.097, C 0.087) |
| Tokens | not surfaced by AutoDev telemetry → marked missing (not fabricated) |

## 7. Strategy comparison (real, paired over 6 tasks)

| arm | task success | recall@5 | MRR | target_found | ContradictionAvoidanceRate¹ | Δ success (95% CI) |
| --- | --- | --- | --- | --- | --- | --- |
| A `similarity_only` | **0.000** | 0.500 | 0.283 | 0.500 | **0.00** (fails all) | — |
| B `sim_importance` | **0.000** | 0.833 | 0.569 | 1.000 | **1.00** (avoids all) | +0.000 [0, 0] · 0W/6T/0L |
| C `salience_v2` | **0.000** | 0.833 | 0.569 | 1.000 | **1.00** (avoids all) | +0.000 [0, 0] · 0W/6T/0L |

¹ CAR = fraction of contradiction tasks where the correct memory outranks the
obsolete one. (The JSON's `contradiction_failure_rate` is the complement: A = 1.00
fails, B/C = 0.00.)

## 8. Retrieval metrics
Retrieval improved clearly and as predicted by Experiments 1 & 4:
- **recall@5 0.50 → 0.83** (+0.33), **MRR 0.28 → 0.57** (+0.29), **target_found
  0.50 → 1.00**.
- **Contradiction avoidance:** A retrieved the obsolete memory in *every*
  contradiction task; B/C avoided it in *every* one (CAR 0.00 → 1.00). This
  replicates Exp 4's importance-resolves-contradictions finding inside a real agent
  pipeline.

## 9. Execution metrics
**Task success = 0.000 for all three arms** (0/6 each). Acceptance/validation/review
pass rates all 0. The dry-run agent produced real diffs (focused, non-empty) for
every run but none passed the task's tests.

Failure breakdown (why each arm failed):
| arm | contradiction_retrieval | implementation_failure | validation_failure |
| --- | --- | --- | --- |
| A | 4 | 1 | 1 |
| B | 0 | 2 | 4 |
| C | 0 | 2 | 4 |

A fails mostly by retrieving the *wrong* memory (4 contradiction tasks); B/C retrieve
the *right* memory but still fail downstream (implementation/validation). So even
correct context did not yield a correct implementation.

## 10. Correlation analysis
`recall@5 / MRR / target_found / context_efficiency` vs `task_success`: **Pearson =
Spearman = 0.000** (n=18). Trivially zero because `task_success` has **no variance**
(all 0). The correlation is therefore **uninformative**, not evidence of "no
relationship."

## 11. Main finding
Two things are simultaneously true and both honest:
1. **Salience retrieval works at the agent layer.** Importance-weighted retrieval
   (B/C) beat similarity-only (A) on recall@5 (+0.33), MRR (+0.29), and drove
   contradiction avoidance from 0% to 100% — in a real dry-run agent pipeline, not a
   simulation.
2. **The execution payoff is undetermined.** Success floored at 0/6 for every arm,
   so the experiment has **no statistical power** to detect an execution-success
   difference. This is **Outcome B (retrieval improves, execution unchanged)** as
   *observed*, but the cause is a **floor effect**: the dry-run agent (gpt-4.1 coder
   on under-specified issues) could not solve any task, regardless of context. We
   therefore **cannot** claim "better retrieval doesn't help execution" — only that
   it didn't, *and couldn't have been detected to*, on this benchmark.

## 12. Is the result evidential?
**Yes** — `evidential=true`, 18 real agent runs, real model, real pytest validation,
real retrieval telemetry, Phase-3 gate passed. The retrieval comparison is real
evidence; the execution-success comparison is real but **underpowered (floor)**.

## 13. Recommendation for paper inclusion
- **Include the retrieval-layer result**: salience retrieval, driven into a real
  agent over MCP, improves recall and eliminates contradiction retrieval (replicates
  Exp 1 & 4 downstream of the retrieval-only benchmark).
- **Do NOT claim salience improves agent task success** — there is no such evidence
  (and the floor means none was obtainable here).
- **Do NOT claim it fails to** — the floor makes that unmeasurable.
- Report execution impact as **open**, pending a benchmark where the agent has
  non-zero success (so the metric has variance).

## What's needed to actually measure execution impact
The binding constraint was the agent's success rate, not retrieval. To get a
measurable execution signal:
1. **Solvable tasks** — easier / better-specified issues so success > 0% for at least
   the well-retrieved arms (variance is required to detect an effect).
2. **Stronger coder model and/or non-dry-run** so implementations actually pass tests.
3. **More trials per task** for paired-bootstrap power once success varies.
4. Consider hiding the acceptance tests from the agent (run them only as a hidden
   validation set) to keep the task genuinely memory-dependent.

## Honest caveats
- AutoDev's `salience_v2` arm = similarity + importance + **recency** (no confidence
  ranker), so C tests importance+recency, not Mars's confidence-based v2; with recency
  neutralized in the benchmark, **B ≈ C** (as observed — identical retrieval metrics).
- `diff_quality` / `focused_diff` here are presence proxies (diff non-empty), not
  scored quality; `token_usage`/`review_quality` were not returned by AutoDev and are
  marked missing.
- Memory was re-seeded before every run to isolate AutoDev's run-summary writeback;
  without this, accumulated run memory pollutes later arms (observed and fixed).

## Re-run
```
# memory auto-reseeds before each run; --no-reseed to disable
python experiments/run_execution_impact.py --real-autodev --dry-run \
  --issues-file experiments/issues.yaml --limit-tasks 6
```
(Requires MARS_AUTODEV_MCP_* + the keys forwarded via MARS_AUTODEV_MCP_ENV; AutoDev
configs/models.yaml on valid ids; benchmark memory seeded via
`experiments/seed_autodev_memory.py`.)
