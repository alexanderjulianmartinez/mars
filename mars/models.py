"""Domain model for Mars.

These are the pure, transport-agnostic data structures that flow through the
evaluation pipeline:

    EvalSuite -> EvalCase -> ContextPackage (from Cortex)
                          -> AgentRun       (from AutoDev)
                          -> EvalRun        (scored result, owned by Mars)

Everything here is a Pydantic model so it can be validated, serialized to JSON
for reporting/replay, and round-tripped through storage.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AgentRunStatus(str, Enum):
    """Outcome of an AutoDev execution, independent of evaluation."""

    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"
    TIMEOUT = "timeout"


class EvalStatus(str, Enum):
    """Outcome of a Mars evaluation of an AgentRun."""

    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


class SuccessCriterion(str, Enum):
    """Named, machine-checkable success conditions a case can require."""

    TESTS_PASS = "tests_pass"
    ENDPOINT_EXISTS = "endpoint_exists"
    NO_UNRELATED_CHANGES = "no_unrelated_changes"
    DIFF_NONEMPTY = "diff_nonempty"
    WITHIN_TIMEOUT = "within_timeout"


# --------------------------------------------------------------------------- #
# Benchmark definitions (authored as YAML, see suites/)
# --------------------------------------------------------------------------- #


class EvalCase(BaseModel):
    """A single benchmark task."""

    model_config = ConfigDict(extra="forbid")

    id: str
    suite_id: str
    name: str
    description: str = ""
    repo: str = ""
    task_prompt: str
    context_profile: str = "default"
    setup_commands: list[str] = Field(default_factory=list)
    test_commands: list[str] = Field(default_factory=list)
    success_criteria: list[SuccessCriterion] = Field(default_factory=list)
    timeout_seconds: int = 600


class EvalSuite(BaseModel):
    """A collection of related benchmark cases."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    cases: list[EvalCase] = Field(default_factory=list)

    def case(self, case_id: str) -> EvalCase:
        for c in self.cases:
            if c.id == case_id:
                return c
        raise KeyError(f"case {case_id!r} not found in suite {self.id!r}")


# --------------------------------------------------------------------------- #
# Inputs consumed from Cortex and AutoDev
# --------------------------------------------------------------------------- #


class ContextPackage(BaseModel):
    """Context returned by Cortex for a case's ``context_profile``."""

    model_config = ConfigDict(extra="forbid")

    id: str
    profile: str
    version: str
    generated_at: datetime = Field(default_factory=_utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TestResult(BaseModel):
    """Result of a single test command reported by AutoDev."""

    model_config = ConfigDict(extra="forbid")

    name: str
    passed: bool
    duration_ms: int = 0
    output: str = ""


class AgentRun(BaseModel):
    """Raw execution result returned by AutoDev for a case."""

    model_config = ConfigDict(extra="forbid")

    id: str
    agent: str
    model: str
    status: AgentRunStatus
    logs: str = ""
    diff: str = ""
    runtime_ms: int = 0
    cost_usd: float = 0.0
    test_results: list[TestResult] = Field(default_factory=list)
    files_changed: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Mars output
# --------------------------------------------------------------------------- #


class ScoreComponent(BaseModel):
    """One scorer's contribution to the composite score."""

    model_config = ConfigDict(extra="forbid")

    scorer: str
    value: float  # 0-100
    weight: float
    detail: str = ""


class EvalRun(BaseModel):
    """A Mars evaluation of a single AgentRun against a single EvalCase.

    This is the central, replayable record. It links the case, the context
    package used, the agent run, and the computed score, and stores enough
    metadata to re-score or replay later.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    suite_id: str
    case_id: str
    context_package_id: str | None = None
    agent_run_id: str

    agent: str
    model: str

    score: float = 0.0  # composite, 0-100
    status: EvalStatus = EvalStatus.ERROR
    duration_ms: int = 0
    cost_usd: float = 0.0
    failure_reason: str | None = None

    score_components: list[ScoreComponent] = Field(default_factory=list)
    test_results: list[TestResult] = Field(default_factory=list)
    criteria_met: dict[str, bool] = Field(default_factory=dict)
    evaluation_summary: str = ""

    created_at: datetime = Field(default_factory=_utcnow)
