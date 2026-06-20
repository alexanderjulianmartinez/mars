"""Track A: agentic-evaluation scorers, diff parsing, propagation, fixture."""

import pytest

from mars.fixtures import get_fixture, score_fixture
from mars.models import (
    AgentRun,
    AgentRunStatus,
    EvalCase,
    LiteralCheck,
    LiteralCheckType,
    LiteralRequirement,
)
from mars.providers.task_payload import build_task_payload, format_task_prompt
from mars.scoring.agentic import DiffQualityScorer, LiteralInstructionScorer, NoiseScorer
from mars.scoring.diffutil import glob_match, parse_unified_diff

# --- diff parsing + globs -------------------------------------------------- #

GIT_DIFF = """diff --git a/CLAUDE.md b/CLAUDE.md
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -4,7 +4,7 @@
-spec in `docs/claude_code_mars_boostrap.md` here
+spec in `docs/claude_code_mars_bootstrap.md` here
"""

NOISE_DIFF = """diff --git a/docs/APOLLO.md b/docs/APOLLO.md
--- a/docs/APOLLO.md
+++ b/docs/APOLLO.md
@@ -90,4 +90,4 @@
-  correction yet). See `BACKLOG.md`.
+  correction yet). See `BACKLOG.md`.
"""


def test_parse_git_and_plain_diff():
    fds = parse_unified_diff(GIT_DIFF)
    assert len(fds) == 1 and fds[0].path == "CLAUDE.md"
    assert any("bootstrap" in a for a in fds[0].added)
    assert any("boostrap" in r for r in fds[0].removed)


def test_noise_detection():
    fd = parse_unified_diff(NOISE_DIFF)[0]
    assert fd.is_noise is True
    assert parse_unified_diff(GIT_DIFF)[0].is_noise is False


def test_glob_match():
    assert glob_match("docs/APOLLO.md", "docs/**")
    assert glob_match("secrets/key.txt", "secrets/**")
    assert not glob_match("mars/cli.py", "docs/**")
    assert glob_match("README.md", "README.md")


def _case(**kw):
    base = dict(id="c", suite_id="s", name="c", task_prompt="t")
    base.update(kw)
    return EvalCase(**base)


def _run(diff, files, status=AgentRunStatus.SUCCESS):
    return AgentRun(id="r", agent="a", model="m", status=status, diff=diff, files_changed=files)


# --- DiffQualityScorer ----------------------------------------------------- #


def test_diff_quality_targeted_vs_noisy():
    case = _case(expected_files=["CLAUDE.md"], allowed_files=["docs/**"])
    assert DiffQualityScorer().score(case, _run(GIT_DIFF, ["CLAUDE.md"])).value == 100.0
    # touch a file outside expected+allowed -> unexpected
    out = _run(GIT_DIFF + "diff --git a/mars/x.py b/mars/x.py\n+x\n", ["CLAUDE.md", "mars/x.py"])
    assert DiffQualityScorer().score(case, out).value == 70.0


def test_diff_quality_forbidden_is_zero():
    case = _case(expected_files=["CLAUDE.md"], forbidden_files=[".env"])
    run = _run("diff --git a/.env b/.env\n+SECRET=1\n", [".env"])
    assert DiffQualityScorer().score(case, run).value == 0.0


def test_diff_quality_empty_is_zero():
    assert DiffQualityScorer().score(_case(), _run("", [])).value == 0.0


def test_diff_quality_noop_when_unconfigured():
    assert DiffQualityScorer().score(_case(), _run(GIT_DIFF, ["CLAUDE.md"])).value == 100.0


# --- NoiseScorer ----------------------------------------------------------- #


def test_noise_flags_whitespace_churn():
    case = _case(allowed_files=["docs/**", "CLAUDE.md"])
    run = _run(GIT_DIFF + NOISE_DIFF, ["CLAUDE.md", "docs/APOLLO.md"])
    out = NoiseScorer().score(case, run)
    assert out.value == 80.0
    assert out.data["noisy_files"] == ["docs/APOLLO.md"]


