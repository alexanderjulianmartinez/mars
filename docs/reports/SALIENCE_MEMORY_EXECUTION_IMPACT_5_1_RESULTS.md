# Salience Memory — Execution Impact (Experiment 5.1) Results

> **Question.** Does improved memory retrieval improve *real* agent task outcomes?
> Three retrieval arms, same tasks, same model, same task spec — only the injected
> context differs.
>
> | Arm | Strategy | Ranking signal |
> |---|---|---|
> | **A** | `similarity_only` | term overlap only |
> | **B** | `sim_importance` | overlap + importance |
> | **C** | `salience_v2` | overlap + importance + recency decay |

This is the first **evidential** execution-impact run for Salience Memory: Mars
drives **real AutoDev** agent runs (plan → implement → validate → review) over a
purpose-built, memory-dependent benchmark, and scores each run against the task's
own oracle test. `evidential=true` only because a real agent was invoked; no
outcome is simulated.

## TL;DR

**Outcome B (with a behavioural twist).** On this benchmark, salience-aware
retrieval **clearly improved retrieval** (importance arms surface the corrective
memory the similarity arm never sees: target-found 0.83 vs 0.00, MRR 0.56 vs 0.00
at `retrieval_limit=3`) and **demonstrably steered the agent's *approach*** toward
the repo's current convention (right-approach rate 1.00 for B/C vs 0.83 for A; the
clean case is `bench-4`, where the similarity arm followed the **stale doc** and
used a session cookie while both importance arms used JWT). **But task-success
(oracle pass) did not move**: every arm passed the same 2 of 6 tasks (0.333), and
retrieval quality did **not** positively predict success (recall↔success
Pearson −0.32). The four harder tasks failed in *all* arms for
implementation/iteration reasons unrelated to retrieval.

**Verdict:** Salience improves retrieval and changes what the agent does, but on
this benchmark that did **not** translate into better downstream task outcomes.
Evidential (18 real agent runs) but **single-trial and partially floored** (4/6
tasks unwinnable by any arm at `max_iterations=3`) — do **not** claim a downstream
execution win, and do not yet put this in an arXiv draft as a positive result.
It belongs in the paper as an honest negative/null with a real behavioural signal.

## Why the earlier verdict was "untested/open"

Experiment 5 shipped a real 3-arm harness but had never produced an evidential
A/B/C comparison: no model key/issue tasks, and — more fundamentally — no
benchmark where retrieval was *task-relevant*. The generic adversarial seed
(`experiment_seed.py`) only diverges for a single "healthcheck" query, which is
irrelevant to real tasks, so injecting it could not move execution. 5.1 fixes the
benchmark so retrieval genuinely matters, then measures.

## Benchmark design (the part that makes this honest)

Six tasks in a small, dependency-free repo
(`alexanderjulianmartinez/mars-exec-impact-bench`), each **memory-dependent**: the
knowledge needed to do it the repo's way lives in a *decision/postmortem/convention*
that is either not visible in the file being edited, or actively contradicted by a
**stale doc** still present in the repo.

| Task | Category | Trap a memory-less agent falls into |
|---|---|---|
| `bench-1-audit-log-table` | long-horizon pattern reuse | integer PK / irreversible migration |
| `bench-2-payments-retry` | repo evolution | hand-rolled loop / adds `tenacity` |
| `bench-3-locale-backfill` | repo evolution | one blocking update, not batched |
| `bench-4-protect-admin-reports` | **contradiction** | follows stale `docs/AUTH.md` → session cookie |
| `bench-5-feature-x-flag` | **contradiction** | follows stale `docs/CONFIG.md` → `legacy_env` |
| `bench-6-order-refunded-event` | long-horizon pattern reuse | calls a broker directly / unversioned event |

**Success oracle** = the task's targeted test (e.g. `pytest tests/test_admin_auth.py`).
The test file is **forbidden** so a run cannot pass by editing the test.

### Controlled memory + verified divergence

Each task gets an **isolated 5-record store**, reseeded before *every* run:

* one **corrective** record (the decision/postmortem/convention) — importance 3.5,
  **old**, and deliberately **low term-overlap** with the issue. A pure-similarity
  ranker buries it; importance-aware rankers surface it.
* four **recent, higher-overlap distractors** — short unhelpful run summaries; for
  the contradiction tasks, some **echo the stale docs** (the `contradictory` gold).

Divergence is **proven offline** with AutoDev's *real* scorers at
`retrieval_limit=3` (`experiments/verify_exec_impact_5_1_divergence.py`): for all
six tasks, arm A misses the corrective record while B and C surface it, and the
three arms inject different context. This is apparatus validation, not evidence of
execution impact.

## Apparatus (Mars ⇄ AutoDev)

* Mars `AutoDevMCPProvider` drives the real AutoDev MCP server over stdio
  (`experiments/launch_exec_impact_5_1.py` wires keys + a generous call timeout;
  `start_run` blocks for the whole pipeline).
