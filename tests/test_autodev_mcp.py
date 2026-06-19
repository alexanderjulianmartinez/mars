"""Tests for the real-contract AutoDev MCP provider.

No live server: a FakeToolCaller returns canned responses shaped like the real
AutoDev tools (verified against the live server), so request-shaping and the
response→domain mapping are fully exercised, including envelope unwrapping and
get_run polling.
"""

import pytest

from mars.agents import make_autodev, using_real_autodev
from mars.models import AgentRunStatus, EvalCase
from mars.providers.autodev_mcp import AutoDevMCPProvider, config_from_env
from mars.providers.mcp_client import MCPServerConfig
from mars.providers.mock import MockAutoDevProvider


def env(data=None, *, ok=True, error=None):
    """Wrap a payload in AutoDev's {ok, data, error} envelope."""
    return {"ok": ok, "data": data or {}, "error": error}


class FakeToolCaller:
    """Returns queued responses per tool name; records calls."""

    def __init__(self, responses: dict) -> None:
        # value may be a single response or a list consumed in order.
        self.responses = {k: (v if isinstance(v, list) else [v]) for k, v in responses.items()}
        self.calls: list[tuple[str, dict]] = []
        self.closed = False

    def call_tool(self, name: str, arguments: dict):
        self.calls.append((name, arguments))
        queue = self.responses.get(name) or [env({})]
        return queue.pop(0) if len(queue) > 1 else queue[0]

    def close(self):
        self.closed = True

    def names(self):
        return [c[0] for c in self.calls]


@pytest.fixture
def issue_case():
    return EvalCase(
        id="add-health-endpoint",
        suite_id="backend-api",
        name="Add health endpoint",
        task_prompt="Add /health",
        issue_url="https://github.com/acme/repo/issues/42",
        test_commands=["pytest -q"],
    )


def _terminal_get_run(diff_path=None, *, status="completed", files=("mars/x.py",), inline_diff=None):
    run_meta = {}
    if diff_path is not None:
        run_meta["implementation_diff_path"] = str(diff_path)
    data = {
        "run": {
            "run_id": "run-abc",
            "status": status,
            "started_at": "2026-06-19T17:00:00Z",
            "completed_at": "2026-06-19T17:05:00Z",
            "metadata": run_meta,
        },
        "validation_results": [
            {"commands": [{"command": "pytest", "exit_code": 0, "status": "passed",
                           "duration_seconds": 0.3, "stdout": "ok"}], "passed": True}
        ],
        "review_results": [{"decision": "approved", "metadata": {"files_modified": list(files)}}],
    }
    if inline_diff is not None:
        data["diff"] = inline_diff
    return env(data)


# -- agentic flow ----------------------------------------------------------- #


def test_agentic_run_agent_starts_polls_and_maps(issue_case, tmp_path):
    diff_file = tmp_path / "impl.diff"
    diff_file.write_text("--- a/mars/x.py\n+++ b/mars/x.py\n+pass\n")
    caller = FakeToolCaller(
        {
            "autodev_start_run": env({"run_id": "run-abc", "status": "running"}),
            # poll: running, then terminal
            "autodev_get_run": [env({"run": {"run_id": "run-abc", "status": "running"}}),
                                _terminal_get_run(diff_path=diff_file)],
        }
    )
    p = AutoDevMCPProvider(caller, poll_interval_s=0)
    ws = p.create_workspace(issue_case, None)
    assert ws.id.startswith("pending-")  # start_run owns provisioning

    run = p.run_agent(ws, issue_case, None)
    assert run.id == "run-abc"
    assert run.status == AgentRunStatus.SUCCESS
    assert run.runtime_ms == 5 * 60 * 1000  # 5 minutes from timestamps
    assert run.files_changed == ["mars/x.py"]
    assert "pass" in run.diff
    assert ws.metadata["run_id"] == "run-abc"

    # start_run got the issue url + dry_run; get_run polled twice.
    start_args = caller.calls[0][1]
    assert start_args["issue_url"] == issue_case.issue_url
    assert start_args["dry_run"] is True
    assert caller.names() == ["autodev_start_run", "autodev_get_run", "autodev_get_run"]


def test_run_tests_calls_validate_and_maps(issue_case):
    caller = FakeToolCaller(
        {
            "autodev_validate": env(
                {"commands": [
                    {"command": "pytest -q", "exit_code": 0, "status": "passed",
                     "duration_seconds": 0.5, "stdout": "4 passed"},
                ], "passed": True}
            )
        }
    )
    p = AutoDevMCPProvider(caller)
    ws = p.create_workspace(issue_case, None)
    ws.metadata["run_id"] = "run-abc"
    result = p.run_tests(ws, issue_case)
    assert result.status == AgentRunStatus.SUCCESS
    assert result.test_results[0].name == "pytest -q"
    assert result.test_results[0].duration_ms == 500
    args = caller.calls[0][1]
    assert args["run_id"] == "run-abc"
    assert args["commands"] == ["pytest -q"]
    assert args["stop_on_first_failure"] is False


def test_run_tests_failure_when_command_fails(issue_case):
    caller = FakeToolCaller(
        {"autodev_validate": env({"commands": [
            {"command": "pytest", "exit_code": 1, "status": "failed", "stderr": "boom"}], "passed": False})}
    )
    p = AutoDevMCPProvider(caller)
    ws = p.create_workspace(issue_case, None)
    ws.metadata["run_id"] = "r"
    assert p.run_tests(ws, issue_case).status == AgentRunStatus.FAILURE


