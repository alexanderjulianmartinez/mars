"""Tests for the MCP-backed Cortex provider (no live server required)."""

import pytest

from mars.agents import make_cortex, using_real_cortex
from mars.providers.cortex_mcp import CortexMCPProvider, config_from_env
from mars.providers.mock import MockCortexProvider


class FakeToolCaller:
    def __init__(self, responses: dict) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []
        self.closed = False

    def call_tool(self, name: str, arguments: dict):
        self.calls.append((name, arguments))
        return self.responses.get(name, {})

    def close(self) -> None:
        self.closed = True


def test_list_profiles_object_and_bare_list():
    obj = CortexMCPProvider(FakeToolCaller({"list_profiles": {"profiles": ["a", "b"]}}))
    assert obj.list_profiles() == ["a", "b"]
    bare = CortexMCPProvider(FakeToolCaller({"list_profiles": ["x"]}))
    assert bare.list_profiles() == ["x"]


def test_get_context_package_maps_fields():
    caller = FakeToolCaller(
        {
            "get_context_package": {
                "id": "ctx-9",
                "profile": "backend",
                "version": "v3",
                "generated_at": "2026-06-19T12:00:00Z",
                "metadata": {"files_indexed": 120},
            }
        }
    )
    pkg = CortexMCPProvider(caller).get_context_package("backend")
    assert pkg.id == "ctx-9"
    assert pkg.profile == "backend"
    assert pkg.version == "v3"
    assert pkg.metadata["files_indexed"] == 120
    assert pkg.generated_at.year == 2026
    assert caller.calls[0] == ("get_context_package", {"profile": "backend"})


def test_get_context_package_defaults_for_sparse_server():
    pkg = CortexMCPProvider(FakeToolCaller({"get_context_package": {}})).get_context_package("p")
    assert pkg.id.startswith("ctx-")
    assert pkg.profile == "p"
    assert pkg.version == "unknown"
    assert pkg.metadata == {}


def test_get_context_for_case_uses_per_case_tool(case):
    caller = FakeToolCaller(
        {"get_context_for_case": {"id": "ctx-c", "metadata": {"relevance": 0.8}}}
    )
    pkg = CortexMCPProvider(caller).get_context_for_case(case)
    assert pkg.id == "ctx-c"
    assert pkg.metadata["relevance"] == 0.8
    name, args = caller.calls[0]
    assert name == "get_context_for_case"
    assert args["case_id"] == case.id
    assert args["task_prompt"] == case.task_prompt


def test_per_case_disabled_falls_back_to_profile(case):
    caller = FakeToolCaller({"get_context_package": {"id": "ctx-p", "profile": case.context_profile}})
    provider = CortexMCPProvider(caller, per_case=False)
    pkg = provider.get_context_for_case(case)
    assert pkg.id == "ctx-p"
    assert caller.calls[0][0] == "get_context_package"


def test_works_through_eval_runner(case, repo):
    from mars.engine.runner import EvalRunner
    from mars.providers.mock import MockAutoDevProvider

    cortex = CortexMCPProvider(
        FakeToolCaller({"get_context_for_case": {"id": "ctx-x", "version": "v1"}})
    )
    runner = EvalRunner(cortex, MockAutoDevProvider(quality=1.0), repository=repo)
    result = runner.run_case(case)
    assert result.context_package_id == "ctx-x"


def test_custom_tool_names():
    caller = FakeToolCaller({"cortex.list_profiles": {"profiles": ["z"]}})
    provider = CortexMCPProvider(caller, tool_names={"list_profiles": "cortex.list_profiles"})
    assert provider.list_profiles() == ["z"]


def test_close_propagates():
    caller = FakeToolCaller({})
    CortexMCPProvider(caller).close()
    assert caller.closed


# -- env / factory ---------------------------------------------------------- #


def test_config_from_env_none_when_unset(monkeypatch):
    monkeypatch.delenv("MARS_CORTEX_MCP_URL", raising=False)
    monkeypatch.delenv("MARS_CORTEX_MCP_COMMAND", raising=False)
    assert config_from_env() is None
    assert CortexMCPProvider.from_env() is None


def test_config_from_env_http(monkeypatch):
    monkeypatch.setenv("MARS_CORTEX_MCP_URL", "http://localhost:8800/mcp")
    monkeypatch.delenv("MARS_CORTEX_MCP_COMMAND", raising=False)
    cfg = config_from_env()
    assert cfg is not None and cfg.url.endswith("/mcp")


def test_make_cortex_falls_back_to_mock(monkeypatch):
    monkeypatch.delenv("MARS_CORTEX_MCP_URL", raising=False)
    monkeypatch.delenv("MARS_CORTEX_MCP_COMMAND", raising=False)
    assert not using_real_cortex()
    assert isinstance(make_cortex(), MockCortexProvider)
