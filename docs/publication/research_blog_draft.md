# Should an agent treat all its memories equally? A study in salience-weighted retrieval

*A research write-up. Conservative by design: it leads with what we could measure, and
it is explicit about what we could not.*

An agent that maintains a software system over weeks builds up a pile of memory —
design decisions, incident postmortems, naming conventions, and documentation that
slowly goes stale. When it sits down to do the next task, it can't fit all of that
into its context window, so something has to choose which memories to surface. That
choice is a retrieval problem, and the standard answer is: rank by semantic
similarity, take the top few.

We spent a research program testing whether that default is good enough, and whether
one extra signal — *how important a memory is* — makes it better. Short version:

> Salience-aware retrieval clearly improved **retrieval quality** and measurably
> **changed the agent's behavior** on real tasks. It did **not** raise task-success
> rates. We're not claiming it did.

The rest of this post is how we got there, what held up, and what didn't.

---

## The problem: the most *similar* memory is often the wrong one

Here's the failure mode that motivates everything. Imagine the agent is adding
authentication to an endpoint. Its memory contains:

- a stale `docs/AUTH.md` that describes the *old* session-cookie scheme, and
- a buried postmortem that says *"we migrated to JWT after the cookie incident."*

Semantic similarity loves the stale doc — it's full of auth vocabulary that matches
the task. The postmortem, written months ago in different words, ranks lower. So
similarity retrieves the wrong memory, the agent implements the deprecated approach,
and the retrieval system never had any way to say *"that note is out of date and this
decision matters more."*

That's the gap. Similarity measures *resemblance*, not *usefulness*. Our hypothesis
was narrow and testable: **memories should not be treated as equally important, and a
ranker that knows about importance retrieves better.**

We call the extra signals *salience* — importance, confidence, novelty, urgency,
recency. This is a deliberately boring, computational notion. It is not emotion
modeling or cognition; it's a prioritization prior over a memory store. The whole
program is built on three systems with hard boundaries: **Cortex** owns memory and
retrieval, **Mars** (the evaluation layer) owns experiments and scoring, and
**AutoDev** owns agent execution.

*[Figure 1 — System Architecture]*
*[Figure 2 — Retrieval Pipeline]*

---

## The benchmark: build one that can actually fail

Before measuring anything, we needed a benchmark that *discriminates*. Our first
attempt — a 13-memory smoke test — was useless: every strategy scored a perfect
recall@5 of 1.0. You cannot measure a ranker on a benchmark that everything aces.

So we built **Salience Memory Benchmark v1.0.0**: 30 queries, 552 memories, six
labeled categories. The key design choice is that it's **adversarial on purpose**. The
distractor memories (210 of them) are written to be *more* semantically similar to the
query than the genuinely relevant ones — but they carry low importance. That's exactly
the long-horizon trap, and it's what forces a ranker to use something beyond
similarity to win.

*[Figure 3 — Benchmark Composition]*

The corpus is **frozen and hash-pinned** (SHA256 `a464085c…`). The bytes never change
silently; a fix means a new version. We treat reproducibility as a feature, not an
afterthought — there's a committed retrieval cache that lets most experiments run
offline and deterministically.

---

## What we ran, and what we found

We ran five experiments. The structure is deliberately self-critical: each one after
the first exists to attack a weakness in the result before it.

### 1. Importance helps — a lot

Using real semantic retrieval (Cortex with Voyage embeddings), importance-weighted
ranking beat similarity-only across the board: **recall@5 went from 0.237 to 0.672**
(+0.435) and **MRR from 0.31 to 0.97**. Paired bootstrap confidence intervals exclude
zero, and 29–30 of the 30 queries individually improved.

*[Figure 4 — Experiment 1 Results]*

You can watch the mechanism on a single query. For a database-migration task, the top
three semantic matches are distractors (similarity ≈ 0.78, importance ≈ 0.05) and a
contradictory note — they bury the correct memory at rank 6. Adding importance lifts
the right memory to rank 1.

*[Figure 9 — Retrieval Ranking Example]*

**The honest caveat, stated immediately:** importance in this benchmark is *authored*
— we wrote relevant memories to be important and distractors to be unimportant. So
+0.435 is an **upper bound**, not what you'd get from an importance signal you had to
*learn*. Which is exactly why we ran the next experiment.

### 2. It survives noise

If importance is hand-authored, the obvious objection is: *you just encoded the answer
into the labels.* So we corrupted importance, sweeping it from a perfect oracle to
fully random (shuffling the values), 25 seeds at each level.

*[Figure 5 — Noisy Importance]*

The advantage degrades **smoothly and monotonically** — there's no cliff, and it never
falls to the similarity baseline. Even with importance fully scrambled, the salience
arm still beats plain similarity at every level we tested. The cleanest way to state
the importance signal's own contribution is *oracle minus scrambled*: recall@5
0.672 → 0.330, so about **78% of the win is carried by importance itself**, not by
benchmark construction artifacts.

That doesn't erase the upper-bound caveat — but it bounds it. The effect is not just a
labeling trick.

### 3. Recency is *not* the hero (so we cut it)

A natural instinct is to add recency: newer memories are probably more relevant. We
tested it across four timestamp regimes, isolating recency's marginal contribution.

*[Figure 6 — Temporal Salience]*

- When recency *aligned* with relevance: it helped (+0.262).
- When it *misaligned* (distractors are newer): it hurt by almost the same amount
  (−0.206).
