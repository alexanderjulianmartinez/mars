import pytest

from mars.models import AgentRun, AgentRunStatus, EvalCase, SuccessCriterion, TestResult
from mars.storage.db import Database
from mars.storage.repository import Repository


@pytest.fixture
def case() -> EvalCase:
    return EvalCase(
        id="add-health-endpoint",
        suite_id="backend-api",
        name="Add health endpoint",
        task_prompt="Add /health",
        context_profile="backend",
        test_commands=["pytest tests/test_health.py"],
        success_criteria=[
            SuccessCriterion.TESTS_PASS,
            SuccessCriterion.NO_UNRELATED_CHANGES,
        ],
        timeout_seconds=600,
    )


@pytest.fixture
def passing_run() -> AgentRun:
    return AgentRun(
        id="agent-1",
        agent="claude-code",
        model="claude-opus",
        status=AgentRunStatus.SUCCESS,
        diff="--- a/x\n+++ b/x\n+pass\n",
        runtime_ms=5000,
        cost_usd=0.04,
        files_changed=["src/health.py", "tests/test_health.py"],
        test_results=[TestResult(name="pytest", passed=True, duration_ms=300)],
    )


@pytest.fixture
def repo() -> Repository:
    return Repository(Database("sqlite:///:memory:"))
