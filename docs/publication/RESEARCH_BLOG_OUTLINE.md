# Research Blog Outline

**Working title:** *Should an agent treat all its memories equally? A study in
salience-weighted retrieval.*

**Audience:** engineers, AI-infra, research engineers, hiring managers.
**Tone:** technical, plain, honest. No hype, no AGI framing, no startup language.
**Length target:** 1,800–2,500 words + the seven figures.

**Throughline:** *We made memory retrieval better and proved it survives noise — and
we're honest that "better retrieval" did not (yet) mean "the agent finishes more
tasks."* The credibility of the post comes from saying that out loud.

---

## 0. Hook (≈150 words)
- Concrete scene: a long-lived coding agent has a stale `docs/AUTH.md` and a buried
  postmortem that says "we moved to JWT." Similarity retrieves the stale doc. The
  agent does the wrong thing.
- One sentence thesis: ranking memories by similarity alone is a weak default for
  long-horizon agents; a single extra signal — importance — fixes the ranking.

## 1. Problem (≈250 words)
- Long-horizon agents accumulate memory; context windows are finite; retrieval picks
  what the model sees.
- The failure mode: the *most similar* memory is often a distractor or stale note.
- Frame as **attention allocation / prioritization**, not cognition or emotion.
- **Figure 1 (architecture)** / **Figure 2 (pipeline)** for orientation.

## 2. Hypothesis (≈150 words)
- Memories should not be treated equally. Add a per-memory *salience* signal
  (importance, confidence, novelty, urgency, recency) to the ranker.
- This first study isolates **importance**. State it as a narrow, testable claim.

## 3. The benchmark (≈300 words)
- Why a new benchmark: the old 13-memory smoke test saturated (recall@5 = 1.0 for
  everything). You can't measure a ranker on a benchmark everything aces.
- v1.0.0: 30 queries, 552 memories, six categories; **adversarial by design** —
  distractors are *more* similar than the truly-relevant memories but carry low
  importance.
- Frozen + hash-pinned (reproducibility as a feature, not an afterthought).
- **Figure 3 (corpus composition).**

## 4. Experiments & findings (≈700 words — the core)
Walk the five experiments as a narrative, one short beat each:

1. **Importance helps (a lot).** recall@5 +0.435, MRR 0.31→0.97; every metric up; CIs
   exclude zero. **Figure 4.** Immediately add the honest caveat: importance is
   *authored* here, so this is an **upper bound**. **Figure 9** for the mechanism
   (target lifted from rank 6 to rank 1).
2. **It survives noise.** Degrade importance oracle→random; the advantage shrinks
   smoothly and never collapses; ~78% of the win is the importance signal itself.
   **Figure 5.** This is the answer to "you just encoded the answer in the labels."
3. **Recency is not the hero.** Helps when aligned, hurts when misaligned, neutral in
   the realistic regime — so we deliberately *didn't* promote it. **Figure 6.** Lesson:
   a plausible signal that fails an ablation is a finding, not a feature.
4. **Confidence rescues contradictions.** When an important memory is *wrong*,
   importance-only ranks it first (CAR 0.000); gating importance by confidence
   restores 0.964. **Figure 7.**
5. **Inside a real agent (the honest part).** 18 real AutoDev runs: retrieval improved
   and the agent's *behavior* changed (JWT instead of the stale cookie) — but
   task-success did not move. **Figure 8.** Name it: **Outcome B.**

## 5. Lessons (≈250 words)
- Build the benchmark to *not* saturate, or you'll measure nothing.
- Ablate your own signals; kill the ones that don't earn their place (recency).
- A multiplicative gate beat an additive term for confidence — form matters.
- Reproducibility infra (frozen hash, committed cache) is what lets you trust a small-n
  result.
- Separating "retrieval improved" from "task-success improved" is the whole ballgame
  for honest agent evaluation.

## 6. Limitations (≈200 words — do not bury)
- Synthetic corpus; authored importance/confidence; single embedding model + weight
  set; execution underpowered (floor, single trial, 6 tasks, dry-run).
- Explicit two lists: **what we can claim** (retrieval ↑, contradiction avoidance ↑,
  confidence valuable as a gate, recency weak, behavior changes) vs **what we cannot**
  (task-success ↑, production outcomes ↑, generalization beyond tested conditions).

## 7. Future work (≈150 words)
- Larger/less-floored execution benchmark; learned importance; real-world memory
  traces; external replication. Framed as the open frontier (execution), not as a
  to-do the post promises to finish.

## 8. Reproduce / read more (≈100 words)
- Links: technical report, frozen benchmark (hash), repo, one-command repro per
  experiment (offline tier needs no credentials).

---

### Style guardrails
- Every quantitative claim cites the metric and the caveat in the same breath.
- No "breakthrough," "unlocks," "emergent," "human-like." Salience = prioritization.
- Lead the execution section with the null, not around it.
- Figures do the heavy lifting; prose stays tight.
