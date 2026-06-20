# Salience Memory Experiment — Readiness Audit

**Research objective:** determine whether salience-weighted retrieval improves
memory performance.

**Audit date:** 2026-06-20 · branch `track-a-and-b-eval-readiness` (PR #22) ·
105 tests passing, no API keys.

This audit answers one question: **can Mars execute and measure Salience Memory
v1 today?** Short answer: **yes, on the synthetic corpus** (reproducible, all
metrics, honest reporting). A *real-Cortex semantic* run is blocked by three
external (Cortex-side / data) issues, not by Mars code.

---

## Audit results

### 1. Apollo / experiment framework
| Check | Status | Evidence |
| --- | --- | --- |
| Experiments execute | ✅ | `mars experiments run salience-memory-v1` produces a full report |
| Baseline vs candidate | ✅ | `similarity_only` vs `salience_weighted_v1`, with a Δ column |
| Reports generate | ✅ | hypothesis, methodology, metrics+deltas, limitations, recommendation |

> Note: the retrieval experiment is a **separate path** (`mars/memory/salience_v1.py`)
> from Apollo's agentic execution sweep (`mars/apollo/experiment.py`), by design
> (execution stays mocked for v1). "Apollo over real Cortex" for the *agentic*
> sweep remains future work.

### 2. Cortex integration
| Check | Status | Evidence |
| --- | --- | --- |
| Real Cortex provider works | ⚠️ partial | `CortexMCPProvider.search_memories` transports correctly, but a **freshly-spawned Cortex server errors** (see Blocking #1). The long-lived Claude-Code Cortex server answers `search_memory`. |
| Retrieval strategies selectable | ✅ | baseline/candidate strategies; `--cortex-provider synthetic|mcp` |
| Retrieved memory metadata exposed | ✅ | live `search_memory` returns `ranking_breakdown` with `keyword_score`, `importance_score`, `recency_factor`, `semantic_score` |

### 3. Retrieval metrics — ✅ all present and tested
`recall@k`, `precision@k`, `MRR`, `target found`, `context efficiency`
(`mars/memory/metrics.py`). Synthetic run: recall **0.500 → 0.967**, target-found
**0.50 → 1.00** (candidate vs baseline).

### 4. Semantic retrieval handling — ✅
- `semantic_score: null` detection (`semantic_available`, `Retrieved.semantic_available`).
- **Verified against live Cortex**: `search_memory` returns `semantic_score: null`
  (embeddings disabled), and the report marks semantic **UNAVAILABLE**, never
  claims a semantic baseline, and `--strict-semantic` exits non-zero.
- Synthetic runs are now explicitly flagged "simulated signals, not production evidence."

### 5. salience-memory-v1 experiment
| Check | Status | Evidence |
| --- | --- | --- |
| Definition exists | ✅ | `experiments/salience-memory-v1.yaml` (hypothesis/methodology/k/baseline/candidate/queries/gold) |
| Executes | ✅ | synthetic source, no keys |
| Reproducible | ✅ | identical metrics across repeated runs (seeded synthetic; covered by a test) |

---

## Complete
- Retrieval-only experiment path with baseline-vs-candidate comparison.
- All five retrieval metrics + per-metric deltas.
- `semantic_score: null` detection, honest reporting, `--strict-semantic`.
- `salience-memory-v1.yaml` definition + gold-label loading (local YAML).
- Reproducible synthetic run; report with hypothesis → recommendation.
- Live Cortex exposes retrieval metadata; transport verified.

## Missing
- ~~Cortex-sourced gold labels / labeled corpus~~ — **tooling now exists** (issue #7):
  `experiments/corpus/salience-memory-v1.corpus.yaml` + `mars experiments seed-corpus`
  seeds the corpus and captures gold labels keyed to real Cortex ids. The remaining
  step is to *run* the seed once Cortex is reachable (blocked by the DB migration).
- **Cortex embeddings** — `semantic_score` is null, so a real run is keyword-only.

## Blocking (only for a *real-Cortex semantic* measurement — not for the first run)
1. **Cortex DB schema mismatch.** A freshly-spawned Cortex server fails:
   `sqlite3.OperationalError: no such column: memory_objects.novelty_score`.
   The DB is behind the Cortex code. → Run the Cortex DB migration (Cortex side).
2. **Cortex embeddings disabled** (`semantic_score: null`). → Install Cortex
   `--extra embeddings` + set a Voyage key (`VOYAGE_API_KEY`).
3. **No matching gold labels / labeled corpus** in real Cortex. → Seed a labeled
   memory set and gold labels keyed to real memory ids (issue #7).
4. **CLI `--cortex-provider mcp` config.** `from_env()` needs `MARS_CORTEX_MCP_*`
   pointing at a Cortex launch command that also sets `CORTEX_DATABASE_URL` /
   `CORTEX_PROJECT=mars` (use the `sh -c '… exec cortex mcp serve'` wrapper).

## Recommended next steps
1. **Run the first experiment now** on the synthetic corpus (command below) to
   establish the framework baseline and a reproducible result.
2. Fix Cortex DB migration (Blocking #1) — quickest unblock for any live retrieval.
3. Enable Cortex embeddings + Voyage key (Blocking #2) to make the baseline semantic.
4. Seed a labeled Cortex memory corpus + gold labels (Blocking #3 / issue #7).
5. Then rerun with `--cortex-provider mcp --strict-semantic` for a real result.

---

## Bottom line
- **First experiment: executable today** (synthetic). No Mars code blockers.
- **Real-Cortex semantic experiment:** blocked by Cortex DB migration + embeddings
  + a labeled corpus — all **external to Mars**.
- Mars never claims semantic evidence until `semantic_score` is real.

**Exact command (runnable now):**
```bash
mars experiments run salience-memory-v1
```

**Real-Cortex command (after the three Cortex-side blockers are cleared):**
```bash
mars experiments run salience-memory-v1 --cortex-provider mcp --strict-semantic
```
