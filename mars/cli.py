"""Mars command-line interface (Typer + Rich).

Commands:

    mars list-suites
    mars list-cases  --suite SUITE
    mars run         --suite SUITE [--case CASE] --agent AGENT
    mars report      --run-id RUN
    mars compare     --suite SUITE --agents a,b,c
    mars replay      --run-id RUN
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from mars.agents import (
    known_agents,
    make_autodev,
    make_cortex,
    using_real_autodev,
    using_real_cortex,
)
from mars.apollo.experiment import ExperimentRunner
from mars.apollo.registry import get_experiment, list_experiments
from mars.engine.regression import detect_regression
from mars.engine.runner import EvalRunner
from mars.models import EvalRun, EvalStatus
from mars.reporting.report import render_json, render_markdown
from mars.scoring.composite import default_composite
from mars.storage.db import Database
from mars.storage.repository import Repository
from mars.suites import load_suite, load_suites

app = typer.Typer(add_completion=False, help="Continuous evaluation for AI software engineering agents.")
console = Console()

DB_OPTION = typer.Option("mars.db", "--db", help="SQLite database path or URL.")


def _repo(db: str) -> Repository:
    url = db if "://" in db else f"sqlite:///{db}"
    return Repository(Database(url))


def _status_style(status: EvalStatus) -> str:
    return {
        EvalStatus.PASSED: "green",
        EvalStatus.FAILED: "red",
        EvalStatus.ERROR: "yellow",
    }[status]


@app.command("list-suites")
def list_suites() -> None:
    """List available benchmark suites."""
    suites = load_suites()
    if not suites:
        console.print("[yellow]No suites found.[/]")
        raise typer.Exit()
    table = Table(title="Benchmark Suites")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Cases", justify="right")
    table.add_column("Tags", style="dim")
    for suite in suites.values():
        table.add_row(suite.id, suite.name, str(len(suite.cases)), ", ".join(suite.tags))
    console.print(table)


@app.command("list-cases")
def list_cases(suite: str = typer.Option(..., "--suite", help="Suite id.")) -> None:
    """List the cases in a suite."""
    s = load_suite(suite)
    table = Table(title=f"Cases — {s.name}")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Profile", style="dim")
    table.add_column("Criteria", style="dim")
    for case in s.cases:
        table.add_row(
            case.id,
            case.name,
            case.context_profile,
            ", ".join(c.value for c in case.success_criteria),
        )
    console.print(table)


@app.command()
def run(
    suite: str = typer.Option(..., "--suite", help="Suite id."),
    agent: str = typer.Option("mock-agent", "--agent", help="Agent to evaluate."),
    case: Optional[str] = typer.Option(None, "--case", help="Run a single case."),
    db: str = DB_OPTION,
) -> None:
    """Run an evaluation for a suite (or a single case) with an agent."""
    s = load_suite(suite)
    cases = [s.case(case)] if case else s.cases
    repo = _repo(db)
    autodev_backend = "AutoDev MCP" if using_real_autodev() else "mock"
    cortex_backend = "Cortex MCP" if using_real_cortex() else "mock"
    console.print(f"[dim]Cortex backend: {cortex_backend}  |  AutoDev backend: {autodev_backend}[/]")
    runner = EvalRunner(make_cortex(), make_autodev(agent), repository=repo)

    table = Table(title=f"Run — {s.name} / {agent}")
    table.add_column("Case", style="cyan")
    table.add_column("Status")
    table.add_column("Score", justify="right")
    table.add_column("Runtime", justify="right")
    table.add_column("Cost", justify="right")
    table.add_column("Run ID", style="dim")
    table.add_column("Regression", style="dim")

    for c in cases:
        baseline = repo.latest_eval_run(suite_id=s.id, case_id=c.id, agent=agent)
        result = runner.run_case(c)
        reg = detect_regression(result, baseline)
        table.add_row(
            c.id,
            f"[{_status_style(result.status)}]{result.status.value}[/]",
            f"{result.score:.1f}",
            f"{result.duration_ms} ms",
            f"${result.cost_usd:.4f}",
            result.id,
            "[red]⚠ " + reg.summary + "[/]" if reg.has_regression else "ok",
        )
    console.print(table)


@app.command()
def report(
    run_id: str = typer.Option(..., "--run-id", help="EvalRun id."),
    fmt: str = typer.Option("md", "--format", help="md or json."),
    out: Optional[Path] = typer.Option(None, "--out", help="Write to file instead of stdout."),
    db: str = DB_OPTION,
) -> None:
    """Render a stored evaluation run as Markdown or JSON."""
    repo = _repo(db)
    eval_run = repo.get_eval_run(run_id)
    if eval_run is None:
        console.print(f"[red]Run {run_id!r} not found.[/]")
        raise typer.Exit(code=1)
    baseline = repo.latest_eval_run(
        suite_id=eval_run.suite_id, case_id=eval_run.case_id, agent=eval_run.agent, before=run_id
    )
    reg = detect_regression(eval_run, baseline)
    text = render_json(eval_run, reg) if fmt == "json" else render_markdown(eval_run, reg)
    if out:
        out.write_text(text)
        console.print(f"[green]Wrote {fmt} report to {out}[/]")
    else:
        console.print(text)


@app.command()
def compare(
    suite: str = typer.Option(..., "--suite", help="Suite id."),
    agents: str = typer.Option(..., "--agents", help="Comma-separated agent ids."),
    db: str = DB_OPTION,
) -> None:
    """Run a suite across multiple agents and print a leaderboard."""
    s = load_suite(suite)
    repo = _repo(db)
    agent_ids = [a.strip() for a in agents.split(",") if a.strip()]

    results: dict[str, list[EvalRun]] = {}
    for agent in agent_ids:
        runner = EvalRunner(make_cortex(), make_autodev(agent), repository=repo)
        results[agent] = runner.run_suite(s.cases)

    table = Table(title=f"Leaderboard — {s.name}")
    table.add_column("Agent", style="cyan")
    table.add_column("Avg score", justify="right")
    table.add_column("Pass rate", justify="right")
    table.add_column("Avg cost", justify="right")

    ranked = []
    for agent, runs in results.items():
        n = len(runs) or 1
        avg = sum(r.score for r in runs) / n
        passed = sum(1 for r in runs if r.status == EvalStatus.PASSED)
        avg_cost = sum(r.cost_usd for r in runs) / n
        ranked.append((agent, avg, passed / n, avg_cost))
    ranked.sort(key=lambda x: x[1], reverse=True)
    for agent, avg, pass_rate, avg_cost in ranked:
        table.add_row(agent, f"{avg:.1f}", f"{pass_rate * 100:.0f}%", f"${avg_cost:.4f}")
    console.print(table)


@app.command()
def replay(
    run_id: str = typer.Option(..., "--run-id", help="EvalRun id to replay."),
    db: str = DB_OPTION,
) -> None:
    """Re-score a stored agent run with the current scorer (replay).

    Demonstrates evaluating a frozen execution under a new scoring strategy
    without re-running the agent.
    """
    repo = _repo(db)
    original = repo.get_eval_run(run_id)
    if original is None:
        console.print(f"[red]Run {run_id!r} not found.[/]")
        raise typer.Exit(code=1)
    agent_run = repo.get_agent_run(original.agent_run_id)
    if agent_run is None:
        console.print(f"[red]Agent run {original.agent_run_id!r} not found.[/]")
        raise typer.Exit(code=1)
    case = load_suite(original.suite_id).case(original.case_id)

    result = default_composite().score(case, agent_run)
    delta = result.score - original.score
    console.print(f"Replayed [cyan]{run_id}[/] ({original.case_id})")
    console.print(f"  original score: {original.score:.1f}")
    console.print(f"  replayed score: {result.score:.1f}  ([{'green' if delta >= 0 else 'red'}]{delta:+.1f}[/])")
    for c in result.components:
        console.print(f"    - {c.scorer}: {c.value:.1f} (w={c.weight:.2f}) {c.detail}")


@app.command("list-agents")
def list_agents() -> None:
    """List the built-in (mock) agent presets."""
    console.print("Known agents: " + ", ".join(known_agents()))


@app.command("list-experiments")
def list_experiments_cmd() -> None:
    """List available Apollo experiments."""
    table = Table(title="Apollo Experiments")
    table.add_column("ID", style="cyan")
    table.add_column("Title")
    table.add_column("Arms", justify="right")
    for exp in list_experiments():
        table.add_row(exp.id, exp.title, str(len(exp.arms)))
    console.print(table)


@app.command()
def experiment(
    name: str = typer.Option(..., "--experiment", help="Experiment id."),
    trials: Optional[int] = typer.Option(None, "--trials", help="Override trial count."),
    agent: Optional[str] = typer.Option(None, "--agent", help="Override agent."),
    seed: Optional[int] = typer.Option(None, "--seed", help="Override RNG seed."),
) -> None:
    """Run an Apollo experiment and report a baseline-vs-experimental verdict."""
    exp = get_experiment(name)
    if trials is not None:
        exp.trials = trials
    if agent is not None:
        exp.agent = agent
    if seed is not None:
        exp.seed = seed

    console.print(f"[bold]{exp.title}[/]")
    console.print(f"[dim]{exp.hypothesis}[/]")
    console.print(f"[dim]agent={exp.agent}  trials={exp.trials}  seed={exp.seed}  k={exp.retrieval_k}[/]\n")

    result = ExperimentRunner().run(exp)

    arms_table = Table(title="Arms")
    arms_table.add_column("Arm", style="cyan")
    arms_table.add_column("Role", style="dim")
    arms_table.add_column("Mean score", justify="right")
    arms_table.add_column("Pass rate", justify="right")
    arms_table.add_column("Mean relevance", justify="right")
    arms_table.add_column("N", justify="right")
    for arm in result.arms:
        arms_table.add_row(
            arm.name,
            "baseline" if arm.baseline else "experimental",
            f"{arm.mean_score:.1f}",
            f"{arm.pass_rate * 100:.0f}%",
            f"{arm.mean_relevance:.2f}",
            str(arm.n),
        )
    console.print(arms_table)

    cmp_table = Table(title="Comparison vs baseline")
    cmp_table.add_column("Experimental", style="cyan")
    cmp_table.add_column("Δ mean", justify="right")
    cmp_table.add_column("Lift", justify="right")
    cmp_table.add_column("95% CI", justify="right")
    cmp_table.add_column("Cohen's d", justify="right")
    cmp_table.add_column("Verdict")
    for c in result.comparisons:
        style = "green" if (c.significant and c.mean_delta > 0) else ("red" if c.significant else "yellow")
        cmp_table.add_row(
            c.experimental_arm,
            f"{c.mean_delta:+.1f}",
            f"{c.lift_pct:+.1f}%",
            f"[{c.ci_low:+.1f}, {c.ci_high:+.1f}]",
            f"{c.cohens_d:.2f}",
            f"[{style}]{c.verdict}[/]",
        )
    console.print(cmp_table)
    console.print(f"\n[bold]Verdict:[/] {result.headline}")


if __name__ == "__main__":  # pragma: no cover
    app()
