"""Real AutoDevProvider backed by an AutoDev MCP server.

This is the Phase 1 drop-in replacement for ``MockAutoDevProvider``. It speaks
the AutoDev tool contract over MCP and maps responses onto Mars domain models;
the engine and Apollo are unchanged because both depend only on the
``AutoDevProvider`` ABC.

## Tool contract

The provider calls these MCP tools (names overridable via ``tool_names`` for
servers that namespace differently, e.g. ``autodev.run_agent``):

| Tool | Arguments | Returns |
| --- | --- | --- |
| ``create_workspace`` | ``case_id, repo, setup_commands, context`` | ``{workspace_id, path}`` |
| ``run_agent`` | ``workspace_id, agent, model, task_prompt, context`` | ``{agent_run_id?, status, logs?, diff?, runtime_ms?, cost_usd?, files_changed?}`` |
| ``run_tests`` | ``workspace_id, test_commands`` | ``{status?, test_results:[{name,passed,duration_ms?,output?}]}`` |
| ``capture_diff`` | ``workspace_id`` | ``{diff}`` |
| ``cleanup_workspace`` | ``workspace_id`` | ``{ok?}`` |

Unknown/missing fields fall back to sensible defaults so a minimally-compliant
server still works.
"""

from __future__ import annotations

import os
import uuid

from mars.models import AgentRun, AgentRunStatus, ContextPackage, EvalCase, TestResult
from mars.providers.base import AutoDevProvider, Workspace
from mars.providers.mcp_client import MCPServerConfig, MCPToolCaller, ToolCaller

DEFAULT_TOOL_NAMES = {
    "create_workspace": "create_workspace",
    "run_agent": "run_agent",
    "run_tests": "run_tests",
    "capture_diff": "capture_diff",
    "cleanup_workspace": "cleanup_workspace",
}


def _to_status(value: str | None) -> AgentRunStatus:
    try:
        return AgentRunStatus(str(value).lower())
    except ValueError:
        return AgentRunStatus.ERROR


def config_from_env() -> MCPServerConfig | None:
    """Read AutoDev MCP connection settings from the environment.

    Returns ``None`` when no transport is configured. Recognized vars:
    ``MARS_AUTODEV_MCP_URL`` (http) or ``MARS_AUTODEV_MCP_COMMAND`` (stdio),
    plus optional ``MARS_AUTODEV_MCP_ARGS`` and ``MARS_AUTODEV_MCP_TRANSPORT``.
    """
    url = os.environ.get("MARS_AUTODEV_MCP_URL")
    command = os.environ.get("MARS_AUTODEV_MCP_COMMAND")
    if not url and not command:
        return None
    return MCPServerConfig(
        url=url,
        command=command,
        args=os.environ.get("MARS_AUTODEV_MCP_ARGS", "").split(),
        transport=os.environ.get("MARS_AUTODEV_MCP_TRANSPORT", "streamable-http"),
    )


def _context_payload(context: ContextPackage | None) -> dict | None:
    if context is None:
        return None
    return {"id": context.id, "profile": context.profile, "version": context.version}


class AutoDevMCPProvider(AutoDevProvider):
    """Drives a real AutoDev workspace lifecycle over MCP."""

    def __init__(
        self,
        caller: ToolCaller,
        *,
        agent: str = "claude-code",
        model: str = "claude-opus",
        tool_names: dict[str, str] | None = None,
    ) -> None:
        self._caller = caller
        self.agent = agent
        self.model = model
        self._tools = {**DEFAULT_TOOL_NAMES, **(tool_names or {})}

    # -- construction helpers --------------------------------------------- #

    @classmethod
    def from_config(
        cls, config: MCPServerConfig, *, agent: str = "claude-code", model: str = "claude-opus"
    ) -> "AutoDevMCPProvider":
        return cls(MCPToolCaller(config), agent=agent, model=model)

    @classmethod
    def from_env(cls, *, agent: str = "claude-code", model: str = "claude-opus"):
        """Build from ``MARS_AUTODEV_MCP_URL`` or ``MARS_AUTODEV_MCP_COMMAND``.

        Returns ``None`` when neither is set, so callers can fall back to mocks.
        Connecting (and thus requiring the ``mcp`` package + a live server)
        happens only when a config is present.
        """
        config = config_from_env()
        if config is None:
            return None
        return cls.from_config(config, agent=agent, model=model)

    # -- AutoDevProvider -------------------------------------------------- #

    def create_workspace(self, case: EvalCase, context: ContextPackage | None) -> Workspace:
        data = self._caller.call_tool(
            self._tools["create_workspace"],
            {
                "case_id": case.id,
                "repo": case.repo,
                "setup_commands": case.setup_commands,
                "context": _context_payload(context),
            },
        )
        ws_id = data.get("workspace_id") or f"ws-{uuid.uuid4().hex[:12]}"
        return Workspace(id=ws_id, path=data.get("path", ""), metadata={"case": case.id})

    def run_agent(
        self, workspace: Workspace, case: EvalCase, context: ContextPackage | None
    ) -> AgentRun:
        data = self._caller.call_tool(
            self._tools["run_agent"],
            {
                "workspace_id": workspace.id,
                "agent": self.agent,
                "model": self.model,
                "task_prompt": case.task_prompt,
                "context": _context_payload(context),
            },
        )
        return AgentRun(
            id=data.get("agent_run_id") or f"agent-{uuid.uuid4().hex[:12]}",
            agent=self.agent,
            model=self.model,
            status=_to_status(data.get("status")),
            logs=data.get("logs", ""),
            diff=data.get("diff", ""),
            runtime_ms=int(data.get("runtime_ms", 0)),
            cost_usd=float(data.get("cost_usd", 0.0)),
            files_changed=list(data.get("files_changed", []) or []),
            test_results=self._parse_tests(data.get("test_results", [])),
        )

    def run_tests(self, workspace: Workspace, case: EvalCase) -> AgentRun:
        data = self._caller.call_tool(
            self._tools["run_tests"],
            {"workspace_id": workspace.id, "test_commands": case.test_commands},
        )
        results = self._parse_tests(data.get("test_results", []))
        status = data.get("status")
        if status is None:
            passed = bool(results) and all(t.passed for t in results)
            resolved = AgentRunStatus.SUCCESS if passed else AgentRunStatus.FAILURE
        else:
            resolved = _to_status(status)
        return AgentRun(
            id=f"tests-{uuid.uuid4().hex[:12]}",
            agent=self.agent,
            model=self.model,
            status=resolved,
            test_results=results,
        )

    def capture_diff(self, workspace: Workspace) -> str:
        data = self._caller.call_tool(self._tools["capture_diff"], {"workspace_id": workspace.id})
        return data.get("diff", "")

    def cleanup_workspace(self, workspace: Workspace) -> None:
        self._caller.call_tool(self._tools["cleanup_workspace"], {"workspace_id": workspace.id})

    def close(self) -> None:
        self._caller.close()

    @staticmethod
    def _parse_tests(raw: list) -> list[TestResult]:
        results: list[TestResult] = []
        for item in raw or []:
            results.append(
                TestResult(
                    name=item.get("name", "test"),
                    passed=bool(item.get("passed", False)),
                    duration_ms=int(item.get("duration_ms", 0)),
                    output=item.get("output", ""),
                )
            )
        return results
