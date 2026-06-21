#!/usr/bin/env python3
"""Launch the Experiment 5.1 execution-impact run with the real AutoDev MCP server.

Wires Mars's ``AutoDevMCPProvider`` to the SAME stdio AutoDev server this machine
already runs (command + API keys are read from the autodev MCP entry in
``~/.claude.json``; ``GITHUB_TOKEN`` from ``gh auth token``), then execs
``experiments/run_execution_impact.py`` with whatever args follow.

Secrets stay out of the repo — they are read at launch from the existing config.

Examples
--------
  # Phase-4 gate: one task, all three arms (paid, ~3 real agent runs)
  python experiments/launch_exec_impact_5_1.py --real-autodev --dry-run \
      --issues-file experiments/execution_impact_5_1/issues.yaml \
      --only-tasks bench-4-protect-admin-reports

  # Full study: all six tasks × three arms
  python experiments/launch_exec_impact_5_1.py --real-autodev --dry-run \
      --issues-file experiments/execution_impact_5_1/issues.yaml
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

CLAUDE_JSON = Path.home() / ".claude.json"
MARS_DIR = Path(__file__).resolve().parent.parent
AUTODEV_BIN = Path.home() / "git/autodev/.venv/bin/autodev"
WORK_DIR = Path.home() / ".autodev/mcp"


def _autodev_mcp_env() -> dict[str, str]:
    """Find the autodev MCP entry whose env carries the model API keys.

    Several projects register an ``autodev`` server, but only some entries carry
    ANTHROPIC/OPENAI keys (others have just the cortex config). Prefer the mars
    project, else any entry that includes ANTHROPIC_API_KEY.
    """
    cfg = json.loads(CLAUDE_JSON.read_text())
    projects = cfg.get("projects", {})
    candidates = []
    for name, proj in projects.items():
        srv = (proj.get("mcpServers") or {}).get("autodev")
        if srv and srv.get("env"):
            candidates.append((name, dict(srv["env"])))
    # mars project first, then any with the anthropic key.
    for name, env in candidates:
        if name.endswith("/git/mars") and "ANTHROPIC_API_KEY" in env:
            return env
    for _name, env in candidates:
        if "ANTHROPIC_API_KEY" in env:
            return env
    raise SystemExit("no autodev MCP entry in ~/.claude.json carries ANTHROPIC_API_KEY")


def main() -> int:
    server_env = _autodev_mcp_env()
    gh = subprocess.run(["/opt/homebrew/bin/gh", "auth", "token"],
                        capture_output=True, text=True).stdout.strip()
    # env forwarded into the spawned AutoDev stdio child (keys + cortex config).
    # NOTE: retrieval for the experiment uses the FILE-backed memory store
    # (<work-dir>/state/memory/<repo>/), which we seed. AUTODEV_CORTEX_URL is a
    # SEPARATE SQL telemetry sink; the machine's default cortex.db has a stale
    # schema (missing novelty_score) that floods runs with non-fatal delivery
    # errors, so point telemetry at a fresh DB created with the current schema.
    fresh_cortex = f"sqlite+aiosqlite:///{WORK_DIR.parent}/cortex-exp51.db"
    server_env = dict(server_env, AUTODEV_CORTEX_URL=fresh_cortex)
    keys = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "AUTODEV_CORTEX_URL", "AUTODEV_CORTEX_PROJECT"]
    kv = " ".join(f"{k}={server_env[k]}" for k in keys if k in server_env)
    if gh:
        kv += f" GITHUB_TOKEN={gh}"

    env = dict(os.environ)
    env.update({
        "MARS_AUTODEV_MCP_TRANSPORT": "stdio",
        "MARS_AUTODEV_MCP_COMMAND": str(AUTODEV_BIN),
        "MARS_AUTODEV_MCP_ARGS": f"mcp serve --work-dir {WORK_DIR}",
        "MARS_AUTODEV_MCP_ENV": kv,
        "MARS_AUTODEV_MCP_TIMEOUT": os.environ.get("MARS_AUTODEV_MCP_TIMEOUT", "2400"),
    })
    cmd = [str(MARS_DIR / ".venv/bin/python"),
           str(MARS_DIR / "experiments/run_execution_impact.py"), *sys.argv[1:]]
    return subprocess.run(cmd, env=env).returncode


if __name__ == "__main__":
    raise SystemExit(main())