- In a *realistic* regime where age is independent of relevance: it did nothing
  (+0.015, not significant).

Meanwhile importance was flat across all four regimes — time neither helped nor hurt
it. So we **did not promote recency to a core signal.** This is a negative result used
as a design decision, and we think reporting it that way is part of doing this
honestly. A plausible-sounding signal that fails its ablation gets cut.

### 4. Confidence rescues contradictions — but only as a *gate*

What happens when an important memory is *wrong*? We built an adversarial regime where
the obsolete memory is made slightly *more* important than the correct one, but
low-confidence. We measured a new metric, **ContradictionAvoidanceRate** (CAR): how
often the correct memory outranks every contradictory one.

*[Figure 7 — Confidence / Contradiction]*

In that regime, importance-only **collapses to CAR 0.000** — it ranks the
important-but-wrong memory first, every single time. Adding confidence as a
*multiplicative gate* on importance (`importance × confidence`) restores it to
**0.964**. An *additive* confidence term doesn't do this; the form matters. So
confidence joined importance as a core signal — but specifically as a gate, not a
fourth weighted term.

### 5. Inside a real agent: behavior changed, success didn't

This is the part we're most careful about. We wired the retrieval arms into **real
AutoDev agent runs** — 18 of them — on a purpose-built benchmark where the needed
knowledge lives in a memory the file itself doesn't contain (or actively contradicts
via a stale doc).

*[Figure 8 — Execution Impact]*

The retrieval arms behaved exactly as the offline studies predicted: the
similarity-only arm **never** surfaced the corrective record (target-found 0.00),
while the importance-aware arms surfaced it ~5/6 of the time (0.83). And the agent's
*behavior* changed because of it. On one task, the similarity arm followed the stale
`AUTH.md` and built session-cookie auth; the importance-aware arms used the repo's
current JWT convention. The "right approach" rate was 1.00 for the salience arms vs
0.83 for similarity.

**But task-success did not move.** It was 0.333 in every arm — the same two of six
tasks passed. The correlation between retrieval quality and success was even slightly
*negative*, an artifact of which tasks happen to be winnable: the passing tasks were
solvable straight from the code, while the tasks where retrieval helped most were also
the hardest to implement and failed anyway. Four of six tasks were unwinnable by any
arm within the iteration budget.

So the result is **Outcome B: retrieval improved, behavior changed, task-success
didn't.** We do not claim salience improves task-success. It steered the agent toward
the right convention; on this benchmark that wasn't enough to pass.

---

## Lessons

A few things generalize beyond this specific study:

- **Design benchmarks that can fail.** A saturated benchmark hides everything. Most of
  the value here came from building an adversarial corpus where similarity *loses*.
- **Ablate your own signals and cut the ones that don't earn it.** Recency seemed
  obviously useful and wasn't. Reporting that is as valuable as reporting the wins.
- **The form of a signal matters.** Confidence as a multiplicative gate worked;
  confidence as an additive term didn't. "Add the signal" is underspecified.
- **Separate proxy metrics from outcome metrics, and never let a proxy stand in for an
  outcome.** Retrieval quality is a proxy. Task-success is the outcome. Keeping those
  apart — and admitting when only the proxy moved — is the whole ballgame for honest
  agent evaluation.
- **Reproducibility infrastructure is what makes a small-n result trustworthy.** A
  frozen hash and a committed cache are why we believe the numbers.

---

## Limitations

Stated plainly, because the conclusions depend on them:

- The corpus is **synthetic and hand-authored**, not sampled from production memory.
- **Importance and confidence are authored**, not learned — so Experiment 1's effect is
  an upper bound, and the contradiction stress test is a synthetic worst case.
- The **execution study is underpowered**: a single trial over six tasks, dry-run, with
  several tasks floored regardless of context.
- We used **one embedding model and one weight set**, so absolute numbers are
  config-specific.

**What we can claim:** salience improves retrieval quality; it's robust to importance
noise; recency is weak; confidence (as a gate) prevents contradiction failures; better
retrieval changes agent behavior. **What we cannot claim:** that any of this raises
agent task-success, improves production outcomes, or generalizes beyond what we tested.

---

## What's next

The retrieval question is, for this setting, well characterized. The open frontier is
execution:

- A **larger, less-floored execution benchmark** with enough winnable tasks that
  task-success actually has statistical power.
- **Learned importance** — replace authored labels with a real estimator, and find
  where it lands on the noisy-importance curve.
- **Real-world memory traces**, to move off the synthetic corpus.
- **Independent replication** of the retrieval results.

We're framing these as the frontier, not as promises — the point of this post is the
evidence we have, honestly bounded.

---

## Reproduce it

The benchmark is frozen and the offline experiments need no credentials:

```bash
pytest
mars corpus verify-frozen salience-memory-benchmark-v1
python experiments/run_noisy_importance.py --cache-only   # Exp 2, offline
python experiments/run_temporal_salience.py               # Exp 3, offline
python experiments/run_confidence_contradiction.py        # Exp 4, offline
```

Full technical report, paper draft, and figures are in the repository. If you use the
benchmark or results, there's a `CITATION.cff`.

---

*Figures referenced above are rendered in `docs/papers/figures/`. Every number in this
post traces to the technical report and the committed experiment artifacts; none are
estimated for the write-up.*
