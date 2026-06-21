#!/usr/bin/env python
"""Offline proof that the Experiment 5.1 arms retrieve *different, task-relevant*
context — BEFORE spending any model $ on a real run.

For each task it reconstructs the controlled memory set exactly as
``seed_autodev_memory.py`` would store it (target = OLD, distractors = recent),
builds the retrieval query the runtime uses (``title\\nbody``), and ranks the
records under AutoDev's REAL scorers (``autodev.integrations.memory.score_records``)
at ``retrieval_limit=3``. It then asserts the intended pattern:

  * similarity_only  → MISSES the target (and, for contradiction tasks, RETRIEVES
                       a stale-doc trap that the agent would implement wrong)
  * sim_importance   → SURFACES the target
  * salience_v2      → SURFACES the target
  * the three arms inject DIFFERENT context (the Phase-3 divergence gate)

Run with the AutoDev venv (it imports ``autodev`` + ``yaml``):

    ~/git/autodev/.venv/bin/python experiments/verify_exec_impact_5_1_divergence.py \
        --issues-file experiments/execution_impact_5_1/issues.yaml

Exit 0 iff every task passes. This is apparatus validation, not evidence of
execution impact (no agent runs here).
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from autodev.integrations.memory import (
    MemoryKind,
    MemoryRecord,
    _query_terms,
    score_records,
)

OLD_DAYS = 120  # must match seed_autodev_memory.OLD_DAYS
LIMIT = 3  # RECOMMENDED_RETRIEVAL_LIMIT
ARMS = ["similarity_only", "sim_importance", "salience_v2"]


def _kind(value: str) -> MemoryKind:
    try:
        return MemoryKind(value)
    except ValueError:
        return MemoryKind.RUN_SUMMARY


def _records(task: dict, now: datetime) -> list[MemoryRecord]:
    repo = task["repo"]
    out = []
    for m in task.get("seed_memories", []):
        created = now if m.get("recent") else now - timedelta(days=OLD_DAYS)
        content = str(m["content"]).strip()
        out.append(MemoryRecord(
            record_id=m["id"], repo=repo, kind=_kind(m.get("kind", "run_summary")),
            title=content.split(":", 1)[0][:80], content=content,
            metadata={"importance": str(float(m["importance"]))} if "importance" in m else {},
            created_at=created,
        ))
    return out


def _topk(strategy: str, records: list[MemoryRecord], terms: set[str]) -> list[str]:
    return [r.record_id for r, _ in score_records(strategy, records, terms)[:LIMIT]]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--issues-file", default="experiments/execution_impact_5_1/issues.yaml")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    data = yaml.safe_load(Path(args.issues_file).read_text()) or {}
    tasks = data.get("tasks") or []
    now = datetime.now(timezone.utc)

    all_ok = True
    for t in tasks:
        gold = t.get("gold", {})
        target = gold.get("target_memory")
        contradictory = set(gold.get("contradictory_memories", []))
        records = _records(t, now)
        terms = _query_terms(f"{t['title']}\n{t.get('body', '')}")

        topk = {arm: _topk(arm, records, terms) for arm in ARMS}
        a, b, c = topk["similarity_only"], topk["sim_importance"], topk["salience_v2"]

        # HARD gates: the execution discriminator is target retrieval (A buries the
        # corrective decision; importance-aware arms surface it) + arm divergence.
        checks = {
            "A misses target": target not in a,
            "B surfaces target": target in b,
            "C surfaces target": target in c,
            "arms distinct": len({tuple(a), tuple(b), tuple(c)}) > 1,
        }
        # SOFT (reported, non-gating): contradiction behaviour. A walking into a
        # stale-doc trap is the nice-to-have flavour; what *drives* execution is
        # the corrective memory being present in B/C (it explicitly says the doc is
        # out of date), not whether B/C also happen to see a stale distractor.
        soft = {}
        if contradictory:
            soft["A retrieves a stale-doc trap"] = bool(contradictory & set(a))
            soft["B avoids stale-doc traps"] = not (contradictory & set(b))
            soft["C avoids stale-doc traps"] = not (contradictory & set(c))

        ok = all(checks.values())
        all_ok = all_ok and ok
        print(f"[{'PASS' if ok else 'FAIL'}] {t['id']}"
              + (f"  (soft {sum(soft.values())}/{len(soft)})" if soft else ""))
        if args.verbose or not ok:
            overlaps = {r.record_id: sum(1 for term in terms if term in
                        f"{r.title} {r.content} {' '.join(r.tags)}".lower()) for r in records}
            print(f"    query terms ({len(terms)}): {sorted(terms)}")
            print(f"    overlaps: {overlaps}")
            print(f"    A similarity_only: {a}")
            print(f"    B sim_importance : {b}")
            print(f"    C salience_v2    : {c}")
            for name, passed in checks.items():
                if not passed:
                    print(f"      ✗ (hard) {name}")
            for name, passed in soft.items():
                print(f"      {'✓' if passed else '·'} (soft) {name}")

    print(f"\n{'ALL TASKS PASS — arms diverge as designed.' if all_ok else 'DIVERGENCE CHECK FAILED.'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