* Per-arm retrieval is injected via `start_run`'s `retrieval_strategy` +
  `context_package_id`; the full task spec (`acceptance_criteria`,
  `acceptance_checks`, `validation_commands`, `forbidden_files`, …) is threaded so
  AutoDev's review gate renders a real verdict instead of auto-blocking.
* **Phase-3 divergence gate**: the comparison is only claimed `valid_comparison`
  when a real agent ran **and** the arms injected demonstrably different context.
* **Oracle-restoration fix (important).** The agent frequently *rewrites the test
  file* in its workspace. Without intervention, validation runs the agent's tests,
  not the benchmark oracle — measuring the wrong thing (it produced an apparent 0%
  floor). Mars now restores forbidden files to their committed state on the
  (co-located) workspace before validating, so success reflects the agent's
  **implementation** against the **fixed oracle**.
* **Primary success** = agent run completed **and** the implementation passes the
  restored oracle test. AutoDev's own `review.review_passed` is reported separately
  (it additionally blocks on the forbidden-file edits the agent makes across all
  arms, so it is not the discriminating signal here).
* **Honesty:** token usage and per-run cost are **not exposed** by AutoDev in this
  path → reported as missing, never fabricated. AutoDev's Cortex SQL *telemetry*
  sink has a stale schema (missing `novelty_score`) that emits non-fatal delivery
  errors; retrieval uses the separate file-backed store and is unaffected.

## Results

18 real AutoDev agent runs (6 tasks × 3 arms × 1 trial), `dry_run=true` (no PRs),
`retrieval_limit=3`. Model: AutoDev's configured default (observed
`claude-sonnet-4-6`) — Mars does not override it, so it is held constant across
arms. Total run cost ≈ **$1.3** (token usage not exposed by AutoDev).
`evidential=true`, `arms_distinct=true`, `valid_comparison=true`.
Raw: `mars-experiments/salience-memory-execution-impact-5-1.json`;
behavioural: `…-5-1-behavioral.json`.

### Strategy comparison

| arm | task_success | review_pass | recall@5 | target_found | MRR | right-approach | ctx |
|---|---|---|---|---|---|---|---|
| `A_similarity_only` | **0.333** | 0.000 | 0.000 | 0.000 | 0.000 | 0.83 | 3 |
| `B_sim_importance`  | **0.333** | 0.000 | 0.833 | 0.833 | 0.556 | **1.00** | 3 |
| `C_salience_v2`     | **0.333** | 0.000 | 0.833 | 0.833 | 0.556 | **1.00** | 3 |

Paired Δ success vs A: B `+0.000` (6 ties), C `+0.000` (6 ties) — **no execution
difference**. The retrieval columns, by contrast, differ sharply: at `limit=3` the
similarity arm **never** injects the corrective record (recall/target-found 0.0),
while both importance arms inject it ~5/6 of the time. B and C are identical here
(the recency term in `salience_v2` reorders but does not change the top-3 set vs
`sim_importance` on this store — consistent with the Exp-3 finding that recency
adds no execution value).

