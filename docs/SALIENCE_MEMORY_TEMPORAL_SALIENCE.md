# Salience Memory — Temporal Salience Study (Experiment 3)

> Does time improve or degrade salience-weighted memory retrieval?

Experiment 1 showed salience beats semantic retrieval when importance is
informative; Experiment 2 showed that win is robust to noisy importance. In both,
all memories were seeded at once, so the recency term contributed ≈0. This
experiment **isolates the temporal signal**: it assigns synthetic timestamps to
the (real, cached) candidate pools under four regimes and asks whether recency —
raw or decayed — helps, hurts, or is neutral, and whether it earns a place in the
Salience v2 formula.

- Result data: `mars-experiments/salience-memory-temporal-salience.json`
- Code: `mars/memory/temporal_salience.py`, `experiments/run_temporal_salience.py`
- Reproduce (offline, deterministic): `python experiments/run_temporal_salience.py --seeds 10`

## Method

| | |
| --- | --- |
| Corpus | `salience-memory-v1-expanded` (552 memories, 30 queries) — unchanged |
| Candidate pools | the committed real-retrieval cache from Experiment 2 (real Voyage semantic scores + importance + gold). **Nothing is re-embedded**; only timestamps + strategy vary. |
| Timestamps | synthetic, assigned per regime; raw recency normalized within each pool (newest=1, oldest=0); decay = `exp(-age_days / half_life)` |
| Seeds/regime | 10 (ages are drawn with a seeded RNG; per-query metric = mean across seeds) |
| Significance | paired bootstrap (95% CI) over the 30 queries vs the `similarity_only` baseline |

**Timestamp regimes**

| regime | ages | purpose |
| --- | --- | --- |
| **A — uniform** | all memories share one age | control — recency carries no signal; verify no accidental temporal effect |
| **B — recency-aligned** | target/relevant newer (0–20d), rest older (60–180d) | recency *should* help |
| **C — recency-misaligned** | distractors newer, target/relevant older | recency *should* hurt |
| **D — mixed realistic** | ages drawn independently of relevance (0–180d) | the realistic case — importance should dominate |

**Strategies.** `similarity_only` (baseline), `importance_only`, `recency_only`,
`sim_plus_importance` (0.65·sim + 0.25·imp — the blend with the **temporal weight
zeroed**, used as the anchor to isolate recency), `importance_plus_recency`
(0.65·sim + 0.25·imp + 0.10·recency), and `importance_plus_decay_h{7,30,90}`
(same blend with decayed recency). Temporal blend weights are the spec defaults.

**Isolating recency honestly.** The recency *marginal* is
`importance_plus_recency − sim_plus_importance`: the similarity and importance
weights are identical in both arms, so the delta is the 0.10 recency term **alone**
— not the importance-vs-similarity reweighting. This is the number that answers
"does adding recency help?"

## Results (recall@5; full metric suite in the JSON)

| strategy | A uniform | B aligned | C misaligned | D mixed |
| --- | --- | --- | --- | --- |
| `similarity_only` (baseline) | 0.237 | 0.237 | 0.237 | 0.237 |
| `importance_only` | **0.985** | **0.985** | **0.985** | **0.985** |
| `sim_plus_importance` (anchor) | 0.455 | 0.455 | 0.455 | 0.455 |
| `recency_only` | 0.805¹ | 0.992 | **0.008** | 0.433 |
| `importance_plus_recency` | 0.455 | 0.717 | 0.248 | 0.470 |
| `importance_plus_decay_h7` | 0.455 | 0.599 | **0.357** | 0.465 |
| `importance_plus_decay_h30` | 0.455 | 0.725 | 0.241 | 0.466 |
| `importance_plus_decay_h90` | 0.455 | 0.703 | 0.270 | 0.479 |

**Isolated recency marginal** (`importance_plus_recency − sim_plus_importance`, recall@5, paired 95% CI):

| regime | marginal | verdict |
| --- | --- | --- |
| A uniform | +0.000 [+0.000, +0.000] | neutral (control passes) |
| B aligned | **+0.262** [+0.210, +0.316] | recency **helps** |
| C misaligned | **−0.206** [−0.262, −0.155] | recency **hurts** |
| D mixed realistic | +0.015 [−0.025, +0.055] | **neutral** (CI spans 0) |

¹ `recency_only` under the uniform regime (0.805) is **not** a temporal effect:
uniform ages make every recency value identical, so ranking falls back to the
cache's arrival order (Cortex's native ranking, which is decent). It is shown for
transparency; the marginal analysis uses non-tied strategies and is unaffected.

