"""Track B: retrieval metrics, semantic detection, Salience Memory v1."""

from typer.testing import CliRunner

from mars.cli import app
from mars.memory.metrics import (
    context_efficiency,
    mrr,
    precision_at_k,
    recall_at_k,
    target_found,
)
from mars.memory.models import MemoryItem
from mars.memory.retrieval_source import Retrieved, SyntheticRetrievalSource, semantic_available
from mars.memory.salience_v1 import (
    SemanticUnavailableError,
    load_result,
    render_retrieval_report,
    run_salience_memory_v1,
    save_result,
)

runner = CliRunner()


# --- metrics --------------------------------------------------------------- #


def test_retrieval_metrics():
    ranked = ["a", "x", "b", "y", "z"]
    relevant = {"a", "b", "c"}
    assert recall_at_k(ranked, relevant, 5) == 2 / 3
    assert precision_at_k(ranked, relevant, 5) == 2 / 5
    assert mrr(ranked, relevant) == 1.0  # 'a' at rank 1
    assert target_found(ranked, "b", 5) is True
    assert target_found(ranked, "c", 5) is False
    assert context_efficiency(ranked, relevant, 5) == 2 / 5


def test_metrics_empty_relevant():
    assert recall_at_k(["a"], set(), 5) == 0.0
    assert mrr(["a"], set()) == 0.0


# --- semantic detection ---------------------------------------------------- #


class _FakeSource:
    name = "fake-cortex"

    def __init__(self, semantic: bool):
        self._semantic = semantic

    def fetch(self, query_id):
        mems = [
            MemoryItem(id=f"{query_id}-rel-0", content="", similarity=0.3, importance=0.9,
                       recency=0.9, relevant=True),
            MemoryItem(id=f"{query_id}-rel-1", content="", similarity=0.2, importance=0.8,
                       recency=0.8, relevant=True),
            MemoryItem(id=f"{query_id}-dis-0", content="", similarity=0.9, importance=0.1,
                       recency=0.1, relevant=False),
        ]
        notes = [] if self._semantic else ["Cortex returned semantic_score=null; keyword fallback."]
        return Retrieved(
            memories=mems,
            relevant_ids={m.id for m in mems if m.relevant},
            target_id=f"{query_id}-rel-0",
            semantic_available=self._semantic,
            source=self.name,
            notes=notes,
        )


def test_semantic_available_helper():
    assert semantic_available([MemoryItem(id="a", content="", similarity=0.5)]) is False
    m = MemoryItem(id="a", content="", similarity=0.5)
    m.semantic_score = 0.7  # type: ignore[attr-defined]
    assert semantic_available([m]) is True


def test_experiment_unavailable_semantic_is_honest():
    result = run_salience_memory_v1(_FakeSource(semantic=False), ["q1", "q2"], k=2)
    assert result.semantic_available is False
    assert result.limitation is not None
    report = render_retrieval_report(result)
    assert "UNAVAILABLE" in report
    assert "should not be treated as" in report  # honesty disclaimer
    assert "semantic" in report.lower()


def test_strict_semantic_raises_when_unavailable():
    import pytest

    with pytest.raises(SemanticUnavailableError):
        run_salience_memory_v1(_FakeSource(semantic=False), ["q1"], strict_semantic=True)


def test_strict_semantic_ok_when_available():
    result = run_salience_memory_v1(_FakeSource(semantic=True), ["q1"], strict_semantic=True, k=2)
    assert result.semantic_available is True
    assert result.limitation is None


# --- experiment over synthetic source -------------------------------------- #


def test_salience_beats_similarity_on_synthetic():
    result = run_salience_memory_v1(SyntheticRetrievalSource(), k=5)
    assert result.candidate.recall_at_k > result.baseline.recall_at_k
    assert result.retrieval_source == "synthetic"
    assert result.execution_provider == "mock"
    # honesty: synthetic results are clearly flagged as non-production
    assert any("Synthetic corpus" in n for n in result.notes)


def test_synthetic_is_reproducible():
    a = run_salience_memory_v1(SyntheticRetrievalSource(), k=5)
    b = run_salience_memory_v1(SyntheticRetrievalSource(), k=5)
    assert a.candidate.recall_at_k == b.candidate.recall_at_k
    assert a.baseline.recall_at_k == b.baseline.recall_at_k


def test_save_and_load_result(tmp_path):
    result = run_salience_memory_v1(SyntheticRetrievalSource(), ["q1", "q2"], k=3)
    save_result(result, tmp_path)
    loaded = load_result("salience-memory-v1", tmp_path)
    assert loaded is not None
    assert loaded.candidate.recall_at_k == result.candidate.recall_at_k


# --- CLI ------------------------------------------------------------------- #


def test_load_experiment_spec_and_gold():
    from mars.memory.salience_v1 import load_experiment_spec

    spec = load_experiment_spec("salience-memory-v1")
    assert spec.id == "salience-memory-v1"
    assert spec.hypothesis and spec.methodology
    assert spec.baseline_strategy == "similarity_only"
    assert spec.candidate_strategy == "salience_weighted_v1"
    assert "migration-note-task" in spec.queries
    gold = spec.gold_map["migration-note-task"]
    assert gold["target"] == "migration-note-task-rel-0"
    assert "migration-note-task-rel-1" in gold["relevant"]


def test_report_has_hypothesis_methodology_deltas_recommendation():
    from mars.memory.salience_v1 import load_experiment_spec

    spec = load_experiment_spec("salience-memory-v1")
    result = run_salience_memory_v1(SyntheticRetrievalSource(), spec=spec)
    md = render_retrieval_report(result)
    assert "## Hypothesis" in md
    assert "## Methodology" in md
    assert "## Recommendation" in md
    assert "Δ (cand − base)" in md  # per-metric deltas column
    assert result.hypothesis and result.methodology


def test_cli_experiments_run_and_report():
    res = runner.invoke(app, ["experiments", "run", "salience-memory-v1"])
    assert res.exit_code == 0, res.stdout
    assert "Retrieval Experiment Report" in res.stdout
    assert "salience_weighted_v1" in res.stdout

    rep = runner.invoke(app, ["experiments", "report", "salience-memory-v1"])
    assert rep.exit_code == 0
    assert "Retrieval Experiment Report" in rep.stdout


def test_cli_experiments_run_unknown():
    res = runner.invoke(app, ["experiments", "run", "nope"])
    assert res.exit_code == 1


def test_cli_score_fixture():
    res = runner.invoke(app, ["score-fixture", "bootstrap-typo-and-rename"])
    assert res.exit_code == 0
    assert "gpt-like" in res.stdout and "Winner" in res.stdout
