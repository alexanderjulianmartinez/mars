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


class LiteralCheckType(str, Enum):
    """Diff-based checks the LiteralInstructionScorer can evaluate."""

    TEXT_PRESENT = "text_present"
    TEXT_ABSENT = "text_absent"
    FILE_EXISTS = "file_exists"
    FILE_NOT_EXISTS = "file_not_exists"
    FILE_RENAMED = "file_renamed"
    CHANGED_FILE_MATCHES = "changed_file_matches"


class LiteralCheck(BaseModel):
    """A single machine check for a literal requirement."""

    model_config = ConfigDict(extra="forbid")

    type: LiteralCheckType
    pattern: str | None = None  # for text_present / text_absent / changed_file_matches
    path: str | None = None  # for file_exists / file_not_exists
    from_path: str | None = None  # for file_renamed
    to_path: str | None = None  # for file_renamed


class LiteralRequirement(BaseModel):
    """An explicit, literal instruction the agent was asked to follow."""

    model_config = ConfigDict(extra="forbid")

    id: str
    description: str = ""
    required: bool = True
    check: LiteralCheck


class GoldMemory(BaseModel):
    """Ground-truth relevance label for a memory (Track B retrieval metrics)."""

    model_config = ConfigDict(extra="forbid")

    memory_id: str
    relevant: bool = True
    target: bool = False  # the single must-find memory, if any


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
    # GitHub issue / Jira ticket backing this case. Required for real AutoDev
    # agentic runs (autodev_start_run consumes an issue URL); optional otherwise.
    issue_url: str | None = None
    task_prompt: str
    context_profile: str = "default"
    setup_commands: list[str] = Field(default_factory=list)
    test_commands: list[str] = Field(default_factory=list)
    success_criteria: list[SuccessCriterion] = Field(default_factory=list)
    timeout_seconds: int = 600

    # --- agentic-eval extensions (Track A) ---
    # Free-text acceptance criteria propagated to AutoDev / shown in reports.
    acceptance_criteria: list[str] = Field(default_factory=list)
    # Deterministic review checks for AutoDev's review gate (Experiment 5.1
    # contract): {criterion, check, value?} where check ∈ validation_passes /
    # files_include / files_exclude / diff_contains / diff_absent. Propagated to
    # autodev_start_run; empty for non-agentic cases.
    acceptance_checks: list[dict[str, Any]] = Field(default_factory=list)
    # File globs (support ** ) for the diff-quality / noise scorers.
    expected_files: list[str] = Field(default_factory=list)
    allowed_files: list[str] = Field(default_factory=list)
    forbidden_files: list[str] = Field(default_factory=list)
    # Explicit literal instructions checked by LiteralInstructionScorer.
    literal_requirements: list[LiteralRequirement] = Field(default_factory=list)

    # --- retrieval-experiment extensions (Track B) ---
    gold_memories: list[GoldMemory] = Field(default_factory=list)


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
    # Optional enrichment AutoDev may return (None/empty = not provided by the
    # contract, so consumers mark the metric "missing" rather than fabricate it).
    token_usage: int | None = None
    review_decision: str | None = None  # e.g. "approved" / "changes_requested"
    # Memories the run actually retrieved into context: [{id, score, ...}].
    retrieved_context: list[dict[str, Any]] = Field(default_factory=list)


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
    data: dict[str, Any] = Field(default_factory=dict)


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

    # Propagated from the case for transparency in reports/replay.
    setup_commands: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    # Per-requirement literal-instruction results (id -> passed).
    literal_results: dict[str, bool] = Field(default_factory=dict)
    # Files flagged as noisy/unrelated by the noise scorer.
    noisy_files: list[str] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=_utcnow)
