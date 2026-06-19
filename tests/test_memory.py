import statistics

from mars.memory import (
    SalienceWeightedStrategy,
    SimilarityOnlyStrategy,
    generate_case_memories,
    retrieval_quality,
)


def test_memory_generation_is_deterministic():
    a = generate_case_memories("add-health-endpoint", trial=3)
    b = generate_case_memories("add-health-endpoint", trial=3)
    assert [m.id for m in a] == [m.id for m in b]
    assert all(x.similarity == y.similarity for x, y in zip(a, b))


def test_generation_has_expected_relevant_count():
    mems = generate_case_memories("c", trial=0, n_memories=24, n_relevant=6)
    assert len(mems) == 24
    assert sum(1 for m in mems if m.relevant) == 6


def test_salience_weights_normalize():
    s = SalienceWeightedStrategy(w_similarity=4, w_importance=3, w_recency=2, w_frequency=1)
    total = s.w_similarity + s.w_importance + s.w_recency + s.w_frequency
    assert abs(total - 1.0) < 1e-9


def test_salience_beats_similarity_on_average_recall():
    sim = SimilarityOnlyStrategy()
    sal = SalienceWeightedStrategy()
    sim_q, sal_q = [], []
    for trial in range(30):
        mems = generate_case_memories("case", trial=trial)
        sim_q.append(sim.retrieve(mems, 5).quality)
        sal_q.append(sal.retrieve(mems, 5).quality)
    # Salience retrieval should recover more relevant memories on average.
    assert statistics.fmean(sal_q) > statistics.fmean(sim_q) + 0.1


def test_retrieval_quality_bounds():
    mems = generate_case_memories("c", trial=1)
    q = SimilarityOnlyStrategy().retrieve(mems, 5).quality
    assert 0.0 <= q <= 1.0


def test_retrieval_quality_zero_when_no_relevant():
    from mars.memory.models import MemoryItem

    mems = [MemoryItem(id=str(i), content="", similarity=0.5) for i in range(5)]
    assert retrieval_quality(mems, mems[:3], 3) == 0.0
