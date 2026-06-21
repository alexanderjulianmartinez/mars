# Interview Packet Review

**Reviewing:** `docs/interview/RESEARCH_INTERVIEW_PACKET.md`.
**Central question:** *Can a Staff+ interviewer understand the problem, architecture,
experiments, findings, and lessons within 15 minutes?*

**Answer: Yes.** The packet is structured for exactly that and the 15-minute deep dive
is comprehension-complete. Notes below are refinements, not gaps.

---

## Component presence check

| Required component | Present | Where |
| --- | --- | --- |
| 5-minute version | ✓ | "5-Minute Version" |
| 15-minute deep dive | ✓ | "15-Minute Deep Dive" (8 beats) |
| Staff+ narrative | ✓ | "Staff+ Narrative" |
| Research narrative | ✓ | the 5/15-minute versions + "Experiment Explanation" |
| Architecture explanation | ✓ | "Architecture Explanation (whiteboard-ready)" |
| Lessons learned | ✓ | "Lessons Learned" |
| Company-specific framing | ✓ (bonus) | Meta/OpenAI/Anthropic/Google/Two Sigma table |

All required components are present, plus company-specific framing.

---

## 15-minute comprehension test (the actual bar)

Walking the 15-minute deep dive against the five required understandings:

| Understanding | Covered by | Time-to-grasp |
| --- | --- | --- |
| **Problem** | Beat 1–2: ranking not recall; similarity is weak for long-horizon memory | ~2 min |
| **Architecture** | Beat 2 + Architecture section: Cortex/Mars/AutoDev boundary, provider seam, replayable `EvalRun` | ~3 min |
| **Experiments** | Beats 3–7: Exp 1 win → Exp 2 noise → Exp 3 recency cut → Exp 4 gate → Exp 5.1 null | ~6 min |
| **Findings** | one-liners per experiment + the supported/unsupported split | ~2 min |
| **Lessons** | Lessons section: benchmark-can-fail, ablate-and-cut, gate-vs-additive, proxy≠outcome | ~2 min |

Total ≈ 15 minutes with buffer. A Staff+ interviewer leaves able to restate the problem,
draw the architecture, name the five experiments and their findings, and articulate the
honesty discipline. **Test passed.**

---

## Strengths

1. **Leads with judgment, not numbers** in the Staff+ track — boundary discipline, the
   honest null as the most valuable result, knowing when to stop. This is what Staff+
   panels actually probe.
2. **The honest null is an asset, not an apology.** Framing "retrieval improved but
   task-success didn't" as a demonstration of measurement discipline is exactly right
   for senior research/eng interviews.
3. **Company framing is substance-preserving** — same work, shifted emphasis (rigor for
   Two Sigma, capability-eval honesty for OpenAI, provenance for Anthropic).

## Recommended changes (minor)

1. **Add explicit time-boxes** to the 15-minute deep dive beats (e.g. "Beat 3 — 2 min")
   so it can be rehearsed to length.
2. **One concrete number per beat in the 5-minute version.** It currently carries the
   narrative well; anchoring each claim with a single figure (e.g. "MRR 0.31→0.97")
   makes it stickier without bloating.
3. **Anticipate the top pushback** with a one-line rebuttal each: "authored importance"
   → cite Exp 2; "synthetic corpus" → acknowledge + name the real-traces future work;
   "no success win" → that's the honest finding, here's why it's still valuable. (These
   exist in the reviewer notes; surface them in the packet for quick recall.)
4. **A 60-second "elevator" version** above the 5-minute one, for hallway/first-round
   contexts.

## Blocking issues

**None.** The packet meets the 15-minute comprehension bar today. The changes above are
rehearsal aids and would take under an hour.

---

## Interview readiness

**Ready to use now.** Recommend one mock run-through to confirm the 15-minute timing and
to internalize the three pushback rebuttals; otherwise no substantive work remains.
