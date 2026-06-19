"""Policy/audit hooks — extension point for future Sentinel integration.

Sentinel (policy, trust, audit, governance) is out of scope for this task, but
Apollo invokes a :class:`PolicyHook` around runs so a Sentinel implementation
can later enforce policy or record an audit trail without changing the runner.
The default is a no-op.
"""

from __future__ import annotations

from mars.models import EvalCase, EvalRun


class PolicyHook:
    """Lifecycle callbacks fired by the experiment runner.

    A future Sentinel hook can deny a run (raise), redact, or audit by
    overriding these. Default behaviour is to do nothing.
    """

    def before_run(self, experiment_id: str, arm: str, case: EvalCase, trial: int) -> None: ...

    def after_run(
        self, experiment_id: str, arm: str, case: EvalCase, trial: int, eval_run: EvalRun
    ) -> None: ...

    def on_experiment_complete(self, experiment_id: str) -> None: ...


class NoOpPolicyHook(PolicyHook):
    """Default hook: permits everything, records nothing."""
