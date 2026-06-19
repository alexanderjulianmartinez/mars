"""Provider interfaces — the contract between Mars and the outside world.

These are deliberately transport-agnostic. The MVP ships in-process mock
implementations; a future MCP client implementing the same ABCs must be a
drop-in replacement. The Mars engine programs against these types only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from mars.models import AgentRun, ContextPackage, EvalCase


class CortexProvider(ABC):
    """Context generation, owned by Cortex.

    Mars asks Cortex for the context that should accompany a case, but never
    produces context itself.
    """

    @abstractmethod
    def list_profiles(self) -> list[str]:
        """Return the context profiles this provider can serve."""

    @abstractmethod
    def get_context_package(self, profile: str) -> ContextPackage:
        """Return a context package for ``profile``."""

    @abstractmethod
    def get_context_metadata(self, profile: str) -> dict:
        """Return metadata describing the context for ``profile``."""

    def get_context_for_case(self, case: EvalCase) -> ContextPackage:
        """Return the context package for a specific case.

        Defaults to the case's ``context_profile``. Memory-aware providers
        override this to retrieve per-case memories and report retrieval
        relevance in the package metadata. The engine calls this (not
        :meth:`get_context_package`) so per-case retrieval is transparent.
        """
        return self.get_context_package(case.context_profile)


class Workspace:
    """Opaque handle to an AutoDev workspace.

    Mars treats this as a token; only the providing implementation interprets
    its fields.
    """

    def __init__(self, id: str, path: str = "", metadata: dict | None = None) -> None:
        self.id = id
        self.path = path
        self.metadata = metadata or {}

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"Workspace(id={self.id!r}, path={self.path!r})"


class AutoDevProvider(ABC):
    """Agent execution, owned by AutoDev.

    Mars orchestrates the lifecycle (create -> run -> test -> capture -> clean)
    but performs none of the execution itself.
    """

    @abstractmethod
    def create_workspace(self, case: EvalCase, context: ContextPackage | None) -> Workspace:
        """Provision an isolated workspace for ``case``."""

    @abstractmethod
    def run_agent(
        self, workspace: Workspace, case: EvalCase, context: ContextPackage | None
    ) -> AgentRun:
        """Run the agent against the case, returning the raw execution result."""

    @abstractmethod
    def run_tests(self, workspace: Workspace, case: EvalCase) -> AgentRun:
        """Execute the case's test commands, returning an updated AgentRun."""

    @abstractmethod
    def capture_diff(self, workspace: Workspace) -> str:
        """Return the unified diff produced in the workspace."""

    @abstractmethod
    def cleanup_workspace(self, workspace: Workspace) -> None:
        """Tear down the workspace and release its resources."""
