from mars.engine import EvalRunner, detect_regression
from mars.models import EvalRun, EvalStatus
from mars.providers import MockAutoDevProvider, MockCortexProvider
from mars.suites import load_suite


def _runner(quality, repo=None, agent="x"):
    return EvalRunner(
        MockCortexProvider(),
        MockAutoDevProvider(agent=agent, quality=quality),
        repository=repo,
    )


def test_runner_passes_on_good_agent(case):
    result = _runner(1.0).run_case(case)
    assert result.status == EvalStatus.PASSED
    assert result.score > 0
    assert result.criteria_met["tests_pass"] is True


def test_runner_fails_on_bad_agent(case):
    result = _runner(0.0).run_case(case)
    assert result.status == EvalStatus.FAILED
    assert result.failure_reason


def test_runner_persists_and_roundtrips(case, repo):
    result = _runner(1.0, repo=repo).run_case(case)
    fetched = repo.get_eval_run(result.id)
    assert fetched == result
    assert repo.get_agent_run(result.agent_run_id) is not None
    assert repo.get_context_package(result.context_package_id) is not None


def test_repository_filters_and_baseline(case, repo):
    runner = _runner(1.0, repo=repo, agent="x")
    first = runner.run_case(case)
    second = runner.run_case(case)
    runs = repo.list_eval_runs(suite_id=case.suite_id, case_id=case.id, agent="x")
    assert len(runs) == 2
    # latest excluding `second` should be `first`.
    baseline = repo.latest_eval_run(
        suite_id=case.suite_id, case_id=case.id, agent="x", before=second.id
    )
    assert baseline.id == first.id


def test_run_suite_covers_all_cases():
    suite = load_suite("backend-api")
    results = _runner(1.0).run_suite(suite.cases)
    assert len(results) == len(suite.cases)


def test_regression_none_baseline_is_clean():
    current = EvalRun(id="e", suite_id="s", case_id="c", agent_run_id="a", agent="x", model="m", score=90)
    assert detect_regression(current, None).has_regression is False


def test_regression_detects_score_and_status_drop():
    baseline = EvalRun(
        id="b", suite_id="s", case_id="c", agent_run_id="a", agent="x", model="m",
        score=95, status=EvalStatus.PASSED, duration_ms=1000, cost_usd=0.04,
    )
    current = EvalRun(
        id="e", suite_id="s", case_id="c", agent_run_id="a2", agent="x", model="m",
        score=60, status=EvalStatus.FAILED, duration_ms=5000, cost_usd=0.20,
    )
    report = detect_regression(current, baseline)
    assert report.has_regression
    assert any("score regression" in w for w in report.warnings)
    assert any("status regression" in w for w in report.warnings)
    assert any("runtime regression" in w for w in report.warnings)
    assert any("cost regression" in w for w in report.warnings)
