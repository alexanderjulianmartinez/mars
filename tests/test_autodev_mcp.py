"""Tests for the MCP-backed AutoDev provider.

No live MCP server is required: a FakeToolCaller stands in for the transport so
the request-shaping and response-mapping logic is fully exercised. The real
MCPToolCaller transport is isolated and not invoked here.
"""

import pytest

from mars.agents import make_autodev, using_real_autodev
from mars.models import AgentRunStatus
from mars.providers.autodev_mcp import AutoDevMCPProvider, config_from_env
from mars.providers.mcp_client import MCPServerConfig, _result_to_dict
from mars.providers.mock import MockAutoDevProvider


class FakeToolCaller:
    """Records calls and returns canned responses keyed by tool name."""

    def __init__(self, responses: dict[str, dict]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []
        self.closed = False

    def call_tool(self, name: str, arguments: dict) -> dict:
        self.calls.append((name, arguments))
        return self.responses.get(name, {})

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_caller():
    return FakeToolCaller(
        {
            "create_workspace": {"workspace_id": "ws-real-1", "path": "/work/x"},
            "run_agent": {
                "agent_run_id": "agent-real-1",
                "status": "success",
                "logs": "did the thing",
                "diff": "--- a\n+++ b\n+x\n",
                "runtime_ms": 8123,
                "cost_usd": 0.037,
                "files_changed": ["src/x.py", "tests/x_test.py"],
            },
            "run_tests": {
                "test_results": [
                    {"name": "pytest", "passed": True, "duration_ms": 410, "output": "ok"}
                ]
            },
            "capture_diff": {"diff": "DIFF"},
            "cleanup_workspace": {"ok": True},
        }
    )


def test_full_lifecycle_maps_to_domain(case, fake_caller):
    provider = AutoDevMCPProvider(fake_caller, agent="claude-code", model="claude-opus")

    ws = provider.create_workspace(case, None)
    assert ws.id == "ws-real-1" and ws.path == "/work/x"

    run = provider.run_agent(ws, case, None)
    assert run.id == "agent-real-1"
    assert run.status == AgentRunStatus.SUCCESS
    assert run.runtime_ms == 8123
    assert run.cost_usd == 0.037
    assert run.files_changed == ["src/x.py", "tests/x_test.py"]

    tests = provider.run_tests(ws, case)
    assert tests.status == AgentRunStatus.SUCCESS  # inferred from passing results
    assert tests.test_results[0].name == "pytest"
    assert tests.test_results[0].passed is True

    assert provider.capture_diff(ws) == "DIFF"
    provider.cleanup_workspace(ws)
    provider.close()
    assert fake_caller.closed

    # Request shaping: correct tools called with the case's data.
    names = [c[0] for c in fake_caller.calls]
    assert names == [
        "create_workspace",
        "run_agent",
        "run_tests",
        "capture_diff",
        "cleanup_workspace",
    ]
    run_agent_args = fake_caller.calls[1][1]
    assert run_agent_args["workspace_id"] == "ws-real-1"
    assert run_agent_args["task_prompt"] == case.task_prompt


def test_run_tests_status_inferred_when_absent(case):
    caller = FakeToolCaller(
        {"run_tests": {"test_results": [{"name": "t", "passed": False}]}}
    )
    provider = AutoDevMCPProvider(caller)
    result = provider.run_tests(provider.create_workspace(case, None), case)
    assert result.status == AgentRunStatus.FAILURE


def test_unknown_status_maps_to_error(case):
    caller = FakeToolCaller({"run_agent": {"status": "weird"}})
    provider = AutoDevMCPProvider(caller)
    run = provider.run_agent(provider.create_workspace(case, None), case, None)
    assert run.status == AgentRunStatus.ERROR


def test_custom_tool_names_are_used(case):
    caller = FakeToolCaller({"autodev.create_workspace": {"workspace_id": "ns-1"}})
    provider = AutoDevMCPProvider(
        caller, tool_names={"create_workspace": "autodev.create_workspace"}
    )
    ws = provider.create_workspace(case, None)
    assert ws.id == "ns-1"
    assert caller.calls[0][0] == "autodev.create_workspace"


def test_works_through_eval_runner(case, repo):
    from mars.engine.runner import EvalRunner
    from mars.providers.mock import MockCortexProvider

    caller = FakeToolCaller(
        {
            "create_workspace": {"workspace_id": "w"},
            "run_agent": {
                "status": "success",
                "diff": "d",
                "runtime_ms": 1000,
                "cost_usd": 0.01,
                "files_changed": ["a.py"],
            },
            "run_tests": {"test_results": [{"name": "pytest", "passed": True}]},
            "cleanup_workspace": {},
        }
    )
    provider = AutoDevMCPProvider(caller)
    runner = EvalRunner(MockCortexProvider(), provider, repository=repo)
    result = runner.run_case(case)
    assert result.status.value == "passed"


# -- config / env ----------------------------------------------------------- #


def test_config_requires_a_transport():
    with pytest.raises(ValueError):
        MCPServerConfig()


def test_config_from_env_none_when_unset(monkeypatch):
    monkeypatch.delenv("MARS_AUTODEV_MCP_URL", raising=False)
    monkeypatch.delenv("MARS_AUTODEV_MCP_COMMAND", raising=False)
    assert config_from_env() is None
    assert AutoDevMCPProvider.from_env() is None


def test_config_from_env_http(monkeypatch):
    monkeypatch.setenv("MARS_AUTODEV_MCP_URL", "http://localhost:9000/mcp")
    monkeypatch.delenv("MARS_AUTODEV_MCP_COMMAND", raising=False)
    config = config_from_env()
    assert config is not None and config.url.endswith("/mcp")


def test_make_autodev_falls_back_to_mock(monkeypatch):
    monkeypatch.delenv("MARS_AUTODEV_MCP_URL", raising=False)
    monkeypatch.delenv("MARS_AUTODEV_MCP_COMMAND", raising=False)
    assert not using_real_autodev()
    assert isinstance(make_autodev("claude-code"), MockAutoDevProvider)


# -- response normalization ------------------------------------------------- #


class _Block:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Result:
    def __init__(self, content=None, structured=None, is_error=False):
        self.content = content or []
        self.structuredContent = structured
        self.isError = is_error


def test_result_prefers_structured_content():
    r = _Result(structured={"workspace_id": "s1"})
    assert _result_to_dict(r) == {"workspace_id": "s1"}


def test_result_parses_json_text():
    r = _Result(content=[_Block('{"diff": "abc"}')])
    assert _result_to_dict(r) == {"diff": "abc"}


def test_result_raises_on_error():
    with pytest.raises(RuntimeError):
        _result_to_dict(_Result(content=[_Block("boom")], is_error=True))