def test_noise_clean_is_100():
    case = _case(allowed_files=["CLAUDE.md"])
    assert NoiseScorer().score(case, _run(GIT_DIFF, ["CLAUDE.md"])).value == 100.0


# --- LiteralInstructionScorer ---------------------------------------------- #


def test_literal_text_absent_and_file_exists():
    case = _case(
        literal_requirements=[
            LiteralRequirement(id="typo", check=LiteralCheck(type=LiteralCheckType.TEXT_ABSENT, pattern="boostrap")),
            LiteralRequirement(id="rename", check=LiteralCheck(type=LiteralCheckType.FILE_EXISTS, path="docs/NEW.md")),
        ]
    )
    out = LiteralInstructionScorer().score(case, _run(GIT_DIFF, ["CLAUDE.md"]))
    assert out.data["literal_results"] == {"typo": True, "rename": False}
    assert out.value == 50.0


def test_literal_file_renamed():
    rename = "diff --git a/old.md b/new.md\nrename from old.md\nrename to new.md\n"
    case = _case(
        literal_requirements=[
            LiteralRequirement(id="mv", check=LiteralCheck(
                type=LiteralCheckType.FILE_RENAMED, from_path="old.md", to_path="new.md"))
        ]
    )
    assert LiteralInstructionScorer().score(case, _run(rename, ["new.md"])).value == 100.0


def test_literal_noop_when_unconfigured():
    assert LiteralInstructionScorer().score(_case(), _run(GIT_DIFF, ["CLAUDE.md"])).value == 100.0


# --- A7 fixture ------------------------------------------------------------ #


def test_fixture_gpt_beats_claude_both_miss_rename():
    scores = {s.variant: s for s in score_fixture("bootstrap-typo-and-rename")}
    assert scores["gpt-like"].composite > scores["claude-like"].composite
    for s in scores.values():
        lit = next(c for c in s.components if c.scorer == "literal_instruction")
        assert lit.data["literal_results"]["rename_file"] is False  # both miss rename
        assert lit.data["literal_results"]["fix_bootstrap_typo"] is True
    claude_noise = next(c for c in scores["claude-like"].components if c.scorer == "noise")
    assert "docs/APOLLO.md" in claude_noise.data["noisy_files"]


# --- A1/A2 propagation ----------------------------------------------------- #


def test_format_task_prompt_includes_acceptance_criteria():
    case = _case(task_prompt="Do X", acceptance_criteria=["Crit A", "Crit B"])
    prompt = format_task_prompt(case)
    assert "Acceptance Criteria:" in prompt
    assert "- Crit A" in prompt and "- Crit B" in prompt
    assert build_task_payload(case)["acceptance_criteria"] == ["Crit A", "Crit B"]


def test_setup_commands_sent_before_validation():
    from tests.test_autodev_mcp import FakeToolCaller, env
    from mars.providers.autodev_mcp import AutoDevMCPProvider

    caller = FakeToolCaller({"autodev_validate": env({"commands": [], "passed": True})})
    p = AutoDevMCPProvider(caller)
    case = _case(setup_commands=["uv sync"], test_commands=["pytest -q"])
    ws = p.create_workspace(case, None)
    ws.metadata["run_id"] = "run-1"
    p.run_tests(ws, case)
    validate_calls = [c for c in caller.calls if c[0] == "autodev_validate"]
    assert validate_calls[0][1]["commands"] == ["uv sync"]  # setup first
    assert validate_calls[1][1]["commands"] == ["pytest -q"]  # then tests


def test_eval_run_records_setup_and_acceptance(repo):
    from mars.engine.runner import EvalRunner
    from mars.providers.mock import MockAutoDevProvider, MockCortexProvider

    case = _case(
        id="add-health-endpoint",
        setup_commands=["uv sync"],
        acceptance_criteria=["Do not edit unrelated files."],
        test_commands=["pytest"],
    )
    result = EvalRunner(MockCortexProvider(), MockAutoDevProvider(quality=1.0), repository=repo).run_case(case)
    assert result.setup_commands == ["uv sync"]
    assert result.acceptance_criteria == ["Do not edit unrelated files."]
