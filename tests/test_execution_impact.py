"""Experiment 5 — Execution Impact harness: arms, orchestration, metrics, honesty."""

from __future__ import annotations

import json
from dataclasses import asdict

from mars.memory.execution_impact import (
    FAILURE_CLASSES,
    SampleRecord,
    SimulatedOutcomeModel,
    TaskClass,
    _pearson,
    _retrieve,
    _spearman,
    build_internal_benchmark,
    classify_failure,
    render_report,
    retrieval_arms,
    retrieval_execution_correlation,
    run_execution_impact,
    save_result,
)


# --- arm selection --------------------------------------------------------- #


def test_three_arms_with_single_baseline():
    arms = retrieval_arms()
    assert [a.name for a in arms] == ["A_similarity_only", "B_sim_importance", "C_salience_v2"]
    assert sum(1 for a in arms if a.baseline) == 1
    assert arms[0].baseline


def test_arms_rank_differently_on_adversarial_pool():
    # On a task where the target has lower similarity but higher importance, the
    # similarity arm buries the target while the importance/salience arms surface it.
    task = build_internal_benchmark(n_per_class=1)[0]
    arms = {a.name: a for a in retrieval_arms()}
    a = _retrieve(task, arms["A_similarity_only"])
    b = _retrieve(task, arms["B_sim_importance"])
    assert b["recall_at_k"] >= a["recall_at_k"]
    assert b["target_found"] and not a["target_found"]


def test_salience_v2_gates_out_contradiction():
    # On a contradiction task the obsolete memory is important + high-similarity but
    # low-confidence: arm B (no confidence) lets it into context, arm C gates it out.
    contra = next(t for t in build_internal_benchmark() if t.task_class is TaskClass.CONTRADICTION)
    arms = {a.name: a for a in retrieval_arms()}
    b = _retrieve(contra, arms["B_sim_importance"])
    c = _retrieve(contra, arms["C_salience_v2"])
    assert b["contradiction_in_context"]
    assert not c["contradiction_in_context"]


# --- benchmark ------------------------------------------------------------- #


def test_benchmark_has_all_classes_and_only_contradiction_has_obsolete():
    tasks = build_internal_benchmark(n_per_class=4)
    assert len(tasks) == 12
    by_class = {tc: [t for t in tasks if t.task_class is tc] for tc in TaskClass}
    assert all(len(v) == 4 for v in by_class.values())
    for t in tasks:
        if t.task_class is TaskClass.CONTRADICTION:
            assert t.contradictory_ids
        else:
            assert not t.contradictory_ids


# --- outcome model + orchestration ----------------------------------------- #


def test_outcome_luck_is_arm_independent_paired():
    model = SimulatedOutcomeModel()
    task = build_internal_benchmark(n_per_class=1)[0]
    # Same relevance + no contradiction → identical success across arm labels
    # (luck depends only on task+trial).
    a = model.run(task, "A", 0, relevance=0.8, contradiction_in_context=False)
    b = model.run(task, "B", 0, relevance=0.8, contradiction_in_context=False)
    assert a["success"] == b["success"]


def test_orchestration_runs_all_arms_and_is_deterministic():
    tasks = build_internal_benchmark(n_per_class=3)
    a = run_execution_impact(tasks, trials=4)
    b = run_execution_impact(tasks, trials=4)
    assert len(a.arms) == 3
    assert [m.task_success_rate for m in a.arms] == [m.task_success_rate for m in b.arms]
    assert a.arms[0].n == len(tasks) * 4


def test_simulation_is_flagged_non_evidential():
    res = run_execution_impact(build_internal_benchmark(n_per_class=2), trials=2)
    assert res.execution_real is False
    assert res.evidential is False
    assert res.outcome_model is not None  # the stated model is recorded


# --- metric aggregation ---------------------------------------------------- #


