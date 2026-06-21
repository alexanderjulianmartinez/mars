# Table Plan

Publication-ready tables for the consolidated paper. All values quoted from the
technical report and result JSONs (`mars-experiments/*.json`); none are new. Each
table below is final markdown — copy directly into the paper.

---

## Table 1 — Corpus Statistics
*Placement:* §Experimental Framework / Benchmark. *Source:* tech report §1.

| Category | Count | Role |
| --- | ---: | --- |
| `target` | 30 | One primary memory per query (gold target). |
| `relevant` | 102 | Helpful support memories; count toward recall/precision gold. |
| `distractor` | 210 | High semantic overlap, low utility; engineered to mislead similarity. |
| `stale` | 90 | Previously useful, now outdated. |
| `contradictory` | 30 | Conflict with the truth; drive contradiction avoidance. |
| `low_confidence` | 90 | Possibly incorrect (low authored confidence). |
| **Total** | **552** | 30 queries, ~18 memories/query. |

Benchmark v1.0.0, frozen, SHA256 `a464085c…`.

---

## Table 2 — Experiment Summary
*Placement:* §Introduction or §Discussion. *Source:* tech report §9–10.

| # | Experiment | Question | Finding | Decision |
| --- | --- | --- | --- | --- |
| 1 | Salience Retrieval | Does importance-weighting beat similarity-only? | recall@5 +0.435, MRR 0.31→0.97; every metric improves | Importance is a core signal |
| 2 | Noisy Importance | Does the win survive degraded importance? | Graceful, monotonic; never collapses; ~78% of win is the importance signal | Robust to noise |
| 3 | Temporal Salience | Should recency be a core signal? | Helps aligned (+0.262), hurts misaligned (−0.206), neutral realistic (+0.015) | Recency **not** promoted |
| 4 | Confidence/Contradiction | Can confidence avoid important-but-wrong memories? | CAR 0.000→0.964 under gating in regime E | Confidence promoted (gated) |
| 5 / 5.1 | Execution Impact | Do retrieval gains raise agent task-success? | Retrieval + behavior change; task-success unchanged (0.333 all arms) | Outcome B; no task-success claim |

---

## Table 3 — Metric Summary (Experiment 1)
*Placement:* §Experiment 1. *Source:* tech report §2.

| Metric | similarity_only | salience_weighted_v1 | Δ | Paired 95% CI | Wins (W/T/L) |
| --- | ---: | ---: | ---: | --- | --- |
| recall@1 | 0.067 | 0.933 | +0.867 | — | — |
| recall@5 | 0.237 | 0.672 | **+0.435** | [+0.367, +0.502] | 29/1/0 |
| recall@10 | 0.761 | 0.931 | +0.169 | — | — |
| MRR | 0.313 | 0.967 | **+0.654** | — | — |
| nDCG@5 | 0.184 | 0.714 | **+0.531** | [+0.474, +0.583] | 30/0/0 |
| TargetFound@3 | 0.367 | 1.000 | +0.633 | — | — |
| TargetFound@5 | 0.667 | 1.000 | +0.333 | — | — |
| ContextEfficiency@5 | 0.200 | 0.567 | +0.367 | — | — |

---

## Table 4a — Noisy Importance Sweep (Experiment 2)
*Placement:* §Experiment 2. *Source:* tech report §3.

| importance quality | recall@5 | Δ recall@5 (95% CI) | MRR |
| --- | ---: | --- | ---: |
| 1.00 (oracle) | 0.672 | +0.435 [+0.370, +0.503] | 0.967 |
| 0.75 | 0.593 | +0.356 [+0.302, +0.414] | 0.864 |
| 0.50 | 0.506 | +0.269 [+0.218, +0.322] | 0.746 |
| 0.25 | 0.420 | +0.183 [+0.142, +0.224] | 0.584 |
| 0.00 (scrambled) | 0.330 | +0.094 [+0.050, +0.139] | 0.423 |

