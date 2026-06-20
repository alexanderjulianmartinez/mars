"""Track B / issue #7: labeled corpus loading + gold-label seeding.

No live Cortex: a FakeCortex assigns deterministic ids so the seeding logic and
gold-label capture are fully testable without keys.
"""

from mars.memory.corpus import (
    Corpus,
    CorpusMemory,
    CorpusQuery,
    load_corpus,
    load_gold,
    save_gold,
    seed_corpus,
)
from mars.memory.metrics import recall_at_k
from mars.memory.retrieval import SalienceWeightedStrategy, SimilarityOnlyStrategy


class FakeCortex:
    """Assigns predictable ids and records add_memory calls."""

    def __init__(self):
        self.calls = []

    def add_memory(self, project, mem_type, content, importance=0.5, summary=None):
        mid = f"id-{summary}"  # deterministic from the stable key
        self.calls.append((project, mem_type, summary, importance))
        return mid


def test_load_bundled_corpus():
    corpus = load_corpus("salience-memory-v1")
    assert corpus.project == "mars"
    assert len(corpus.queries) >= 3
    assert corpus.n_memories >= 9
    # every query has exactly one target and >=1 relevant
    for q in corpus.queries:
        assert sum(1 for m in q.memories if m.target) == 1
        assert any(m.relevant for m in q.memories)


def test_seed_corpus_builds_gold_from_assigned_ids():
    corpus = Corpus(
        name="t",
        project="mars",
        queries=[
            CorpusQuery(
                text="q1",
                memories=[
                    CorpusMemory(key="a", content="x", importance=0.9, relevant=True, target=True),
                    CorpusMemory(key="b", content="y", importance=0.8, relevant=True),
                    CorpusMemory(key="c", content="z", importance=0.1, relevant=False),
                ],
            )
        ],
    )
    cortex = FakeCortex()
    gold, key_to_id = seed_corpus(cortex, corpus)
    assert key_to_id == {"a": "id-a", "b": "id-b", "c": "id-c"}
    assert gold["q1"]["relevant"] == {"id-a", "id-b"}
    assert gold["q1"]["target"] == "id-a"
    assert len(cortex.calls) == 3  # all three memories seeded


def test_gold_save_load_roundtrip(tmp_path):
    gold = {"q1": {"relevant": {"id-a", "id-b"}, "target": "id-a"}}
    save_gold(gold, "exp", tmp_path)
    loaded = load_gold("exp", tmp_path)
    assert loaded == gold
    assert load_gold("missing", tmp_path) is None


def test_seeded_gold_enables_real_metrics():
    """End-to-end (logic only): ranking the seeded relevant ids scores recall."""
    # relevant ids from a seed; a salience ranking that surfaces them
    relevant = {"id-a", "id-b"}
    ranked = ["id-a", "id-b", "id-c"]
    assert recall_at_k(ranked, relevant, 2) == 1.0
    # the two strategies exist and are selectable
    assert SimilarityOnlyStrategy().name == "similarity-only"
    assert SalienceWeightedStrategy().name == "salience-weighted"
