import json

from typer.testing import CliRunner

from mars.cli import app
from mars.engine import EvalRunner
from mars.providers import MockAutoDevProvider, MockCortexProvider
from mars.reporting import render_json, render_markdown

runner = CliRunner()


def _make_run(case, repo, quality=1.0, agent="claude-code"):
    r = EvalRunner(MockCortexProvider(), MockAutoDevProvider(agent=agent, quality=quality), repository=repo)
    return r.run_case(case)


def test_render_markdown_contains_key_sections(case, repo):
    result = _make_run(case, repo)
    md = render_markdown(result)
    assert "# Mars Agentic Evaluation Report" in md
    assert result.id in md
    assert "Component scores" in md
    assert "Success criteria" in md


def test_render_json_is_valid(case, repo):
    result = _make_run(case, repo)
    data = json.loads(render_json(result))
    assert data["id"] == result.id
    assert data["case_id"] == case.id


def test_cli_list_suites():
    res = runner.invoke(app, ["list-suites"])
    assert res.exit_code == 0
    assert "backend-api" in res.stdout


def test_cli_list_cases():
    res = runner.invoke(app, ["list-cases", "--suite", "backend-api"])
    assert res.exit_code == 0
    assert "add-health-endpoint" in res.stdout


def test_cli_run_and_report(tmp_path):
    db = str(tmp_path / "mars.db")
    res = runner.invoke(app, ["run", "--suite", "backend-api", "--agent", "claude-code", "--db", db])
    assert res.exit_code == 0, res.stdout
    assert "Run —" in res.stdout


def test_cli_report_missing_run(tmp_path):
    db = str(tmp_path / "mars.db")
    res = runner.invoke(app, ["report", "--run-id", "nope", "--db", db])
    assert res.exit_code == 1


def test_cli_compare(tmp_path):
    db = str(tmp_path / "mars.db")
    res = runner.invoke(
        app, ["compare", "--suite", "backend-api", "--agents", "claude-code,codex", "--db", db]
    )
    assert res.exit_code == 0
    assert "Leaderboard" in res.stdout


def test_cli_run_then_replay(tmp_path, case):
    db = str(tmp_path / "mars.db")
    repo_db = db
    # Run via engine to capture a run id deterministically, persisted to the same db.
    from mars.storage.db import Database
    from mars.storage.repository import Repository

    repo = Repository(Database(f"sqlite:///{repo_db}"))
    result = _make_run(case, repo)
    res = runner.invoke(app, ["replay", "--run-id", result.id, "--db", db])
    assert res.exit_code == 0, res.stdout
    assert "Replayed" in res.stdout
