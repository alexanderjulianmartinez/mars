# Salience Memory — Noisy-Importance Study (Track 1)

How much of the Salience Memory v1 win survives when the importance signal is
**noisy** rather than a clean oracle? v1 measured salience-weighted retrieval with
importance authored as ground truth (relevant memories high, distractors low), so
its effect size is an **upper bound**. This study degrades importance across a
quality grid and asks the production-relevant question:

> How good does Cortex's importance estimate need to be for salience weighting to
> still beat plain semantic retrieval — and how much of the win is the importance
> *signal* versus the rest of the salience blend?

- Result data: `mars-experiments/salience-memory-noisy-importance.json`
- Reproduce: `python experiments/run_noisy_importance.py --no-seed --db <cortex.db>`
  (one live retrieval pass, cached), then `--cache-only` to re-sweep offline.
- Code: `mars/memory/importance_noise.py` (noise model),
  `mars/memory/noisy_importance_experiment.py` (sweep + stats).

## Method

| | |
| --- | --- |
| Corpus | `salience-memory-v1-expanded` (552 memories, 30 queries) — unchanged |
| Retrieval | real Cortex over MCP, Voyage embeddings (`semantic_available: true`) |
| Candidate pool | per-query controlled pool; both arms re-rank the **same** retrieved set |
| Baseline | `similarity_only` (rank by semantic score) — **importance-invariant** |
| Candidate | `salience_weighted_v1` (0.40 sim + 0.30 importance + 0.20 recency + 0.10 freq) |
| Importance noise | shuffle model — a fraction `1−quality` of each pool's importance values are permuted among themselves (distribution preserved, assignment degraded) |
| Quality grid | 1.00 (oracle) / 0.75 / 0.50 / 0.25 / 0.00 (scrambled) |
| Noise seeds/level | 25 (per-query metric = mean across seeds; corruption is high-variance on ~12-memory pools) |
| Significance | paired bootstrap (10k) over the 30 queries, `salience(noisy) − similarity_only` |

**Why corrupt importance post-retrieval rather than re-seed?** Importance affects
neither the embeddings nor which memories the similarity search returns (the pool
is fixed) — it only feeds the salience ranking. So corrupting it on the retrieved
pool is faithful to re-seeding Cortex with corrupted labels, while avoiding
re-embedding all 552 memories once per noise level. The oracle level (quality
1.00) reproduces the v1 expanded result **exactly** (recall@5 +0.435, nDCG@5
+0.530, MRR +0.654), which validates the pipeline.

## Results

Baseline (`similarity_only`): recall@5 = 0.237, nDCG@5 = 0.184, MRR = 0.313.
Ablated floor (`salience_no_importance`, importance weight zeroed): recall@5 =
0.237, nDCG@5 = 0.184, MRR = 0.313 — **identical to the baseline**, because in
this corpus recency is uniform and frequency is 0, so removing importance leaves
ranking by similarity alone.

| importance quality | recall@5 | Δ recall@5 (95% CI) | nDCG@5 | Δ nDCG@5 (95% CI) | MRR | Δ MRR (95% CI) |
| --- | --- | --- | --- | --- | --- | --- |
| 1.00 (oracle) | 0.672 | +0.435 [+0.370, +0.503] | 0.714 | +0.530 [+0.475, +0.585] | 0.967 | +0.654 [+0.569, +0.726] |
| 0.75 | 0.593 | +0.356 [+0.302, +0.414] | 0.613 | +0.429 [+0.386, +0.472] | 0.864 | +0.551 [+0.478, +0.612] |
| 0.50 | 0.506 | +0.269 [+0.218, +0.322] | 0.507 | +0.323 [+0.280, +0.364] | 0.746 | +0.434 [+0.358, +0.496] |
| 0.25 | 0.420 | +0.183 [+0.142, +0.224] | 0.392 | +0.208 [+0.177, +0.239] | 0.584 | +0.271 [+0.206, +0.331] |
| 0.00 (scrambled) | 0.330 | +0.094 [+0.050, +0.139] | 0.281 | +0.097 [+0.065, +0.130] | 0.423 | +0.110 [+0.049, +0.160] |

