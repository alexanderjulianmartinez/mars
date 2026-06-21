# Blog Review

**Reviewing:** `docs/publication/research_blog_draft.md` (~1,500 words).
**Against:** the v2 paper and technical report.
**Lens:** technically accurate · understandable to engineers · no hype · consistent with paper.

---

## Verdict

**Publish-ready after a SVG→PNG export and one light copy pass.** The draft is accurate,
honest, and engineer-legible, and it leads with the execution null exactly as intended.

---

## Accuracy check (blog vs. paper)

| Blog statement | Paper source | Accurate? |
| --- | --- | --- |
| recall@5 0.237 → 0.672 (+0.435), MRR 0.31 → 0.97 | §5 / Table 3 | ✓ |
| ~78% of the win is the importance signal | §6 (oracle−scrambled +0.341) | ✓ |
| recency: +0.262 aligned / −0.206 misaligned / +0.015 realistic | §7 / Table 4b | ✓ |
| CAR 0.000 → 0.964 with gating | §8 / Table 4c | ✓ |
| 18 runs; target-found 0.00 → 0.83; success 0.333 all arms | §9.2 / Table 5 | ✓ |
| recall↔success slightly negative | §9.2 (Pearson −0.32) | ✓ |
| JWT vs stale session-cookie on the auth task | §9.2 (bench-4) | ✓ |

No numeric drift between blog and paper. The blog rounds some figures (e.g. "0.31") for
readability, consistent with the paper's own rounding.

## Tone / hype check

- No "breakthrough," "unlocks," "emergent," "human-like," or AGI framing. ✓
- Salience consistently framed as **prioritization**, not cognition/emotion. ✓
- The execution null is in the **second paragraph**, not buried. ✓
- Explicit can-claim / cannot-claim split present in the Limitations section. ✓

## Engineer-legibility check

- Opens with a concrete scenario (stale `AUTH.md` vs. buried JWT postmortem) before any
  numbers. ✓
- Each experiment is one short, self-contained beat with the caveat attached. ✓
- Ends with copy-pasteable offline reproduction commands. ✓

---

## Recommended edits (all minor)

1. **Figure placeholders → embedded images.** The draft uses `[Figure N]` markers.
   Before publishing, export the SVGs to PNG (`figures/README.md` has the one-liner) and
   embed; the platform likely won't render SVG inline.
2. **First-use expansions.** Spell out MRR ("mean reciprocal rank — how high the right
   memory ranks") and nDCG on first use for a broad engineering audience; the paper
   assumes more.
3. **One-line "what is Cortex/Mars/AutoDev"** up front. The blog names them but a cold
   reader benefits from a single clause each (the README has the wording).
4. **Add a closing CTA** linking the repo, technical report, and `CITATION.cff` (the
   reproduce section is there; make the links explicit at the end).
5. **Optional:** a 2-sentence author/affiliation note for credibility on an external
   platform.

## Suggested diagrams (reuse existing assets — no new work)

- **Hero image:** Figure 9 (ranking example, target rank 6 → 1) — it's the most
  intuitive single visual of the mechanism. Lead with it.
- **Figure 4** (Exp 1 bars) near the "importance helps a lot" beat.
- **Figure 5** (noise curve) at the "it survives noise" beat — the most persuasive
  honesty visual.
- **Figure 8** (execution) at the null — show success flat next to retrieval rising.
- **Figure 1** (architecture) optional, only if the audience needs the systems context.

## Suggested screenshots (optional, low priority)

- A terminal capture of `mars corpus verify-frozen …` showing the green check + SHA256 —
  concretely communicates "frozen + reproducible."
- A terminal capture of the offline `run_noisy_importance.py --cache-only` table —
  shows a reader they can rerun it themselves.

(Screenshots are nice-to-have for an external post; not required for accuracy.)

---

## Blocking issues

**None.** The only must-do before publishing is exporting the figures to a
platform-friendly raster format; everything else is optional polish.
