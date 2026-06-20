"""Deterministic mock providers that simulate realistic Cortex/AutoDev results.

The mocks let the full evaluation pipeline run end-to-end with no external
services. Behaviour is seeded from the case id and agent name so runs are
reproducible (important for replay) yet vary across cases and agents.
"""

from __future__ import annotations

import hashlib
import uuid

from mars.models import (
    AgentRun,
    AgentRunStatus,
    ContextPackage,
    EvalCase,
    TestResult,
)
from mars.providers.base import AutoDevProvider, CortexProvider, Workspace


def _seed(*parts: str) -> int:
    digest = hashlib.sha256("::".join(parts).encode()).hexdigest()
    return int(digest[:8], 16)


class MockCortexProvider(CortexProvider):
    """Simulates Cortex by returning versioned context packages per profile."""

    def __init__(self, profiles: list[str] | None = None, version: str = "mock-1") -> None:
        self._profiles = profiles or ["default", "backend", "infra"]
        self._version = version

    def list_profiles(self) -> list[str]:
        return list(self._profiles)

    def get_context_package(self, profile: str) -> ContextPackage:
        return ContextPackage(
            id=f"ctx-{_seed(profile, self._version):08x}",
            profile=profile,
            version=self._version,
            metadata=self.get_context_metadata(profile),
        )

    def get_context_metadata(self, profile: str) -> dict:
        return {
            "profile": profile,
            "version": self._version,
            "files_indexed": 40 + _seed(profile) % 200,
            "tokens": 8000 + _seed(profile, "tok") % 16000,
        }


class MockAutoDevProvider(AutoDevProvider):
    """Simulates AutoDev execution with seeded, reproducible outcomes.

    ``quality`` (0.0-1.0) biases how often the simulated agent succeeds, so
    different agents can be compared. ``cost_per_run`` scales reported cost.
    """

    def __init__(
        self,
        agent: str = "mock-agent",
        model: str = "mock-model",
        quality: float = 0.8,
        cost_per_run: float = 0.05,
    ) -> None:
        self.agent = agent
        self.model = model
        self.quality = quality
        self.cost_per_run = cost_per_run

    def create_workspace(self, case: EvalCase, context: ContextPackage | None) -> Workspace:
        return Workspace(
            id=f"ws-{uuid.uuid4().hex[:12]}",
            path=f"/tmp/mars/{case.id}",
            metadata={"case": case.id, "context": context.id if context else None},
        )

    def _succeeds(self, case: EvalCase) -> bool:
        # Deterministic per (agent, model, case): scale seed into 0-100 and
        # compare against the quality threshold.
        roll = _seed(self.agent, self.model, case.id) % 100
        return roll < int(self.quality * 100)

    def run_agent(
        self, workspace: Workspace, case: EvalCase, context: ContextPackage | None
    ) -> AgentRun:
        succeeds = self._succeeds(case)
        seed = _seed(self.agent, self.model, case.id, "run")
        runtime = 4000 + seed % 20000
        files = [f"src/{case.id.replace('-', '_')}.py"]
        if succeeds:
            files.append("tests/" + case.id.replace("-", "_") + "_test.py")
        diff = self._fake_diff(case, files) if succeeds else ""
        return AgentRun(
            id=f"agent-{uuid.uuid4().hex[:12]}",
            agent=self.agent,
            model=self.model,
            status=AgentRunStatus.SUCCESS if succeeds else AgentRunStatus.FAILURE,
            logs=(
                f"[{self.agent}] setup: {len(case.setup_commands)} command(s) simulated ok\n"
                f"[{self.agent}] acceptance_criteria: {len(case.acceptance_criteria)} provided\n"
                f"[{self.agent}] working on {case.id}\n"
                + ("done\n" if succeeds else "gave up\n")
            ),
            diff=diff,
            runtime_ms=runtime,
            cost_usd=round(self.cost_per_run * (1 + seed % 5), 4),
            files_changed=files if succeeds else [],
        )

    def run_tests(self, workspace: Workspace, case: EvalCase) -> AgentRun:
        succeeds = self._succeeds(case)
        commands = case.test_commands or ["pytest"]
        results = [
            TestResult(
                name=cmd,
                passed=succeeds,
                duration_ms=200 + _seed(case.id, cmd) % 3000,
                output="ok" if succeeds else "assertion failed",
            )
            for cmd in commands
        ]
        # run_tests returns a lightweight AgentRun carrying only test results;
        # the engine merges these into the agent's run.
        return AgentRun(
            id=f"tests-{uuid.uuid4().hex[:12]}",
            agent=self.agent,
            model=self.model,
            status=AgentRunStatus.SUCCESS if succeeds else AgentRunStatus.FAILURE,
            test_results=results,
        )

    def capture_diff(self, workspace: Workspace) -> str:
        return ""  # Real diff is produced by run_agent in the mock.

    def cleanup_workspace(self, workspace: Workspace) -> None:
        return None

    @staticmethod
    def _fake_diff(case: EvalCase, files: list[str]) -> str:
        path = files[0]
        return (
            f"--- a/{path}\n+++ b/{path}\n"
            f"@@ -0,0 +1,3 @@\n"
            f"+# {case.name}\n"
            f"+def solution():\n"
            f"+    return True\n"
        )
