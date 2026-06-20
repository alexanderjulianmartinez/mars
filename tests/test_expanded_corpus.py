"""Expanded benchmark corpus: nDCG metric, schema/loader, validator, CLI."""

from typer.testing import CliRunner

from mars.cli import app
from mars.memory.expanded_corpus import (
    Category,
    ExpandedCorpus,
    ExpandedMemory,
    ExpandedQuery,
    gold_from_corpus,
    load_expanded_corpus,
    validate_corpus,
)
from mars.memory.metrics import ndcg_at_k

runner = CliRunner()


# --- nDCG ------------------------------------------------------------------ #


def test_ndcg_perfect_ranking_is_one():
    ranked = ["a", "b", "c", "x", "y"]
    relevant = {"a", "b", "c"}
    assert ndcg_at_k(ranked, relevant, 5) == 1.0


def test_ndcg_rewards_higher_placement():
    relevant = {"a"}
    top = ndcg_at_k(["a", "x", "y"], relevant, 3)
    low = ndcg_at_k(["x", "y", "a"], relevant, 3)
    assert top == 1.0
    assert 0.0 < low < top


def test_ndcg_empty_relevant_is_zero():
    assert ndcg_at_k(["a", "b"], set(), 5) == 0.0


# --- schema / loader ------------------------------------------------------- #


def test_load_expanded_corpus():
    corpus = load_expanded_corpus("salience-memory-v1-expanded")
    assert corpus.n_queries >= 25
    assert corpus.n_memories >= 500
    counts = corpus.category_counts()
    assert counts["target"] == corpus.n_queries  # >=1 target per query
    assert counts["distractor"] > counts["target"]
    # gold ids resolve and target/relevant are disjoint roles
    gold = gold_from_corpus(corpus)
    q0 = corpus.queries[0]
    assert gold[q0.query]["target"] in {m.id for m in q0.memories}


def test_category_is_relevant():
    assert Category.TARGET.is_relevant and Category.RELEVANT.is_relevant
    assert not Category.DISTRACTOR.is_relevant
    assert not Category.STALE.is_relevant


# --- validator ------------------------------------------------------------- #


def _mem(mid: str, cat: Category) -> ExpandedMemory:
    return ExpandedMemory(id=mid, content="x", category=cat)


def _good_query(prefix: str) -> ExpandedQuery:
    mems = (
        [_mem(f"{prefix}-t", Category.TARGET)]
        + [_mem(f"{prefix}-r{i}", Category.RELEVANT) for i in range(3)]
        + [_mem(f"{prefix}-d{i}", Category.DISTRACTOR) for i in range(6)]
    )
    return ExpandedQuery(
        query=f"q {prefix}",
        memories=mems,
        target_memories=[f"{prefix}-t"],
        relevant_memories=[f"{prefix}-r0", f"{prefix}-r1", f"{prefix}-r2"],
    )


def test_validate_accepts_good_corpus():
    corpus = ExpandedCorpus(name="t", project="mars", queries=[_good_query("a"), _good_query("b")])
    assert validate_corpus(corpus) == []


def test_validate_flags_too_few_memories():
    q = _good_query("a")
    q.memories = q.memories[:5]
    errors = validate_corpus(ExpandedCorpus(name="t", project="mars", queries=[q]))
    assert any("< 10" in e or "memories" in e for e in errors)


def test_validate_flags_missing_target():
    q = _good_query("a")
    q.target_memories = []
    q.memories = [m for m in q.memories if m.category != Category.TARGET]
    q.memories.append(_mem("a-extra", Category.RELEVANT))
    errors = validate_corpus(ExpandedCorpus(name="t", project="mars", queries=[q]))
    assert any("target" in e for e in errors)


def test_validate_flags_no_distractors():
    q = _good_query("a")
    q.memories = [m for m in q.memories if m.category != Category.DISTRACTOR]
    q.memories += [_mem(f"a-x{i}", Category.RELEVANT) for i in range(6)]
    errors = validate_corpus(ExpandedCorpus(name="t", project="mars", queries=[q]))
    assert any("distractor" in e for e in errors)


