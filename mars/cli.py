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

experiments_app = typer.Typer(help="Retrieval experiments (Salience Memory v1).")
app.add_typer(experiments_app, name="experiments")

corpus_app = typer.Typer(help="Inspect and validate labeled benchmark corpora.")
app.add_typer(corpus_app, name="corpus")

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


@app.command("list-fixtures")
def list_fixtures_cmd() -> None:
    """List agentic-evaluation comparison fixtures (no live model calls)."""
    from mars.fixtures import list_fixtures

    console.print("Fixtures: " + ", ".join(list_fixtures()))


@app.command("score-fixture")
def score_fixture_cmd(
    name: str = typer.Argument(..., help="Comparison fixture name."),
) -> None:
    """Score a fixture's pre-recorded mock outputs and compare them.

    Uses no live/paid models — the outputs are deterministic fixtures.
    """
    from mars.fixtures import get_fixture, score_fixture

    fixture = get_fixture(name)
    scores = score_fixture(name)
    console.print(f"[bold]{fixture.case.name}[/]  ([dim]{name}[/])")

    table = Table(title="Component scores")
    table.add_column("Variant", style="cyan")
    table.add_column("Composite", justify="right")
    for scorer in ("test_pass", "literal_instruction", "diff_quality", "noise", "runtime", "cost"):
        table.add_column(scorer.replace("_", " "), justify="right")
    for s in scores:
        comps = {c.scorer: c.value for c in s.components}
        row = [s.variant, f"[bold]{s.composite:.1f}[/]"]
        row += [f"{comps.get(sc, 0):.0f}" for sc in
                ("test_pass", "literal_instruction", "diff_quality", "noise", "runtime", "cost")]
        table.add_row(*row)
    console.print(table)

    winner = scores[0]
    console.print(f"[green]Winner:[/] {winner.variant} (composite {winner.composite:.1f})")
    for s in scores:
        lit = next((c for c in s.components if c.scorer == "literal_instruction"), None)
        noise = next((c for c in s.components if c.scorer == "noise"), None)
        console.print(f"[dim]{s.variant}: literal[{lit.detail if lit else '-'}] "
                      f"noise[{noise.detail if noise else '-'}][/]")


@experiments_app.command("run")
def experiments_run(
    name: str = typer.Argument(..., help="Experiment name (salience-memory-v1)."),
    cortex_provider: str = typer.Option("synthetic", "--cortex-provider", help="synthetic | mcp"),
    autodev_provider: str = typer.Option("mock", "--autodev-provider", help="mock (only)."),
    strict_semantic: bool = typer.Option(False, "--strict-semantic", help="Fail if no semantic scores."),
) -> None:
    """Run a retrieval experiment (real Cortex retrieval + mock execution)."""
    from mars.memory.retrieval_source import SyntheticRetrievalSource
    from mars.memory.salience_v1 import (
        SemanticUnavailableError,
        load_experiment_spec,
        render_retrieval_report,
        run_salience_memory_v1,
        save_result,
    )

    try:
        spec = load_experiment_spec(name)
    except FileNotFoundError:
        console.print(f"[red]No experiment definition experiments/{name}.yaml[/]")
        raise typer.Exit(code=1)

    query_ids = None
    if cortex_provider == "mcp":
        from mars.memory.corpus import load_corpus, load_gold
        from mars.memory.retrieval_source import CortexRetrievalSource
        from mars.providers.cortex_mcp import CortexMCPProvider

        cortex = CortexMCPProvider.from_env()
        if cortex is None:
            console.print("[red]No Cortex MCP server configured (set MARS_CORTEX_MCP_*).[/]")
            raise typer.Exit(code=1)
        # Prefer a seeded labeled corpus + its captured gold labels.
        gold = load_gold(name)
        if gold is not None:
            corpus = load_corpus(name)
            query_ids = corpus.query_texts()
            source = CortexRetrievalSource(cortex, project=corpus.project, gold_map=gold)
        else:
            console.print(
                "[yellow]No seeded gold labels found. Run "
                f"`mars experiments seed-corpus {name}` first for real metrics; "
                "falling back to the spec's (synthetic-id) gold.[/]"
            )
            source = CortexRetrievalSource(cortex, project="mars", gold_map=spec.gold_map)
    else:
        source = SyntheticRetrievalSource()

    try:
        result = run_salience_memory_v1(
            source, query_ids=query_ids, strict_semantic=strict_semantic,
            execution=autodev_provider, spec=spec,
        )
    except SemanticUnavailableError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=2)

    save_result(result)
    console.print(render_retrieval_report(result))


