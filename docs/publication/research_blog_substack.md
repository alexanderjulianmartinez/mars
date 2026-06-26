# Should an AI agent treat all its memories equally?

*We made an agent's memory retrieval substantially better — and showed that it did not make the agent finish more tasks. A conservative writeup that leads with what we could measure and is explicit about what we couldn't.*

> **Publishing note (delete before posting):** images live in `docs/papers/figures/*.png`
> (2× PNGs, ready to upload). Each `![…]()` marker below shows which file to drop in.
> Figures 1, 2, and 10 are schematic diagrams; 3–9 carry the data.

---

An AI agent that maintains a software system over weeks builds up a pile of memory: design decisions, incident postmortems, naming conventions, and documentation that slowly goes stale. When it sits down to do the next task, it can't fit all of that into its context window, so something has to choose which memories to surface — and the standard answer is simple: rank every memory by how *semantically similar* it is to the task, and take the top few.

We ran a research program testing whether that default is good enough — and whether adding one extra signal, **how important a memory is**, makes it better.

The short version:

> Salience-aware retrieval clearly improved **retrieval quality** and measurably **changed the agent's behavior** on real tasks. It did **not** raise task-success rates. We're not claiming it did.

That gap — between "the agent retrieved better" and "the agent did better" — is the most important thing in this post, so I'll keep returning to it. The rest is how we got there, what held up, and what didn't.

---

## The problem: the most *similar* memory is often the wrong one

Here's the failure mode that motivates everything. Suppose the agent is adding authentication to an endpoint, and its memory contains two relevant items:

- a stale `AUTH.md` describing the **old** session-cookie scheme, and
- a buried postmortem that says *"we migrated to JWT after the cookie incident."*

Semantic similarity loves the stale doc — it's full of auth vocabulary that matches the task. The postmortem, written months ago in different words, ranks lower. So similarity surfaces the wrong memory, the agent implements the deprecated approach, and the retrieval system never had any way to express *"that note is out of date, and this decision matters more."*

That's the gap. Similarity measures **resemblance**, not **usefulness**. Our hypothesis was narrow and testable: *memories should not be treated as equally important, and a ranker that knows about importance retrieves better.*

We call these extra signals **salience** — importance, confidence, novelty, urgency, recency. It's a deliberately boring, computational notion: not emotion modeling or cognition, just a prioritization prior over a memory store.

For context, the work spans three systems with hard boundaries: **Cortex** (memory and retrieval — embeddings, ranking), **Mars** (the evaluation layer — experiments, metrics, significance testing), and **AutoDev** (agent execution — workspaces, running tests). Mars never generates context or executes tasks itself; it measures.

![Figure 1 — System architecture: the Cortex / Mars / AutoDev boundary.](figure1_architecture.png)

![Figure 2 — The retrieval pipeline: both ranking strategies re-rank the same candidate pool.](figure2_pipeline.png)

---

## The benchmark: build one that can actually fail

Before measuring anything, we needed a benchmark that *discriminates*. Our first attempt — a 13-memory smoke test — was useless: every strategy scored a perfect **recall@5** of 1.0. (Recall@5 = of the memories that *should* be retrieved, the fraction that land in the top 5.) You can't measure a ranker on a benchmark that everything aces.

So we built **Salience Memory Benchmark v1.0.0**: 30 queries, 552 memories, six labeled categories. The key design choice is that it's **adversarial on purpose**. The 210 distractor memories are written to be *more* semantically similar to the query than the genuinely relevant ones — but they carry low importance. That's exactly the long-horizon trap, and it's what forces a ranker to use something beyond similarity to win.

![Figure 3 — Benchmark composition: 210 high-overlap distractors dominate the corpus.](figure3_corpus_composition.png)

The corpus is **frozen and hash-pinned** (SHA-256 `a464085c…`). The bytes never change silently; a fix means a new version. We treat reproducibility as a feature, not an afterthought — a committed retrieval cache lets most experiments rerun offline and deterministically, so anyone can check the numbers without API keys.

---

## What we ran, and what we found

Five experiments. Each one after the first exists to test a specific weakness in the result before it — the authored labels, the role of time, the case where an important memory is wrong, and finally whether any of it reaches a real agent.

