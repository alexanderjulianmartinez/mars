"""Agent selection and AutoDev provider wiring.

If an AutoDev MCP server is configured (``MARS_AUTODEV_MCP_URL`` /
``MARS_AUTODEV_MCP_COMMAND``), ``make_autodev`` returns the real
:class:`AutoDevMCPProvider`. Otherwise it falls back to mock presets with
distinct quality/cost profiles so comparison/leaderboards show spread.
"""

from __future__ import annotations

from dataclasses import dataclass

from mars.providers.autodev_mcp import AutoDevMCPProvider, config_from_env
from mars.providers.base import AutoDevProvider
from mars.providers.mock import MockAutoDevProvider


@dataclass(frozen=True)
class AgentPreset:
    agent: str
    model: str
    quality: float
    cost_per_run: float


PRESETS: dict[str, AgentPreset] = {
    "claude-code": AgentPreset("claude-code", "claude-opus", quality=0.92, cost_per_run=0.04),
    "codex": AgentPreset("codex", "gpt-5-codex", quality=0.78, cost_per_run=0.06),
    "mock-agent": AgentPreset("mock-agent", "mock-model", quality=0.80, cost_per_run=0.05),
}


def make_autodev(agent: str) -> AutoDevProvider:
    preset = PRESETS.get(agent) or AgentPreset(agent, f"{agent}-model", 0.75, 0.05)
    config = config_from_env()
    if config is not None:
        return AutoDevMCPProvider.from_config(config, agent=preset.agent, model=preset.model)
    return MockAutoDevProvider(
        agent=preset.agent,
        model=preset.model,
        quality=preset.quality,
        cost_per_run=preset.cost_per_run,
    )


def using_real_autodev() -> bool:
    """True when an AutoDev MCP server is configured via the environment."""
    return config_from_env() is not None


def known_agents() -> list[str]:
    return list(PRESETS)