def test_paired_success_delta_present_for_non_baseline_only():
    res = run_execution_impact(build_internal_benchmark(n_per_class=4), trials=4)
    baseline = next(m for m in res.arms if m.baseline)
    others = [m for m in res.arms if not m.baseline]
    assert baseline.success_delta is None
    assert all(m.success_delta is not None for m in others)


def test_contradiction_failure_rate_drops_with_salience_v2():
    res = run_execution_impact(build_internal_benchmark(n_per_class=8), trials=6)
    by = {m.arm: m for m in res.arms}
    # Gating out obsolete memories should reduce contradiction failures vs the
    # importance arm that retrieves them.
    assert by["C_salience_v2"].contradiction_failure_rate <= by["B_sim_importance"].contradiction_failure_rate


# --- correlation ----------------------------------------------------------- #


def test_pearson_spearman_basic():
    assert _pearson([1, 2, 3], [1, 2, 3]) == 1.0
    assert _pearson([1, 2, 3], [3, 2, 1]) == -1.0
    assert _spearman([1, 2, 3, 4], [1, 4, 9, 16]) == 1.0  # monotonic, non-linear


def test_correlation_reports_all_metrics():
    res = run_execution_impact(build_internal_benchmark(n_per_class=4), trials=4)
    names = {c.metric_x for c in res.correlations}
    assert {"recall_at_k", "mrr", "target_found", "context_efficiency"} <= names
    assert all(c.metric_y == "task_success" for c in res.correlations)


# --- failure classification ------------------------------------------------ #


def _rec(**kw) -> SampleRecord:
    base = dict(
        task_id="t", task_class="contradiction", arm="A", trial=0, recall_at_k=1.0, mrr=1.0,
        target_found=True, contradiction_in_context=False, context_efficiency=0.6, context_size=5,
        success=False, acceptance_pass_rate=0.0, review_pass=False, validation_pass=False,
        diff_quality=0.3, review_quality=0.3, focused_diff=False, runtime_s=90.0, token_usage=5000,
    )
    base.update(kw)
    return SampleRecord(**base)


def test_classify_failure_precedence():
    assert classify_failure(_rec(success=True)) is None
    assert classify_failure(_rec(contradiction_in_context=True)) == "contradiction_retrieval"
    assert classify_failure(_rec(target_found=False)) == "retrieval_failure"
    assert classify_failure(_rec(recall_at_k=0.2)) == "planning_failure"
    # good retrieval but still failed → a downstream stage
    cls = classify_failure(_rec(recall_at_k=1.0, target_found=True))
    assert cls in ("implementation_failure", "validation_failure", "review_failure")


def test_failure_classes_are_known():
    res = run_execution_impact(build_internal_benchmark(n_per_class=6), trials=5)
    for arm, counts in res.failure_breakdown.items():
        assert set(counts).issubset(set(FAILURE_CLASSES))


# --- report + serialization ------------------------------------------------ #


def test_report_warns_simulation_and_lists_arms():
    res = run_execution_impact(build_internal_benchmark(n_per_class=3), trials=3)
    report = render_report(res)
    assert "SIMULATION" in report and "NOT EVIDENCE" in report.upper()
    for arm in ("A_similarity_only", "B_sim_importance", "C_salience_v2"):
        assert arm in report
    assert "correlation" in report.lower()


def test_result_json_schema(tmp_path):
    res = run_execution_impact(build_internal_benchmark(n_per_class=3), trials=3)
    path = save_result(res, results_dir=tmp_path)
    data = json.loads(path.read_text())
    assert data["experiment"] == "salience-memory-execution-impact"
    assert data["execution_real"] is False and data["evidential"] is False
    assert len(data["arms"]) == 3
    assert "correlations" in data and "failure_breakdown" in data
    assert {"arm", "task_success_rate", "recall_at_k", "contradiction_failure_rate"} <= set(data["arms"][0])
    assert asdict(res)["n_tasks"] == data["n_tasks"]
