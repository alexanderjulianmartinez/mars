# arXiv LaTeX source

Submittable LaTeX draft of *Salience-Weighted Memory Retrieval for Long-Horizon
Software Agents: Retrieval Gains, Robustness, and an Honest Execution Null*.

The narrative/framing is synced to the posted write-up
(`docs/publication/research_blog_substack.md`); all numbers, tables, and methodology
are drawn from the consolidated technical report
(`docs/papers/salience_weighted_memory_retrieval_v2.md`) and the committed experiment
artifacts. No numbers are estimated for this draft.

## Files
- `main.tex` — the paper.
- `refs.bib` — bibliography. External references are placeholders; **verify each entry
  before submission.**
- `figures/` — PNG exports copied from `docs/papers/figures/` (Figures 1–10).

## Build
```bash
pdflatex main
bibtex main
pdflatex main
pdflatex main
```
Produces `main.pdf`.

## Before submission
- Verify / complete the external citations in `refs.bib` (RAG, agent-memory,
  learning-to-rank, long-context, bootstrap). They are scaffolding, not vetted.
- Replace PNG figures with vector PDFs for print quality (SVG sources live in
  `docs/papers/figures/`); `arxiv` accepts PDF/PNG either way.
- Fill author affiliation / contact and choose an arXiv category (cs.IR / cs.SE / cs.AI).
