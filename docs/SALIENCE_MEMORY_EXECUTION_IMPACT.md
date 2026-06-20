# Salience Memory — Execution Impact Study (Experiment 5)

> Do retrieval improvements translate into measurable improvements in agent
> execution?

This is the first **downstream** experiment in the program. Experiments 1–4
established that salience-weighted retrieval improves *retrieval quality*
(importance, then gated confidence). The question that actually matters for the
thesis is whether those gains reach the agent: better task success, review
quality, fewer contradiction failures, better efficiency.

## Status update (AutoDev wiring fixed)

The earlier "blocked on AutoDev unavailable" diagnosis was **wrong** and has been
corrected. Real AutoDev *is* reachable, and Mars can now call it — see
`docs/AUTODEV_EXECUTION_IMPACT_WIRING.md`.

- **Real AutoDev connectivity is verified.** With `MARS_AUTODEV_MCP_*` pointed at
  the local AutoDev repo (`autodev mcp serve`, stdio), Mars spawns the real server
  and `prepare_workspace` returns a real `run_id` + workspace path with **zero LLM
  cost**: `python experiments/run_execution_impact.py --real-autodev --dry-run
  --connectivity-check`. The block was a missing runner adapter + unset env, not a
  missing provider.
- **The precise remaining blocker is per-arm context injection, not AutoDev
  availability.** `autodev_start_run` accepts only `issue_url` (no context-package
  or retrieval-mode parameter), so Mars cannot make a real agentic run use arm A vs
  B vs C retrieval — AutoDev retrieves its own context. The harness can measure
  *real execution per task*, but **cannot attribute differences to the retrieval
  arm** until AutoDev exposes a context/retrieval-mode argument. The arm is recorded
  as provenance only.
- **What is now runnable for evidence:** real agentic dry-runs over issue-backed
  tasks (`--real-autodev --dry-run --issues-file …`), which produce
  `evidential=true` real execution metrics per task. The A/B/C *comparison* remains
  gated on the context-injection capability above.

## Why a result is still not claimed (honest stop)

The mock/simulated executor defines success as a function of retrieval quality
(`success ∝ floor + (1−floor)·relevance`, penalized under retrieved contradictions),
so running it and reporting "execution improved" would be **circular**. Per the
experiment's own rule — *"Do not optimize for a positive result. Optimize for
truth."* — the runner **honest-stops** (exit 2) without `--real-autodev`/`--simulate`,
and prints a precise availability report rather than a bare "unavailable". No
evidential A/B/C execution result is claimed because the retrieval arm cannot yet be
injected into a real run.

What *was* delivered: the **complete, real, provider-agnostic execution-impact
harness** — three paired retrieval arms, a memory-dependent benchmark, the full
execution/quality/efficiency/retrieval metric suite, the new
`RetrievalToExecutionCorrelation` analysis, and failure classification — plus a
preregistered analysis plan and an explicitly **non-evidential** simulation that
validates the apparatus. When AutoDev is configured, the same harness produces
real evidence with no analysis changes.

- Harness: `mars/memory/execution_impact.py`
- Runner: `experiments/run_execution_impact.py` (`--simulate` for apparatus validation)
- Result data (flagged `execution_real=false, evidential=false`): `mars-experiments/salience-memory-execution-impact.json`

## Design (preregistered)

| | |
| --- | --- |
| Arms (only retrieval varies) | **A** `similarity_only` (baseline) · **B** `sim_plus_importance` (Exp 1 winner) · **C** `salience_v2` = sim + importance + gated confidence (Exp 4) |
| Held constant | model, provider, prompts, acceptance criteria, repository, setup commands, evaluation logic |
| Benchmark | 30 memory-dependent tasks across 3 classes — `repo_evolution`, `contradiction`, `long_horizon` — each with acceptance criteria, a target memory (high importance/confidence but low similarity), supporting relevant memories, high-similarity low-importance distractors, and (contradiction tasks) an obsolete memory that is important + high-similarity but low-confidence |
| Pairing | every (task, trial) runs under A, B, C with **arm-independent luck**, so arms differ only through retrieved context |
| Execution metrics | TaskSuccessRate, AcceptanceCriteriaPassRate, ReviewPassRate, ValidationPassRate |
| Quality metrics | DiffQuality, ReviewQuality, FocusedDiffRate, ContradictionFailureRate |
| Efficiency metrics | RuntimeSeconds, TokenUsage, ContextSize, ContextEfficiency |
| Retrieval metrics | Recall@5, MRR, TargetFound (recorded per sample for correlation) |
| Statistics | paired bootstrap 95% CIs (success, review quality), win rates |
| New metric | **RetrievalToExecutionCorrelation** — Pearson + Spearman between per-sample retrieval metrics and task success |
| Failure analysis | every failure classified: retrieval_failure / contradiction_retrieval / planning_failure / implementation_failure / validation_failure / review_failure, with examples |

## Apparatus validation (SIMULATION — NOT EVIDENCE)

The run below uses `SimulatedOutcomeModel`, in which success is **defined** to rise
with retrieval relevance and collapse when an obsolete contradictory memory enters
context. It exists **only** to prove the harness runs end-to-end and to show the
analysis output. **It cannot support any conclusion about execution** — its result
is true by construction. (30 tasks × 5 trials × 3 arms.)

