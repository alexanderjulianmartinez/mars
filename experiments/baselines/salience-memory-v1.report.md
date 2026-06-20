<!-- Locked baseline — synthetic source, reproducible. Regenerate: mars experiments run salience-memory-v1 -->

# Retrieval Experiment Report

**Experiment:** salience-memory-v1
**Retrieval provider:** synthetic
**Execution provider:** mock
**Semantic scores:** available
**Queries:** 6  **k:** 5

## Hypothesis

Salience-weighted memory retrieval (similarity + importance + recency + frequency) surfaces more of the truly-relevant memories than similarity-only retrieval, especially "long-horizon" memories that are important but not the most semantically similar to the query.

## Methodology

For each query, fetch candidate memories from the retrieval source, rank them with the baseline and candidate strategies, and compute retrieval metrics @k against gold relevance labels. Aggregate (mean) across queries. Execution is mocked; only retrieval quality is measured. If the source cannot provide semantic scores (Cortex embeddings disabled), the result is flagged and must not be read as semantic-vs-salience evidence.

## Metrics

| Metric | baseline (similarity_only) | candidate (salience_weighted_v1) | Δ (cand − base) |
| --- | --- | --- | --- |
| recall@k | 0.500 | 0.967 | +0.467 |
| precision@k | 0.500 | 0.967 | +0.467 |
| MRR | 1.000 | 1.000 | +0.000 |
| target found rate | 0.500 | 1.000 | +0.500 |
| context efficiency | 0.500 | 0.967 | +0.467 |

## Limitations

None noted.
- Synthetic corpus: simulated retrieval signals, not real Cortex memories — illustrative only, not production evidence.

## Recommendation

salience_weighted_v1 outperforms similarity_only on recall@5 (Δ +0.467) over 6 queries (source=synthetic).