### 1. Importance helps — a lot

Using real semantic retrieval (Cortex with Voyage `voyage-3-lite` embeddings), importance-weighted ranking beat similarity-only across the board:

- **recall@5: 0.237 → 0.672** (+0.435)
- **MRR: 0.31 → 0.97**

MRR (mean reciprocal rank) measures how high the single correct memory sits on average; 1.0 means it's always ranked first. So 0.31 → 0.97 means the right memory went from "usually buried" to "almost always on top."

These aren't lucky averages. We used a **paired bootstrap** — repeatedly resampling the 30 queries to check the improvement isn't an artifact of which queries we happened to pick — and the confidence intervals exclude zero. Per query, 29 of 30 improved on recall@5 and all 30 improved on ranking quality.

![Figure 4 — Experiment 1: importance-weighted vs similarity-only across the metric suite.](figure4_exp1_results.png)

You can watch the mechanism on a single query. For a database-migration task, the top three semantic matches are distractors (similarity ≈ 0.78, importance ≈ 0.05) plus a contradictory note — together they bury the correct memory at rank 6. Adding importance lifts it to rank 1.

![Figure 9 — A worked example: importance moves the target from rank 6 to rank 1.](figure9_ranking_example.png)

**The honest caveat, stated immediately:** importance in this benchmark is *authored* — we wrote relevant memories to be important and distractors to be unimportant. So +0.435 is an **upper bound**, not what you'd get from an importance signal a system had to *learn* on its own. That objection is exactly why we ran the next experiment.

### 2. It survives noise

If importance is hand-authored, the obvious objection is: *you just encoded the answer into the labels.* So we corrupted importance — sweeping it from a perfect oracle to fully random by progressively shuffling the values, with 25 random seeds at each level.

![Figure 5 — Noisy importance: the advantage decays smoothly and never reaches the baseline.](figure5_noisy_importance.png)

The advantage degrades **smoothly and monotonically** — there's no cliff. Of the +0.435 advantage at the oracle, the recall@5 gain over the similarity baseline shrinks to +0.094 when importance is fully scrambled, which means roughly **78% of the advantage is carried by the importance signal itself** (the +0.341 that disappears as you destroy it), not by benchmark construction.

What about the residual +0.094 that survives even with *random* importance? That's worth being precise about, because it's tempting to read it as "noise helps." It isn't information — when we instead zero out the importance term entirely, recall collapses exactly back to the similarity baseline (0.237). The small residual comes from random importance values stochastically *breaking ties* in the corpus's adversarial similarity ordering, occasionally nudging a target upward. It's a perturbation effect, not a signal.

The upshot: the effect isn't just a labeling trick. The caveat from Experiment 1 is bounded, not erased.

### 3. Recency is *not* the hero (so we cut it)

A natural instinct is to add recency: newer memories are probably more relevant. We tested it across four timestamp regimes, isolating recency's marginal contribution.

