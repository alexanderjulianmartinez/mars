"""Experiment 5 real-AutoDev wiring: availability, adapter, evidence flags.

No live server: a FakeToolCaller returns canned AutoDev envelopes (the same
pattern as test_autodev_mcp.py), so the adapter's AgentRun→SampleRecord
conversion and the evidential flags are exercised without spending anything.
"""

from __future__ import annotations

import pytest

from mars.memory.execution_impact import (
    AutoDevExecutionImpactAdapter,
    autodev_availability,
    format_availability_report,
    retrieval_arms,
    run_execution_impact,
    run_execution_impact_real,
)
from mars.models import EvalCase
from mars.providers.autodev_mcp import AutoDevMCPProvider


def env(data=None, *, ok=True, error=None):
    return {"ok": ok, "data": data or {}, "error": error}


class FakeToolCaller:
    def __init__(self, responses: dict) -> None:
        self.responses = {k: (v if isinstance(v, list) else [v]) for k, v in responses.items()}
        self.calls: list[tuple[str, dict]] = []

    def call_tool(self, name: str, arguments: dict):
        self.calls.append((name, arguments))
        queue = self.responses.get(name) or [env({})]
        return queue.pop(0) if len(queue) > 1 else queue[0]

    def close(self):
        pass


ARM_A = retrieval_arms()[0]


def _agentic_provider(status="completed", dry_run=True, enriched=False, **kw):
    meta = {"cost_usd": 0.21}
    run = {"run": {"status": status, "started_at": "2026-06-20T00:00:00Z",
                   "completed_at": "2026-06-20T00:02:00Z", "metadata": meta},
           "diff": "--- a/x\n+++ b/x\n@@ +1 @@\n+ok\n",
           "review_results": [{"metadata": {"files_modified": ["x.py"]}}]}
    if enriched:
        meta["token_usage"] = 4200
        run["review_results"] = [{"decision": "approved", "metadata": {"files_modified": ["x.py"]}}]
        run["retrieved_context"] = [{"id": "m-target", "score": 0.9},
                                    {"id": "m-obsolete", "score": 0.8},
                                    {"id": "m-distractor", "score": 0.7}]
    caller = FakeToolCaller({
        "autodev_start_run": env({"run_id": "run-real-1"}),
        "autodev_get_run": env(run),
        "autodev_validate": env({"commands": [{"command": "pytest", "status": "passed",
                                               "exit_code": 0, "duration_seconds": 1.0}]}),
    })
    return AutoDevMCPProvider(caller, agentic=True, dry_run=dry_run, **kw), caller


# --- 1. availability detection --------------------------------------------- #


def test_availability_detects_absence(monkeypatch):
    for v in ("MARS_AUTODEV_MCP_URL", "MARS_AUTODEV_MCP_COMMAND"):
        monkeypatch.delenv(v, raising=False)
    diag = autodev_availability()
    assert diag["available"] is False
    assert diag["provider"].startswith("MockAutoDevProvider")
    report = format_availability_report(diag)
    # actionable: lists every env var checked + a fix
    assert "MARS_AUTODEV_MCP_COMMAND" in report
    assert "How to fix" in report


def test_availability_detects_presence(monkeypatch):
    monkeypatch.setenv("MARS_AUTODEV_MCP_COMMAND", "/bin/true")
    monkeypatch.setenv("MARS_AUTODEV_MCP_ARGS", "mcp serve")
    monkeypatch.setenv("MARS_AUTODEV_MCP_TRANSPORT", "stdio")
    diag = autodev_availability()
    assert diag["available"] is True
    assert diag["provider"] == "AutoDevMCPProvider"
    assert "stdio" in diag["endpoint_attempted"]


# --- 2. real-provider config parsing --------------------------------------- #


def test_config_from_env_parses_stdio(monkeypatch):
    from mars.providers.autodev_mcp import config_from_env

    monkeypatch.setenv("MARS_AUTODEV_MCP_COMMAND", "/x/autodev")
    monkeypatch.setenv("MARS_AUTODEV_MCP_ARGS", "mcp serve")
    monkeypatch.setenv("MARS_AUTODEV_MCP_TRANSPORT", "stdio")
    cfg = config_from_env()
    assert cfg is not None and cfg.command == "/x/autodev" and cfg.args == ["mcp", "serve"]


# --- 3. adapter conversion AgentRun -> SampleRecord ------------------------ #