`review_pass = 0` for every arm because the agent edits forbidden files (it rewrites
the oracle test and edits the stale doc), which AutoDev's review gate blocks
regardless of correctness. Primary success is therefore Mars's **restored-oracle
validation** (the agent's implementation vs the pristine test), not `review_passed`.

### Execution metrics (per oracle test)

- TaskSuccessRate / ValidationPassRate: **2/6 = 0.333 in every arm.**
- The two passing tasks are the **same** in all arms: `bench-1-audit-log-table`
  and `bench-6-order-refunded-event` (pattern-reuse tasks whose convention is also
  visible in the repo code). The four harder tasks fail in all arms.
- ReviewPassRate: 0.000 (forbidden-file edits → blocked; see above).

### Behavioural metric (the real signal)

Did the agent use the repo's **current** convention or fall for the legacy/stale
trap? (from each run's implementation diff)

| task | A_similarity | B_sim_importance | C_salience_v2 |
|---|---|---|---|
| bench-4 protect-admin-reports | ✗ session cookie (stale doc) | ✓ **JWT** | ✓ **JWT** |
| bench-1 / -2 / -3 / -5 / -6 | ✓ right approach | ✓ right approach | ✓ right approach |
| **right-approach rate** | **0.83** | **1.00** | **1.00** |

`bench-4` is the clean demonstration: deprived of the corrective memory, the
similarity arm trusts the repo's out-of-date `docs/AUTH.md` and implements
cookie-session auth; given the corrective memory, both importance arms implement
JWT. Retrieval changed the agent's behaviour — it just wasn't enough to pass the
(stricter, multi-assertion) oracle within the iteration budget.

### Correlation (retrieval → execution), n=18

| x | y | Pearson | Spearman |
|---|---|---|---|
| recall@5 | task_success | −0.316 | −0.316 |
| MRR | task_success | −0.067 | −0.144 |
| target_found | task_success | −0.316 | −0.316 |

Retrieval quality does **not** positively predict task success here — slightly
**negative**, an artifact of *which* tasks are winnable: the 2 tasks that pass are
discoverable-from-code (the similarity arm passes them with recall 0), while the
tasks where retrieval helped most (the contradiction tasks 4/5) are also the
hardest to implement and fail anyway. Better retrieval ≠ better outcome on this set.

### Failure analysis

Primary failure class per failed run:

| arm | contradiction_retrieval | review_failure | validation_failure |
|---|---|---|---|
| `A_similarity_only` | 4 | 0 | 0 |
| `B_sim_importance` | 1 | 2 | 1 |
| `C_salience_v2` | 1 | 2 | 1 |

The **failure modes differ by arm even though the pass rate doesn't**: the
similarity arm fails predominantly by retrieving a contradiction (the stale-doc
distractor) and acting on it; the importance arms, having surfaced the corrective
record, instead fail at implementation/review. Representative examples:

- `bench-4` / A: implemented session-cookie auth from the stale `docs/AUTH.md`
  (`verify_jwt` absent) → wrong scheme.
- `bench-4` / B,C: implemented JWT (`verify_jwt`) but the workspace still failed the
  multi-assertion oracle (rejects-missing / rejects-session / accepts-valid).
- `bench-2` (all arms): test collection error (exit 2) — the implementation broke
  import (e.g. referenced an uninstalled dependency), independent of the arm.

## Interpretation

This maps to **Outcome B** — *salience improves retrieval, but the downstream
benefit was not observed* — sharpened by a behavioural result and a calibration
caveat:

1. **Retrieval improved and behaviour changed** (the importance arms surface the
   corrective decision the similarity arm misses, and the agent acts on it — JWT vs
   stale cookie on `bench-4`; right-approach 1.00 vs 0.83). This is a genuine,
   observed retrieval→behaviour effect.
2. **Task-success did not improve** (0.333 in every arm; the same two tasks pass).
3. **Why:** downstream pass/fail on this benchmark is dominated by implementation
   quality and a per-task difficulty floor (4/6 tasks fail in every arm at
   `max_iterations=3`), not by which memories were retrieved.

**Do not claim Salience v2 improves agent task outcomes.** The honest, supported
claim is: *Salience v2 improves retrieval and steers the agent toward the repo's
current conventions; on this benchmark that did not yet raise task-success.*

### Threats / caveats

- **Single trial** per (task, arm): 6 binary outcomes/arm → coarse; model output is
  not seed-pinned. More reps would tighten the (currently exactly-tied) pass rates.
- **Partial floor:** 4/6 tasks unwinnable by any arm here → low power to detect an
  execution gain even if one existed. Needs easier-to-pass-but-still-memory-gated
  tasks and/or a higher iteration budget.
- **B vs C indistinguishable** on this store (recency reorders, doesn't change the
  top-3 set) — consistent with prior temporal-salience results.
- **`review_passed` unusable as the success signal** because the agent edits
  forbidden files across all arms; we use restored-oracle validation instead.
- AutoDev does not expose token usage (reported missing); its Cortex SQL telemetry
  has a stale schema (non-fatal noise; retrieval is file-backed and unaffected).

### Should this go in the technical report / arXiv draft?

Yes — as an **honest null/negative with a real behavioural signal**, not as a
downstream win. It is the first evidential execution-impact measurement for
Salience Memory and it cleanly separates "retrieval improved + behaviour changed"
from "task-success improved" (the latter unproven). Strengthen before any positive
claim: multiple trials, a less-floored task set, and an iteration budget that lets
correct approaches actually pass.

## Reproduce

```bash
# 1. (offline, free) prove the arms diverge on the real scorers at limit=3
~/git/autodev/.venv/bin/python experiments/verify_exec_impact_5_1_divergence.py

# 2. (paid, ~$1.3) run the full study — real AutoDev agent runs, dry-run (no PRs).
#    retrieval_limit=3 is REQUIRED: with the 5-record store, the similarity arm only
#    excludes the buried corrective record when limit < store size. (At AutoDev's
#    default limit=5 every arm injects the whole store and arms differ only in order.)
python experiments/launch_exec_impact_5_1.py --real-autodev --dry-run \
    --issues-file experiments/execution_impact_5_1/issues.yaml \
    --retrieval-limit 3 --experiment salience-memory-execution-impact-5-1

# 3. (offline, free) behavioural analysis — did the agent use the right convention?
python experiments/analyze_exec_impact_5_1.py
```

> **Methodological note.** A first full run at the AutoDev default `limit=5`
> injected all 5 records in every arm (`context_size=5`), so the arms differed only
> in *order*; success was identical and the contrast untested. The reported run uses
> `limit=3` so the similarity arm is genuinely deprived of the corrective record.
