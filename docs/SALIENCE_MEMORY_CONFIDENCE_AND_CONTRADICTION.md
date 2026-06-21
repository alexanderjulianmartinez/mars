# Salience Memory — Confidence & Contradiction Study (Experiment 4)

> All results are reported against Salience Memory Benchmark v1.0.0
> (`salience-memory-benchmark-v1`). See
> [SALIENCE_MEMORY_BENCHMARK_V1.md](SALIENCE_MEMORY_BENCHMARK_V1.md).

> Can confidence-aware retrieval improve memory prioritization — and can it help
> agents avoid retrieving outdated, incorrect, or contradictory memories?

Importance is the dominant salience signal found so far (Exp 1–3). This experiment
asks the next question: **what should happen when an important memory may be
wrong?** A memory can be important *and* untrustworthy — e.g. an obsolete "use
integer IDs" decision later superseded by "use UUIDs". Confidence-aware retrieval
should prioritize the trustworthy memory and suppress the contradictory one.

- Result data: `mars-experiments/salience-memory-confidence-and-contradiction.json`
- Code: `mars/memory/confidence_contradiction.py`, `experiments/run_confidence_contradiction.py`
- Reproduce (offline, deterministic): `python experiments/run_confidence_contradiction.py --seeds 10`

## Method

| | |
| --- | --- |
| Corpus | `salience-memory-v1-expanded` (552 memories, 30 queries) — unchanged |
| Candidate pools | the committed real-retrieval cache from Exp 2 (real Voyage semantic scores + importance + gold), **joined to the corpus by content** to recover each memory's authored `category` + `confidence`. Nothing re-embedded. |
| Confidence | synthetic per regime; regime D uses the authored per-category confidence (realistic) |
| Seeds/regime | 10 (confidence drawn from seeded bands; per-query metric = across-seed mean) |
| Significance | paired bootstrap (95% CI) over the 30 queries vs the `similarity_only` baseline |
| Contradiction eligibility | 28 of 30 queries have both the `target` and ≥1 `contradictory` memory in the cached pool |

**Strategies.** `similarity_only`, `importance_only`, `confidence_only`,
`sim_plus_importance` (0.65·sim + 0.25·imp — the anchor with the confidence weight
zeroed), `importance_plus_confidence` (0.65·sim + 0.25·imp + 0.10·conf),
`importance_plus_confidence_gated` (**0.65·sim + 0.35·(importance × confidence)** —
confidence multiplies importance, so an untrusted memory's importance is
discounted), and `importance_plus_recency_plus_confidence` (comparison only;
0.60·sim + 0.20·imp + 0.10·conf + 0.10·recency, recency = flat cache value).

**New metric — ContradictionAvoidanceRate (CAR).** Over contradiction-eligible
queries, the fraction where the correct `target` outranks **every** obsolete
`contradictory` memory present. This is the metric that directly measures "did we
avoid the outdated/incorrect memory?"

**Confidence regimes.** A high-everywhere (control); B low-confidence distractors;
C contradictory (obsolete = low confidence); D mixed-realistic (authored
confidence). Plus a fifth **H4 stress regime, E**, added because regimes A–D cannot
test the experiment's motivating case: in this corpus importance is *already*
correlated with correctness (target importance 0.43–0.50 > contradictory
0.10–0.34), so importance alone resolves every contradiction and confidence looks
redundant. Regime E decouples them — the obsolete memories are forced to be
*slightly more important than the target* but low-confidence (the adversarial
"important but wrong" case) — so importance actively gets it wrong and only
confidence can rescue it.

## Results — retrieval quality (recall@5; full suite in the JSON)

| strategy | A control | B low-conf-distr | C contradictory | D realistic | E important-but-wrong |
| --- | --- | --- | --- | --- | --- |
| `similarity_only` | 0.237 | 0.237 | 0.237 | 0.237 | 0.237 |
| `importance_only` | **0.985** | **0.985** | **0.985** | **0.985** | 0.952 |
| `sim_plus_importance` (anchor) | 0.455 | 0.455 | 0.455 | 0.455 | 0.440 |
| `confidence_only` | 0.441 | 0.992 | 0.992 | 0.860 | 0.992 |
| `importance_plus_confidence` | 0.465 | 0.720 | 0.624 | 0.563 | 0.586 |
| `importance_plus_confidence_gated` | 0.550 | 0.651 | 0.611 | 0.580 | 0.612 |
| `importance_plus_recency_plus_confidence` | 0.443 | 0.717 | 0.612 | 0.555 | 0.574 |

**Isolated confidence marginal** (`importance_plus_confidence − sim_plus_importance`, confidence weight 0.10 vs 0; recall@5, paired 95% CI):

| regime | marginal | verdict |
| --- | --- | --- |
| A control | +0.010 [+0.003, +0.018] | ≈ neutral |
| B low-conf-distractors | **+0.265** [+0.208, +0.321] | helps |
| C contradictory | **+0.169** [+0.122, +0.216] | helps |
| D mixed-realistic | **+0.108** [+0.062, +0.155] | helps |
| E important-but-wrong | **+0.146** [+0.106, +0.185] | helps |

## Results — ContradictionAvoidanceRate (the decisive metric)

