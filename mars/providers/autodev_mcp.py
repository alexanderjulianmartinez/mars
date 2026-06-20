"""Real AutoDevProvider backed by an AutoDev MCP server.

Drop-in replacement for ``MockAutoDevProvider`` (engine + Apollo unchanged, they
depend only on the ``AutoDevProvider`` ABC). It speaks the **actual** AutoDev
tool contract — an issue-driven durable pipeline — verified against the live
server in this project.

## Real tool contract (responses are wrapped in ``{ok, data, error}``)

| Tool | Key args | Key data |
| --- | --- | --- |
| ``autodev_prepare_workspace`` | ``source_path``/``repo_full_name``, ``isolation_mode``, ``backlog_item_id`` | ``run_id``, ``workspace_path`` |
| ``autodev_start_run`` | ``issue_url``, ``dry_run``, ``isolation_mode``, ``max_iterations`` | ``run_id`` (pipeline runs plan→implement→validate→review) |
| ``autodev_validate`` | ``run_id``, ``commands``, ``stop_on_first_failure`` | ``commands:[{command,exit_code,status,duration_seconds,stdout,stderr}]``, ``passed`` |
| ``autodev_get_run`` | ``run_id`` | ``run{status,started_at,completed_at,metadata{implementation_diff_path}}``, ``validation_results``, ``review_results`` |
| ``autodev_review_gates`` | ``run_id`` | ``decision``, ``checks``, ``changed_files`` |

## Two modes

* **agentic** (default, requires ``case.issue_url``): ``run_agent`` calls
  ``start_run`` then polls ``get_run`` to terminal, extracting diff/files/status.
  Costs LLM $ on the AutoDev side. ``promote`` is never called (no PRs).
* **deterministic** (``agentic=False``): ``create_workspace`` calls
  ``prepare_workspace``; ``run_agent`` is a no-op; ``run_tests`` calls
  ``validate``. Zero LLM cost — used for harness/integration validation.

## Operational caveats (learned from the live server)

1. ``validate`` runs commands under AutoDev's own venv; pass interpreter-safe
   commands (or ensure deps are installed in the workspace).
2. Diff capture needs a real git workspace — use ``isolation_mode="branch"`` (or
   ``worktree``) / ``repo_full_name``, not a non-git source export.
3. ``audit_run`` only exists for journaled ``start_run`` runs.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from mars.models import AgentRun, AgentRunStatus, ContextPackage, EvalCase, TestResult
from mars.providers.base import AutoDevProvider, Workspace
from mars.providers.mcp_client import MCPServerConfig, MCPToolCaller, ToolCaller, parse_kv_env
from mars.providers.task_payload import build_task_payload

logger = logging.getLogger(__name__)

# Tools the provider actively calls. (review_gates/promote run *inside* the
# start_run pipeline; Mars reads their outcome via get_run rather than calling
# them — and never calls promote, so it opens no PRs.)
DEFAULT_TOOL_NAMES = {
    "prepare_workspace": "autodev_prepare_workspace",
    "start_run": "autodev_start_run",
    "validate": "autodev_validate",
    "get_run": "autodev_get_run",
}

# AutoDev run.status -> Mars AgentRunStatus.
_RUN_STATUS_MAP = {
    "completed": AgentRunStatus.SUCCESS,
    "succeeded": AgentRunStatus.SUCCESS,
    "success": AgentRunStatus.SUCCESS,
    "promoted": AgentRunStatus.SUCCESS,
    "done": AgentRunStatus.SUCCESS,
    "blocked": AgentRunStatus.FAILURE,
    "failed": AgentRunStatus.FAILURE,
    "rejected": AgentRunStatus.FAILURE,
    "error": AgentRunStatus.ERROR,
    "timeout": AgentRunStatus.TIMEOUT,
}
_TERMINAL_STATUSES = set(_RUN_STATUS_MAP)


def config_from_env() -> MCPServerConfig | None:
    """Read AutoDev MCP connection settings from the environment.

    ``None`` when no transport is configured. Recognized vars:
    ``MARS_AUTODEV_MCP_URL`` (http) or ``MARS_AUTODEV_MCP_COMMAND`` (stdio), plus
    optional ``MARS_AUTODEV_MCP_ARGS`` and ``MARS_AUTODEV_MCP_TRANSPORT``.
    """
    url = os.environ.get("MARS_AUTODEV_MCP_URL")
    command = os.environ.get("MARS_AUTODEV_MCP_COMMAND")
    if not url and not command:
        return None
    return MCPServerConfig(
        url=url,
        command=command,
        args=os.environ.get("MARS_AUTODEV_MCP_ARGS", "").split(),
        env=parse_kv_env(os.environ.get("MARS_AUTODEV_MCP_ENV")),
        cwd=os.environ.get("MARS_AUTODEV_MCP_CWD"),
        transport=os.environ.get("MARS_AUTODEV_MCP_TRANSPORT", "streamable-http"),
    )


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


class AutoDevMCPProvider(AutoDevProvider):
    """Drives the real AutoDev issue pipeline over MCP."""

    def __init__(
        self,
        caller: ToolCaller,
        *,
        agent: str = "claude-code",
        model: str = "claude-opus",
        agentic: bool = True,
        isolation_mode: str = "branch",
        dry_run: bool = True,
        max_iterations: int = 3,
        repo_full_name: str | None = None,
        source_path: str | None = None,
        validation_commands: list[str] | None = None,
        poll_interval_s: float = 5.0,
        poll_timeout_s: float = 1800.0,
        tool_names: dict[str, str] | None = None,
    ) -> None:
        self._caller = caller
        self.agent = agent
        self.model = model
        self.agentic = agentic
        self.isolation_mode = isolation_mode
        self.dry_run = dry_run
        self.max_iterations = max_iterations
        self.repo_full_name = repo_full_name
        self.source_path = source_path
        self.validation_commands = validation_commands
        self.poll_interval_s = poll_interval_s
        self.poll_timeout_s = poll_timeout_s
        self._tools = {**DEFAULT_TOOL_NAMES, **(tool_names or {})}

    # -- construction helpers --------------------------------------------- #

    @classmethod
    def from_config(cls, config: MCPServerConfig, **kwargs) -> "AutoDevMCPProvider":
        return cls(MCPToolCaller(config), **kwargs)

    @classmethod
    def from_env(cls, **kwargs):
        """Build from env, or ``None`` when no AutoDev MCP server is configured."""
        config = config_from_env()
        if config is None:
            return None
        return cls.from_config(config, **kwargs)

    # -- tool plumbing ---------------------------------------------------- #

    def _call(self, tool: str, args: dict) -> dict:
        """Call a tool and unwrap AutoDev's ``{ok, data, error}`` envelope."""
        resp = self._caller.call_tool(self._tools[tool], args)
        if isinstance(resp, dict) and "ok" in resp and ("data" in resp or "error" in resp):
            if resp.get("ok") is False or resp.get("error"):
                raise RuntimeError(f"AutoDev tool {self._tools[tool]!r} failed: {resp.get('error')}")
            return resp.get("data") or {}
        return resp if isinstance(resp, dict) else {}

    @staticmethod
    def _run_id(workspace: Workspace) -> str:
        run_id = workspace.metadata.get("run_id")
        if not run_id:
            raise RuntimeError("workspace has no run_id; create_workspace/run_agent not called")
        return run_id

    # -- AutoDevProvider -------------------------------------------------- #

    def create_workspace(self, case: EvalCase, context: ContextPackage | None) -> Workspace:
        if self.agentic:
            # start_run owns workspace provisioning; defer until run_agent.
            return Workspace(
                id=f"pending-{case.id}", metadata={"case": case.id, "issue_url": case.issue_url}
            )
        data = self._call(
            "prepare_workspace",
            {
                "source_path": self.source_path,
                "repo_full_name": self.repo_full_name or (case.repo or None),
                "isolation_mode": self.isolation_mode,
                "backlog_item_id": case.id,
            },
        )
        run_id = data.get("run_id") or f"run-{uuid.uuid4().hex[:12]}"
        return Workspace(
            id=run_id,
            path=data.get("workspace_path", ""),
            metadata={"case": case.id, "run_id": run_id},
        )

    def run_agent(
        self, workspace: Workspace, case: EvalCase, context: ContextPackage | None
    ) -> AgentRun:
        if not self.agentic:
            # Deterministic harness mode: no agent implementation step.
            return AgentRun(
                id=f"agent-{uuid.uuid4().hex[:12]}",
                agent=self.agent,
                model=self.model,
                status=AgentRunStatus.SUCCESS,
                logs="deterministic mode: no agentic run",
            )
        if not case.issue_url:
            raise ValueError(
                f"case {case.id!r} has no issue_url; required for agentic AutoDev runs"
            )
        # Record the structured task payload (criteria + setup) for transparency.
        payload = build_task_payload(case)
        workspace.metadata["task_payload"] = payload
        if case.acceptance_criteria:
            logger.warning(
                "AutoDev start_run accepts issue_url only; %d acceptance criteria for case %r "
                "were recorded in metadata but not propagated over MCP. Put them in the issue "
                "body to influence the run.",
                len(case.acceptance_criteria),
                case.id,
            )
        started = self._call(
            "start_run",
            {
                "issue_url": case.issue_url,
                "dry_run": self.dry_run,
                "isolation_mode": self.isolation_mode,
                "max_iterations": self.max_iterations,
            },
        )
        run_id = started.get("run_id") or (started.get("run") or {}).get("run_id")
        if not run_id:
            raise RuntimeError(f"start_run returned no run_id: {started!r}")
        workspace.metadata["run_id"] = run_id
        run = self._poll_until_terminal(run_id)
        return self._agent_run_from(run_id, run)

    def run_tests(self, workspace: Workspace, case: EvalCase) -> AgentRun:
        run_id = self._run_id(workspace)
        # A1: install dependencies (setup commands) before validation so tests
        # can actually run. Run as a separate, gated validate call — these are
        # not folded into the scored test results.
        if case.setup_commands:
            self._call(
                "validate",
                {"run_id": run_id, "commands": case.setup_commands, "stop_on_first_failure": True},
            )
        commands = self.validation_commands or case.test_commands
        if commands:
            data = self._call(
                "validate",
                {"run_id": run_id, "commands": commands, "stop_on_first_failure": False},
            )
            cmd_results = data.get("commands", [])
        else:
            # No explicit commands: reuse validation the pipeline already ran.
            data = self._call("get_run", {"run_id": run_id})
            vrs = data.get("validation_results") or []
            cmd_results = vrs[-1].get("commands", []) if vrs else []
        results = self._parse_validation(cmd_results)
        passed = bool(results) and all(t.passed for t in results)
        return AgentRun(
            id=f"tests-{uuid.uuid4().hex[:12]}",
            agent=self.agent,
            model=self.model,
            status=AgentRunStatus.SUCCESS if passed else AgentRunStatus.FAILURE,
            test_results=results,
        )

    def capture_diff(self, workspace: Workspace) -> str:
        data = self._call("get_run", {"run_id": self._run_id(workspace)})
        return self._extract_diff(data)

    def cleanup_workspace(self, workspace: Workspace) -> None:
        # AutoDev owns run lifecycle; no destroy tool. Runs remain replayable.
        return None

    def close(self) -> None:
        self._caller.close()

    # -- polling + mapping ------------------------------------------------ #

    def _poll_until_terminal(self, run_id: str) -> dict:
        import time

        deadline = time.monotonic() + self.poll_timeout_s
        while True:
            data = self._call("get_run", {"run_id": run_id})
            run = data.get("run") or {}
            status = str(run.get("status", "")).lower()
            if run.get("completed_at") or status in _TERMINAL_STATUSES:
                return data
            if time.monotonic() >= deadline:
                raise TimeoutError(f"AutoDev run {run_id} did not finish within {self.poll_timeout_s}s")
            time.sleep(self.poll_interval_s)

    def _agent_run_from(self, run_id: str, data: dict) -> AgentRun:
        run = data.get("run") or {}
        status = str(run.get("status", "")).lower()
        agent_status = _RUN_STATUS_MAP.get(status)
        if agent_status is None:
            agent_status = AgentRunStatus.SUCCESS if run.get("completed_at") else AgentRunStatus.ERROR
        runtime_ms = 0
        start, end = _parse_iso(run.get("started_at")), _parse_iso(run.get("completed_at"))
        if start and end:
            runtime_ms = max(0, int((end - start).total_seconds() * 1000))
        meta = run.get("metadata") or {}
        cost = float(meta.get("cost_usd") or meta.get("cost") or 0.0)
        return AgentRun(
            id=run_id,
            agent=self.agent,
            model=self.model,
            status=agent_status,
            logs=str(run.get("summary") or meta.get("validation_results") or ""),
            diff=self._extract_diff(data),
            runtime_ms=runtime_ms,
            cost_usd=cost,
            files_changed=self._extract_files(data),
        )

    @staticmethod
    def _extract_diff(data: dict) -> str:
        # Prefer inline diff; fall back to the artifact file on a shared host.
        if data.get("diff"):
            return str(data["diff"])
        run = data.get("run") or {}
        meta = run.get("metadata") or {}
        path = meta.get("implementation_diff_path") or data.get("implementation_diff_path")
        if path:
            p = Path(path)
            if p.is_file():
                try:
                    return p.read_text()
                except OSError:
                    return ""
        return ""

    @staticmethod
    def _extract_files(data: dict) -> list[str]:
        for review in reversed(data.get("review_results") or []):
            files = (review.get("metadata") or {}).get("files_modified")
            if files:
                return list(files)
        changed = data.get("changed_files")
        return list(changed) if changed else []

    @staticmethod
    def _parse_validation(cmd_results: list) -> list[TestResult]:
        results: list[TestResult] = []
        for c in cmd_results or []:
            status = str(c.get("status", "")).lower()
            passed = status == "passed" if status else (int(c.get("exit_code", 1)) == 0)
            duration_ms = int(float(c.get("duration_seconds", 0.0)) * 1000)
            output = c.get("stdout", "") or c.get("stderr", "")
            results.append(
                TestResult(
                    name=c.get("command", "validate"),
                    passed=passed,
                    duration_ms=duration_ms,
                    output=output,
                )
            )
        return results