def test_agentic_requires_issue_url():
    case = EvalCase(id="c", suite_id="s", name="c", task_prompt="x")  # no issue_url
    p = AutoDevMCPProvider(FakeToolCaller({}))
    ws = p.create_workspace(case, None)
    with pytest.raises(ValueError):
        p.run_agent(ws, case, None)


def test_blocked_run_maps_to_failure(issue_case, tmp_path):
    caller = FakeToolCaller(
        {
            "autodev_start_run": env({"run_id": "run-abc"}),
            "autodev_get_run": _terminal_get_run(status="blocked"),
        }
    )
    p = AutoDevMCPProvider(caller, poll_interval_s=0)
    ws = p.create_workspace(issue_case, None)
    assert p.run_agent(ws, issue_case, None).status == AgentRunStatus.FAILURE


def test_end_to_end_through_eval_runner(issue_case, repo):
    from mars.engine.runner import EvalRunner
    from mars.providers.mock import MockCortexProvider

    diff = "--- a/x\n+++ b/x\n+y\n"
    caller = FakeToolCaller(
        {
            "autodev_start_run": env({"run_id": "run-abc"}),
            "autodev_get_run": _terminal_get_run(inline_diff=diff),
            "autodev_validate": env({"commands": [
                {"command": "pytest -q", "exit_code": 0, "status": "passed"}], "passed": True}),
        }
    )
    p = AutoDevMCPProvider(caller, poll_interval_s=0)
    result = EvalRunner(MockCortexProvider(), p, repository=repo).run_case(issue_case)
    assert result.status.value == "passed"
    assert result.agent == "claude-code"


# -- deterministic mode ----------------------------------------------------- #


def test_deterministic_prepare_and_validate(issue_case):
    caller = FakeToolCaller(
        {
            "autodev_prepare_workspace": env({"run_id": "run-det", "workspace_path": "/ws"}),
            "autodev_validate": env({"commands": [
                {"command": "echo ok", "exit_code": 0, "status": "passed"}], "passed": True}),
        }
    )
    p = AutoDevMCPProvider(caller, agentic=False, source_path="/tmp/mars-clean")
    ws = p.create_workspace(issue_case, None)
    assert ws.id == "run-det" and ws.metadata["run_id"] == "run-det"
    # deterministic run_agent is a no-op (no agentic implementation step)
    agent = p.run_agent(ws, issue_case, None)
    assert agent.status == AgentRunStatus.SUCCESS and agent.diff == ""
    tests = p.run_tests(ws, issue_case)
    assert tests.status == AgentRunStatus.SUCCESS
    prep_args = caller.calls[0][1]
    assert prep_args["source_path"] == "/tmp/mars-clean"
    assert prep_args["isolation_mode"] == "branch"
    assert prep_args["backlog_item_id"] == issue_case.id


# -- envelope + diff extraction --------------------------------------------- #


def test_envelope_error_raises(issue_case):
    caller = FakeToolCaller({"autodev_start_run": env(ok=False, error={"message": "nope"})})
    p = AutoDevMCPProvider(caller, poll_interval_s=0)
    ws = p.create_workspace(issue_case, None)
    with pytest.raises(RuntimeError):
        p.run_agent(ws, issue_case, None)


def test_capture_diff_reads_inline_then_file(issue_case, tmp_path):
    # inline wins
    caller = FakeToolCaller({"autodev_get_run": _terminal_get_run(inline_diff="INLINE")})
    p = AutoDevMCPProvider(caller)
    ws = p.create_workspace(issue_case, None)
    ws.metadata["run_id"] = "r"
    assert p.capture_diff(ws) == "INLINE"

    # falls back to artifact file
    f = tmp_path / "d.diff"
    f.write_text("FROMFILE")
    caller2 = FakeToolCaller({"autodev_get_run": _terminal_get_run(diff_path=f)})
    p2 = AutoDevMCPProvider(caller2)
    ws2 = p2.create_workspace(issue_case, None)
    ws2.metadata["run_id"] = "r"
    assert p2.capture_diff(ws2) == "FROMFILE"


def test_custom_tool_names(issue_case):
    caller = FakeToolCaller({"ad.start": env({"run_id": "run-abc"}),
                             "ad.get": _terminal_get_run(inline_diff="d")})
    p = AutoDevMCPProvider(
        caller, poll_interval_s=0,
        tool_names={"start_run": "ad.start", "get_run": "ad.get"},
    )
    ws = p.create_workspace(issue_case, None)
    p.run_agent(ws, issue_case, None)
    assert caller.calls[0][0] == "ad.start"


def test_close_propagates():
    caller = FakeToolCaller({})
    AutoDevMCPProvider(caller).close()
    assert caller.closed


# -- config / env ----------------------------------------------------------- #


def test_config_requires_a_transport():
    with pytest.raises(ValueError):
        MCPServerConfig()


def test_config_from_env_none_when_unset(monkeypatch):
    monkeypatch.delenv("MARS_AUTODEV_MCP_URL", raising=False)
    monkeypatch.delenv("MARS_AUTODEV_MCP_COMMAND", raising=False)
    assert config_from_env() is None
    assert AutoDevMCPProvider.from_env() is None


def test_make_autodev_falls_back_to_mock(monkeypatch):
    monkeypatch.delenv("MARS_AUTODEV_MCP_URL", raising=False)
    monkeypatch.delenv("MARS_AUTODEV_MCP_COMMAND", raising=False)
    assert not using_real_autodev()
    assert isinstance(make_autodev("claude-code"), MockAutoDevProvider)
