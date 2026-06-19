from mars.models import AgentRunStatus
from mars.providers import MockAutoDevProvider, MockCortexProvider


def test_cortex_lists_and_returns_context():
    cortex = MockCortexProvider()
    assert "backend" in cortex.list_profiles()
    pkg = cortex.get_context_package("backend")
    assert pkg.profile == "backend"
    assert pkg.metadata["files_indexed"] > 0


def test_cortex_is_deterministic():
    a = MockCortexProvider().get_context_package("backend")
    b = MockCortexProvider().get_context_package("backend")
    assert a.id == b.id


def test_autodev_high_quality_succeeds_more(case):
    good = MockAutoDevProvider(agent="good", quality=1.0)
    bad = MockAutoDevProvider(agent="bad", quality=0.0)
    ws_g = good.create_workspace(case, None)
    ws_b = bad.create_workspace(case, None)
    assert good.run_agent(ws_g, case, None).status == AgentRunStatus.SUCCESS
    assert bad.run_agent(ws_b, case, None).status == AgentRunStatus.FAILURE


def test_autodev_is_reproducible(case):
    p = MockAutoDevProvider(agent="x", quality=1.0)
    ws = p.create_workspace(case, None)
    r1 = p.run_agent(ws, case, None)
    r2 = p.run_agent(ws, case, None)
    # Same seed inputs -> same runtime/cost/files (ids differ by design).
    assert r1.runtime_ms == r2.runtime_ms
    assert r1.cost_usd == r2.cost_usd
    assert r1.files_changed == r2.files_changed


def test_autodev_tests_track_quality(case):
    p = MockAutoDevProvider(agent="x", quality=1.0)
    ws = p.create_workspace(case, None)
    tests = p.run_tests(ws, case)
    assert tests.test_results and all(t.passed for t in tests.test_results)