def test_adapter_converts_agent_run_to_sample_record():
    provider, caller = _agentic_provider()
    adapter = AutoDevExecutionImpactAdapter(provider, dry_run=True)
    case = EvalCase(id="t1", suite_id="s", name="t1", task_prompt="do it",
                    issue_url="https://github.com/o/r/issues/1", test_commands=["pytest"])
    out = adapter.run_sample(ARM_A, case, None, 0,
                             retrieval={"recall_at_k": 0.8, "mrr": 1.0, "target_found": True})
    rec = out.record
    assert rec.source == "real_autodev"
    assert rec.run_id == "run-real-1"
    assert rec.dry_run is True
    assert rec.success is True  # completed + validation passed
    assert rec.validation_pass is True
    assert rec.cost_usd == pytest.approx(0.21)
    assert rec.recall_at_k == 0.8  # retrieval metrics threaded through (provenance)
    # honest about what AutoDev does not expose
    assert "token_usage" in rec.missing_fields
    assert "review_quality" in rec.missing_fields
    assert out.agent_invoked is True
    # start_run was called with the issue url and dry_run
    start = next(a for n, a in caller.calls if n == "autodev_start_run")
    assert start["issue_url"].endswith("/issues/1") and start["dry_run"] is True


def test_adapter_marks_failure_on_blocked_run():
    provider, _ = _agentic_provider(status="failed")
    adapter = AutoDevExecutionImpactAdapter(provider, dry_run=True)
    case = EvalCase(id="t2", suite_id="s", name="t2", task_prompt="x",
                    issue_url="https://github.com/o/r/issues/2", test_commands=["pytest"])
    rec = adapter.run_sample(ARM_A, case, None, 0).record
    assert rec.success is False
    assert rec.failure_class is not None


# --- 4 & 5. evidential / dry_run flags ------------------------------------- #


def test_agentic_run_is_evidence_eligible_and_marks_dry_run():
    provider, _ = _agentic_provider(dry_run=True)
    adapter = AutoDevExecutionImpactAdapter(provider, dry_run=True)
    case = EvalCase(id="t1", suite_id="s", name="t1", task_prompt="x",
                    issue_url="https://github.com/o/r/issues/1", test_commands=["pytest"])
    out = adapter.run_sample(ARM_A, case, None, 0)
    assert out.agent_invoked is True  # agentic → evidence-eligible
    assert out.record.dry_run is True


def test_real_result_evidential_only_with_agent_invocation():
    # deterministic provider: prepare_workspace + validate, NO agent → not evidence
    caller = FakeToolCaller({
        "autodev_prepare_workspace": env({"run_id": "run-det", "workspace_path": "/tmp/ws"}),
        "autodev_validate": env({"commands": [{"command": "pytest", "status": "passed",
                                               "exit_code": 0, "duration_seconds": 0.5}]}),
    })
    provider = AutoDevMCPProvider(caller, agentic=False, dry_run=True)
    adapter = AutoDevExecutionImpactAdapter(provider, dry_run=True)
    case = EvalCase(id="d1", suite_id="s", name="d1", task_prompt="x", test_commands=["pytest"])
    result = run_execution_impact_real(adapter, [case], trials=1)
    assert result.execution_real is True
    assert result.evidential is False  # no agent invoked → not evidence
    assert result.dry_run is True


# --- 7. simulation stays non-evidential ------------------------------------ #


def test_simulation_is_never_evidential():
    from mars.memory.execution_impact import build_internal_benchmark

    res = run_execution_impact(build_internal_benchmark(n_per_class=2), trials=2)
    assert res.execution_real is False and res.evidential is False


# --- starter issues.example.yaml ------------------------------------------- #