Every CI excludes zero, so the salience arm beats plain semantic retrieval at
**every** tested importance quality — the minimum quality that still beats the
baseline is **0.00**.

## Interpretation

1. **Graceful, monotonic degradation.** The advantage shrinks smoothly as
   importance degrades — recall@5 Δ falls +0.435 → +0.356 → +0.269 → +0.183 →
   +0.094. There is no cliff: salience does not suddenly collapse at some noise
   threshold. Even at half-corrupted importance (quality 0.50) salience retains
   well over half its oracle gain (recall@5 +0.269, nDCG@5 +0.323).

2. **The importance *signal's* true contribution is oracle − scrambled.** The
   q=0.00 row still beats the baseline by +0.094, but that is **not** importance
   information — at q=0 importance is random, so the residual edge comes from the
   *stochastic perturbation* breaking this corpus's adversarial similarity
   ordering (distractors are authored to out-similar the relevant memories, so
   any reshuffle of the thin top-of-pool margin tends to surface buried relevant
   memories). The honest measure of the importance signal is **oracle minus
   scrambled** — same blend, differing only in whether importance points at the
   right memory: **recall@5 0.672 → 0.330 = +0.341**, roughly **78% of the
   advantage over baseline is carried by the importance signal itself**, the
   remaining ~22% by the blend's perturbation of a misleading similarity ranking.

3. **The ablated floor pins the blend's value at zero here.** With importance
   weight zeroed, salience collapses exactly onto the similarity baseline
   (0.237), confirming that on this corpus *all* of salience's deterministic
   value comes from importance — recency and frequency contribute nothing because
   they are uniform (everything seeded at once, no access history). This is the
   same caveat flagged in v1 and is exactly what Track 3 (Temporal Cognition) and
   the frequency work will exercise.

## Decision

**Continue.** Salience weighting is **robust to substantial importance noise**:
on this benchmark it beats semantic retrieval across the entire quality range, and
even at 50%-corrupted importance it keeps a large, significant gain. The dependence
on importance quality is smooth and predictable, not brittle. For a production
store where Cortex's importance estimate is imperfect, this is the encouraging
answer — the signal does not need to be near-perfect to pay off.

## Weaknesses / threats to validity

1. **Upper-bound corpus.** Importance and relevance are perfectly correlated by
   construction, so the oracle is maximally informative; a real store's importance
   may be both noisier *and* less correlated with task relevance than a clean
   shuffle of an oracle. This study degrades *accuracy of assignment*, not the
   *ceiling correlation*.
2. **Adversarial baseline inflates the q=0 floor.** Because similarity is authored
   to be actively misleading, random perturbation alone beats it; on a corpus
   where similarity is merely weak (not adversarial) the scrambled-importance row
   would likely sit at or below baseline. The oracle−scrambled contribution is the
   noise-robust headline, not the q=0 Δ-vs-baseline.
3. **Recency/frequency untested.** Both are uniform here, so the blend's non-
   importance terms add nothing — pair this with the recency sub-study (stagger
   `created_at`) to isolate those terms.
4. **Single weight set.** One importance weight (0.30). A natural follow-up is to
   sweep the importance weight jointly with quality (does a lower importance weight
   help when importance is known to be noisy?).

## Next

- **Recency sub-study (Track 3):** stagger timestamps so `recency_factor` carries
  signal; re-run this sweep to see whether recency compensates as importance
  degrades.
- **Importance-weight × quality grid:** find the weight that is most robust to
  noisy importance (adaptive down-weighting of an untrusted signal).
- **Learned importance (Track 1 cont.):** replace authored/shuffled importance
  with an estimator and measure where on this curve it lands.
