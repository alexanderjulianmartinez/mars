from mars.models import AgentRun, AgentRunStatus, TestResult
from mars.scoring import (
    CostScorer,
    DiffScorer,
    RuntimeScorer,
    TestPassScorer,
    default_composite,
)
from mars.scoring.composite import CompositeScorer


def test_test_pass_scorer_fraction(case):
    run = AgentRun(
        id="r",
        agent="a",
        model="m",
        status=AgentRunStatus.SUCCESS,
        test_results=[
            TestResult(name="t1", passed=True),
            TestResult(name="t2", passed=False),
        ],
    )
    assert TestPassScorer().score(case, run).value == 50.0


def test_test_pass_scorer_no_tests_is_zero(case, passing_run):
    passing_run.test_results = []
    assert TestPassScorer().score(case, passing_run).value == 0.0


def test_runtime_scorer_under_budget_is_full(case, passing_run):
    # budget = 600s * 0.5 = 300_000ms; 5000ms is well under.
    assert RuntimeScorer().score(case, passing_run).value == 100.0


def test_runtime_scorer_decays_over_budget(case, passing_run):
    passing_run.runtime_ms = case.timeout_seconds * 1000  # 2x the default budget
    assert RuntimeScorer().score(case, passing_run).value == 0.0


def test_cost_scorer_budget(case, passing_run):
    assert CostScorer(budget_usd=0.10).score(case, passing_run).value == 100.0
    passing_run.cost_usd = 0.20
    assert CostScorer(budget_usd=0.10).score(case, passing_run).value == 0.0


def test_diff_scorer_focus_vs_sprawl(case, passing_run):
    assert DiffScorer(focus_files=3).score(case, passing_run).value == 100.0
    passing_run.files_changed = [f"f{i}.py" for i in range(9)]
    assert DiffScorer(focus_files=3).score(case, passing_run).value == 0.0


def test_diff_scorer_no_diff_is_zero(case):
    failed = AgentRun(id="r", agent="a", model="m", status=AgentRunStatus.FAILURE, diff="")
    assert DiffScorer().score(case, failed).value == 0.0


def test_composite_is_weighted_and_bounded(case, passing_run):
    result = default_composite().score(case, passing_run)
    assert 0.0 <= result.score <= 100.0
    assert abs(sum(c.weight for c in result.components) - 1.0) < 1e-6
    # All sub-scores are 100 here, so composite must be 100.
    assert result.score == 100.0


def test_composite_rejects_empty():
    try:
        CompositeScorer([])
    except ValueError:
        return
    raise AssertionError("expected ValueError")
