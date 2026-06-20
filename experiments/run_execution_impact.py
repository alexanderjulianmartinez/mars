#!/usr/bin/env python3
"""Experiment 5 — Execution Impact study runner.

Do retrieval gains improve real agent execution? Answering this needs **real
AutoDev runs**. Mars already ships a real ``AutoDevMCPProvider`` that speaks the
verified AutoDev tool contract; this runner wires Experiment 5 to it.

Modes (default still honest-stops — never fabricates):

- (no flags)                  honest-stop + precise AutoDev availability report.
- ``--simulate``              non-evidential apparatus validation (``evidential=false``).
- ``--real-autodev``          use real AutoDev (requires ``MARS_AUTODEV_MCP_*``).
    - ``--connectivity-check``  deterministic ``prepare_workspace`` (zero LLM) — proves
                                Mars↔AutoDev wiring. NOT evidential (no agent invoked).
    - ``--issues-file PATH``    run the three arms over real issue-backed tasks
                                (agentic, paid on AutoDev's side) → ``evidential=true``.
    - ``--dry-run``             real agentic run that creates no PR (still evidential).
    - ``--limit-tasks N`` / ``--limit-arms N`` / ``--model NAME``

Paid safety: real agentic runs only happen with explicit ``--real-autodev`` +
``--issues-file``; nothing spends model $ by default.

Smoke:  python experiments/run_execution_impact.py --real-autodev --dry-run --connectivity-check
Full:   python experiments/run_execution_impact.py --real-autodev --dry-run --issues-file issues.yaml --limit-tasks 30
"""

from __future__ import annotations

import sys
from pathlib import Path

from mars.agents import using_real_autodev, using_real_cortex
from mars.memory.execution_impact import (
    AutoDevExecutionImpactAdapter,
    autodev_availability,
    build_internal_benchmark,
    format_availability_report,
    render_report,
    retrieval_arms,
    run_execution_impact,
    run_execution_impact_real,
    save_result,
)


