"""Agentic-evaluation scorers (Track A).

These score a *real AutoDev run's diff* against a case's declared expectations,
so model comparisons differentiate on the things that actually matter: did the
agent change the right files, avoid noise, and follow the literal instructions.

- DiffQualityScorer       — focus/breadth of the change vs expected/forbidden files
- NoiseScorer             — unrelated edits + whitespace/newline churn
- LiteralInstructionScorer — explicit, machine-checkable requirements

All three are graceful no-ops (score 100) when the case declares no relevant
config, so they're safe to include in the default composite.
"""

from __future__ import annotations

from mars.models import AgentRun, EvalCase, LiteralCheck, LiteralCheckType
from mars.scoring.base import ScoreOutcome, Scorer
from mars.scoring.diffutil import FileDiff, matches_any, parse_unified_diff


def _file_diffs(run: AgentRun) -> list[FileDiff]:
    if run.diff.strip():
        return parse_unified_diff(run.diff)
    # No diff text but files were reported: degrade to path-only records.
    return [FileDiff(path=p) for p in run.files_changed]


class DiffQualityScorer(Scorer):
    """Rewards a targeted change touching expected files; penalizes sprawl."""

    name = "diff_quality"

    def __init__(self, max_lines: int = 400) -> None:
        self.max_lines = max_lines

    def score(self, case: EvalCase, run: AgentRun) -> ScoreOutcome:
        fds = _file_diffs(run)
        if not fds:
            return ScoreOutcome(0.0, "empty diff")
        paths = [f.path for f in fds]

        forbidden = [p for p in paths if matches_any(p, case.forbidden_files)]
        if forbidden:
            return ScoreOutcome(0.0, f"forbidden files touched: {forbidden}")

        allowed = case.expected_files + case.allowed_files
        if case.expected_files:
            hit = [p for p in paths if matches_any(p, case.expected_files)]
            if not hit:
                return ScoreOutcome(30.0, "no expected files touched (mostly unrelated)")

        unexpected = (
            [p for p in paths if not matches_any(p, allowed)] if allowed else []
        )
        changed_lines = sum(f.changed_lines for f in fds)
        large = changed_lines > self.max_lines

        if not unexpected and not large:
            return ScoreOutcome(100.0, f"{len(paths)} file(s), {changed_lines} lines; targeted")
        if len(unexpected) <= 1 and not large:
            return ScoreOutcome(70.0, f"minor extra changes: {unexpected or 'large diff'}")
        return ScoreOutcome(40.0, f"noisy/broad: unexpected={unexpected} lines={changed_lines}")


class NoiseScorer(Scorer):
    """Penalizes unrelated edits and whitespace/newline-only churn."""

    name = "noise"

    def score(self, case: EvalCase, run: AgentRun) -> ScoreOutcome:
        fds = _file_diffs(run)
        if not fds:
            return ScoreOutcome(100.0, "no changes", {"noisy_files": []})
        allowed = case.expected_files + case.allowed_files
        noisy: list[str] = []
        for f in fds:
            outside = bool(allowed) and not matches_any(f.path, allowed)
            if outside or f.is_noise:
                noisy.append(f.path)
        n = len(noisy)
        value = 100.0 if n == 0 else 80.0 if n == 1 else 50.0 if n <= 3 else 0.0
        detail = "no unrelated edits" if n == 0 else f"noisy files: {noisy}"
        return ScoreOutcome(value, detail, {"noisy_files": noisy})


class LiteralInstructionScorer(Scorer):
    """Checks explicit literal requirements against the diff."""

    name = "literal_instruction"

    def score(self, case: EvalCase, run: AgentRun) -> ScoreOutcome:
        reqs = case.literal_requirements
        if not reqs:
            return ScoreOutcome(100.0, "no literal requirements", {"literal_results": {}})
        fds = _file_diffs(run)
        results = {r.id: self._check(r.check, fds) for r in reqs}

        pool = [r for r in reqs if r.required] or reqs
        passed = sum(1 for r in pool if results[r.id])
        value = 100.0 * passed / len(pool)
        detail = "; ".join(f"{r.id}={'pass' if results[r.id] else 'FAIL'}" for r in reqs)
        return ScoreOutcome(value, detail, {"literal_results": results})

    @staticmethod
    def _check(check: LiteralCheck, fds: list[FileDiff]) -> bool:
        added = [line for f in fds for line in f.added]
        removed = [line for f in fds for line in f.removed]
        paths = [f.path for f in fds]
        deleted = {f.path for f in fds if f.is_deleted}
        rename_to = {f.path for f in fds if f.is_rename}
        rename_from = {f.old_path for f in fds if f.is_rename and f.old_path}
        exists = (set(paths) | rename_to) - deleted

        t = check.type
        if t == LiteralCheckType.TEXT_PRESENT:
            return any((check.pattern or "") in line for line in added)
        if t == LiteralCheckType.TEXT_ABSENT:
            return not any((check.pattern or "") in line for line in added)
        if t == LiteralCheckType.FILE_EXISTS:
            return any(_eq_or_glob(p, check.path) for p in exists)
        if t == LiteralCheckType.FILE_NOT_EXISTS:
            return not any(_eq_or_glob(p, check.path) for p in exists)
        if t == LiteralCheckType.FILE_RENAMED:
            explicit = check.from_path in rename_from and check.to_path in rename_to
            implied = check.from_path in deleted and check.to_path in exists
            return bool(explicit or implied)
        if t == LiteralCheckType.CHANGED_FILE_MATCHES:
            return any(_eq_or_glob(p, check.pattern) for p in paths)
        return False  # pragma: no cover - defensive


def _eq_or_glob(path: str, pattern: str | None) -> bool:
    if not pattern:
        return False
    return path == pattern or matches_any(path, [pattern])
