"""EvalRunner — orchestrates a single evaluation end to end.

Pipeline per case:

    1. Ask Cortex for the context package (Mars does not generate context).
    2. Ask AutoDev to create a workspace, run the agent, and run tests
       (Mars does not execute anything itself).
    3. Merge the agent run with its test results.
    4. Check the case's success criteria and score the run.
    5. Persist the context package, agent run, and resulting EvalRun.

The runner owns none of the execution or context logic — it only sequences the
providers and measures the outcome.
"""

from __future__ import annotations

import uuid

from mars.models import (
    AgentRun,
    AgentRunStatus,
    EvalCase,
    EvalRun,
    EvalStatus,
    SuccessCriterion,
)
from mars.providers.base import AutoDevProvider, CortexProvider
from mars.scoring.composite import CompositeScorer, default_composite
from mars.storage.repository import Repository


class EvalRunner:
    def __init__(
        self,
        cortex: CortexProvider,
        autodev: AutoDevProvider,
        repository: Repository | None = None,
        scorer: CompositeScorer | None = None,
    ) -> None:
        self.cortex = cortex
        self.autodev = autodev
        self.repository = repository
        self.scorer = scorer or default_composite()

    def run_case(self, case: EvalCase) -> EvalRun:
        context = self.cortex.get_context_for_case(case)

        workspace = self.autodev.create_workspace(case, context)
        try:
            agent_run = self.autodev.run_agent(workspace, case, context)
            test_run = self.autodev.run_tests(workspace, case)
            agent_run = self._merge_tests(agent_run, test_run, workspace)
        finally:
            self.autodev.cleanup_workspace(workspace)

        criteria_met = self._check_criteria(case, agent_run)
        result = self.scorer.score(case, agent_run)

        status, failure_reason = self._verdict(agent_run, criteria_met)

        # Surface structured scorer extras (noise + literal results) on the run.
        noisy_files: list[str] = []
        literal_results: dict[str, bool] = {}
        for comp in result.components:
            if comp.scorer == "noise":
                noisy_files = list(comp.data.get("noisy_files", []))
            elif comp.scorer == "literal_instruction":
                literal_results = dict(comp.data.get("literal_results", {}))

        eval_run = EvalRun(
            id=f"eval-{uuid.uuid4().hex[:12]}",
            suite_id=case.suite_id,
            case_id=case.id,
            context_package_id=context.id,
            agent_run_id=agent_run.id,
            agent=agent_run.agent,
            model=agent_run.model,
            score=result.score,
            status=status,
            duration_ms=agent_run.runtime_ms,
            cost_usd=agent_run.cost_usd,
            failure_reason=failure_reason,
            score_components=result.components,
            test_results=agent_run.test_results,
            criteria_met=criteria_met,
            evaluation_summary=self._summary(case, status, result.score, criteria_met),
            setup_commands=list(case.setup_commands),
            acceptance_criteria=list(case.acceptance_criteria),
            literal_results=literal_results,
            noisy_files=noisy_files,
        )

        if self.repository is not None:
            self.repository.save_context_package(context)
            self.repository.save_agent_run(agent_run)
            self.repository.save_eval_run(eval_run)

        return eval_run

    def run_suite(self, cases: list[EvalCase]) -> list[EvalRun]:
        return [self.run_case(case) for case in cases]

    # -- helpers ---------------------------------------------------------- #

    @staticmethod
    def _merge_tests(agent_run: AgentRun, test_run: AgentRun, workspace) -> AgentRun:
        """Fold the test-only run's results back into the main agent run."""
        merged = agent_run.model_copy(deep=True)
        if test_run.test_results:
            merged.test_results = test_run.test_results
        if not merged.diff:
            captured = ""  # capture_diff is a no-op in the mock; real providers may differ
            merged.diff = captured
        return merged

    @staticmethod
    def _check_criteria(case: EvalCase, run: AgentRun) -> dict[str, bool]:
        results: dict[str, bool] = {}
        tests_pass = bool(run.test_results) and all(t.passed for t in run.test_results)
        for criterion in case.success_criteria:
            if criterion == SuccessCriterion.TESTS_PASS:
                met = tests_pass
            elif criterion == SuccessCriterion.DIFF_NONEMPTY:
                met = bool(run.diff.strip())
            elif criterion == SuccessCriterion.ENDPOINT_EXISTS:
                # Proxy: success + passing tests imply the artifact was created.
                met = run.status == AgentRunStatus.SUCCESS and tests_pass
            elif criterion == SuccessCriterion.NO_UNRELATED_CHANGES:
                met = len(run.files_changed) <= 3
            elif criterion == SuccessCriterion.WITHIN_TIMEOUT:
                met = run.runtime_ms <= case.timeout_seconds * 1000
            else:  # pragma: no cover - defensive
                met = False
            results[criterion.value] = met
        return results

    @staticmethod
    def _verdict(run: AgentRun, criteria_met: dict[str, bool]) -> tuple[EvalStatus, str | None]:
        if run.status == AgentRunStatus.ERROR:
            return EvalStatus.ERROR, "agent run errored"
        if run.status == AgentRunStatus.TIMEOUT:
            return EvalStatus.FAILED, "agent run timed out"
        unmet = [name for name, met in criteria_met.items() if not met]
        if unmet:
            return EvalStatus.FAILED, "unmet criteria: " + ", ".join(unmet)
        if run.status != AgentRunStatus.SUCCESS:
            return EvalStatus.FAILED, "agent did not succeed"
        return EvalStatus.PASSED, None

    @staticmethod
    def _summary(case: EvalCase, status: EvalStatus, score: float, criteria: dict[str, bool]) -> str:
        met = sum(1 for v in criteria.values() if v)
        return (
            f"{case.id}: {status.value.upper()} score={score:.1f} "
            f"criteria={met}/{len(criteria)}"
        )
