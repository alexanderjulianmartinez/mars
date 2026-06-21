# Reviewer Notes — *Salience-Weighted Memory Retrieval for Long-Horizon Software Agents* (v1)

Internal review notes for the draft at
`docs/papers/salience_weighted_memory_retrieval_v1.md`. These notes are for the
authors, not for publication. The goal is to stress-test the draft before external
review.

---

## 1. Strongest claims (well-supported)

- **Importance-weighted retrieval beats similarity-only on this benchmark.** Every
  metric improves; recall@5 +0.435 (95% CI [+0.367, +0.502]) and nDCG@5 +0.531
  (95% CI [+0.474, +0.583]) with 29/1/0 and 30/0/0 per-query directionality. The
  significance is genuine and the effect is broad-based, not a one-query fluke.
- **The mechanism is verified, not inferred.** The migration-query trace (three
  distractors at sim ≈ 0.77–0.79 / importance ≈ 0.04–0.07 burying the target at rank
  6) shows the ranker doing exactly what the corpus was designed to test. This is the
  single most defensible part of the paper.
- **The benchmark is non-saturating and frozen.** The 13-memory smoke test saturating
  at recall@5 = 1.0 is good evidence the new corpus actually discriminates; the
  hash-pin (SHA256 `a464085c…`) supports reproducibility claims.
- **Honesty constraint is real and enforced.** The `semantic_score: null` guard means
  the semantic baseline claim is not hand-waved.

## 2. Weakest claims (most exposed)

- **The headline effect size is a near-oracle artifact.** Importance is authored to
  be high on relevant memories and low on distractors; the ranker is fed the answer.
  The paper says this (calls it an upper bound), but a skeptical reader will still
  read +0.435 as inflated. This is the paper's central vulnerability.
- **"Substantially improves retrieval quality" generalizes further than one corpus,
  one weight set, one embedding model can support.** Internally valid, externally
  unproven. The draft's hedges are correct but a reviewer will want at least a weight
  sensitivity sweep or a second embedding model.
- **Prioritization / attention-allocation framing** is interpretive. It is reasonable
  but unmeasured — there is no direct measurement of "context budget spent on useful
  memories" beyond ContextEfficiency@5, which is itself defined to reward this.

## 3. Assumptions worth surfacing

- Importance is correlated with relevance (by authoring). The whole result rests on
  this correlation being present and informative.
- Recency and frequency are constant across each query's pool (simultaneous seeding),
  so the v1 formula reduces in practice to sim + importance. The paper states this;
  reviewers may still ask why a four-term formula is presented when two terms are
  inert.
- Both strategies re-rank an identical pool, so first-stage recall is assumed fixed
  and out of scope. A real deployed system might let the ranker influence pool
  selection.
- Gold relevance labels are correct and complete. Synthetic authoring makes this
  defensible but unverified against any external judgment.

## 4. Limitations (already in the paper — confirm none were dropped)

1. Authored importance → upper bound. ✓
2. Synthetic benchmark → external validity open. ✓
3. Recency/frequency inert → no temporal evidence; effective contrast is sim vs
   sim+importance. ✓
4. No execution evaluation → no agent task-success claim. ✓
5. Single embedding model + single weight set → numbers are config-specific. ✓

Gaps not yet explicit enough: (a) no weight-sensitivity analysis; (b) no
inter-annotator / label-quality check on the synthetic gold; (c) shared-pool
re-ranking caveat is stated but easy to miss.

## 5. Likely reviewer objections (full list)

- "Your importance signal is the label in disguise — this measures benchmark
  construction, not a method." (Most likely and most serious.)
- "Synthetic corpus; show me real memory traces or at least a realistic distribution."
- "One embedding model, one weight set — where is the ablation/sweep?"
- "Retrieval metrics are a proxy; without an execution result, why should a systems
  audience care?"
- "Novelty is thin — scalar memory importance and hybrid ranking already exist."
- "Why present a 4-term formula when 2 terms are provably inert in your only
  experiment?"
- "n = 30 queries is small for a benchmark paper; bootstrap CIs help but the
  population is tiny and hand-built."
- "Shared-pool re-ranking understates the difficulty of end-to-end retrieval."

## 6. Recommended next experiments (priority order)

1. **Noisy-importance sweep** — degrade importance from oracle → random; report where
   the advantage lands and whether any CI crosses zero. Directly answers objection #1.
   *(Note: completed in the program; folding its result in would materially strengthen
   the paper.)*
2. **Execution impact via AutoDev** — the result a systems venue actually wants;
   answers objection #4. *(Partially completed in the program: retrieval and behavior
   change demonstrated, task-success unchanged — this is honest and publishable as a
   null, but must not be overclaimed.)*
3. **Weight-sensitivity + second embedding model** — cheap, directly answers
   objections #3 and #6.
4. **Learned-importance estimator** — replace authored importance; locate it on the
   noisy curve. The experiment that determines real-world reachability of the ceiling.
5. **Real-world memory traces** — external validity; the hardest and highest-value.

---

## Final assessment

### Top 5 likely reviewer criticisms

1. **Authored importance is circular** — the benchmark may encode the answer into the
   ranked signal, so +0.435 is an upper bound, not a method result.
2. **Synthetic benchmark** — no evidence it reflects real production memory.
3. **No execution / downstream result** — retrieval gains are a proxy; a systems
   audience wants task-success.
4. **Thin novelty** — scalar importance and hybrid ranking are prior art; the
   contribution is the controlled measurement, which must be framed as such.
5. **Single configuration, small n** — one embedding model, one weight set, 30
   hand-built queries; needs sweeps and (eventually) scale.

### Readiness recommendation

| Track | Ready? | Rationale |
| --- | --- | --- |
| **Technical Report** | **Yes — now.** | Claims are scoped, limitations explicit, results reproducible against a frozen hash. This is the right home for the current evidence. |
| **Research Blog** | **Yes — now.** | The mechanism story (importance rescues the buried target) is accessible and honest. Lead with the upper-bound caveat. |
| **Open-Source Release** | **Yes — now.** | The frozen corpus + reproduction commands are publishable and invite external validation; the hash-pin makes this safe. |
| **arXiv** | **Not yet — close.** | The standalone v1 retrieval result is too narrow and too exposed on the circularity objection to stand alone at arXiv. Fold in the noisy-importance sweep (defuses #1), a weight/embedding ablation (defuses #3, #5), and the honest execution null (addresses #4), and it becomes a credible workshop/arXiv submission. |

**Experiments to complete before arXiv submission:**

1. Noisy-importance sweep — *mandatory*; it is the direct answer to the strongest
   objection.
2. Weight-sensitivity + a second embedding model — *strongly recommended*; cheap and
   closes the "single configuration" objection.
3. Execution-impact study reported honestly (retrieval/behavior change vs. unchanged
   task-success) — *recommended*; converts the proxy-metric objection into a
   contribution, provided the null is stated plainly and not dressed up.
4. (Optional but high-value) A first learned-importance estimator to show the upper
   bound is at least partially reachable.
