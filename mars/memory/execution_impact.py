"""Execution Impact study (Experiment 5) — do retrieval gains reach the agent?

Experiments 1–4 established that salience-weighted retrieval (importance, then
confidence) improves *retrieval quality*. This experiment asks the question that
actually matters: **do those retrieval improvements translate into measurably
better agent execution** — task success, review quality, fewer contradiction
failures, better efficiency?

This module is the **orchestration + analysis harness**. It is provider-agnostic:
it sequences a ``CortexProvider`` (retrieval) and an ``AutoDevProvider``
(execution) over a memory-dependent benchmark across three retrieval arms and
measures outcomes. Mars stays in its lane — it does **not** execute tasks itself
(that is AutoDev's job behind the provider boundary).

Honesty contract (this is the whole point of the experiment):

- Real execution evidence requires a **real AutoDev** run. When AutoDev is not
  configured, the harness runs in **simulation** mode against an explicit outcome
  model and every result is flagged ``execution_real=False`` and
  ``evidential=False``. A simulation cannot be evidence that retrieval helps
  execution, because the simulated outcome is *defined* as a function of retrieval
  quality — it only validates the apparatus and the analysis. See
  :class:`SimulatedOutcomeModel`.

The three arms (only the retrieval strategy varies; model/prompts/tasks/criteria
are held constant):

- **A** ``similarity_only`` — semantic baseline.
- **B** ``sim_plus_importance`` — Experiment 1 winner.
- **C** ``salience_v2`` — similarity + importance + gated confidence (Exp 4).
"""

from __future__ import annotations

import json
import math
import statistics
from dataclasses import asdict, dataclass, field
from enum import Enum
from hashlib import sha256
from pathlib import Path

from mars.memory.confidence_contradiction import ImportancePlusConfidenceGatedStrategy
from mars.memory.metrics import mrr, recall_at_k, target_found
from mars.memory.models import MemoryItem
from mars.memory.noisy_importance_experiment import Paired, _paired
from mars.memory.retrieval import SimilarityOnlyStrategy
from mars.memory.temporal_salience import SimPlusImportanceStrategy

RESULTS_DIR = Path("mars-experiments")
K = 5  # context budget


# --- retrieval arms -------------------------------------------------------- #


@dataclass(frozen=True)
class RetrievalArm:
    name: str
    label: str
    strategy: object  # has .score(MemoryItem) and .name
    baseline: bool = False


def retrieval_arms() -> list[RetrievalArm]:
    return [
        RetrievalArm("A_similarity_only", "similarity_only", SimilarityOnlyStrategy(), baseline=True),
        RetrievalArm("B_sim_importance", "sim_plus_importance", SimPlusImportanceStrategy()),
        RetrievalArm("C_salience_v2", "salience_v2 (sim+importance+gated confidence)",
                     ImportancePlusConfidenceGatedStrategy()),
    ]


# --- memory-dependent benchmark tasks -------------------------------------- #


class TaskClass(str, Enum):
    REPO_EVOLUTION = "repo_evolution"  # follow a prior architecture/pattern decision
    CONTRADICTION = "contradiction"  # obsolete guidance contradicts the current truth
    LONG_HORIZON = "long_horizon"  # outcome depends on historical context


@dataclass
class ExecutionTask:
    """A memory-dependent task: succeeding requires retrieving the right memory.

    ``memories`` is the candidate pool the agent's context is drawn from;
    ``target_id`` is the single memory that the task hinges on; ``relevant_ids``
    are supporting memories; ``contradictory_ids`` are obsolete memories that, if
    retrieved into context, mislead the agent.
    """

    id: str
    task_class: TaskClass
    acceptance_criteria: list[str]
    memories: list[MemoryItem]
    target_id: str
    relevant_ids: set[str]
    contradictory_ids: set[str] = field(default_factory=set)


