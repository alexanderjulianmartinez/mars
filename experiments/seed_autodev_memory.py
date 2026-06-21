#!/usr/bin/env python
"""Seed Experiment 5's task-specific memories into AutoDev's memory store.

Reads the ``seed_memories`` blocks from an issues YAML (the Mars task suite) and
writes them into AutoDev's file-backed memory store for the benchmark repo, using
the record ids declared there — so AutoDev's ``retrieved_context`` lines up with
Mars's ``gold`` (and recall / ContradictionAvoidanceRate are real).

Memory is per-repo: all tasks' memories share the repo namespace, so each issue's
retrieval query surfaces its own relevant subset and treats the rest as distractors.

Run with the AutoDev venv (it imports ``autodev``):

    ~/git/autodev/.venv/bin/python experiments/seed_autodev_memory.py \
        --issues-file experiments/issues.yaml --work-dir ~/.autodev/mcp

Idempotent: clears the repo namespace, then re-seeds the exact declared set.
Inspect with:  autodev memory show <owner/repo> --work-dir <work-dir>
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from autodev.integrations.memory import FileMemoryProvider, MemoryKind, MemoryRecord

# How old a non-"recent" memory is (matches the experiment_seed convention so the
# recency-decay term in salience_v2 has range). Recent memories are written ~now.
OLD_DAYS = 120


def _kind(value: str) -> MemoryKind:
    try:
        return MemoryKind(value)
    except ValueError:
        return MemoryKind.RUN_SUMMARY


def _records(tasks: list[dict], now: datetime) -> list[MemoryRecord]:
    records: list[MemoryRecord] = []
    seen: set[str] = set()
    for t in tasks:
        repo = t["repo"]
        for m in t.get("seed_memories", []):
            rid = m["id"]
            if rid in seen:  # shared id across tasks → seed once
                continue
            seen.add(rid)
            created = now if m.get("recent") else now - timedelta(days=OLD_DAYS)
            content = str(m["content"]).strip()
            records.append(MemoryRecord(
                record_id=rid,
                repo=repo,
                kind=_kind(m.get("kind", "run_summary")),
                title=content.split(":", 1)[0][:80],
                content=content,
                metadata={"importance": str(float(m.get("importance", 0.5)))},
                created_at=created,
            ))
    return records


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--issues-file", required=True)
    ap.add_argument("--work-dir", default="~/.autodev/mcp")
    ap.add_argument("--keep-existing", action="store_true")
    args = ap.parse_args()

    data = yaml.safe_load(Path(args.issues_file).read_text()) or {}
    tasks = data.get("tasks") or data.get("cases") or []
    if not tasks:
        print("no tasks in issues file"); return 1

    state_root = Path(args.work_dir).expanduser() / "state" / "memory"
    provider = FileMemoryProvider(state_root)
    records = _records(tasks, datetime.now(timezone.utc))
    repos = sorted({r.repo for r in records})

    if not args.keep_existing:
        for repo in repos:
            removed = provider.clear(repo)
            print(f"cleared {removed} existing record(s) for {repo}")
    for r in records:
        provider.store(r)
    print(f"seeded {len(records)} memories across {len(repos)} repo namespace(s): {', '.join(repos)}")
    for repo in repos:
        got = provider.list_records(repo)
        print(f"  {repo}: {len(got)} records -> {sorted(r.record_id for r in got)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