Importance signal contribution = oracle − scrambled = 0.672 − 0.330 = **+0.341**
(~78% of the advantage). Importance-ablated floor collapses to the similarity
baseline (0.237).

## Table 4b — Temporal Recency Marginal (Experiment 3)
*Placement:* §Experiment 3. *Source:* tech report §4.

| Regime | Recency marginal Δrecall@5 (95% CI) | Verdict |
| --- | --- | --- |
| A uniform (control) | +0.000 [+0.000, +0.000] | neutral |
| B recency-aligned | +0.262 [+0.210, +0.316] | helps |
| C recency-misaligned | −0.206 [−0.262, −0.155] | hurts |
| D mixed-realistic | +0.015 [−0.025, +0.055] | neutral (CI spans 0) |

`importance_only` is regime-invariant: recall@5 0.985 / MRR 1.000 in all regimes.

## Table 4c — ContradictionAvoidanceRate (Experiment 4)
*Placement:* §Experiment 4. *Source:* tech report §5.

| Strategy | A | B | C | D | E (important-but-wrong) |
| --- | ---: | ---: | ---: | ---: | ---: |
| `similarity_only` | 0.643 | 0.643 | 0.643 | 0.643 | 0.643 |
| `importance_only` | 1.000 | 1.000 | 1.000 | 1.000 | **0.000** |
| `confidence_only` | 0.479 | 1.000 | 1.000 | 1.000 | 1.000 |
| `importance × confidence` (gated) | 0.964 | 0.964 | 0.964 | 0.964 | **0.964** |

---

## Table 5 — Execution Results (Experiment 5.1)
*Placement:* §Experiment 5.1. *Source:* tech report §7. 18 real AutoDev runs (6 tasks
× 3 arms × 1 trial), dry-run, `retrieval_limit=3`, ≈$1.3.

| Arm | Task success | recall@5 | Target found | MRR | Right-approach |
| --- | ---: | ---: | ---: | ---: | ---: |
| A — similarity_only | 0.333 | 0.000 | 0.000 | 0.000 | 0.833 |
| B — sim+importance | 0.333 | 0.833 | 0.833 | 0.556 | 1.000 |
| C — salience_v2 | 0.333 | 0.833 | 0.833 | 0.556 | 1.000 |

Paired Δ success vs A: B +0.000 (6 ties), C +0.000 (6 ties). recall↔success Pearson
−0.32 (task-winnability artifact). Evidential: `evidential=true`,
`valid_comparison=true`.

---

## Table 6 — Threats to Validity
*Placement:* §Limitations. *Source:* tech report §11.

| Threat | Scope affected | Status |
| --- | --- | --- |
| Authored importance (correlated with relevance) | Exp 1 effect size | Upper bound; bounded by Exp 2 |
| Synthetic, hand-authored corpus | All retrieval claims | Disclosed; external validity open |
| Authored confidence labels | Exp 4 | Synthetic stress test (regime E) |
| Recency/frequency inert (simultaneous seeding) | Exp 1 | Studied directly in Exp 3 |
| Single trial / 6 tasks / dry-run | Exp 5.1 | Underpowered; no task-success claim |
| retrieval_limit sensitivity | Exp 5.1 contrast | Only exists at limit=3 |
| Single embedding model + single weight set | All | Numbers are corpus/config-specific |

---

## Table 7 — Future Research
*Placement:* §Future Work / Conclusion. *Source:* tech report §12 (no new experiments
proposed; these characterize the open frontier).

| Direction | Open question | Priority |
| --- | --- | --- |
| Larger / less-floored execution benchmark | Does retrieval ever move task-success with power? | High |
| Learned importance estimation | Where on the noisy-importance curve does a real estimator land? | High |
| Real-world memory traces | Do results hold off the synthetic corpus? | High |
| Multiple-trial execution | Variance-aware execution effect | Medium |
| External replication | Independent confirmation of retrieval results | Medium |

(Listed as research frontier, not as work to be executed in this publication phase.)
