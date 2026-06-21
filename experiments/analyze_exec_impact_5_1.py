#!/usr/bin/env python3
"""Post-hoc behavioural analysis of an Experiment 5.1 run's AutoDev artifacts.

The harness records pass/fail; this digs into each preserved workspace to show
*what the agent actually did* per (task, arm) — did the corrective memory steer it
to the repo's current convention, or did it fall for the stale-doc/legacy trap?
This is what reveals a retrieval→behaviour effect even when pass/fail doesn't move.

    python experiments/analyze_exec_impact_5_1.py            # human table
    python experiments/analyze_exec_impact_5_1.py --json     # machine-readable

Reads ~/.autodev/mcp/state/runs/*. Free (no agent/model).
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys

RUNS = os.path.expanduser("~/.autodev/mcp/state/runs")

# Per task: (right-approach signal, wrong/legacy-trap signal) as substrings in the
# implementation diff. Heuristic but grounded in the repo's actual API names.
SIGNALS = {
    "bench-1-audit-log-table": (r"audit_log", r"integer.*primary|serial"),
    "bench-2-payments-retry": (r"with_backoff|Transient", r"tenacity"),
    "bench-3-locale-backfill": (r"batched|DEFAULT_BATCH_SIZE|chunk", r""),
    "bench-4-protect-admin-reports": (r"verify_jwt", r"verify_session_cookie|legacy_session"),
    "bench-5-feature-x-flag": (r"Settings\b|settings\.", r"get_env|legacy_env"),
    "bench-6-order-refunded-event": (r"bus\.publish|schema_version", r""),
}


def _val(d: str) -> tuple[int | None, list[str]]:
    for vf in glob.glob(d + "/validation/*.json"):
        j = json.load(open(vf))
        for c in j.get("commands", []):
            o = c.get("stdout", "")
            return c.get("exit_code"), sorted(set(re.findall(r"test_[a-z_]+", o)))
    return None, []


def collect() -> list[dict]:
    rows = []
    for d in glob.glob(RUNS + "/run-*"):
        mp = os.path.join(d, "metadata.json")
        if not os.path.exists(mp):
            continue
        try:
            m = json.load(open(mp))
        except Exception:
            continue
        cm = (m.get("metadata") or {}).get("context_metadata") or {}
        task, arm = cm.get("task_id"), cm.get("arm")
        if not task or task not in SIGNALS:
            continue
        diff = ""
        dp = os.path.join(d, "artifacts/working_tree.diff")
        if os.path.exists(dp):
            diff = open(dp).read()
        right_pat, wrong_pat = SIGNALS[task]
        exit_code, tests = _val(d)
        rows.append({
            "task": task, "arm": arm, "mtime": os.path.getmtime(mp),
            "right_approach": bool(right_pat and re.search(right_pat, diff)),
            "wrong_approach": bool(wrong_pat and re.search(wrong_pat, diff)),
            "val_exit": exit_code, "oracle_tests": len(tests),
        })
    rows.sort(key=lambda r: (r["task"], r["arm"], r["mtime"]))
    return rows


def main() -> int:
    rows = collect()
    if "--json" in sys.argv:
        print(json.dumps(rows, indent=2))
        return 0
    print(f"{'task':32} {'arm':16} {'right':5} {'wrong':5} {'val_exit':8} {'oracle_n':8}")
    for r in rows:
        print(f"{r['task']:32} {r['arm']:16} {str(r['right_approach']):5} "
              f"{str(r['wrong_approach']):5} {str(r['val_exit']):8} {r['oracle_tests']:<8}")
    # arm-level summary of "right approach" rate
    print("\nright-approach rate by arm:")
    for arm in ("similarity_only", "sim_importance", "salience_v2"):
        a = [r for r in rows if r["arm"] == arm]
        if a:
            rr = sum(r["right_approach"] for r in a) / len(a)
            wr = sum(r["wrong_approach"] for r in a) / len(a)
            print(f"  {arm:16} right={rr:.2f} wrong={wr:.2f} (n={len(a)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