@experiments_app.command("seed-corpus")
def experiments_seed_corpus(
    name: str = typer.Argument(..., help="Experiment name (salience-memory-v1)."),
) -> None:
    """Seed the labeled corpus into Cortex and write captured gold labels.

    Live, opt-in: writes memories to the Cortex project. Requires MARS_CORTEX_MCP_*.
    """
    from mars.memory.corpus import load_corpus, save_gold, seed_corpus
    from mars.providers.cortex_mcp import CortexMCPProvider

    try:
        corpus = load_corpus(name)
    except FileNotFoundError:
        console.print(f"[red]No corpus experiments/corpus/{name}.corpus.yaml[/]")
        raise typer.Exit(code=1)

    cortex = CortexMCPProvider.from_env()
    if cortex is None:
        console.print("[red]No Cortex MCP server configured (set MARS_CORTEX_MCP_*).[/]")
        raise typer.Exit(code=1)

    console.print(
        f"[yellow]Seeding {corpus.n_memories} memories into Cortex project "
        f"'{corpus.project}' across {len(corpus.queries)} queries…[/]"
    )
    try:
        gold, key_to_id = seed_corpus(cortex, corpus)
    finally:
        cortex.close()
    path = save_gold(gold, name)
    console.print(f"[green]Seeded {len(key_to_id)} memories; gold labels written to {path}[/]")
    console.print(f"Now run: [cyan]mars experiments run {name} --cortex-provider mcp[/]")


@experiments_app.command("report")
def experiments_report(
    name: str = typer.Argument(..., help="Experiment name."),
) -> None:
    """Render the last stored result for a retrieval experiment."""
    from mars.memory.salience_v1 import load_result, render_retrieval_report

    result = load_result(name)
    if result is None:
        console.print(f"[red]No stored result for {name!r}; run it first.[/]")
        raise typer.Exit(code=1)
    console.print(render_retrieval_report(result))


@corpus_app.command("validate")
def corpus_validate(
    name: str = typer.Argument(..., help="Corpus name (salience-memory-v1-expanded)."),
) -> None:
    """Validate a labeled benchmark corpus; exit non-zero on any error."""
    from mars.memory.expanded_corpus import load_expanded_corpus, validate_corpus

    try:
        corpus = load_expanded_corpus(name)
    except FileNotFoundError:
        console.print(f"[red]No corpus experiments/corpus/{name}.corpus.yaml[/]")
        raise typer.Exit(code=1)

    errors = validate_corpus(corpus)
    if errors:
        console.print(f"[red]✗ {name}: {len(errors)} validation error(s)[/]")
        for e in errors[:50]:
            console.print(f"  [red]- {e}[/]")
        raise typer.Exit(code=1)
    console.print(
        f"[green]✓ {name} valid:[/] {corpus.n_queries} queries, {corpus.n_memories} memories"
    )


@corpus_app.command("stats")
def corpus_stats(
    name: str = typer.Argument(..., help="Corpus name."),
) -> None:
    """Show corpus statistics: query/memory counts and category breakdown."""
    from mars.memory.expanded_corpus import load_expanded_corpus

    try:
        corpus = load_expanded_corpus(name)
    except FileNotFoundError:
        console.print(f"[red]No corpus experiments/corpus/{name}.corpus.yaml[/]")
        raise typer.Exit(code=1)

    per_query = corpus.n_memories / corpus.n_queries if corpus.n_queries else 0
    console.print(f"[bold]{name}[/] — {corpus.n_queries} queries, {corpus.n_memories} memories "
                  f"({per_query:.1f} per query)")
    table = Table(title="Category breakdown")
    table.add_column("Category")
    table.add_column("Count", justify="right")
    for cat, n in corpus.category_counts().items():
        table.add_row(cat, str(n))
    console.print(table)


@corpus_app.command("hash")
def corpus_hash(
    path: str = typer.Argument(..., help="Path to a .corpus.yaml file."),
) -> None:
    """Print the SHA256 of a corpus file (for pinning a frozen benchmark)."""
    from mars.memory.benchmark_manifest import corpus_sha256

    file_path = Path(path)
    if not file_path.exists():
        console.print(f"[red]No such file: {path}[/]")
        raise typer.Exit(code=1)
    console.print(f"{corpus_sha256(file_path)}  {path}")


@corpus_app.command("verify-frozen")
def corpus_verify_frozen(
    benchmark_id: str = typer.Argument(
        ..., help="Frozen benchmark id (salience-memory-benchmark-v1)."
    ),
) -> None:
    """Verify a frozen benchmark: recompute the corpus hash, validate it, and
    confirm the manifest's recorded stats still hold. Exit non-zero on drift."""
    from mars.memory.benchmark_manifest import verify_frozen

    try:
        result = verify_frozen(benchmark_id)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1)

    if not result.ok:
        console.print(
            f"[red]✗ {result.benchmark_id} v{result.version}: NOT frozen-clean[/]"
        )
        for reason in result.failures():
            console.print(f"  [red]- {reason}[/]")
        raise typer.Exit(code=1)

    console.print(
        f"[green]✓ {result.benchmark_id} v{result.version} frozen & verified[/]"
    )
    console.print(f"  corpus: {result.corpus_name}")
    console.print(f"  sha256: {result.actual_sha256}")
    corpus = result.corpus
    if corpus is not None:
        console.print(f"  queries: {corpus.n_queries}  memories: {corpus.n_memories}")
        table = Table(title="Category breakdown")
        table.add_column("Category")
        table.add_column("Count", justify="right")
        for cat, n in corpus.category_counts().items():
            table.add_row(cat, str(n))
        console.print(table)


if __name__ == "__main__":  # pragma: no cover
    app()