## Analysis (the required questions)

**1. Does recency help when aligned with relevance?** Yes, strongly and
significantly. When relevant memories are genuinely newer, `recency_only` reaches
recall@5 0.992 (near-perfect) and the isolated recency marginal is +0.262
[+0.210, +0.316]. *But this is the most favourable, least realistic regime.*

**2. Does recency hurt when misaligned?** Yes, by a nearly symmetric amount.
When distractors are newer, `recency_only` collapses to 0.008 (well below the
0.237 similarity baseline) and the isolated marginal is −0.206 [−0.262, −0.155].
Raw recency actively pulls newer-but-wrong memories into the budget.

**3. Does importance remain robust under temporal noise?** Yes — completely.
`importance_only` is **regime-invariant** at recall@5 0.985 / nDCG@5 0.982 / MRR
1.000 across all four regimes. Time neither helps nor harms importance; importance
is the dominant, time-stable salience signal.

**4. Does importance + recency outperform importance alone?** No. (a) Against
`importance_only` (0.985), no temporal blend at the spec's 0.65 similarity weight
comes close (best ≈0.72) — similarity dilution on this adversarial corpus costs
more than recency adds. (b) Against the fair anchor `sim_plus_importance` (0.455),
adding raw recency helps only when aligned, hurts when misaligned, and is
**statistically neutral in the realistic mixed regime** (+0.015, CI spans 0). So
recency does not reliably improve retrieval.

**5. Which temporal weighting strategy is safest?** Short half-life decay
(`importance_plus_decay_h7`). It is the **only** temporal strategy that
significantly beats the similarity baseline in *every* regime, including misaligned
C (+0.121 [+0.081, +0.164]). A short half-life compresses recency's influence,
capping both its upside (B: +0.362 vs raw +0.480) and — crucially — its downside
(C: stays positive while raw recency and longer half-lives fall to a tie or worse).
Raw recency and long half-lives (h30/h90) swing widely and are risky under
misalignment.

**6. Should recency be included in Salience v2?** Only as a weak, decayed,
gated feature — **not** a primary signal. In the realistic mixed regime raw recency
adds nothing; its benefit shows up only under the artificial aligned regime, while
it does real damage when misaligned; and importance dominates it everywhere.

## Interpretation vs the expected outcomes

This run matches **Outcome A** (recency helps only when aligned), **Outcome B**
(raw recency is risky — symmetric harm when misaligned), and **Outcome C**
(importance dominates recency). **Outcome D** (decay helps) holds only in the
narrow sense that *short-half-life* decay is **safer** than raw recency, not that
decay unlocks new gains — it never beats `importance_only`.

The key question was not whether time *can* help (it can, under regime B) but
whether it helps **reliably enough across regimes** to justify inclusion. It does
not: in the realistic regime its marginal is indistinguishable from zero, and its
downside risk under misalignment is real.

## Recommendation for Salience v2

1. **Keep importance as the primary salience signal.** It is the strongest and the
   only signal invariant to temporal structure.
2. **Do not include raw recency as a core weighted term.** Its realistic-regime
   contribution is statistically zero and its misalignment downside is large.
3. **If a temporal term is included, use short-half-life decay (≈7 days) at a low
   weight, gated by importance/confidence** so a fresh-but-unimportant memory can
   never displace an old-but-important one. This is the only configuration that
   was never significantly harmful here.
4. **Revisit with reinforcement-style recency** (access frequency / recall counts)
   rather than write-time recency — write-time age is exactly the signal that
   misalignment breaks.

**Decision: Continue research — but recency is NOT promoted to a core Salience v2
signal.** Importance remains primary; temporal weighting is, at best, an optional
short-decay, low-weight, importance-gated add-on.

## Weaknesses / threats to validity

1. **Synthetic timestamps.** Ages are assigned, not observed; real stores will sit
   somewhere between regimes B/C/D. The mixed regime (D) is the best proxy and is
   where recency is neutral.
2. **Adversarial similarity.** The corpus is built so distractors out-similar
   relevant memories, which is why the 0.65-similarity blends underperform
   `importance_only`. The temporal comparison is fair (all temporal arms share the
   same similarity weight), but absolute blend numbers are corpus-specific.
3. **Cached arrival-order artifact** in `recency_only` under the uniform regime
   (footnote 1) — flagged, and excluded from the marginal analysis.
4. **Write-time recency only.** Reinforcement/access-frequency recency is untested
   (see recommendation 4) and is the natural follow-up.
