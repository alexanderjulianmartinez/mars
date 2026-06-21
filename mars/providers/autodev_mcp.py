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
        # autodev_start_run BLOCKS until the whole plan→implement→validate→review
        # pipeline finishes, so a single call can run for minutes. Default the
        # per-call timeout generously and let MARS_AUTODEV_MCP_TIMEOUT override.
        timeout_seconds=float(os.environ.get("MARS_AUTODEV_MCP_TIMEOUT", "1800")),
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
        retrieval_strategy: str | None = None,
        retrieval_arg_name: str = "retrieval_strategy",
        send_retrieval: bool = False,
        context_package_id: str | None = None,
        retrieval_limit: int | None = None,
        send_task_spec: bool = True,
        context_metadata: dict[str, Any] | None = None,
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
        # Per-run retrieval control. ``start_run``'s schema is additionalProperties:
        # false today, so the extra arg is sent ONLY when ``send_retrieval`` is
        # explicitly enabled (i.e. once the AutoDev side accepts it). The arg name
        # is configurable so Mars need not be re-released when AutoDev names it.
        self.retrieval_strategy = retrieval_strategy
        self.retrieval_arg_name = retrieval_arg_name
        self.send_retrieval = send_retrieval
        self.context_package_id = context_package_id
        # Top-k memories injected. Critical for the A/B/C contrast: with the
        # controlled 5-record store, limit must be < store size (e.g. 3) so the
        # similarity arm actually EXCLUDES the buried high-importance record. At
        # the AutoDev default (5) every arm injects the whole store and arms
        # differ only in order, not content.
        self.retrieval_limit = retrieval_limit
        # Experiment 5.1: send the per-run task spec (acceptance criteria/checks,
        # validation/setup commands, file checks) on start_run so AutoDev's review
        # gate renders a real verdict instead of auto-blocking on a missing spec.
        # Additive/optional in the contract; on by default, disable for an older
        # server whose start_run rejects the fields.
        self.send_task_spec = send_task_spec
        self.context_metadata = context_metadata

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
        start_args = {
            "issue_url": case.issue_url,
            "dry_run": self.dry_run,
            "isolation_mode": self.isolation_mode,
            "max_iterations": self.max_iterations,
        }
        # Experiment 5.1 contract: thread the per-run task spec to start_run. All
        # fields are additive/optional; only non-empty ones are sent. Present
        # acceptance criteria/checks ⇒ the review gate evaluates instead of
        # auto-blocking, which is what lifts the success floor.
        if self.send_task_spec:
            spec: dict[str, Any] = {}
            if case.acceptance_criteria:
                spec["acceptance_criteria"] = list(case.acceptance_criteria)
            if case.acceptance_checks:
                spec["acceptance_checks"] = list(case.acceptance_checks)
            validation = self.validation_commands or case.test_commands
            if validation:
                spec["validation_commands"] = list(validation)
            if case.setup_commands:
                spec["setup_commands"] = list(case.setup_commands)
            if case.expected_files:
                spec["expected_files"] = list(case.expected_files)
            if case.forbidden_files:
                spec["forbidden_files"] = list(case.forbidden_files)
            cmeta = self._context_metadata_for(case)
            if cmeta:
                spec["context_metadata"] = cmeta
                workspace.metadata["context_metadata"] = cmeta
            start_args.update(spec)
            workspace.metadata["task_spec_sent"] = sorted(spec)
        if self.send_retrieval and self.retrieval_strategy:
            # AutoDev's StartRunRequest accepts retrieval_strategy + context_package_id
            # (the experiment's variable of variation). Recorded for provenance.
            start_args[self.retrieval_arg_name] = self.retrieval_strategy
            workspace.metadata["retrieval_strategy"] = self.retrieval_strategy
            if self.context_package_id:
                start_args["context_package_id"] = self.context_package_id
                workspace.metadata["context_package_id"] = self.context_package_id
            if self.retrieval_limit:
                start_args["retrieval_limit"] = self.retrieval_limit
                workspace.metadata["retrieval_limit"] = self.retrieval_limit
        started = self._call("start_run", start_args)
        run_id = started.get("run_id") or (started.get("run") or {}).get("run_id")
        if not run_id:
            raise RuntimeError(f"start_run returned no run_id: {started!r}")
        workspace.metadata["run_id"] = run_id
        run = self._poll_until_terminal(run_id)
        return self._agent_run_from(run_id, run)

    def _context_metadata_for(self, case: EvalCase) -> dict[str, Any]:
        """Arm tag stamped on the run record + event journal (5.1 provenance).

        Combines any caller-supplied ``context_metadata`` with the active arm
        (``retrieval_strategy``) and the task id so a run is auditable as
        "which task, under which arm?".
        """
        meta: dict[str, Any] = dict(self.context_metadata or {})
        if self.send_retrieval and self.retrieval_strategy:
            meta.setdefault("arm", self.retrieval_strategy)
        meta.setdefault("task_id", case.id)
        return meta

    def run_tests(self, workspace: Workspace, case: EvalCase) -> AgentRun:
        run_id = self._run_id(workspace)
        # Restore forbidden files (the oracle tests) to their pristine committed
        # state before validation. The agent sometimes rewrites the test file in
        # its workspace; without this, validation would run the AGENT's tests, not
        # the benchmark oracle — measuring the wrong thing. AutoDev's validate
        # runs commands through a supervisor allowlist that blocks ``git``, so we
        # restore directly on the (co-located) workspace filesystem instead.
        if case.forbidden_files:
            self._restore_forbidden_files(run_id, case.forbidden_files)
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

    def _workspace_path(self, run_id: str) -> str | None:
        data = self._call("get_run", {"run_id": run_id})
        run = data.get("run") or {}
        return run.get("workspace_path") or data.get("workspace_path")

    def _restore_forbidden_files(self, run_id: str, forbidden: list[str]) -> None:
        """Revert forbidden paths to their committed state on the workspace fs.

        Best-effort and only when the workspace is local (AutoDev co-located with
        Mars, as in the execution-impact study). Leaves the implementation diff
        intact — only the named paths are checked out from HEAD.
        """
        import subprocess

        ws = self._workspace_path(run_id)
        if not ws or not Path(ws).is_dir():
            logger.warning("cannot restore forbidden files for %s: workspace %r not local",
                           run_id, ws)
            return
        try:
            subprocess.run(["git", "checkout", "HEAD", "--", *forbidden],
                           cwd=ws, check=False, capture_output=True, text=True)
        except OSError as exc:  # git missing, etc. — non-fatal
            logger.warning("forbidden-file restore failed for %s: %s", run_id, exc)

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
        # cost_usd is exposed both top-level (5.1) and in run.metadata (older).
        cost = float(
            data.get("cost_usd") or meta.get("cost_usd") or meta.get("cost") or 0.0
        )
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
            token_usage=self._extract_tokens(data, meta),
            review_decision=self._extract_review_decision(data),
            retrieved_context=self._extract_retrieved_context(data, meta),
        )

    @staticmethod
    def _extract_tokens(data: dict, meta: dict) -> int | None:
        for src in (meta, data, data.get("usage") or {}):
            for key in ("token_usage", "tokens", "total_tokens"):
                if src.get(key) is not None:
                    try:
                        return int(src[key])
                    except (TypeError, ValueError):
                        return None
        return None

    @staticmethod
    def _extract_review_decision(data: dict) -> str | None:
        # 5.1 contract: a singular ``review`` object with ``decision`` +
        # ``review_passed`` (the primary task-success signal).
        review = data.get("review")
        if isinstance(review, dict):
            decision = review.get("decision")
            if decision:
                return str(decision)
            passed = review.get("review_passed")
            if passed is not None:
                return "approved" if passed else "blocked"
        # Older schema: a ``review_results`` list.
        reviews = data.get("review_results") or []
        if reviews:
            last = reviews[-1]
            decision = last.get("decision") or (last.get("metadata") or {}).get("decision")
            return str(decision) if decision else None
        return None

    @staticmethod
    def _extract_retrieved_context(data: dict, meta: dict) -> list[dict]:
        for src in (data.get("retrieved_context"), meta.get("retrieved_context"),
                    (data.get("context") or {}).get("memories")):
            if isinstance(src, list):
                return [m if isinstance(m, dict) else {"id": str(m)} for m in src]
        return []

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

    @classmethod
    def _extract_files(cls, data: dict) -> list[str]:
        review = data.get("review")
        if isinstance(review, dict):
            files = review.get("changed_files") or (review.get("metadata") or {}).get("files_modified")
            if files:
                return list(files)
        for review in reversed(data.get("review_results") or []):
            files = (review.get("metadata") or {}).get("files_modified")
            if files:
                return list(files)
        changed = data.get("changed_files")
        if changed:
            return list(changed)
        # 5.1: get_run exposes the diff but not always changed_files — derive the
        # touched paths from the unified diff so focused-diff metrics are real.
        return cls._files_from_diff(cls._extract_diff(data))

    @staticmethod
    def _files_from_diff(diff: str) -> list[str]:
        files: list[str] = []
        for line in (diff or "").splitlines():
            if line.startswith("+++ ") and not line.startswith("+++ /dev/null"):
                path = line[4:].strip()
                if path.startswith("b/"):
                    path = path[2:]
                if path and path not in files:
                    files.append(path)
        return files

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