def _unit(*parts: str) -> float:
    return int(sha256("::".join(parts).encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def build_internal_benchmark(n_per_class: int = 10) -> list[ExecutionTask]:
    """Construct a small, deterministic memory-dependent benchmark.

    Each task pool contains: the target (high importance + high confidence, but a
    *lower* semantic similarity than the distractors — the adversarial structure
    from the salience corpus), supporting relevant memories, high-similarity
    low-importance distractors, and (for contradiction tasks) an obsolete memory
    that is highly important but low-confidence. So arm A is fooled by similarity,
    arm B recovers via importance, and arm C additionally gates out the obsolete
    contradictory memory via confidence.
    """
    tasks: list[ExecutionTask] = []
    classes = list(TaskClass)
    for ci, tclass in enumerate(classes):
        for j in range(n_per_class):
            tid = f"{tclass.value}-{j:02d}"
            mems: list[MemoryItem] = []
            # target: low similarity, high importance + confidence
            target = MemoryItem(f"{tid}-target", "target", similarity=0.55 + 0.02 * _unit(tid, "t"),
                                importance=0.9, confidence=0.92)
            mems.append(target)
            relevant_ids = {target.id}
            # two supporting relevant memories
            for r in range(2):
                rid = f"{tid}-rel{r}"
                mems.append(MemoryItem(rid, "relevant", similarity=0.5 + 0.05 * _unit(tid, rid),
                                       importance=0.7, confidence=0.8))
                relevant_ids.add(rid)
            # high-similarity, low-importance distractors
            for d in range(6):
                did = f"{tid}-dis{d}"
                mems.append(MemoryItem(did, "distractor", similarity=0.75 + 0.02 * d,
                                       importance=0.1, confidence=0.7))
            contradictory_ids: set[str] = set()
            if tclass is TaskClass.CONTRADICTION:
                # obsolete memory: important AND high-similarity, but low confidence
                cid = f"{tid}-obsolete"
                mems.append(MemoryItem(cid, "contradictory", similarity=0.82,
                                       importance=0.9, confidence=0.2))
                contradictory_ids.add(cid)
            tasks.append(
                ExecutionTask(
                    id=tid,
                    task_class=tclass,
                    acceptance_criteria=[f"{tid}-ac{a}" for a in range(3)],
                    memories=mems,
                    target_id=target.id,
                    relevant_ids=relevant_ids,
                    contradictory_ids=contradictory_ids,
                )
            )
    return tasks


# --- per-sample execution record ------------------------------------------- #


@dataclass
class SampleRecord:
    task_id: str
    task_class: str
    arm: str
    trial: int
    # retrieval
    recall_at_k: float
    mrr: float
    target_found: bool
    contradiction_in_context: bool  # an obsolete memory entered the top-k above target
    context_efficiency: float
    context_size: int
    # execution
    success: bool
    acceptance_pass_rate: float
    review_pass: bool
    validation_pass: bool
    # quality / efficiency
    diff_quality: float
    review_quality: float
    focused_diff: bool
    runtime_s: float
    token_usage: int
    failure_class: str | None = None
    # provenance (real runs). ``source`` is "simulation" or "real_autodev".
    source: str = "simulation"
    run_id: str | None = None
    dry_run: bool = False
    cost_usd: float | None = None
    # ids of the memories actually injected into this run's context (for the
    # Phase-3 "did the arms differ?" gate). Empty when AutoDev returns no telemetry.
    injected_context_ids: tuple = ()
    # names of metrics the real run could not provide (marked, never fabricated)
    missing_fields: list[str] = field(default_factory=list)


# --- simulated outcome model (NON-evidential) ------------------------------ #


@dataclass
class SimulatedOutcomeModel:
    """Maps a retrieved context to an execution outcome — a STATED HYPOTHESIS.

    This is the model real AutoDev runs would *test*, not confirm. It encodes:
    success rises with retrieval relevance (H1) and falls sharply when an obsolete
    contradictory memory enters context (H3). The ``luck`` roll is seeded by
    (task, trial) and is **independent of the arm**, so arms are paired and differ
    only through the retrieved context.
    """

    base_quality: float = 0.9
    floor: float = 0.30  # success floor at zero relevance
    contradiction_penalty: float = 0.35  # multiplier when a contradiction is in context

    def run(self, task: ExecutionTask, arm: str, trial: int, *, relevance: float,
            contradiction_in_context: bool) -> dict:
        eff = self.base_quality * (self.floor + (1 - self.floor) * relevance)
        if contradiction_in_context:
            eff *= self.contradiction_penalty
        luck = _unit(task.id, str(trial))  # arm-independent → paired
        success = luck < eff
        rt_seed = _unit(task.id, str(trial), "rt")
        # successes finish faster (fewer retries); failures burn extra runtime/tokens
        runtime = (45 if success else 95) + rt_seed * 40 + (1 - relevance) * 30
        tokens = int(3000 + (1 - relevance) * 4000 + (0 if success else 2500))
        return {
            "success": success,
            "acceptance_pass_rate": 1.0 if success else round(self.floor * relevance, 4),
            "review_pass": success and _unit(task.id, str(trial), "rev") < 0.95,
            "validation_pass": success,
            "diff_quality": round((0.85 if success else 0.3) * (0.6 + 0.4 * relevance), 4),
            "review_quality": round((0.8 if success else 0.35) * (0.6 + 0.4 * relevance), 4),
            "focused_diff": success and not contradiction_in_context,
            "runtime_s": round(runtime, 2),
            "token_usage": tokens,
        }


# --- retrieval over a task pool -------------------------------------------- #


def _retrieve(task: ExecutionTask, arm: RetrievalArm, k: int = K) -> dict:
    ranked = sorted(task.memories, key=arm.strategy.score, reverse=True)
    ranked_ids = [m.id for m in ranked]
    topk = ranked_ids[:k]
    rel = task.relevant_ids
    contradiction_in_ctx = any(
        c in topk and (task.target_id not in topk or topk.index(c) < topk.index(task.target_id))
        for c in task.contradictory_ids
    )
    relevant_hits = sum(1 for i in topk if i in rel)
    return {
        "recall_at_k": recall_at_k(ranked_ids, rel, k),
        "mrr": mrr(ranked_ids, rel),
        "target_found": target_found(ranked_ids, task.target_id, k),
        "contradiction_in_context": contradiction_in_ctx,
        "context_efficiency": round(relevant_hits / len(topk), 4) if topk else 0.0,
        "context_size": len(topk),
    }


# --- failure classification ------------------------------------------------ #

FAILURE_CLASSES = (
    "retrieval_failure",
    "contradiction_retrieval",
    "planning_failure",
    "implementation_failure",
    "validation_failure",
    "review_failure",
)


def classify_failure(rec: SampleRecord) -> str | None:
    """Classify why a sample failed (None when it succeeded).

    Retrieval-side causes take precedence (the target never reached context, or an
    obsolete memory did); otherwise the failure is downstream of retrieval and is
    attributed to the stage that broke, via a deterministic sub-roll.
    """
    if rec.success:
        return None
    if rec.contradiction_in_context:
        return "contradiction_retrieval"
    if not rec.target_found:
        return "retrieval_failure"
    if rec.recall_at_k < 0.5:
        return "planning_failure"
    roll = _unit(rec.task_id, str(rec.trial), "stage")
    if not rec.validation_pass and roll < 0.5:
        return "validation_failure"
    if not rec.review_pass and roll >= 0.8:
        return "review_failure"
    return "implementation_failure"


# --- aggregation ----------------------------------------------------------- #


@dataclass
class ArmMetrics:
    arm: str
    label: str
    baseline: bool
    n: int
    # execution
    task_success_rate: float
    acceptance_pass_rate: float
    review_pass_rate: float
    validation_pass_rate: float
    # quality
    diff_quality: float
    review_quality: float
    focused_diff_rate: float
    contradiction_failure_rate: float  # over contradiction-class tasks
    # efficiency
    runtime_s: float
    token_usage: float
    context_size: float
    context_efficiency: float
    # retrieval
    recall_at_k: float
    mrr: float
    target_found_rate: float
    # cost (real runs only; None when unavailable / simulated)
    cost_usd: float | None = None
    # paired vs baseline (success)
    success_delta: Paired | None = None
    review_quality_delta: Paired | None = None


def _mean(xs: list[float]) -> float:
    return round(statistics.fmean(xs), 4) if xs else 0.0


def _mean_opt(xs: list[float | None]) -> float | None:
    """Mean over present (non-None) values; None when none are available."""
    present = [x for x in xs if x is not None]
    return round(statistics.fmean(present), 4) if present else None


def _aggregate(arm: RetrievalArm, recs: list[SampleRecord]) -> ArmMetrics:
    contra = [r for r in recs if r.task_class == TaskClass.CONTRADICTION.value]
    return ArmMetrics(
        arm=arm.name,
        label=arm.label,
        baseline=arm.baseline,
        n=len(recs),
        task_success_rate=_mean([1.0 if r.success else 0.0 for r in recs]),
        acceptance_pass_rate=_mean([r.acceptance_pass_rate for r in recs]),
        review_pass_rate=_mean([1.0 if r.review_pass else 0.0 for r in recs]),
        validation_pass_rate=_mean([1.0 if r.validation_pass else 0.0 for r in recs]),
        diff_quality=_mean([r.diff_quality for r in recs]),
        review_quality=_mean([r.review_quality for r in recs]),
        focused_diff_rate=_mean([1.0 if r.focused_diff else 0.0 for r in recs]),
        contradiction_failure_rate=_mean(
            [1.0 if (not r.success and r.failure_class == "contradiction_retrieval") else 0.0
             for r in contra]
        ),
        runtime_s=_mean([r.runtime_s for r in recs]),
        token_usage=_mean([float(r.token_usage) for r in recs]),
        context_size=_mean([float(r.context_size) for r in recs]),
        context_efficiency=_mean([r.context_efficiency for r in recs]),
        recall_at_k=_mean([r.recall_at_k for r in recs]),
        mrr=_mean([r.mrr for r in recs]),
        target_found_rate=_mean([1.0 if r.target_found else 0.0 for r in recs]),
        cost_usd=_mean_opt([r.cost_usd for r in recs]),
    )


# --- retrieval→execution correlation --------------------------------------- #


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    vy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return round(cov / (vx * vy), 4) if vx > 0 and vy > 0 else 0.0


def _ranks(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _spearman(xs: list[float], ys: list[float]) -> float:
    return _pearson(_ranks(xs), _ranks(ys))


@dataclass
class Correlation:
    metric_x: str
    metric_y: str
    pearson: float
    spearman: float
    n: int


def retrieval_execution_correlation(records: list[SampleRecord]) -> list[Correlation]:
    """Do better retrieval metrics predict better execution, sample-by-sample?"""
    success = [1.0 if r.success else 0.0 for r in records]
    out = []
    for name, xs in (
        ("recall_at_k", [r.recall_at_k for r in records]),
        ("mrr", [r.mrr for r in records]),
        ("target_found", [1.0 if r.target_found else 0.0 for r in records]),
        ("context_efficiency", [r.context_efficiency for r in records]),
    ):
        out.append(
            Correlation(name, "task_success", _pearson(xs, success), _spearman(xs, success), len(records))
        )
    return out


# --- result --------------------------------------------------------------- #


@dataclass
class ExecutionImpactResult:
    experiment: str
    execution_real: bool
    evidential: bool
    n_tasks: int
    trials: int
    arms: list[ArmMetrics]
    correlations: list[Correlation]
    failure_breakdown: dict[str, dict[str, int]]  # arm -> failure_class -> count
    failure_examples: list[dict]
    dry_run: bool = False
    # Phase-3 gate: did the arms actually inject *different* contexts? A valid A/B/C
    # comparison requires this — otherwise the only thing varied (retrieval) didn't
    # vary. ``None`` for the simulation (n/a).
    arms_distinct: bool | None = None
    valid_comparison: bool = False
    notes: list[str] = field(default_factory=list)
    outcome_model: dict | None = None


def run_execution_impact(
    tasks: list[ExecutionTask],
    *,
    trials: int = 5,
    outcome_model: SimulatedOutcomeModel | None = None,
    execution_real: bool = False,
    k: int = K,
    experiment: str = "salience-memory-execution-impact",
    notes: list[str] | None = None,
) -> ExecutionImpactResult:
    """Run all three arms over the benchmark (paired by (task, trial)).

    ``outcome_model`` (simulation) is required when ``execution_real`` is False.
    A real run would instead drive an ``AutoDevProvider`` and populate the same
    :class:`SampleRecord` fields from real ``AgentRun`` results.
    """
    if not execution_real and outcome_model is None:
        outcome_model = SimulatedOutcomeModel()

    arms = retrieval_arms()
    per_arm: dict[str, list[SampleRecord]] = {a.name: [] for a in arms}

    for arm in arms:
        for task in tasks:
            for trial in range(trials):
                r = _retrieve(task, arm, k)
                outcome = outcome_model.run(
                    task, arm.name, trial,
                    relevance=r["recall_at_k"],
                    contradiction_in_context=r["contradiction_in_context"],
                )
                rec = SampleRecord(
                    task_id=task.id, task_class=task.task_class.value, arm=arm.name, trial=trial,
                    recall_at_k=r["recall_at_k"], mrr=r["mrr"], target_found=r["target_found"],
                    contradiction_in_context=r["contradiction_in_context"],
                    context_efficiency=r["context_efficiency"], context_size=r["context_size"],
                    **outcome,
                )
                rec.failure_class = classify_failure(rec)
                per_arm[arm.name].append(rec)

    baseline = next(a for a in arms if a.baseline)
    base_success = [1.0 if r.success else 0.0 for r in per_arm[baseline.name]]
    base_revq = [r.review_quality for r in per_arm[baseline.name]]

    arm_metrics: list[ArmMetrics] = []
    failure_breakdown: dict[str, dict[str, int]] = {}
    for arm in arms:
        recs = per_arm[arm.name]
        m = _aggregate(arm, recs)
        if not arm.baseline:
            m.success_delta = _paired([1.0 if r.success else 0.0 for r in recs], base_success, seed=7)
            m.review_quality_delta = _paired([r.review_quality for r in recs], base_revq, seed=8)
        arm_metrics.append(m)
        counts: dict[str, int] = {}
        for r in recs:
            if r.failure_class:
                counts[r.failure_class] = counts.get(r.failure_class, 0) + 1
        failure_breakdown[arm.name] = counts

    # one example per failure class (from the baseline arm, the most failure-prone)
    examples: list[dict] = []
    seen: set[str] = set()
    for r in per_arm[baseline.name]:
        if r.failure_class and r.failure_class not in seen:
            seen.add(r.failure_class)
            examples.append({
                "arm": r.arm, "task_id": r.task_id, "task_class": r.task_class,
                "failure_class": r.failure_class, "recall_at_k": r.recall_at_k,
                "target_found": r.target_found, "contradiction_in_context": r.contradiction_in_context,
            })

    correlations = retrieval_execution_correlation(
        [r for arm in arms for r in per_arm[arm.name]]
    )

    return ExecutionImpactResult(
        experiment=experiment,
        execution_real=execution_real,
        evidential=execution_real,  # only a real run is evidence
        n_tasks=len(tasks),
        trials=trials,
        arms=arm_metrics,
        correlations=correlations,
        failure_breakdown=failure_breakdown,
        failure_examples=examples,
        notes=notes or [],
        outcome_model=None if execution_real else asdict(outcome_model),
    )


# --- AutoDev availability discovery ---------------------------------------- #

_AUTODEV_ENV_VARS = (
    "MARS_AUTODEV_MCP_URL",
    "MARS_AUTODEV_MCP_COMMAND",
    "MARS_AUTODEV_MCP_ARGS",
    "MARS_AUTODEV_MCP_TRANSPORT",
    "MARS_AUTODEV_MCP_CWD",
    "MARS_AUTODEV_MCP_ENV",
)


def autodev_availability() -> dict:
    """Precise diagnostics about whether Mars can reach real AutoDev.

    Reports the selected provider, every env var checked (with present/absent),
    the transport/endpoint that would be attempted, and an exact fix snippet —
    never a bare "AutoDev unavailable".
    """
    import os

    from mars.agents import using_real_autodev
    from mars.providers.autodev_mcp import config_from_env

    available = using_real_autodev()
    config = config_from_env()
    env_state = {v: (os.environ.get(v) or None) for v in _AUTODEV_ENV_VARS}
    endpoint = None
    if config is not None:
        endpoint = config.url or f"stdio: {config.command} {' '.join(config.args)}".strip()
    fix = (
        "Set an AutoDev MCP server, e.g. the local AutoDev repo over stdio:\n"
        "  export MARS_AUTODEV_MCP_COMMAND=$HOME/git/autodev/.venv/bin/autodev\n"
        "  export MARS_AUTODEV_MCP_ARGS='mcp serve'\n"
        "  export MARS_AUTODEV_MCP_TRANSPORT=stdio\n"
        "  export MARS_AUTODEV_MCP_CWD=$HOME/git/autodev"
    )
    return {
        "available": available,
        "provider": "AutoDevMCPProvider" if available else "MockAutoDevProvider (fallback)",
        "env_vars": env_state,
        "transport": config.transport if config else None,
        "endpoint_attempted": endpoint,
        "tools": list(__import__("mars.providers.autodev_mcp", fromlist=["DEFAULT_TOOL_NAMES"]).DEFAULT_TOOL_NAMES.values()),
        "fix": fix,
    }


def format_availability_report(diag: dict) -> str:
    lines = [
        "AutoDev availability:",
        f"  available: {diag['available']}",
        f"  provider selected: {diag['provider']}",
        f"  transport: {diag['transport']}",
        f"  endpoint attempted: {diag['endpoint_attempted']}",
        f"  tools used: {', '.join(diag['tools'])}",
        "  env vars checked:",
    ]
    for k, v in diag["env_vars"].items():
        lines.append(f"    {k} = {'<set>' if v else '(unset)'}")
    if not diag["available"]:
        lines += ["", "  How to fix:"] + [f"  {ln}" for ln in diag["fix"].splitlines()]
    return "\n".join(lines)


# --- real AutoDev execution adapter ---------------------------------------- #


@dataclass
class AdapterOutcome:
    """One real-AutoDev (arm, task) execution, converted to a SampleRecord."""

    record: SampleRecord
    run_id: str | None
    agent_invoked: bool


def _metrics_from_retrieved_context(retrieved: list[dict], gold: dict, k: int = K) -> dict:
    """Real retrieval metrics from what an AutoDev run actually retrieved.

    ``retrieved`` is ``[{id, score?}, ...]``; ``gold`` carries ``relevant_ids``,
    ``target_id`` and ``contradictory_ids`` for the task.
    """
    ranked = [str(m.get("id")) for m in
              sorted(retrieved, key=lambda m: m.get("score", 0.0), reverse=True)]
    topk = ranked[:k]
    rel = set(gold.get("relevant_ids", set()))
    target = gold.get("target_id")
    contradictory = set(gold.get("contradictory_ids", set()))
    contradiction_in_ctx = any(
        c in topk and (target not in topk or topk.index(c) < topk.index(target))
        for c in contradictory
    )
    relevant_hits = sum(1 for i in topk if i in rel)
    return {
        "task_class": gold.get("task_class", "real"),
        "recall_at_k": recall_at_k(ranked, rel, k),
        "mrr": mrr(ranked, rel),
        "target_found": target_found(ranked, target, k),
        "contradiction_in_context": contradiction_in_ctx,
        "context_efficiency": round(relevant_hits / len(topk), 4) if topk else 0.0,
        "context_size": len(topk),
    }


class AutoDevExecutionImpactAdapter:
    """Drive a **real** ``AutoDevProvider`` for one (arm, task) and convert the
    resulting ``AgentRun`` into a :class:`SampleRecord`.

    Honesty contract:

    - Real execution metrics (success, validation, runtime, cost, diff presence)
      are read from the real ``AgentRun`` / ``TestResult`` objects. Metrics the
      AutoDev contract does not expose (token usage, review quality, a focused-diff
      judgement without file globs) are **marked in ``missing_fields``**, never
      fabricated.
    - ``setup_commands`` and ``test_commands`` are propagated to AutoDev's
      ``validate``; ``acceptance_criteria`` ride in the issue body (the real
      ``start_run`` contract takes ``issue_url`` only — it has no context/criteria
      parameter, so Mars cannot inject them over MCP).
    - **The retrieval arm cannot be injected into a real agentic run**: ``start_run``
      accepts only ``issue_url`` (no context-package parameter). The arm is recorded
      as provenance and drives Mars-side retrieval metrics only; it does *not* change
      what the real agent retrieves. Honest per-arm execution comparison needs
      AutoDev to expose a context/retrieval-mode parameter.
    """

    #: review decisions counted as a pass.
    _REVIEW_PASS = {"approved", "approve", "passed", "pass", "accepted"}

    def __init__(self, autodev, *, dry_run: bool = True,
                 arm_retrieval: dict[str, str] | None = None,
                 send_retrieval: bool = False) -> None:
        self._autodev = autodev
        self.dry_run = dry_run
        # arm.name -> AutoDev retrieval value (e.g. "salience_v2"). Applied to the
        # provider per arm only when ``send_retrieval`` is enabled AND the provider
        # supports it (duck-typed) — see the start_run schema caveat in the wiring
        # doc. Until AutoDev ships the parameter the arm is provenance only.
        self.arm_retrieval = arm_retrieval or {}
        self.send_retrieval = send_retrieval

    def run_sample(self, arm: RetrievalArm, case, context, trial: int,
                   *, retrieval: dict | None = None, gold: dict | None = None) -> AdapterOutcome:
        from mars.models import AgentRunStatus

        self._apply_arm_retrieval(arm)
        ws = self._autodev.create_workspace(case, context)
        agent_run = self._autodev.run_agent(ws, case, context)
        agent_invoked = bool(getattr(self._autodev, "agentic", True))
        tests = self._autodev.run_tests(ws, case)
        run_id = ws.metadata.get("run_id") or agent_run.id

        test_results = tests.test_results
        validation_pass = bool(test_results) and all(t.passed for t in test_results)
        agent_ok = agent_run.status == AgentRunStatus.SUCCESS
        success = agent_ok and (validation_pass if test_results else True)
        acceptance = (
            round(sum(1 for t in test_results if t.passed) / len(test_results), 4)
            if test_results else None
        )

        missing: list[str] = []

        # Retrieval metrics: prefer what the run ACTUALLY retrieved (real), else the
        # Mars-side provenance dict, else mark missing.
        if agent_run.retrieved_context and gold:
            r = _metrics_from_retrieved_context(agent_run.retrieved_context, gold)
        elif retrieval:
            r = retrieval
        else:
            r = {}
            missing.append("retrieval_metrics")

        # token usage (real when AutoDev returns it)
        token = agent_run.token_usage
        if token is None:
            missing.append("token_usage")

        # review (real when AutoDev returns a decision)
        if agent_run.review_decision is None:
            review_pass = False
            missing += ["review_pass", "review_quality"]
        else:
            review_pass = agent_run.review_decision.lower() in self._REVIEW_PASS
            missing.append("review_quality")  # decision yes, numeric quality no

        if not case.allowed_files and not case.forbidden_files:
            missing.append("focused_diff")
        if not test_results:
            missing.append("acceptance_pass_rate")

        rec = SampleRecord(
            task_id=case.id, task_class=r.get("task_class", "real"), arm=arm.name, trial=trial,
            recall_at_k=float(r.get("recall_at_k", 0.0)), mrr=float(r.get("mrr", 0.0)),
            target_found=bool(r.get("target_found", False)),
            contradiction_in_context=bool(r.get("contradiction_in_context", False)),
            context_efficiency=float(r.get("context_efficiency", 0.0)),
            context_size=int(r.get("context_size", len(agent_run.retrieved_context))),
            success=success,
            acceptance_pass_rate=acceptance if acceptance is not None else 0.0,
            review_pass=review_pass,
            validation_pass=validation_pass,
            diff_quality=1.0 if agent_run.diff else 0.0,  # presence only; quality unscored here
            review_quality=0.0,
            focused_diff=bool(agent_run.files_changed) and bool(agent_run.diff),
            runtime_s=round(agent_run.runtime_ms / 1000.0, 2),
            token_usage=int(token) if token is not None else 0,
            source="real_autodev",
            run_id=run_id,
            dry_run=self.dry_run,
            cost_usd=float(agent_run.cost_usd) if agent_run.cost_usd else None,
            injected_context_ids=tuple(str(m.get("id")) for m in agent_run.retrieved_context),
            missing_fields=missing,
        )
        rec.failure_class = classify_failure(rec)
        return AdapterOutcome(record=rec, run_id=run_id, agent_invoked=agent_invoked)

    def _apply_arm_retrieval(self, arm: RetrievalArm) -> None:
        """Set the provider's per-run retrieval strategy + context-package id for
        this arm (no-op when ``send_retrieval`` is disabled)."""
        if not self.send_retrieval:
            return
        value = self.arm_retrieval.get(arm.name, arm.label)
        if hasattr(self._autodev, "retrieval_strategy"):
            self._autodev.retrieval_strategy = value
            self._autodev.send_retrieval = True
            if hasattr(self._autodev, "context_package_id"):
                self._autodev.context_package_id = f"exp5-{arm.name}"


def _arms_distinct(injected: dict[tuple, dict[str, tuple]]) -> bool:
    """Did the arms inject *different* contexts on at least one sample?

    The Phase-3 gate: a valid A/B/C comparison requires retrieval to actually
    differ across arms. Returns False when every arm injected identical context
    (e.g. no memory to rank, or AutoDev returned no telemetry) — in which case the
    comparison is invalid and must not be claimed.
    """
    for arm_ids in injected.values():
        if len({ids for ids in arm_ids.values()}) > 1:
            return True
    return False


def run_execution_impact_real(
    adapter: AutoDevExecutionImpactAdapter,
    cases: list,
    *,
    context_for=None,
    gold_for=None,
    before_each=None,
    trials: int = 1,
    experiment: str = "salience-memory-execution-impact",
    notes: list[str] | None = None,
) -> ExecutionImpactResult:
    """Run the three arms over real issue-backed ``cases`` via real AutoDev.

    ``context_for(arm, case)`` returns the (ContextPackage, retrieval-metrics dict)
    for an arm; if omitted, no context is sent (arm is provenance only).
    ``gold_for(case)`` returns the task's gold (``relevant_ids``/``target_id``/
    ``contradictory_ids``) so real retrieval metrics can be computed from what the
    run actually retrieved. Produces an ``evidential=True`` result iff a real agent
    was actually invoked.
    """
    arms = retrieval_arms()
    per_arm: dict[str, list[SampleRecord]] = {a.name: [] for a in arms}
    agent_invoked_any = False
    # per (case, trial) -> {arm -> tuple of retrieved memory ids}, for the gate
    injected: dict[tuple, dict[str, tuple]] = {}

    for arm in arms:
        for case in cases:
            for trial in range(trials):
                # Restore the controlled memory set before each run so every arm
                # retrieves from an identical store (AutoDev writes run summaries
                # back after a run, which would otherwise pollute later arms).
                if before_each is not None:
                    before_each(arm, case, trial)
                context, retrieval = (None, None)
                if context_for is not None:
                    context, retrieval = context_for(arm, case)
                gold = gold_for(case) if gold_for is not None else None
                outcome = adapter.run_sample(arm, case, context, trial,
                                             retrieval=retrieval, gold=gold)
                agent_invoked_any = agent_invoked_any or outcome.agent_invoked
                per_arm[arm.name].append(outcome.record)
                injected.setdefault((case.id, trial), {})[arm.name] = \
                    outcome.record.injected_context_ids

    arms_distinct = _arms_distinct(injected)

    baseline = next(a for a in arms if a.baseline)
    base_success = [1.0 if r.success else 0.0 for r in per_arm[baseline.name]]
    base_revq = [r.review_quality for r in per_arm[baseline.name]]

    arm_metrics, failure_breakdown = [], {}
    for arm in arms:
        recs = per_arm[arm.name]
        m = _aggregate(arm, recs)
        if not arm.baseline and recs:
            m.success_delta = _paired([1.0 if r.success else 0.0 for r in recs], base_success, seed=7)
            m.review_quality_delta = _paired([r.review_quality for r in recs], base_revq, seed=8)
        arm_metrics.append(m)
        counts: dict[str, int] = {}
        for r in recs:
            if r.failure_class:
                counts[r.failure_class] = counts.get(r.failure_class, 0) + 1
        failure_breakdown[arm.name] = counts

    all_recs = [r for arm in arms for r in per_arm[arm.name]]
    return ExecutionImpactResult(
        experiment=experiment,
        execution_real=True,
        evidential=agent_invoked_any,  # only real agent invocation is evidence
        n_tasks=len(cases),
        trials=trials,
        arms=arm_metrics,
        correlations=retrieval_execution_correlation(all_recs) if all_recs else [],
        failure_breakdown=failure_breakdown,
        failure_examples=[],
        dry_run=adapter.dry_run,
        arms_distinct=arms_distinct,
        # a valid A/B/C comparison needs BOTH a real agent run AND demonstrably
        # different injected contexts across arms (Phase 3).
        valid_comparison=bool(agent_invoked_any and arms_distinct),
        notes=notes or [],
        outcome_model=None,
    )


# --- persistence + rendering ---------------------------------------------- #


def save_result(result: ExecutionImpactResult, results_dir: Path | None = None) -> Path:
    directory = results_dir or RESULTS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{result.experiment}.json"
    path.write_text(json.dumps(asdict(result), indent=2, default=str))
    return path


def _dp(p: Paired | None) -> str:
    if p is None:
        return "—"
    return f"{p.mean_delta:+.3f} [{p.ci_low:+.3f}, {p.ci_high:+.3f}]"


def render_report(result: ExecutionImpactResult) -> str:
    status = ("REAL AUTODEV EXECUTION" if result.execution_real
              else "SIMULATION — NOT EVIDENCE (outcome is a stated function of retrieval)")
    lines = [
        f"# {result.experiment} — Results",
        "",
        f"**Execution:** {status}  ",
        f"**Evidential:** {result.evidential}  "
        + (f"**Dry run:** {result.dry_run}  " if result.execution_real else ""),
        f"**Tasks:** {result.n_tasks}  **Trials:** {result.trials}",
        "",
    ]
    if result.execution_real:
        lines += [
            f"**Arms injected distinct contexts (Phase-3 gate):** {result.arms_distinct}  ",
            f"**Valid A/B/C comparison:** {result.valid_comparison}  ",
            "",
        ]
        if not result.valid_comparison:
            lines += [
                "> ⚠️ The arms did not demonstrably inject different contexts (or no "
                "real agent ran). Per Phase 3, the A/B/C comparison is **not claimed**.",
                "",
            ]
    if not result.execution_real:
        lines += [
            "> ⚠️ **This run is a simulation, not evidence.** Real AutoDev was not "
            "available, so outcomes come from a stated outcome model in which success "
            "is *defined* to rise with retrieval relevance and fall under retrieved "
            "contradictions. It validates the harness and shows what the analysis "
            "would report — it cannot confirm that retrieval helps execution. Run "
            "against real AutoDev (`MARS_AUTODEV_MCP_*`) for evidence.",
            "",
        ]
    # execution + retrieval table
    lines += [
        "| arm | success | Δ success (95% CI) | review_pass | review_quality | contra_fail | runtime_s | tokens | recall@5 | MRR |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for m in result.arms:
        lines.append(
            f"| `{m.arm}` | {m.task_success_rate:.3f} | {_dp(m.success_delta)} "
            f"| {m.review_pass_rate:.3f} | {m.review_quality:.3f} "
            f"| {m.contradiction_failure_rate:.3f} | {m.runtime_s:.1f} | {m.token_usage:.0f} "
            f"| {m.recall_at_k:.3f} | {m.mrr:.3f} |"
        )
    lines += ["", "## Retrieval → Execution correlation (per-sample)", "",
              "| retrieval metric | vs | Pearson | Spearman | n |",
              "| --- | --- | --- | --- | --- |"]
    for c in result.correlations:
        lines.append(f"| {c.metric_x} | {c.metric_y} | {c.pearson:+.3f} | {c.spearman:+.3f} | {c.n} |")

    lines += ["", "## Failure breakdown (count by class)", "",
              "| arm | " + " | ".join(FAILURE_CLASSES) + " |",
              "| --- |" + " --- |" * len(FAILURE_CLASSES)]
    for m in result.arms:
        fb = result.failure_breakdown.get(m.arm, {})
        lines.append(f"| `{m.arm}` | " + " | ".join(str(fb.get(fc, 0)) for fc in FAILURE_CLASSES) + " |")

    if result.notes:
        lines += ["", "## Notes", ""] + [f"- {n}" for n in result.notes]
    return "\n".join(lines)
