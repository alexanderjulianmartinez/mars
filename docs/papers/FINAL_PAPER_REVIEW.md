# Final Paper Review

**Paper:** `docs/papers/salience_weighted_memory_retrieval_v2.md` (consolidated v2,
Experiments 1–5; ~5,500 words, appendices A–I inlined).
**Reviewer role:** internal pre-submission gate. The goal is to catch claim/evidence
drift, terminology slips, and any blurring of completed vs. future work before camera-ready.

---

## Coverage verification

- **Figure references:** all of Figures 1–10 are cited in the body. ✓
- **Table references:** Tables 1, 2, 3, 4a, 4b, 4c, 5, 6, 7 all cited. ✓
- **Experiments:** §5 (Exp 1), §6 (Exp 2), §7 (Exp 3), §8 (Exp 4), §9.1 (Exp 5), §9.2
  (Exp 5.1) — all five represented. ✓
- **Numbers:** headline values spot-checked against the technical report and against
  *live reruns this session* (Exp 2–4 reproduced offline). ✓

---

## Claim → evidence map (the core check)

| Claim in paper | Evidence | Verdict |
| --- | --- | --- |
| Importance-weighting improves retrieval (recall@5 +0.435, MRR 0.31→0.97) | §5 / Table 3 / Fig 4; paired bootstrap CI excludes 0 | **Supported** |
| Gain is an upper bound (authored importance) | stated in §5 and §10–11; not overstated | **Supported (honest)** |
| Advantage survives noise; ~78% from importance | §6 / Table 4a / Fig 5; reproduced live | **Supported** |
| Recency unreliable, not promoted | §7 / Table 4b / Fig 6; reproduced live | **Supported** |
| Confidence-gating rescues CAR 0.000→0.964 | §8 / Table 4c / Fig 7; reproduced live (0.643→0.964) | **Supported** |
| Retrieval + behavior change in a real agent | §9.2 / Table 5 / Fig 8 (18 runs) | **Supported** |
| Task-success NOT improved | §9.2 explicitly; 0.333 all arms | **Supported (null stated)** |
| No claim of production/generalization gains | §10 unsupported-claims list | **Correctly withheld** |

**No unsupported claim found.** Every quantitative statement is paired with its source
and, where relevant, its caveat.

---

## Completed-vs-future audit

- Experiments 2–5 are presented as **completed results** (§6–§9), which is correct —
  they are done and reproduced. ✓
- Future work (§7 decision text, §10, §12 and the future-research table) lists only
  genuinely open items: larger/less-floored execution benchmark, learned importance,
  real-world memory traces, external replication. **None of these are presented as
  done.** ✓
- Experiment 5 is correctly framed as a *methodology milestone* (floor effect →
  unmeasurable), not as a task-success result. ✓

**No completed work is described as future; no future work is described as completed.**

---

## Top strengths

1. **Intellectual honesty is structural, not cosmetic.** The supported/unsupported
   claim lists are kept strictly separate, and the headline number is labeled an upper
   bound at first mention. The execution result is reported as a null without spin.
2. **Each experiment attacks the prior one's weakness.** Exp 2 answers the circularity
   objection to Exp 1; Exp 3 justifies dropping recency; Exp 4 shows the gate's
   necessity. The arc is self-critical and hard to attack on cherry-picking grounds.
3. **Reproducibility is demonstrated.** Frozen hash, committed cache, deterministic
   figures, and offline reruns mean a reviewer can verify the central numbers without
   credentials.
4. **The benchmark design is a genuine contribution.** The saturation story (13-memory
   smoke test → adversarial 552-memory corpus) motivates the methodology cleanly.

## Top weaknesses

1. **Authored importance ceiling.** Even with Exp 2 bounding it, a reviewer may discount
   the absolute effect size. Mitigated, not eliminated; the paper is honest about it.
2. **Synthetic corpus / external validity.** No real memory traces. This is the most
   likely "reject/major-revision" lever at a top venue and is disclosed but unresolved.
3. **Execution underpowered.** Single trial, 6 tasks, dry-run, 4/6 floored. The
   behavioral result is real but thin; the task-success null has little statistical
   power. Disclosed.
4. **Single embedding model + single weight set.** No sensitivity sweep. Absolute
   numbers are corpus/config-specific.

These are the *known* limitations and are all already in §10–§11; none are concealed.

## Remaining edits (camera-ready, non-blocking)

1. **Venue/LaTeX port.** Markdown → the chosen template; wire figures (SVG→PDF) and the
   `citation.bib`. (Blocks arXiv only.)
2. **Optional CI whiskers on Fig 5** (see `FIGURE_REVIEW.md` MINOR-1).
3. **Related-work citations.** The Related Work section is prose-only; add concrete
   references for RAG, agent-memory, learning-to-rank, and long-context lines when
   formatting the bibliography.
4. **Abstract length.** Slightly long for some workshop limits; trim ~15% if the venue
   caps the abstract.

## Publication recommendation

- **Technical report / blog / OSS:** ready now.
- **arXiv:** ready after the LaTeX/venue formatting pass and bibliography — **no new
  experiments or analysis required.** Recommend submitting as an honest
  retrieval-studies-plus-execution-null paper; the framing already matches that.
- **Top-tier conference main track:** would likely require the external-validity work
  (real traces) and a sensitivity sweep — out of scope for this RC and explicitly listed
  as future work.

**Verdict:** the paper is internally consistent, claim-faithful, and honest about its
limits. It is **ready for v1.0.0-rc1** and for arXiv pending only mechanical formatting.
