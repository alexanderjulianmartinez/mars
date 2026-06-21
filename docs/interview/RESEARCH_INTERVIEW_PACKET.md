# Research Interview Packet

How to present the Salience & Attention research in interviews. Framing is
**systems / evaluation / research infrastructure** — not AGI, not product marketing.
The recurring credibility move is the same as in the papers: separate *what the
evidence supports* from *what it does not*, out loud.

---

## 5-Minute Version

> Long-horizon agents accumulate memory — decisions, postmortems, conventions, stale
> docs. They retrieve a few of those into context before acting, and the default is to
> rank by semantic similarity. That's a weak default: the *most similar* memory is
> often a distractor or an outdated note. I studied whether adding a per-memory
> **importance** signal to the ranker helps.
>
> I built a frozen, adversarial benchmark — 30 queries, 552 memories — where
> distractors are deliberately *more* similar than the relevant memories but carry low
> importance, so similarity-only ranking fails. On real semantic retrieval,
> importance-weighting lifted recall@5 from 0.24 to 0.67 and MRR from 0.31 to 0.97,
> with confidence intervals that exclude zero.
>
> Then I stress-tested it: importance is *authored* in the benchmark, so the headline
> number is an upper bound. I degraded importance from oracle toward random; the
> advantage shrank smoothly and never collapsed — about 78% of the win is carried by
> the importance signal. I ablated recency and *dropped* it because it only helped when
> artificially aligned. I added confidence as a multiplicative gate, which rescued
> contradiction-avoidance from 0.0 to 0.96 when an important memory was wrong.
>
> Finally I wired it into a real agent — 18 runs. Retrieval improved and the agent's
> *behavior* changed: it used the repo's current JWT convention instead of a stale
> cookie scheme. But task-success did **not** move. So the honest claim is: salience
> improves retrieval and steers behavior; I have *not* shown it raises task-success.

## 15-Minute Deep Dive

Beats to hit, with the "why" for each:

1. **The problem is ranking, not recall.** Both arms re-rank the *same* retrieved pool,
   isolating the ranking function. (Shows experimental hygiene.)
2. **Benchmark design is the real contribution.** The previous smoke test saturated at
   recall@5 = 1.0 — you can't measure a ranker on a benchmark everything aces. I built
   a non-saturating, adversarial, frozen, hash-pinned corpus. Reproducibility is a
   first-class feature: a committed retrieval cache makes the robustness, temporal, and
   confidence studies fully offline and deterministic.
3. **Experiment 1 — the win**, with the mechanism: on the migration query, three
   distractors (sim ≈ 0.78, importance ≈ 0.05) and a contradiction bury the target at
   rank 6; importance lifts it to rank 1. Not a metric artifact.
4. **Experiment 2 — defusing my own strongest objection.** Authored importance is
   correlated with relevance by construction, so I treated +0.435 as an upper bound and
   measured how much survives noise. Graceful, monotonic; ablated floor lands exactly
   on the similarity baseline.
5. **Experiment 3 — killing a signal.** Recency flips sign by regime; importance is
   regime-invariant. I deliberately did not promote recency. (A negative result used as
   a design decision.)
6. **Experiment 4 — form matters.** Confidence is redundant with importance until they
   diverge; a *multiplicative gate* (`importance × confidence`) beat an additive term
   and is the only strategy robust across every regime.
7. **Experiment 5/5.1 — the honest null.** Built the real-agent pipeline; it floored at
   0% success first (unmeasurable, not "no effect"), so I built a memory-dependent
   benchmark. Result: retrieval ↑, behavior changed, task-success flat. recall↔success
   was slightly negative — an artifact of which tasks are winnable, which I can explain.
8. **What I'd do next:** less-floored execution benchmark with power; learned importance
   (where does a real estimator land on the noise curve?); real memory traces.

## Staff+ Narrative

Lead with judgment and systems thinking, not the numbers:

- **Framing:** "I treated agent memory retrieval as a measurement problem first. The
  risk in this space is shipping a plausible heuristic that you never actually
  measured, or measuring it on a benchmark that can't fail."
- **Boundary discipline:** four systems with hard ownership lines — Cortex (retrieval),
  Mars (evaluation), AutoDev (execution), Sentinel (governance). Memory/execution logic
  lives behind provider interfaces; the eval layer never executes tasks or generates
  context. This is what let me swap mocks for real MCP providers as drop-ins.
- **Intellectual honesty as method:** I structured the whole program so the supported
  and unsupported claim-lists never blur. The most valuable result is arguably the
  *null* — "better retrieval did not raise task-success here" — because it prevents an
  org from over-investing on a retrieval number.
- **Knowing when to stop:** the retrieval question is well-characterized; I'm explicit
  that the open frontier is execution, and I did *not* manufacture more retrieval
  experiments to pad the story.

## Architecture Explanation (whiteboard-ready)

- Pipeline: `EvalSuite → EvalCase → ContextPackage (Cortex) → AgentRun (AutoDev) →
  EvalRun (scored)`. The `EvalRun` carries enough metadata to **replay** later against
  new models/prompts/strategies — replayability is designed in.
- Providers are interfaces with mocks + real MCP implementations; auto-selected by env
  (`MARS_*_MCP_*`), lazily imported so the optional `mcp` dep never loads at import.
- Scoring is pluggable (add a scorer, don't edit existing ones). Apollo runs paired A/B
  experiments with a seeded "luck" roll keyed by (agent, case, trial) but **not**
  strategy, so arms stay paired.

## Experiment Explanation (the one-liner per study)
- 1: importance beats similarity (recall@5 +0.435).
- 2: it survives noise (never collapses; ~78% from the signal).
- 3: recency is unreliable (dropped).
- 4: confidence-gating rescues contradictions (CAR 0.000→0.964).
- 5.1: retrieval + behavior change, task-success flat (Outcome B).

## Lessons Learned
- Design benchmarks that can fail; saturation hides everything.
- Ablate your own signals and report the negatives as decisions.
- Separate proxy metrics (retrieval) from outcome metrics (task-success) and never let
  a proxy win stand in for an outcome win.
- Reproducibility infra (frozen hash, committed cache) is what makes a small-n result
  trustworthy.
- Form of a signal (gated vs additive) can matter more than its presence.

---

## How to discuss the work by company

Same substance everywhere; emphasis shifts. Keep it to *systems/evaluation/research/
infrastructure*.

| Company | Lead with | Hook |
| --- | --- | --- |
| **Meta** | Systems + scale + rigorous offline eval | "Adversarial, frozen benchmark; paired bootstrap significance; reproducible offline via a committed cache. I care about measuring ranking changes before they ship." |
| **OpenAI** | Agent memory + honest capability evaluation | "I separated retrieval improvement from agent task-success and reported the null — exactly the discipline you want before claiming an agent capability." |
| **Anthropic** | Evaluation honesty + safety-adjacent provenance | "The program is built around not overclaiming; Sentinel is a reserved provenance/audit seam. The headline result is bounded as an upper bound on purpose." |
| **Google** | Retrieval/ranking + ablation methodology | "It's a learning-to-rank-flavored study with clean ablations: I isolated each signal's marginal and dropped recency when it failed its ablation." |
| **Two Sigma** | Statistical rigor + signal robustness under noise | "Paired bootstrap CIs, a noise sweep with 25 seeds/level, and a signal-attribution decomposition (oracle−scrambled). I treat a retrieval signal like an alpha signal: prove it survives degradation." |

**Do not** pitch this as AGI, emotion modeling, or a product. It is an evaluation +
retrieval-ranking study with an honest execution null.
