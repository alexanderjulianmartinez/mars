from typer.testing import CliRunner

from mars.apollo import ExperimentRunner, compare_arms, get_experiment, list_experiments
from mars.apollo.hooks import PolicyHook
from mars.cli import app
from mars.memory.retrieval import SimilarityOnlyStrategy
from mars.providers.memory_mock import (
    MemoryAwareAutoDevProvider,
    MemoryAwareCortexProvider,
)
from mars.suites import load_suite

runner = CliRunner()


def _fast_experiment(trials=8):
    exp = get_experiment("salience-memory")
    exp.trials = trials
    return exp


def test_registry_lists_salience_memory():
    ids = [e.id for e in list_experiments()]
    assert "salience-memory" in ids


def test_cortex_reports_relevance_per_case():
    cortex = MemoryAwareCortexProvider(SimilarityOnlyStrategy(), k=5)
    case = load_suite("backend-api").cases[0]
    pkg = cortex.get_context_for_case(case)
    assert "relevance" in pkg.metadata
    assert 0.0 <= pkg.metadata["relevance"] <= 1.0
    assert cortex.last_relevance == pkg.metadata["relevance"]


def test_autodev_success_tracks_relevance():
    case = load_suite("backend-api").cases[0]
    autodev = MemoryAwareAutoDevProvider(base_quality=1.0, floor=0.0)
    # Build contexts with low vs high relevance and count successes across trials.
    from mars.models import ContextPackage

    def successes(relevance):
        count = 0
        for t in range(40):
            autodev.trial = t
            ctx = ContextPackage(id="c", profile="p", version="v", metadata={"relevance": relevance})
            ws = autodev.create_workspace(case, ctx)
            if autodev.run_agent(ws, case, ctx).status.value == "success":
                count += 1
        return count

    assert successes(1.0) > successes(0.2)


def test_paired_comparison_detects_improvement():
    base = [50.0] * 40
    exp = [70.0] * 40
    cmp = compare_arms("base", base, "exp", exp, seed=1)
    assert cmp.significant
    assert cmp.mean_delta == 20.0
    assert "outperforms" in cmp.verdict
    assert cmp.ci_low > 0


def test_paired_comparison_no_difference():
    base = [50.0, 60.0, 55.0, 52.0] * 10
    exp = list(base)
    cmp = compare_arms("base", base, "exp", exp, seed=1)
    assert not cmp.significant
    assert cmp.verdict == "no significant difference"


def test_experiment_run_salience_beats_baseline():
    result = ExperimentRunner().run(_fast_experiment(trials=12))
    arms = {a.name: a for a in result.arms}
    assert arms["salience-weighted"].mean_relevance > arms["baseline-similarity"].mean_relevance
    cmp = result.comparisons[0]
    assert cmp.mean_delta > 0
    assert cmp.significant


def test_arm_vectors_are_paired_and_aligned():
    result = ExperimentRunner().run(_fast_experiment(trials=5))
    base, exp = result.arms
    assert base.sample_keys == exp.sample_keys
    assert base.n == exp.n


def test_policy_hook_invoked():
    calls = {"before": 0, "after": 0, "complete": 0}

    class CountingHook(PolicyHook):
        def before_run(self, *a):
            calls["before"] += 1

        def after_run(self, *a):
            calls["after"] += 1

        def on_experiment_complete(self, *a):
            calls["complete"] += 1

    ExperimentRunner(hook=CountingHook()).run(_fast_experiment(trials=3))
    assert calls["before"] == calls["after"] > 0
    assert calls["complete"] == 1


def test_cli_list_experiments():
    res = runner.invoke(app, ["list-experiments"])
    assert res.exit_code == 0
    assert "salience-memory" in res.stdout


def test_cli_experiment_run():
    res = runner.invoke(app, ["experiment", "--experiment", "salience-memory", "--trials", "6"])
    assert res.exit_code == 0, res.stdout
    assert "Verdict:" in res.stdout
    assert "salience-weighted" in res.stdout