def test_validate_flags_duplicate_ids():
    qa, qb = _good_query("a"), _good_query("b")
    qb.memories[0].id = "a-t"  # collide with qa's target id
    errors = validate_corpus(ExpandedCorpus(name="t", project="mars", queries=[qa, qb]))
    assert any("duplicate" in e for e in errors)


def test_validate_flags_dangling_gold_id():
    q = _good_query("a")
    q.relevant_memories = ["a-does-not-exist"]
    errors = validate_corpus(ExpandedCorpus(name="t", project="mars", queries=[q]))
    assert any("not among its memories" in e for e in errors)


# --- CLI ------------------------------------------------------------------- #


def test_cli_corpus_validate():
    res = runner.invoke(app, ["corpus", "validate", "salience-memory-v1-expanded"])
    assert res.exit_code == 0, res.stdout
    assert "valid" in res.stdout


def test_cli_corpus_validate_unknown():
    res = runner.invoke(app, ["corpus", "validate", "nope"])
    assert res.exit_code == 1


def test_cli_corpus_stats():
    res = runner.invoke(app, ["corpus", "stats", "salience-memory-v1-expanded"])
    assert res.exit_code == 0
    assert "Category breakdown" in res.stdout
    assert "distractor" in res.stdout


# --- seeding + benchmark runner -------------------------------------------- #


class _FakeCortex:
    """Assigns sequential ids on add_memory; search returns the seeded memories
    for a query ranked so a salience ranker can beat similarity."""

    def __init__(self):
        self._n = 0
        self._by_summary: dict[str, dict] = {}

    def add_memory(self, project, mem_type, content, importance=0.5, summary=""):
        self._n += 1
        mid = f"uuid-{self._n}"
        # Distractors get HIGH semantic similarity but low importance; relevant
        # memories get moderate similarity but high importance.
        is_distractor = "distractor" in summary or "stale" in summary or "low_confidence" in summary
        self._by_summary[mid] = {
            "id": mid,
            "content": content,
            "semantic_score": 0.9 if is_distractor else 0.5,
            "importance_score": importance,
            "recency_factor": 0.5,
        }
        return mid

    def register_pool(self, query, ids):
        self._pool = getattr(self, "_pool", {})
        self._pool[query] = ids

    def search_memories(self, project, query, limit=25):
        ids = getattr(self, "_pool", {}).get(query, list(self._by_summary))
        rows = [self._by_summary[i] for i in ids if i in self._by_summary]
        rows.sort(key=lambda r: r["semantic_score"], reverse=True)
        return rows[:limit]


def test_seed_expanded_corpus_captures_gold_and_pools():
    from mars.memory.expanded_corpus import seed_expanded_corpus

    corpus = load_expanded_corpus("salience-memory-v1-expanded")
    small = ExpandedCorpus(name="t", project="mars", queries=corpus.queries[:2])
    cx = _FakeCortex()
    gold, pools, key_to_id = seed_expanded_corpus(cx, small)
    q0 = small.queries[0].query
    assert gold[q0]["target"] is not None
    assert gold[q0]["target"] in gold[q0]["relevant"]
    assert pools[q0] >= gold[q0]["relevant"]  # pool contains all relevant
    assert len(key_to_id) == small.n_memories


def test_run_benchmark_salience_beats_similarity_on_fake():
    from mars.memory.expanded_corpus import seed_expanded_corpus
    from mars.memory.expanded_experiment import run_benchmark
    from mars.memory.retrieval_source import CortexRetrievalSource

    corpus = load_expanded_corpus("salience-memory-v1-expanded")
    small = ExpandedCorpus(name="t", project="mars", queries=corpus.queries[:5])
    cx = _FakeCortex()
    gold, pools, _ = seed_expanded_corpus(cx, small)
    for q, ids in pools.items():
        cx.register_pool(q, list(ids))
    source = CortexRetrievalSource(cx, project="mars", gold_map=gold, pools=pools, limit=100)
    result = run_benchmark(source, [q.query for q in small.queries])
    assert result.semantic_available is True
    # importance-aware salience should recover more relevant @5 than similarity-only,
    # since distractors are engineered to have higher similarity.
    assert result.candidate.recall[5] >= result.baseline.recall[5]
    assert result.candidate.ndcg[5] > result.baseline.ndcg[5]