| strategy | A | B | C | D | **E (important-but-wrong)** |
| --- | --- | --- | --- | --- | --- |
| `similarity_only` | 0.643 | 0.643 | 0.643 | 0.643 | 0.643 |
| `importance_only` | 1.000 | 1.000 | 1.000 | 1.000 | **0.000** |
| `sim_plus_importance` | 0.929 | 0.929 | 0.929 | 0.929 | 0.500 |
| `confidence_only` | 0.479 | 1.000 | 1.000 | 1.000 | **1.000** |
| `importance_plus_confidence` | 0.907 | 0.968 | 0.964 | 0.964 | 0.875 |
| `importance_plus_confidence_gated` | 0.964 | 0.964 | 0.964 | 0.964 | **0.964** |
| `importance_plus_recency_plus_confidence` | 0.871 | 0.964 | 0.964 | 0.964 | 0.914 |

The headline: in the easy regimes (A–D) importance already achieves perfect
avoidance, so confidence is **redundant** there. In the adversarial regime E,
`importance_only` collapses to **CAR 0.000** (it ranks the important-but-wrong
memory first in all 28 queries; its MRR falls to 0.533) — and **confidence-gating
restores avoidance to 0.964**, the only importance-based strategy that stays robust.

## Analysis (the required questions)

**1. Does confidence improve retrieval?** Conditionally. Its isolated marginal over
the no-confidence blend is positive and significant whenever confidence is
informative (B +0.265, C +0.169, D +0.108, E +0.146 recall@5) and ≈0 in the
control (A +0.010). But it does **not** beat `importance_only` on raw recall — the
0.65-similarity blends are diluted by this corpus's adversarial similarity, exactly
as in Exp 3.

**2. Does confidence improve ranking?** Yes where informative — MRR/nDCG rise with
confidence in B/C/D/E — and, crucially, it improves the ranking of the *correct*
memory over contradictory ones (the CAR result).

**3. Does confidence help under contradiction?** Decisively, in the case that
matters. When the obsolete memory is genuinely less important (regimes C/D),
importance already handles it and confidence is redundant. When the obsolete memory
is *important but wrong* (regime E), confidence is **indispensable**: it rescues
contradiction avoidance from 0.000 (importance-only) to 0.964 (gated).

**4. Does confidence outperform recency?** Clearly. Confidence has large,
significant effects in the contradiction regimes where recency (Exp 3) was neutral
or harmful, and `importance_plus_recency_plus_confidence` never beats the
confidence blend without recency. Confidence is a far more reliable signal than raw
recency.

**5. Does confidence add value beyond importance?** For general recall on this
corpus, **no** — importance dominates and confidence is mostly *redundant* because
importance and confidence are usually correlated (good memories are both important
and trusted). Its unique, non-redundant value appears exactly when the two
**diverge** — the important-but-wrong memory — where it is the only signal that
prevents catastrophic contradiction retrieval.

**6. Should confidence become a core Salience v2 signal?** Yes — but as a
**multiplicative gate on importance** (`effective_importance = importance ×
confidence`), not as a flat additive ranking term. Gating is redundant-but-harmless
when importance and confidence agree (almost always) and decisive when they
diverge. The gated strategy is the only one with robust CAR (0.964) across *every*
regime, including the adversarial one.

## Interpretation vs the expected outcomes

This matches **Outcome B** (confidence helps mainly in contradiction regimes —
elsewhere importance already suffices) with a strong lean toward **Outcome A** for
the **gated** formulation specifically: confidence-gating is the safest contradiction
defence and costs nothing when unneeded. It is **not** Outcome C (confidence is not
mere metadata — it is essential in the important-but-wrong case) and **not** Outcome
D (confidence does not harm retrieval).

Distinguishing the signals, as required:
- **importance** — the primary, dominant signal for *what to retrieve*; but blind to
  trust (CAR 0.000 when importance is misleading).
- **confidence** — a *trust/correctness* signal; largely redundant with importance
  until they diverge, then decisive. Best applied as a gate, not an additive term.
- **temporal (recency)** — the weakest and least reliable (Exp 3); contributes
  nothing here.

## Recommendation for Salience v2

1. **Keep importance as the primary salience signal.**
2. **Adopt confidence as a multiplicative gate on importance**
   (`effective_importance = importance × confidence`) rather than a flat additive
   term. This is the only configuration that is both harmless when confidence is
   uninformative and decisive when an important memory is untrustworthy.
3. **Do not rely on importance alone for contradiction/supersession.** Importance is
   catastrophically wrong (CAR 0.000) when an obsolete memory still looks important;
   the gate fixes this.
4. **Keep recency out of the core formula** (Exp 3) — confidence, not recency, is
   the signal worth adding next to importance.

**Decision: Continue research — confidence joins importance as a core Salience v2
signal, in gated (multiplicative) form.** It is the first signal since importance
itself to earn promotion, on the strength of the contradiction-avoidance result.

## Weaknesses / threats to validity

1. **Importance and correctness are collinear by construction** in regimes A–D, which
   is why confidence looks redundant there; regime E deliberately breaks this to
   expose confidence's true value, but E is a synthetic stress test, not observed
   data.
2. **Synthetic confidence.** Real Cortex confidence will be noisier than these bands;
   a noisy-confidence sweep (cf. Exp 2 for importance) is the natural follow-up.
3. **Adversarial similarity** caps the 0.65-similarity blends below `importance_only`
   on raw recall; absolute blend numbers are corpus-specific. The contradiction
   result (CAR) does not depend on this.
4. **Binary relevance / single weight set**; the gate weight (0.35) and the additive
   weight (0.10) were not tuned.

## Next

- **Noisy-confidence sweep** — degrade confidence quality (à la Exp 2) and find how
  good the confidence estimate must be for the gate to pay off.
- **Confidence × importance weight tuning** for the gated formulation.
- **Real contradiction detection** — pair with Cortex `find_contradictions` /
  `resolve` so contradiction labels come from the store, not the corpus.