![Figure 6 — Temporal salience: recency's effect flips sign depending on the regime.](figure6_temporal_salience.png)

- When recency **aligned** with relevance (relevant memories are newer): it helped (+0.262).
- When it **misaligned** (distractors are newer): it hurt by almost the same amount (−0.206).
- In a **realistic** regime, where age is independent of relevance: it did nothing (+0.015, not statistically significant).

Meanwhile importance was flat across all four regimes — time neither helped nor hurt it. So we **did not promote recency to a core signal.** This is a negative result used as a design decision, and reporting it that way is part of doing this honestly. A plausible-sounding signal that fails its ablation gets cut.

### 4. Confidence rescues contradictions — but only as a *gate*

What happens when an important memory is *wrong*? We built an adversarial regime where an obsolete memory is made slightly *more* important than the correct one, but low-confidence. We measured a new metric, **ContradictionAvoidanceRate (CAR)**: how often the correct memory outranks every contradictory one.

![Figure 7 — Confidence and contradiction: only the gated form is robust across every regime.](figure7_confidence_contradiction.png)

In that regime, importance-only **collapses to CAR 0.000** — it ranks the important-but-wrong memory first, every single time. Adding confidence as a *multiplicative gate* on importance (`importance × confidence`) restores it to **0.964**. An *additive* confidence term doesn't do this; the form matters. So confidence joined importance as a core signal — but specifically as a gate, not a fourth weighted term.

### 5. Inside a real agent: behavior changed, success didn't

This is the part we're most careful about. We wired the retrieval strategies into **real AutoDev agent runs** — 18 in total, one per task–strategy pair across six tasks and three retrieval arms — on a purpose-built benchmark where the knowledge the agent needs lives in a memory the file itself doesn't contain (or actively contradicts, via a stale doc).

![Figure 8 — Execution impact: retrieval and "right approach" rise across arms while task-success stays flat.](figure8_execution_impact.png)

The retrieval arms behaved exactly as the offline studies predicted. The similarity-only arm **never** surfaced the corrective record (target-found 0.00); the importance-aware arms surfaced it ~5 times out of 6 (0.83). And the agent's *behavior* changed because of it: on one task, the similarity arm followed the stale `AUTH.md` and built session-cookie auth, while the importance-aware arms used the repo's current JWT convention. The "right approach" rate was 1.00 for the salience arms versus 0.83 for similarity.

**But task-success did not move.** It was 0.333 in every arm — the same two of six tasks passed each time. The correlation between retrieval quality and success was even slightly negative (Pearson −0.32), though with only six tasks that number is descriptive, not significant. It reflects *which* tasks happen to be winnable: the two passing tasks were solvable straight from the code, while the tasks where retrieval helped most were also the hardest to implement and failed anyway. Four of six tasks were unwinnable by any arm within the iteration budget.

So the result is **Outcome B: retrieval improved, behavior changed, task-success didn't.** We do not claim salience improves task-success. It steered the agent toward the right convention; on this benchmark that wasn't enough to pass.

This is the discipline the whole study is built around: retrieval quality is a *proxy*, task-success is the *outcome*, and the two came apart here. It would have been easy to report the retrieval and behavior wins and let a reader infer the rest — most agent results blur exactly this line. Keeping it sharp, and saying plainly when only the proxy moved, is the point.

---

## Limitations

Stated plainly, because the conclusions depend on them:

- The corpus is **synthetic and hand-authored**, not sampled from production memory.
- **Importance and confidence are authored**, not learned — so Experiment 1's effect is an upper bound, and the contradiction regime is a synthetic worst case.
- The **execution study is underpowered**: a single trial over six tasks, dry-run, with four of six tasks floored regardless of context. And the behavioral contrast depended on a tight retrieval budget — at a larger budget every arm injects the whole small memory store, and the arms differ only in ordering.
- We used **one embedding model and one weight set**, so absolute numbers are configuration-specific.

**What we can claim:** salience improves retrieval quality; it's robust to importance noise; recency is weak; confidence (as a gate) prevents contradiction failures; and better retrieval changes agent behavior.

**What we cannot claim:** that any of this raises agent task-success, improves production outcomes, or generalizes beyond what we tested.

---

## What's next

For this setting, the retrieval question is well characterized. The open frontier is execution:

- A **larger, less-floored execution benchmark** with enough winnable tasks that task-success actually has statistical power.
- **Learned importance** — replace authored labels with a real estimator, and find where it lands on the noisy-importance curve from Experiment 2.
- **Real-world memory traces**, to move off the synthetic corpus.
- **Independent replication** of the retrieval results.

These are the frontier, not promises. The point of this post is the evidence we have, honestly bounded.

---

## Reproduce it

The benchmark is frozen and the offline experiments need no credentials. Clone the [repository](https://github.com/alexanderjulianmartinez/mars), then:

```bash
uv venv --python 3.12 && uv pip install -e ".[dev]"
pytest
mars corpus verify-frozen salience-memory-benchmark-v1
python experiments/run_noisy_importance.py --cache-only   # Experiment 2, offline
python experiments/run_temporal_salience.py               # Experiment 3, offline
python experiments/run_confidence_contradiction.py        # Experiment 4, offline
```

The full technical report, paper, and figures are in the repository, along with a `CITATION.cff` if you use the benchmark or results.

*Every number in this post traces to the technical report and the committed experiment artifacts; none are estimated for the writeup.*
