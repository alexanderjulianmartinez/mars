# Salience Memory v1 — Expanded Benchmark Corpus

The original `salience-memory-v1` corpus (4 queries, 13 memories, 2–4 memories
per query) is a **smoke test**: with k=5 retrieval and ≤4 candidates per query,
every relevant memory fits in the top-5, so **recall@5 saturates at 1.0 for every
strategy**. It can detect ranking changes (MRR) but cannot detect retrieval-
*coverage* changes — which is exactly the claim the Salience Memory hypothesis is
about. This document describes the expanded corpus built to fix that.

- Corpus: `experiments/corpus/salience-memory-v1-expanded.corpus.yaml`
- Generator (reproducible): `experiments/corpus/generate_expanded.py` + `scenarios_data.py`
- Validator: `mars corpus validate salience-memory-v1-expanded`
- Stats: `mars corpus stats salience-memory-v1-expanded`

## Research question

> Does salience-weighted memory retrieval (similarity + importance + recency +
> frequency) improve retrieval **quality** relative to semantic similarity alone?

Working hypothesis: salience improves **prioritization and coverage under a tight
budget** — it surfaces important-but-not-closest memories and demotes plausible
look-alikes — rather than simply re-ordering an already-complete result set.

## Corpus statistics

| Statistic | Value |
| --- | --- |
| Queries | 30 |
| Total memories | 552 |
| Memories per query | ~18.4 |
| Domains | 6 (database, reliability, security, architecture, agent-systems, code-review), 5 queries each |
| Relevant per query (target + support) | 4–6 (mean 4.4); 6 queries exceed k=5 |
| Retrieval cutoffs supported | recall/precision @1/3/5/10, MRR, nDCG@5/10, TargetFound@1/3/5, ContextEfficiency |

### Category breakdown

| Category | Count | Role |
| --- | --- | --- |
| target | 30 | The primary memory we want retrieved (1 per query, importance 0.85–1.0) |
| relevant | 102 | Helpful support (importance 0.5–0.85) |
| distractor | 210 | High keyword/semantic overlap, low importance (0.05–0.25) — should fool similarity |
| stale | 90 | Once correct, now outdated (low importance + low novelty) |
| contradictory | 30 | Directly conflicts with the target (for future contradiction research) |
| low_confidence | 90 | Possibly incorrect, unverified (confidence 0.1–0.4) |

Every memory carries `importance`, `novelty`, `urgency`, `confidence`, and a
`category`; every query carries explicit `target_memories` and `relevant_memories`
gold lists. Signal values are drawn deterministically (`seed=1729`) from each
category's range, so the corpus is byte-stable across regeneration.

### Example query

**Query:** *what caused the authentication outage and how was it remediated*

- **Target** (`rel-auth-outage-target-0`, importance 0.90): *"The auth outage was a
  token clock-skew bug: nodes drifted, so freshly issued JWTs failed not-before
  validation; the fix pins NTP and widens the nbf/exp tolerance to 60 seconds."*
- **Distractor** (`rel-auth-outage-distractor-0`, importance 0.08): *"The login page
  copy was updated and the outage banner component was removed afterward."*
  — high keyword overlap ("outage", "login", "auth") but useless for the question.

## Why semantic-only retrieval may struggle here

Distractors are written to be **semantically adjacent** to the query: same domain
vocabulary, same incident nouns, similar phrasing — but low importance and no
real answer. A pure nearest-neighbor retriever ranks on surface similarity, so:

- with ~13 plausible non-relevant memories per query competing for 5 slots, a
  similarity-only ranker is expected to spend budget on look-alikes and **miss
  some of the 4–6 truly relevant memories → recall@5 < 1.0**;
- **stale** and **contradictory** memories are often *more* keyword-similar to the
  query than the correct target (they're about exactly the same topic), so they
  actively pull a similarity ranker toward wrong answers.

This is the saturation break: unlike the smoke test, the retriever now sees far
more candidates than it can return, so coverage becomes measurable.

## Why salience weighting may help

The target and relevant-support memories carry **high importance** (0.5–1.0) while
distractors/stale/low-confidence carry **low importance** (0.05–0.3). A ranker that
blends importance and recency with similarity can:

- promote the high-importance target above equally-similar but low-value distractors;
- demote **stale** memories via recency and **low-confidence** memories via confidence;
- recover relevant memories that are important but not the closest embedding match.

If the hypothesis holds, we expect salience to lift **recall@5, precision@5, and
nDCG@5/10** over the similarity-only baseline — not just MRR.

## Limitations

- **Synthetic content.** Scenarios are hand-authored to be realistic, but they are
  not sampled from a production memory store; absolute scores are not externally
  comparable. Treat this as a controlled discrimination benchmark, not a leaderboard.
- **Binary relevance.** Metrics use binary gold (relevant vs not); graded relevance
  (target ≫ support) is only partially captured via nDCG's ranking sensitivity.
- **Distractor difficulty is authored, not measured.** "Plausible" is a human
  judgment; once embeddings are run we should confirm distractors actually land
  close to the target in embedding space (otherwise they're too easy).
- **Recall normalization.** `recall@k` here divides by `min(k, |relevant|)`, so a
  query with 6 relevant can still reach recall@5 = 1.0 if the top-5 are all
  relevant. Discrimination therefore comes primarily from the **distractor pool
  size**, reinforced by precision@k and nDCG; recall@10 gives the >5-relevant
  queries room to separate.
- **Not yet run against real Cortex.** Seeding 552 memories with embeddings is a
  paid step (Voyage) and is intentionally left as an explicit next action.

## How to run it

```bash
mars corpus validate salience-memory-v1-expanded   # structural checks
mars corpus stats    salience-memory-v1-expanded   # counts + category breakdown
# Real semantic run (paid; seeds 552 embedded memories into an isolated Cortex DB)
# is the next step — see docs/SALIENCE_MEMORY_V1.md for the seed/run commands.
```

## Discrimination estimate

The smoke test could not separate strategies because **recall@5 = 1.0 for both
arms by construction**. The expanded corpus removes that ceiling: with ~18
candidates and only 4–6 relevant per query, a retriever must *choose* 5 of 18, and
~13 of those 18 are plausible non-answers. A similarity-only baseline that is
fooled by the high-overlap distractors will score recall@5 and precision@5 strictly
below a perfect ranker, leaving measurable headroom for salience to fill. The
benchmark is therefore expected to **discriminate similarity_only from
salience_weighted_v1 on coverage metrics (recall@5/precision@5/nDCG), not just MRR**
— pending confirmation from a real embedded run.
