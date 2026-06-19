"""Memory-aware mock providers for Apollo experiments.

These extend the Cortex/AutoDev mocks so that **retrieval quality propagates to
task outcomes**:

    retrieval strategy -> top-k memories -> context relevance
                       -> agent success probability -> Mars score

Both providers carry a mutable ``trial`` the experiment runner advances between
trials, giving a reproducible distribution of outcomes per condition.

Crucially, the AutoDev "luck" roll is seeded by (agent, case, trial) and *not*
by the strategy, so baseline and experimental arms see identical luck and differ
only through retrieval relevance — a proper paired design.
"""

from __future__ import annotations

import hashlib
import uuid

from mars.memory.retrieval import RetrievalStrategy
from mars.memory.store import generate_case_memories
from mars.models import (
    AgentRun,
    AgentRunStatus,
    ContextPackage,
    EvalCase,
    TestResult,
)
from mars.providers.base import AutoDevProvider, CortexProvider, Workspace


def _unit(*parts: str) -> float:
    """Deterministic float in [0, 1) from the given parts."""
    digest = hashlib.sha256("::".join(parts).encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


class MemoryAwareCortexProvider(CortexProvider):
    """Retrieves per-case memories with a configurable strategy.

    ``get_context_for_case`` runs the strategy over the case's memory set and
    reports retrieval recall as ``metadata["relevance"]``. ``last_relevance``
    exposes the most recent value to the experiment runner.
    """

    def __init__(self, strategy: RetrievalStrategy, k: int = 5, seed: int = 0) -> None:
        self.strategy = strategy
        self.k = k
        self.seed = seed
        self.trial = 0
        self.last_relevance: float | None = None

    def list_profiles(self) -> list[str]:
        return ["memory"]

    def get_context_metadata(self, profile: str) -> dict:
        return {"profile": profile, "strategy": self.strategy.name, "k": self.k}

    def get_context_package(self, profile: str) -> ContextPackage:  # pragma: no cover - unused path
        return ContextPackage(id=f"ctx-{profile}", profile=profile, version=self.strategy.name)

    def get_context_for_case(self, case: EvalCase) -> ContextPackage:
        memories = generate_case_memories(case.id, self.trial)
        result = self.strategy.retrieve(memories, self.k)
        self.last_relevance = result.quality
        return ContextPackage(
            id=f"ctx-{case.id}-t{self.trial}-{self.strategy.name}",
            profile=case.context_profile,
            version=self.strategy.name,
            metadata={
                "relevance": round(result.quality, 4),
                "strategy": self.strategy.config(),
                "k": self.k,
                "n_memories": len(memories),
                "retrieved": [m.id for m in result.ranked],
            },
        )


class MemoryAwareAutoDevProvider(AutoDevProvider):
    """Mock AutoDev whose success probability scales with context relevance.

    Effective success probability = ``base_quality * (floor + (1-floor)*relevance)``,
    so a long-horizon task only succeeds reliably when retrieval surfaced the
    memories it needs.
    """

    def __init__(
        self,
        agent: str = "claude-code",
        model: str = "claude-opus",
        base_quality: float = 0.9,
        cost_per_run: float = 0.04,
        floor: float = 0.35,
    ) -> None:
        self.agent = agent
        self.model = model
        self.base_quality = base_quality
        self.cost_per_run = cost_per_run
        self.floor = floor
        self.trial = 0

    def create_workspace(self, case: EvalCase, context: ContextPackage | None) -> Workspace:
        relevance = float(context.metadata.get("relevance", 1.0)) if context else 1.0
        effective = _clamp(self.base_quality * (self.floor + (1 - self.floor) * relevance))
        roll = _unit(self.agent, self.model, case.id, str(self.trial))
        succeeded = roll < effective
        return Workspace(
            id=f"ws-{uuid.uuid4().hex[:12]}",
            path=f"/tmp/mars/{case.id}",
            metadata={
                "case": case.id,
                "relevance": relevance,
                "succeeded": succeeded,
                "seed": f"{case.id}:{self.trial}",
            },
        )

    def run_agent(
        self, workspace: Workspace, case: EvalCase, context: ContextPackage | None
    ) -> AgentRun:
        succeeded = bool(workspace.metadata.get("succeeded"))
        runtime_seed = _unit(self.agent, case.id, str(self.trial), "rt")
        runtime = int(4000 + runtime_seed * 20000)
        files = [f"src/{case.id.replace('-', '_')}.py"]
        if succeeded:
            files.append("tests/" + case.id.replace("-", "_") + "_test.py")
        return AgentRun(
            id=f"agent-{uuid.uuid4().hex[:12]}",
            agent=self.agent,
            model=self.model,
            status=AgentRunStatus.SUCCESS if succeeded else AgentRunStatus.FAILURE,
            logs=f"[{self.agent}] {case.id} relevance={workspace.metadata.get('relevance'):.2f}\n",
            diff=self._fake_diff(case, files) if succeeded else "",
            runtime_ms=runtime,
            cost_usd=round(self.cost_per_run * (1 + runtime_seed), 4),
            files_changed=files if succeeded else [],
        )

    def run_tests(self, workspace: Workspace, case: EvalCase) -> AgentRun:
        succeeded = bool(workspace.metadata.get("succeeded"))
        commands = case.test_commands or ["pytest"]
        results = [
            TestResult(
                name=cmd,
                passed=succeeded,
                duration_ms=int(200 + _unit(case.id, cmd) * 3000),
                output="ok" if succeeded else "assertion failed",
            )
            for cmd in commands
        ]
        return AgentRun(
            id=f"tests-{uuid.uuid4().hex[:12]}",
            agent=self.agent,
            model=self.model,
            status=AgentRunStatus.SUCCESS if succeeded else AgentRunStatus.FAILURE,
            test_results=results,
        )

    def capture_diff(self, workspace: Workspace) -> str:
        return ""

    def cleanup_workspace(self, workspace: Workspace) -> None:
        return None

    @staticmethod
    def _fake_diff(case: EvalCase, files: list[str]) -> str:
        path = files[0]
        return f"--- a/{path}\n+++ b/{path}\n@@ -0,0 +1,2 @@\n+# {case.name}\n+pass\n"