| arm | success | Δ success (95% CI) | review_pass | review_quality | contra_fail | runtime_s | tokens | recall@5 | MRR |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `A_similarity_only` | 0.233 | — | 0.227 | 0.273 | 0.880 | 134.1 | 8917 | 0.000 | 0.137 |
| `B_sim_importance` | 0.367 | +0.133 [+0.080, +0.193] | 0.360 | 0.378 | 0.860 | 117.4 | 7249 | 0.333 | 0.833 |
| `C_salience_v2` | 0.560 | +0.327 [+0.253, +0.407] | 0.553 | 0.486 | **0.000** | 102.7 | 6100 | 0.500 | 1.000 |

RetrievalToExecutionCorrelation (per sample, n=450): recall@5↔success Pearson +0.31,
MRR↔success +0.30, target_found↔success +0.22. Failure breakdown: arm A fails by
`retrieval_failure` (71) + `contradiction_retrieval` (44); arm B fixes retrieval but
still retrieves contradictions (43) and adds `planning_failure` (52); arm C
eliminates retrieval + contradiction failures, leaving only downstream
implementation/validation/review failures.

**Read this table as a wiring diagram, not a result.** Every number is a
mechanical consequence of the stated outcome model. Its only legitimate uses are:
(a) the harness runs and is deterministic; (b) the analysis (paired CIs,
correlation, failure classes) is computed correctly; (c) a *power* check — if real
execution did respond to retrieval, this analysis would detect it.

## Analysis questions — answered conservatively

**1. Do retrieval improvements improve execution?** **Unknown — untested.** No real
execution was run; the simulation cannot answer this without circularity. This is
the central open question of the program.

**2. Which retrieval strategy performs best?** On *retrieval quality* (Exp 1–4),
arm C (`salience_v2`) is best, then B, then A. On *execution*, **undetermined** —
the experiment exists precisely because retrieval rank need not equal execution
rank (the spec's Outcomes B/C).

**3. Do confidence signals reduce contradiction failures?** Established only at the
**retrieval** layer (Exp 4: importance_only CAR 0.000 → gated 0.964). Whether
suppressing a contradictory memory in *context* actually prevents a *contradiction
failure in execution* is **untested** — the simulation assumes it (contra_fail →
0.000 for arm C) but that is the assumption, not evidence.

**4. Do better retrieval metrics predict better task outcomes?** **Unknown.** This
is exactly what `RetrievalToExecutionCorrelation` measures and exactly what needs a
real run; the simulated correlation (+0.31) is built in.

**5. Is Salience v2 worth the added complexity?** **Not yet decidable on execution
grounds.** The retrieval case for Salience v2 is strong and cheap (it reuses
signals Cortex already stores). But the added complexity should be justified by
*execution* impact, which is unmeasured. Conservative recommendation: do **not**
promote Salience v2 on execution grounds until the real run is done; the retrieval
evidence stands on its own.

**6. What remains unexplained?** Essentially the entire downstream link:
whether better context changes what the agent *does*; whether real models actually
fail on retrieved contradictions or recover from them; the real cost/latency/token
tradeoffs; and whether any effect generalizes beyond a synthetic benchmark to real
repositories (e.g. a SWE-bench Verified subset, listed as optional external
validation and also not run).

## Outcome classification

The spec's Outcomes A–D each presuppose a real execution result (retrieval
improves + execution improves/unchanged/worsens/mixed). **None applies**: the
honest status is **"evidence pending — BLOCKED on AutoDev."** Recording this as
inconclusive rather than forcing a verdict is the truthful outcome.

## Recommendation

1. **Do not claim Salience v2 improves agent outcomes.** Experiments 1–4 justify it
   as a *retrieval* improvement only.
2. **Keep the retrieval conclusions as established**; treat execution impact as an
   open, preregistered question.
3. **To obtain evidence**, configure a real AutoDev MCP server and an
   embedding-capable Cortex, then run `python experiments/run_execution_impact.py`.
   The harness will run the three arms paired and emit an `evidential=true` result
   with the same analysis. Then re-evaluate questions 1–5 against real data.
4. **Optional external validation**: once the internal benchmark shows signal, run a
   small SWE-bench Verified / SWE-EVO subset through the same harness for external
   validity (secondary evidence only).

## Threats to validity (for the eventual real run)

- **Synthetic benchmark**: the internal tasks are hand-constructed to be
  memory-dependent and adversarial; real-repo tasks will differ.
- **Arm→retrieval wiring**: the real path must map each arm to an equivalent Cortex
  retrieval mode and adapt `AgentRun` → `SampleRecord`; until that adapter lands the
  runner refuses real mode rather than silently simulate.
- **Confounds**: holding model/prompts/repo constant is essential; only retrieval
  may vary.
- **Effect size**: retrieval gains can be real yet washed out by model robustness
  (the agent recovering from imperfect context) — a genuine Outcome B is plausible
  and must be reported as such.

## Re-run

```
python experiments/run_execution_impact.py                                   # honest-stops (exit 2); prints precise AutoDev availability report
python experiments/run_execution_impact.py --simulate                        # apparatus validation only (NOT evidence)
python experiments/run_execution_impact.py --real-autodev --dry-run --connectivity-check   # real AutoDev wiring proof (zero LLM, not evidence)
python experiments/run_execution_impact.py --real-autodev --dry-run --issues-file issues.yaml --limit-tasks 30   # real evidential per-task runs
```

Set the AutoDev env first (see `docs/AUTODEV_EXECUTION_IMPACT_WIRING.md`):
`MARS_AUTODEV_MCP_COMMAND`, `MARS_AUTODEV_MCP_ARGS='mcp serve'`,
`MARS_AUTODEV_MCP_TRANSPORT=stdio`, `MARS_AUTODEV_MCP_CWD`.
