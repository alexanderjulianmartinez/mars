"""Unified-diff parsing + glob matching shared by the agentic-eval scorers.

Mars only sees the agent's unified diff (not the live workspace), so these
helpers extract per-file change facts from the diff text: which files changed,
added/removed content, renames, and whether a change is pure noise (whitespace /
trailing-newline churn with no net content change).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class FileDiff:
    path: str
    old_path: str | None = None
    is_new: bool = False
    is_deleted: bool = False
    is_rename: bool = False
    is_binary: bool = False
    added: list[str] = field(default_factory=list)  # content of '+' lines (no prefix)
    removed: list[str] = field(default_factory=list)  # content of '-' lines (no prefix)

    @property
    def changed_lines(self) -> int:
        return len(self.added) + len(self.removed)

    @property
    def is_noise(self) -> bool:
        """True when the change has no net content (whitespace / newline only).

        A file is noise when every added line, stripped, matches a removed line,
        stripped, and vice-versa — i.e. the multiset of stripped content is
        unchanged. A trailing-newline-only edit and pure reformatting both fall
        here. A genuine addition/removal does not.
        """
        if self.is_binary or self.is_new or self.is_deleted or self.is_rename:
            return False
        if not self.added and not self.removed:
            return True
        added = sorted(s.strip() for s in self.added)
        removed = sorted(s.strip() for s in self.removed)
        return added == removed


def _strip_ab(path: str) -> str:
    path = path.strip()
    return path[2:] if path.startswith(("a/", "b/")) else path


def parse_unified_diff(diff: str) -> list[FileDiff]:
    """Parse a unified diff (git or plain) into per-file :class:`FileDiff` records."""
    files: list[FileDiff] = []
    current: FileDiff | None = None

    def flush() -> None:
        nonlocal current
        if current is not None:
            files.append(current)
            current = None

    for line in diff.splitlines():
        if line.startswith("diff --git "):
            flush()
            m = re.match(r"diff --git a/(.+) b/(.+)", line)
            current = FileDiff(
                path=m.group(2) if m else line[len("diff --git ") :],
                old_path=m.group(1) if m else None,
            )
        elif line.startswith("--- "):
            old = _strip_ab(line[4:])
            # Plain-diff file boundary, unless this is the '---' inside a git header.
            if current is None or current.added or current.removed:
                flush()
                current = FileDiff(path=old, old_path=old)
            else:
                current.old_path = old
        elif line.startswith("+++ "):
            new = _strip_ab(line[4:])
            if current is not None and not (current.added or current.removed):
                if new and new != "/dev/null":
                    current.path = new
        elif current is None:
            continue
        elif line.startswith("rename from "):
            current.is_rename = True
            current.old_path = line[len("rename from ") :]
        elif line.startswith("rename to "):
            current.is_rename = True
            current.path = line[len("rename to ") :]
        elif line.startswith("new file"):
            current.is_new = True
        elif line.startswith("deleted file"):
            current.is_deleted = True
        elif line.startswith("Binary files") or line.startswith("GIT binary patch"):
            current.is_binary = True
        elif line.startswith("+"):
            current.added.append(line[1:])
        elif line.startswith("-"):
            current.removed.append(line[1:])
    flush()
    return files


def changed_paths(diff: str) -> list[str]:
    return [f.path for f in parse_unified_diff(diff)]


def _translate(pattern: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern[i : i + 2] == "**":
            out.append(".*")
            i += 2
            if i < len(pattern) and pattern[i] == "/":
                i += 1
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return "^" + "".join(out) + "$"


def glob_match(path: str, pattern: str) -> bool:
    """Match ``path`` against a glob with ``*``, ``?`` and recursive ``**``."""
    return re.match(_translate(pattern), path) is not None


def matches_any(path: str, patterns: list[str]) -> bool:
    return any(glob_match(path, p) for p in patterns)