def _arg(flag: str, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def _load_issue_cases(path: Path, limit: int | None):
    import yaml

    from mars.models import EvalCase

    data = yaml.safe_load(path.read_text()) or {}
    raw = data.get("tasks") or data.get("cases") or []
    cases = []
    for t in raw[: limit or None]:
        cases.append(EvalCase(
            id=t["id"], suite_id=t.get("suite_id", "execution-impact"),
            name=t.get("name", t["id"]), task_prompt=t.get("task_prompt", t.get("name", t["id"])),
            repo=t.get("repo", ""), issue_url=t.get("issue_url"),
            setup_commands=t.get("setup_commands", []), test_commands=t.get("test_commands", []),
            acceptance_criteria=t.get("acceptance_criteria", []),
            allowed_files=t.get("allowed_files", []), forbidden_files=t.get("forbidden_files", []),
        ))
    return cases


def _connectivity_check() -> int:
    """Deterministic real call (prepare_workspace) — proves wiring, zero LLM."""
    from mars.models import EvalCase
    from mars.providers.autodev_mcp import AutoDevMCPProvider

    prov = AutoDevMCPProvider.from_env(agentic=False, source_path=str(Path.cwd()),
                                       isolation_mode="branch")
    case = EvalCase(id="exec-impact-connectivity", suite_id="smoke", name="connectivity",
                    task_prompt="connectivity probe")
    try:
        ws = prov.create_workspace(case, None)
    except Exception as exc:  # noqa: BLE001 - report the exact error
        print(f"CONNECTIVITY FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 4
    finally:
        try:
            prov.close()
        except Exception:  # noqa: BLE001
            pass
    print("REAL AutoDev connectivity OK (deterministic, zero LLM).")
    print(f"  run_id: {ws.id}")
    print(f"  workspace: {ws.path}")
    print("  This proves Mars can call real AutoDev. It is NOT evidence for the "
          "A/B/C execution comparison (no agent/model was invoked).")
    return 0


def main() -> int:
    simulate = "--simulate" in sys.argv
    real = "--real-autodev" in sys.argv
    dry_run = "--dry-run" in sys.argv
    limit_tasks = int(_arg("--limit-tasks", 0)) or None
    limit_arms = int(_arg("--limit-arms", 0)) or None
    model = _arg("--model", "claude-opus")
    issues_file = _arg("--issues-file")

    diag = autodev_availability()

    if real:
        if not diag["available"]:
            print("Cannot run --real-autodev: AutoDev is not reachable.\n", file=sys.stderr)
            print(format_availability_report(diag), file=sys.stderr)
            return 2
        print(format_availability_report(diag), file=sys.stderr)

        if "--connectivity-check" in sys.argv:
            return _connectivity_check()

        if not issues_file:
            print(
                "\nREAL agentic run needs issue-backed tasks (the AutoDev `start_run` "
                "contract takes `issue_url` only). Provide --issues-file <yaml> with "
                "tasks [{id, issue_url, repo, setup_commands, acceptance_criteria, "
                "test_commands}].\n\n"
                "NOTE: `start_run` has no context-injection parameter yet, so by default "
                "the per-arm retrieval (A/B/C) is provenance only. Mars is wired to inject "
                "it the moment AutoDev accepts the arg — add --send-retrieval "
                "[--retrieval-arg-name NAME] to send it (and real per-arm retrieval "
                "metrics come back via get_run's retrieved_context).\n"
                "Run --connectivity-check to verify wiring without spend.",
                file=sys.stderr,
            )
            return 3

        cases = _load_issue_cases(Path(issues_file), limit_tasks)
        if not cases:
            print(f"No tasks found in {issues_file}.", file=sys.stderr)
            return 3
        send_retrieval = "--send-retrieval" in sys.argv  # only once AutoDev accepts the arg
        retrieval_arg_name = _arg("--retrieval-arg-name", "retrieval_strategy")
        # arm.name -> AutoDev retrieval value (the experimental variable, once injectable)
        arm_retrieval = {
            "A_similarity_only": "similarity_only",
            "B_sim_importance": "sim_importance",
            "C_salience_v2": "salience_v2",
        }
        from mars.providers.autodev_mcp import AutoDevMCPProvider
        autodev = AutoDevMCPProvider.from_env(
            agentic=True, dry_run=dry_run, model=model,
            retrieval_arg_name=retrieval_arg_name, send_retrieval=send_retrieval,
        )
        adapter = AutoDevExecutionImpactAdapter(
            autodev, dry_run=dry_run, arm_retrieval=arm_retrieval, send_retrieval=send_retrieval,
        )
        if send_retrieval:
            inject = (f"Per-arm retrieval INJECTED via start_run '{retrieval_arg_name}' "
                      f"(A/B/C are real different retrievals).")
        else:
            inject = ("Per-arm retrieval NOT injected (start_run has no context arg yet); "
                      "arm is provenance only. Enable with --send-retrieval once AutoDev "
                      "accepts the parameter.")
        notes = [
            f"REAL AutoDev agentic run (dry_run={dry_run}); model={model}.",
            inject,
            "Execution metrics are real; token usage / review / retrieved context are "
            "used when AutoDev returns them, else marked missing (never fabricated).",
        ]
        arms = retrieval_arms()[: limit_arms or None]
        if limit_arms:
            notes.append(f"limited to {len(arms)} arm(s).")
        result = run_execution_impact_real(adapter, cases, trials=1, notes=notes)
        try:
            autodev.close()
        except Exception:  # noqa: BLE001
            pass
        save_result(result)
        print(render_report(result))
        return 0

    if not simulate:
        # honest-stop, but now with a precise availability report
        print("BLOCKED — no real execution evidence was produced (honest stop).\n", file=sys.stderr)
        print(format_availability_report(diag), file=sys.stderr)
        print(
            "\nReal AutoDev IS reachable when MARS_AUTODEV_MCP_* is set (see above). Then:\n"
            "  python experiments/run_execution_impact.py --real-autodev --dry-run --connectivity-check\n"
            "For non-evidential apparatus validation: --simulate.",
            file=sys.stderr,
        )
        return 2

    # simulation
    notes = [
        "SIMULATION ONLY — execution_real=False, evidential=False.",
        "Outcomes come from SimulatedOutcomeModel: success is DEFINED to rise with "
        "retrieval relevance and fall under retrieved contradictions. NOT evidence.",
        f"Real Cortex configured: {using_real_cortex()}; real AutoDev configured: {using_real_autodev()}.",
    ]
    result = run_execution_impact(build_internal_benchmark(), trials=5, execution_real=False, notes=notes)
    save_result(result)
    print(render_report(result))
    print("\n[reminder] Simulation, not evidence. See docs/SALIENCE_MEMORY_EXECUTION_IMPACT.md.",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
