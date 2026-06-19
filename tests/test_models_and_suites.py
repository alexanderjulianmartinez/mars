from mars.models import EvalSuite, SuccessCriterion
from mars.suites import DEFAULT_SUITES_DIR, load_suite, load_suites


def test_bundled_suites_load():
    suites = load_suites()
    assert {"backend-api", "infra"} <= set(suites)
    backend = suites["backend-api"]
    assert isinstance(backend, EvalSuite)
    assert any(c.id == "add-health-endpoint" for c in backend.cases)


def test_loader_injects_suite_id():
    suite = load_suite("backend-api")
    for c in suite.cases:
        assert c.suite_id == "backend-api"


def test_success_criteria_parsed_as_enum():
    suite = load_suite("backend-api")
    case = suite.case("add-health-endpoint")
    assert SuccessCriterion.TESTS_PASS in case.success_criteria


def test_suite_case_lookup_raises_for_unknown():
    suite = load_suite("infra")
    try:
        suite.case("nope")
    except KeyError:
        return
    raise AssertionError("expected KeyError")


def test_suites_dir_exists():
    assert DEFAULT_SUITES_DIR.is_dir()
