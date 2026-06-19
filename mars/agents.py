"""Mock agent presets for the MVP.

Until a real AutoDevProvider is wired in, named agents map to mock providers
with different quality/cost profiles so comparison and leaderboards show
meaningful spread. Replace this module's body when integrating real AutoDev.
"""

from __future__ import annotations

from dataclasses import dataclass

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


def make_autodev(agent: str) -> MockAutoDevProvider:
    preset = PRESETS.get(agent) or AgentPreset(agent, f"{agent}-model", 0.75, 0.05)
    return MockAutoDevProvider(
        agent=preset.agent,
        model=preset.model,
        quality=preset.quality,
        cost_per_run=preset.cost_per_run,
    )


def known_agents() -> list[str]:
    return list(PRESETS)