def _runner():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "run_execution_impact", Path("experiments/run_execution_impact.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_example_issues_yaml_parses_with_gold():
    from pathlib import Path

    runner = _runner()
    cases, gold = runner._load_issue_cases(Path("experiments/issues.example.yaml"), None)
    assert len(cases) == 6 and len(gold) == 6
    # every task carries an issue_url, acceptance criteria, and resolvable gold
    for c in cases:
        assert c.issue_url and c.acceptance_criteria
        g = gold[c.id]
        assert g["target_id"] in g["relevant_ids"]  # target counts toward relevant
        assert g["contradictory_ids"]  # each task has an obsolete memory to suppress


def test_gold_from_task_maps_fields():
    runner = _runner()
    g = runner._gold_from_task({
        "id": "t", "task_class": "contradiction",
        "gold": {"target_memory": "m-t", "relevant_memories": ["m-r"],
                 "contradictory_memories": ["m-c"]}})
    assert g["target_id"] == "m-t"
    assert g["relevant_ids"] == {"m-t", "m-r"}
    assert g["contradictory_ids"] == {"m-c"}
    assert runner._gold_from_task({"id": "t"}) is None  # no gold block → None


# --- forward-compat: per-arm retrieval control + enriched output ----------- #


def _issue_case(cid="t1"):
    return EvalCase(id=cid, suite_id="s", name=cid, task_prompt="x",
                    issue_url=f"https://github.com/o/r/issues/{cid}", test_commands=["pytest"])


def test_start_run_carries_retrieval_only_when_enabled():
    # disabled (default): the extra arg is NOT sent (start_run schema is strict).
    prov, caller = _agentic_provider(retrieval_strategy="salience_v2", send_retrieval=False)
    prov.run_agent(prov.create_workspace(_issue_case(), None), _issue_case(), None)
    args = next(a for n, a in caller.calls if n == "autodev_start_run")
    assert "retrieval_strategy" not in args

    # enabled: sent under the configured arg name.
    prov, caller = _agentic_provider(retrieval_strategy="salience_v2", send_retrieval=True,
                                     retrieval_arg_name="retrieval_mode")
    prov.run_agent(prov.create_workspace(_issue_case(), None), _issue_case(), None)
    args = next(a for n, a in caller.calls if n == "autodev_start_run")
    assert args["retrieval_mode"] == "salience_v2"


def test_get_run_enrichment_parsed_into_agent_run():
    prov, _ = _agentic_provider(enriched=True)
    run = prov.run_agent(prov.create_workspace(_issue_case(), None), _issue_case(), None)
    assert run.token_usage == 4200
    assert run.review_decision == "approved"
    assert [m["id"] for m in run.retrieved_context] == ["m-target", "m-obsolete", "m-distractor"]


def test_adapter_uses_enrichment_and_real_retrieval_metrics():
    prov, _ = _agentic_provider(enriched=True)
    adapter = AutoDevExecutionImpactAdapter(prov, dry_run=True)
    gold = {"relevant_ids": {"m-target"}, "target_id": "m-target",
            "contradictory_ids": {"m-obsolete"}}
    rec = adapter.run_sample(ARM_A, _issue_case(), None, 0, gold=gold).record
    # token + review now real → not in missing
    assert rec.token_usage == 4200
    assert rec.review_pass is True
    assert "token_usage" not in rec.missing_fields
    assert "review_pass" not in rec.missing_fields
    # real retrieval metrics from what the run retrieved
    assert rec.target_found is True
    assert rec.recall_at_k == 1.0
    # target (0.9) outranks the obsolete (0.8) → contradiction avoided
    assert rec.contradiction_in_context is False
    assert rec.context_size == 3


def test_adapter_marks_missing_when_enrichment_absent():
    prov, _ = _agentic_provider(enriched=False)
    adapter = AutoDevExecutionImpactAdapter(prov, dry_run=True)
    rec = adapter.run_sample(ARM_A, _issue_case(), None, 0).record
    assert "token_usage" in rec.missing_fields
    assert "review_pass" in rec.missing_fields
    assert "retrieval_metrics" in rec.missing_fields


def test_apply_arm_retrieval_sets_provider_strategy_and_package():
    prov, _ = _agentic_provider(enriched=True, send_retrieval=False)
    adapter = AutoDevExecutionImpactAdapter(
        prov, dry_run=True, send_retrieval=True,
        arm_retrieval={ARM_A.name: "similarity_only"})
    adapter.run_sample(ARM_A, _issue_case(), None, 0)
    assert prov.retrieval_strategy == "similarity_only"
    assert prov.send_retrieval is True
    assert prov.context_package_id == f"exp5-{ARM_A.name}"


def test_start_run_carries_context_package_id_when_enabled():
    prov, caller = _agentic_provider(send_retrieval=True, retrieval_strategy="salience_v2",
                                     context_package_id="exp5-C")
    prov.run_agent(prov.create_workspace(_issue_case(), None), _issue_case(), None)
    args = next(a for n, a in caller.calls if n == "autodev_start_run")
    assert args["retrieval_strategy"] == "salience_v2"
    assert args["context_package_id"] == "exp5-C"


# --- Phase 3 divergence gate ----------------------------------------------- #


def test_arms_distinct_true_when_contexts_differ():
    from mars.memory.execution_impact import _arms_distinct

    injected = {("t1", 0): {"A": ("m1",), "B": ("m2",), "C": ("m3",)}}
    assert _arms_distinct(injected) is True


def test_arms_distinct_false_when_contexts_identical():
    from mars.memory.execution_impact import _arms_distinct

    # every arm injected the same memories (or none) → not a valid comparison
    assert _arms_distinct({("t1", 0): {"A": (), "B": (), "C": ()}}) is False
    assert _arms_distinct({("t1", 0): {"A": ("m1",), "B": ("m1",), "C": ("m1",)}}) is False


def test_valid_comparison_requires_distinct_contexts():
    # Deterministic provider returns no retrieved_context → arms identical → invalid.
    caller = FakeToolCaller({
        "autodev_prepare_workspace": env({"run_id": "run-det", "workspace_path": "/tmp/ws"}),
        "autodev_validate": env({"commands": [{"command": "pytest", "status": "passed",
                                               "exit_code": 0, "duration_seconds": 0.5}]}),
    })
    prov = AutoDevMCPProvider(caller, agentic=False, dry_run=True)
    adapter = AutoDevExecutionImpactAdapter(prov, dry_run=True)
    case = EvalCase(id="d1", suite_id="s", name="d1", task_prompt="x", test_commands=["pytest"])
    result = run_execution_impact_real(adapter, [case], trials=1)
    assert result.arms_distinct is False
    assert result.valid_comparison is False  # no distinct contexts → comparison not claimed
